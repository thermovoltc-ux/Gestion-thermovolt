from __future__ import annotations

from django.db.models import Q

from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import OrdenTrabajo
from gestion_mantenimiento.solicitudes.models import Solicitud


def obtener_cliente_actual(user):
    perfil = getattr(user, 'perfil_usuario', None)
    if perfil is None:
        return None
    return getattr(perfil, 'cliente', None)


def _collect_descendants_ids(ubicacion_id):
    ids = {int(ubicacion_id)}
    children = Ubicacion.objects.filter(parent_id=ubicacion_id).values_list('id', flat=True)
    for child_id in children:
        ids |= _collect_descendants_ids(child_id)
    return ids


def obtener_scope_ubicacion_ids(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return set()

    tipo_cuenta = request.session.get('tipo_cuenta')
    if tipo_cuenta != 'administrador':
        return set()

    co = request.session.get('co')
    co_value = (co or '').strip()
    if not co_value:
        return set()

    rooted = Ubicacion.objects.filter(co__iexact=co_value)
    ids = set()
    for ubicacion in rooted:
        ids |= _collect_descendants_ids(ubicacion.id)
    return ids


def obtener_scope_ubicaciones(request):
    ids = obtener_scope_ubicacion_ids(request)
    if not ids:
        return Ubicacion.objects.none()
    return Ubicacion.objects.filter(id__in=ids)


def obtener_scope_equipos(request):
    ids = obtener_scope_ubicacion_ids(request)
    if not ids:
        return Equipo.objects.none()
    return Equipo.objects.filter(ubicacion_id__in=ids)


def obtener_scope_solicitudes(request):
    ids = obtener_scope_ubicacion_ids(request)
    if not ids:
        return Solicitud.objects.none()
    return Solicitud.objects.filter(
        Q(ubicacion_id__in=ids) | Q(equipo__ubicacion_id__in=ids)
    )


def obtener_scope_ots(request):
    ids = obtener_scope_ubicacion_ids(request)
    if not ids:
        return OrdenTrabajo.objects.none()
    return OrdenTrabajo.objects.filter(
        Q(solicitud__ubicacion_id__in=ids) | Q(solicitud__equipo__ubicacion_id__in=ids)
    )
