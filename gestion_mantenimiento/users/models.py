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
