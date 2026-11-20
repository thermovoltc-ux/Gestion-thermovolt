from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    SOLICITUD = 'SOLICITUD'
    OT_ASIGNADA = 'OT_ASIGNADA'
    OT_REASIGNADA = 'OT_REASIGNADA'
    SOLICITUD_URGENTE = 'SOLICITUD_URGENTE'
    COMENTARIO_OT = 'COMENTARIO_OT'
    SOLICITUD_ACEPTADA = 'SOLICITUD_ACEPTADA'
    TECNICO_EN_CAMINO = 'TECNICO_EN_CAMINO'
    MANTENIMIENTO_PREVENTIVO = 'MANTENIMIENTO_PREVENTIVO'
    RECORDATORIO_OT = 'RECORDATORIO_OT'
    RECORDATORIO_MANTENIMIENTO = 'RECORDATORIO_MANTENIMIENTO'
    STOCK_BAJO = 'STOCK_BAJO'
    OT_FINALIZADA = 'OT_FINALIZADA'
    OT_SIN_ASIGNAR = 'OT_SIN_ASIGNAR'
    ERROR_INFORME = 'ERROR_INFORME'

    TIPO_CHOICES = [
        (SOLICITUD, 'Nueva solicitud'),
        (OT_ASIGNADA, 'OT asignada'),
        (OT_REASIGNADA, 'OT reasignada'),
        (SOLICITUD_URGENTE, 'Solicitud urgente'),
        (COMENTARIO_OT, 'Comentario en OT'),
        (SOLICITUD_ACEPTADA, 'Solicitud aceptada'),
        (TECNICO_EN_CAMINO, 'Técnico en camino'),
        (MANTENIMIENTO_PREVENTIVO, 'Mantenimiento preventivo'),
        (RECORDATORIO_OT, 'Recordatorio de OT'),
        (RECORDATORIO_MANTENIMIENTO, 'Recordatorio de mantenimiento'),
        (STOCK_BAJO, 'Stock bajo'),
        (OT_FINALIZADA, 'OT finalizada'),
        (OT_SIN_ASIGNAR, 'OT sin asignar'),
        (ERROR_INFORME, 'Error de informe'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones',
    )
    titulo = models.CharField(max_length=180)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=40, choices=TIPO_CHOICES, db_index=True)
    leida = models.BooleanField(default=False, db_index=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    url_destino = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-fecha_creacion', '-pk']
        indexes = [
            models.Index(
                fields=['usuario', 'leida', '-fecha_creacion'],
                name='notif_user_read_date_idx',
            ),
        ]
        verbose_name = 'notificación'
        verbose_name_plural = 'notificaciones'

    def __str__(self):
        return f'{self.titulo} — {self.usuario}'
