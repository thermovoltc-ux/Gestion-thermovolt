from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse

from gestion_mantenimiento.Activos.models import CentroOperaciones
from gestion_mantenimiento.users.models import PerfilUsuario

from .models import Notificacion


def crear_notificacion(usuario, tipo, titulo, mensaje, url_destino=''):
    return Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        url_destino=url_destino,
    )


def notificar_usuarios(usuarios, tipo, titulo, mensaje, url_destino=''):
    return [
        crear_notificacion(usuario, tipo, titulo, mensaje, url_destino)
        for usuario in usuarios.distinct()
    ]


def notificar_administradores(tipo, titulo, mensaje, url_destino=''):
    user_model = get_user_model()
    administradores = user_model.objects.filter(is_active=True).filter(
        Q(is_superuser=True)
        | Q(is_staff=True)
        | Q(groups__name__in=['Admin', 'Supervisor', 'Jefe de Área', 'Jefe de Area']),
    ).exclude(
        groups__name='Cliente',
    ).distinct()
    return notificar_usuarios(
        administradores,
        tipo,
        titulo,
        mensaje,
        url_destino,
    )


def _centro_de_ubicacion(ubicacion):
    actual = ubicacion
    while actual is not None:
        if actual.centro_operaciones_id:
            return actual.centro_operaciones
        codigo_co = (actual.co or '').strip()
        if codigo_co:
            centro = CentroOperaciones.objects.filter(
                codigo__iexact=codigo_co,
                activo=True,
            ).first()
            if centro:
                return centro
        actual = actual.parent
    return None


def usuarios_cliente_de_ubicacion(ubicacion):
    if ubicacion is None:
        return get_user_model().objects.none()
    centro = _centro_de_ubicacion(ubicacion)
    if centro is None:
        return get_user_model().objects.none()
    return get_user_model().objects.filter(
        is_active=True,
        perfil_usuario__cliente__activo=True,
        perfil_usuario__cliente__centros_operaciones=centro,
    ).distinct()


def notificar_mantenimiento_preventivo(solicitud, plan, fecha_programada):
    equipo = plan.equipo
    ubicacion = equipo.ubicacion
    ubicacion_nombre = ubicacion.nombre if ubicacion else 'ubicación no especificada'
    fecha_texto = fecha_programada.strftime('%d/%m/%Y')
    url_destino = reverse('lista_solicitudes')

    titulo_admin = 'Mantenimiento preventivo programado'
    mensaje_admin = (
        f'El plan {plan.nombre} ha generado la solicitud '
        f'#{solicitud.consecutivo} para el equipo {equipo.nombre} '
        f'en {ubicacion_nombre}, programada para el {fecha_texto}.'
    )
    notificar_administradores(
        Notificacion.MANTENIMIENTO_PREVENTIVO,
        titulo_admin,
        mensaje_admin,
        url_destino,
    )

    mensaje_cliente = (
        f'Se ha programado un mantenimiento preventivo para el equipo '
        f'{equipo.nombre} en {ubicacion_nombre} para el día {fecha_texto}.'
    )
    return notificar_usuarios(
        usuarios_cliente_de_ubicacion(ubicacion),
        Notificacion.MANTENIMIENTO_PREVENTIVO,
        titulo_admin,
        mensaje_cliente,
        url_destino,
    )


def notificar_nueva_solicitud(solicitud):
    ubicacion_nombre = solicitud.ubicacion_nombre or 'ubicación no especificada'
    creador = solicitud.solicitado_por or solicitud.creado_por
    mensaje = (
        f'El usuario {creador} creó la solicitud #{solicitud.consecutivo} '
        f'para {solicitud.equipo.nombre} en {ubicacion_nombre}.'
    )
    return notificar_administradores(
        Notificacion.SOLICITUD,
        'Nueva solicitud de mantenimiento',
        mensaje,
        reverse('lista_solicitudes'),
    )
