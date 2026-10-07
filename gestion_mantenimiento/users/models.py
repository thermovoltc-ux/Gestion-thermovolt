from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nombre


class PerfilUsuario(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil_usuario',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfiles_usuario',
    )
    is_administrador_cliente = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        cliente_nombre = self.cliente.nombre if self.cliente else 'Sin cliente'
        return f'{self.user.username} -> {cliente_nombre}'


class RegistroAsistencia(models.Model):
    """Registro de entrada y salida de un usuario técnico."""

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='registros_asistencia',
        verbose_name='Usuario',
    )
    fecha = models.DateField(
        default=timezone.now,
        verbose_name='Fecha',
        help_text='Fecha del registro de asistencia.',
    )
    hora_entrada = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Hora de entrada',
    )
    hora_salida = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Hora de salida',
    )
    horas_trabajadas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Horas trabajadas',
        help_text='Horas calculadas automáticamente cuando ambas marcas están disponibles.',
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    actualizado = models.DateTimeField(auto_now=True, verbose_name='Actualizado')

    class Meta:
        verbose_name = 'Registro de asistencia'
        verbose_name_plural = 'Registros de asistencia'
        ordering = ['-fecha', '-hora_entrada']
        unique_together = [['usuario', 'fecha']]

    def calcular_horas(self):
        if self.hora_entrada and self.hora_salida:
            delta = self.hora_salida - self.hora_entrada
            return round(Decimal(delta.total_seconds()) / Decimal(3600), 2)
        return None

    def save(self, *args, **kwargs):
        self.horas_trabajadas = self.calcular_horas()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.usuario.username} - {self.fecha}'


# ============================================================
# MODELOS DE NÓMINA
# ============================================================

class ConfiguracionPago(models.Model):
    """Configuración de pago por técnico."""

    TIPO_PAGO_CHOICES = [
        ('por_dia', 'Por día'),
        ('salario_fijo', 'Salario fijo mensual'),
        ('mixto', 'Mixto'),
    ]
    DIAS_SEMANA_CHOICES = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='configuracion_pago',
        verbose_name='Usuario',
    )
    tipo_pago = models.CharField(
        max_length=20,
        choices=TIPO_PAGO_CHOICES,
        default='por_dia',
        verbose_name='Tipo de pago',
    )
    valor_dia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor por día trabajado (ej: 122000)',
        verbose_name='Valor por día',
    )
    salario_mensual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Salario mensual si aplica',
        verbose_name='Salario mensual',
    )
    valor_hora_normal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor por hora normal (si se calcula por hora)',
        verbose_name='Valor hora normal',
    )
    valor_hora_extra = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor por hora extra',
        verbose_name='Valor hora extra',
    )
    recargo_nocturno_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('35.00'),
        help_text='Recargo nocturno según ley Colombia (%)',
        verbose_name='Recargo nocturno (%)',
    )
    recargo_festivo_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('75.00'),
        help_text='Recargo festivo según ley Colombia (%)',
        verbose_name='Recargo festivo (%)',
    )
    horas_semana_estandar = models.IntegerField(
        default=42,
        help_text='Horas estándar semanales antes de extras',
        verbose_name='Horas semanales',
    )
    dia_pico_placa = models.IntegerField(
        choices=DIAS_SEMANA_CHOICES,
        null=True,
        blank=True,
        help_text='Día de pico y placa (rota cada 6 meses)',
        verbose_name='Día de pico y placa',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Pago'
        verbose_name_plural = 'Configuraciones de Pago'

    def __str__(self):
        return f'{self.usuario.username} - {self.get_tipo_pago_display()}'


class CalendarioTecnico(models.Model):
    """Días especiales, descansos y licencias del técnico."""

    TIPO_CHOICES = [
        ('descanso', 'Descanso'),
        ('licencia_medica', 'Licencia médica'),
        ('licencia_remunerada', 'Licencia remunerada'),
        ('licencia_no_remunerada', 'Licencia NO remunerada'),
        ('pico_placa', 'Pico y placa'),
        ('feriado', 'Feriado'),
        ('otro', 'Otro'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dias_especiales',
        verbose_name='Usuario',
    )
    fecha = models.DateField(verbose_name='Fecha')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, verbose_name='Tipo')
    horas_esperadas = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('8.00'),
        help_text='Horas que debería trabajar este día (0 si es descanso)',
        verbose_name='Horas esperadas',
    )
    remunerado = models.BooleanField(
        default=True,
        help_text='Si el día se paga aunque no trabaje',
        verbose_name='¿Remunerado?',
    )
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Día Especial'
        verbose_name_plural = 'Días Especiales'
        ordering = ['-fecha']
        unique_together = [['usuario', 'fecha', 'tipo']]

    def __str__(self):
        return f'{self.usuario.username} - {self.fecha} ({self.get_tipo_display()})'


