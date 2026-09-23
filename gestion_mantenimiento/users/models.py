from django.contrib.auth.models import User
from django.db import models


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
    centro_operaciones = models.ForeignKey(
        'Activos.CentroOperaciones',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfiles_usuario',
    )
    is_administrador_cliente = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def clean(self):
        super().clean()
        if self.cliente_id and self.centro_operaciones_id and self.centro_operaciones.cliente_id != self.cliente_id:
            raise models.ValidationError('El centro de operaciones debe pertenecer al mismo cliente del perfil.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        cliente_nombre = self.cliente.nombre if self.cliente else 'Sin cliente'
        co_nombre = self.centro_operaciones.nombre if self.centro_operaciones else 'Sin CO'
        return f'{self.user.username} -> {cliente_nombre} / {co_nombre}'
