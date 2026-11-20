from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, F, Sum, When
from django.utils import timezone


class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'categoría de producto'
        verbose_name_plural = 'categorías de productos'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    material_asociado = models.OneToOneField(
        'Gestion_ot.Material',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='producto_almacen',
    )
    categoria = models.ForeignKey(
        CategoriaProducto,
        on_delete=models.PROTECT,
        related_name='productos',
    )
    unidad_medida = models.CharField(
        max_length=30,
        help_text='Por ejemplo: Unidad, Metro o Litro.',
    )
    stock_minimo = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )

    class Meta:
        ordering = ['nombre', 'codigo']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    @property
    def stock(self):
        if self.pk is None:
            return Decimal('0')

        saldo = MovimientoInventario.objects.filter(producto_id=self.pk).aggregate(
            stock=Sum(
                Case(
                    When(tipo=MovimientoInventario.ENTRADA, then=F('cantidad')),
                    When(tipo=MovimientoInventario.SALIDA, then=-F('cantidad')),
                    When(tipo=MovimientoInventario.AJUSTE, then=F('cantidad')),
                    output_field=DecimalField(max_digits=15, decimal_places=3),
                ),
                output_field=DecimalField(max_digits=15, decimal_places=3),
            ),
        )['stock']
        return saldo if saldo is not None else Decimal('0')

    @property
    def costo_promedio_actual(self):
        if self.pk is None:
            return Decimal('0.00')

        cantidad_actual = Decimal('0')
        valor_actual = Decimal('0')
        movimientos = self.movimientos.order_by('fecha', 'pk').values_list(
            'tipo',
            'cantidad',
            'costo_unitario',
        )

        for tipo, cantidad, costo_unitario in movimientos:
            if tipo == MovimientoInventario.ENTRADA:
                valor_actual += cantidad * costo_unitario
                cantidad_actual += cantidad
            elif tipo == MovimientoInventario.SALIDA:
                costo_salida = (
                    valor_actual / cantidad_actual
                    if cantidad_actual > 0
                    else Decimal('0')
                )
                valor_actual -= cantidad * costo_salida
                cantidad_actual -= cantidad
            elif tipo == MovimientoInventario.AJUSTE:
                if cantidad > 0:
                    costo_ajuste = costo_unitario
                    if cantidad_actual > 0 and costo_ajuste == 0:
                        costo_ajuste = valor_actual / cantidad_actual
                    valor_actual += cantidad * costo_ajuste
                else:
                    costo_ajuste = (
                        valor_actual / cantidad_actual
                        if cantidad_actual > 0
                        else Decimal('0')
                    )
                    valor_actual += cantidad * costo_ajuste
                cantidad_actual += cantidad

            if cantidad_actual <= 0:
                cantidad_actual = Decimal('0')
                valor_actual = Decimal('0')

        if cantidad_actual == 0:
            return Decimal('0.00')
        return (valor_actual / cantidad_actual).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )


class HerramientaUnidad(models.Model):
    DISPONIBLE = 'DISPONIBLE'
    ASIGNADA = 'ASIGNADA'
    EN_REPARACION = 'EN_REPARACION'
    BAJA = 'BAJA'

    ESTADO_CHOICES = [
        (DISPONIBLE, 'Disponible'),
        (ASIGNADA, 'Asignada'),
        (EN_REPARACION, 'En reparación'),
        (BAJA, 'Baja'),
    ]

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='herramientas_unidad',
    )
    identificador_unico = models.CharField(max_length=100, unique=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=DISPONIBLE,
        db_index=True,
    )
    tecnico_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='herramientas_asignadas',
    )
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['producto__nombre', 'identificador_unico']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        estado='ASIGNADA',
                        tecnico_asignado__isnull=False,
                        fecha_asignacion__isnull=False,
                    )
                    | models.Q(
                        estado__in=['DISPONIBLE', 'EN_REPARACION', 'BAJA'],
                        tecnico_asignado__isnull=True,
                        fecha_asignacion__isnull=True,
                    )
                ),
                name='almacen_herramienta_estado_asignacion_valido',
            ),
        ]
        verbose_name = 'herramienta individual'
        verbose_name_plural = 'herramientas individuales'

    def __str__(self):
        return f'{self.producto} — {self.identificador_unico}'


class HistorialHerramienta(models.Model):
    herramienta = models.ForeignKey(
        HerramientaUnidad,
        on_delete=models.PROTECT,
        related_name='historial',
    )
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='historial_herramientas',
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_devolucion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_asignacion', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['herramienta'],
                condition=models.Q(fecha_devolucion__isnull=True),
                name='almacen_herramienta_una_asignacion_abierta',
            ),
        ]
        verbose_name = 'historial de herramienta'
        verbose_name_plural = 'historial de herramientas'

    def __str__(self):
        return f'{self.herramienta} — {self.tecnico}'


class MovimientoInventarioQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Los movimientos de inventario son inmutables.')

    def delete(self):
        raise ValidationError('Los movimientos de inventario no se pueden eliminar.')


class MovimientoInventario(models.Model):
    ENTRADA = 'ENTRADA'
    SALIDA = 'SALIDA'
    AJUSTE = 'AJUSTE'

    TIPO_CHOICES = [
        (ENTRADA, 'Entrada'),
        (SALIDA, 'Salida'),
        (AJUSTE, 'Ajuste'),
    ]

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='movimientos',
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, db_index=True)
    cantidad = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        help_text='Las entradas/salidas deben ser positivas; el ajuste es una diferencia firmada.',
    )
    costo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='movimientos_inventario',
    )
    documento_referencia = models.CharField(max_length=150, blank=True)
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = MovimientoInventarioQuerySet.as_manager()

    class Meta:
        ordering = ['-fecha', '-pk']
        constraints = [
            models.CheckConstraint(
                check=models.Q(tipo__in=['ENTRADA', 'SALIDA', 'AJUSTE']),
                name='almacen_movimiento_tipo_valido',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(tipo='AJUSTE', cantidad__gt=0)
                    | models.Q(tipo='AJUSTE', cantidad__lt=0)
                    | models.Q(tipo__in=['ENTRADA', 'SALIDA'], cantidad__gt=0)
                ),
                name='almacen_movimiento_cantidad_valida',
            ),
            models.CheckConstraint(
                check=models.Q(costo_unitario__gte=0),
                name='almacen_movimiento_costo_no_negativo',
            ),
        ]
        verbose_name = 'movimiento de inventario'
        verbose_name_plural = 'movimientos de inventario'

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad} {self.producto.unidad_medida} - {self.producto}'

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.cantidad is not None
            and self.tipo in (self.ENTRADA, self.SALIDA)
            and self.cantidad <= 0
        ):
            errors['cantidad'] = 'La cantidad de una entrada o salida debe ser mayor que cero.'
        elif (
            self.cantidad is not None
            and self.tipo == self.AJUSTE
            and self.cantidad == 0
        ):
            errors['cantidad'] = 'Un ajuste debe representar una diferencia distinta de cero.'
        if self.costo_unitario is not None and self.costo_unitario < 0:
            errors['costo_unitario'] = 'El costo unitario no puede ser negativo.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Los movimientos de inventario son inmutables; registre un movimiento inverso para corregirlos.')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Los movimientos de inventario no se pueden eliminar; registre un movimiento inverso para corregirlos.')
