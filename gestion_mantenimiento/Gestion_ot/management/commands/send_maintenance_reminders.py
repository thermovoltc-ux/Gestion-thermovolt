from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from gestion_mantenimiento.Gestion_ot.models import (
    OrdenTrabajo,
    TareaMantenimiento,
)
from gestion_mantenimiento.notificaciones.models import Notificacion
from gestion_mantenimiento.notificaciones.utils import (
    crear_notificacion,
    usuarios_cliente_de_ubicacion,
)


class Command(BaseCommand):
    help = 'Envía recordatorios diarios de OTs y mantenimientos preventivos próximos.'

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        manana = hoy + timedelta(days=1)
        fecha_preventivo = hoy + timedelta(days=3)
        user_model = get_user_model()
        enviados = 0

        ots = OrdenTrabajo.objects.filter(
            fecha_actividad__date=manana,
        ).exclude(
            estado__nombre='finalizada',
        ).select_related(
            'solicitud__equipo',
            'solicitud__ubicacion',
        )
        for ot in ots:
            if not ot.tecnico_asignado:
                continue
            tecnico = user_model.objects.filter(
                username__iexact=ot.tecnico_asignado,
                is_active=True,
            ).first()
            if tecnico is None:
                continue
            mensaje = (
                f'Tienes asignada la OT #{ot.solicitud.consecutivo} para '
                f'{ot.solicitud.equipo.nombre}, programada para mañana '
                f'({manana:%d/%m/%Y}).'
            )
            if _ya_enviado(tecnico, Notificacion.RECORDATORIO_OT, mensaje, hoy):
                continue
            crear_notificacion(
                tecnico,
                Notificacion.RECORDATORIO_OT,
                'Recordatorio de OT próxima',
                mensaje,
                reverse('cierre_ot', args=[ot.pk]),
            )
            enviados += 1

        tareas = TareaMantenimiento.objects.filter(
            fecha_programada=fecha_preventivo,
            estado='pendiente',
            plan__activo=True,
        ).select_related(
            'plan__equipo__ubicacion',
            'plan',
        )
        for tarea in tareas:
            equipo = tarea.plan.equipo
            ubicacion = equipo.ubicacion
            mensaje = (
                f'El mantenimiento preventivo {tarea.plan.nombre} para '
                f'{equipo.nombre} está programado para el '
                f'{fecha_preventivo:%d/%m/%Y}.'
            )
            clientes = usuarios_cliente_de_ubicacion(ubicacion)
            for cliente in clientes:
                if _ya_enviado(
                    cliente,
                    Notificacion.RECORDATORIO_MANTENIMIENTO,
                    mensaje,
                    hoy,
                ):
                    continue
                crear_notificacion(
                    cliente,
                    Notificacion.RECORDATORIO_MANTENIMIENTO,
                    'Recordatorio de mantenimiento',
                    mensaje,
                    reverse('lista_solicitudes'),
                )
                enviados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Recordatorios enviados: {enviados}.',
        ))


def _ya_enviado(usuario, tipo, mensaje, fecha):
    return Notificacion.objects.filter(
        usuario=usuario,
        tipo=tipo,
        mensaje=mensaje,
        fecha_creacion__date=fecha,
    ).exists()