class Descuento(models.Model):
    """Descuentos aplicables a un técnico en un período de pago."""

    TIPO_CHOICES = [
        ('prestamo', 'Préstamo'),
        ('adelanto', 'Adelanto'),
        ('fiscal', 'Retención fiscal'),
        ('seguridad_social', 'Seguridad social'),
        ('otro', 'Otro'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='descuentos',
        verbose_name='Usuario',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name='Tipo')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    fecha_aplicacion = models.DateField(verbose_name='Fecha de aplicación')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    cuotas_totales = models.IntegerField(
        null=True,
        blank=True,
        help_text='Si es un préstamo, cuántas cuotas tiene',
        verbose_name='Cuotas totales',
    )
    cuota_actual = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Cuota actual',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Descuento'
        verbose_name_plural = 'Descuentos'
        ordering = ['-fecha_aplicacion']

    def __str__(self):
        return f'{self.usuario.username} - {self.get_tipo_display()}: ${self.monto}'


class ReciboPago(models.Model):
    """Recibo de pago generado como snapshot del período."""

    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('aprobado', 'Aprobado'),
        ('pagado', 'Pagado'),
        ('anulado', 'Anulado'),
    ]
    TIPO_PERIODO_CHOICES = [
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
        ('semanal', 'Semanal'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recibos_pago',
        verbose_name='Usuario',
    )
    tipo_periodo = models.CharField(
        max_length=20,
        choices=TIPO_PERIODO_CHOICES,
        default='quincenal',
        verbose_name='Tipo de período',
    )
    fecha_inicio = models.DateField(verbose_name='Fecha inicio')
    fecha_fin = models.DateField(verbose_name='Fecha fin')
    horas_normales = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Horas normales',
    )
    horas_extras = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Horas extras',
    )
    horas_nocturnas = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Horas nocturnas',
    )
    horas_festivas = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Horas festivas',
    )
    dias_trabajados = models.IntegerField(default=0, verbose_name='Días trabajados')
    dias_descanso = models.IntegerField(default=0, verbose_name='Días de descanso')
    bruto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Bruto',
    )
    total_descuentos = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Total descuentos',
    )
    neto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Neto a pagar',
    )
    detalles = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detalle de cálculos: valores por hora, descuentos aplicados, etc.',
        verbose_name='Detalles',
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='borrador',
        verbose_name='Estado',
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    pdf_path = models.CharField(max_length=500, blank=True, verbose_name='Ruta del PDF')
    enviado_por_email = models.BooleanField(default=False, verbose_name='Enviado por email')
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de envío')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Recibo de Pago'
        verbose_name_plural = 'Recibos de Pago'
        ordering = ['-fecha_inicio', '-creado']
        unique_together = [['usuario', 'tipo_periodo', 'fecha_inicio', 'fecha_fin']]

    def __str__(self):
        return f'Recibo {self.usuario.username} - {self.fecha_inicio} a {self.fecha_fin} ({self.get_estado_display()})'
