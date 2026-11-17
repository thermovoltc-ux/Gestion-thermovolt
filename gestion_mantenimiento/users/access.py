from __future__ import annotations

from django.db.models import Q

from gestion_mantenimiento.Activos.models import CentroOperaciones, Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import OrdenTrabajo, TareaMantenimiento
from gestion_mantenimiento.solicitudes.models import Solicitud

_UNSET = object()


class Alcance:
    def __init__(self, rol, ubicacion_ids):
        self.rol = rol
        self.ubicacion_ids = ubicacion_ids


def obtener_cliente_actual(user):
    perfil = getattr(user, 'perfil_usuario', None)
    if perfil is None:
        return None
    return getattr(perfil, 'cliente', None)


def _centro_de_sesion(request):
    if 'centro_operaciones_id' in request.session:
        try:
            centro_id = int(request.session.get('centro_operaciones_id'))
        except (TypeError, ValueError):
            return None, True
        centro = CentroOperaciones.objects.filter(pk=centro_id, activo=True).first()
        return centro, True

    codigo = (request.session.get('co') or '').strip()
    if codigo:
        centro = CentroOperaciones.objects.filter(
            codigo__iexact=codigo,
            activo=True,
        ).first()
        return centro, True

    return None, False


def _ubicaciones_del_centro(centro):
    codigo = centro.codigo.strip()
    raices = Ubicacion.objects.filter(
        Q(centro_operaciones=centro)
        | Q(centro_operaciones__isnull=True, co__iexact=codigo)
    ).distinct()
    ubicaciones = set()
    pendientes = list(raices)

    while pendientes:
        actual = pendientes.pop()
        if actual.pk in ubicaciones:
            continue
        ubicaciones.add(actual.pk)

        for hijo in Ubicacion.objects.filter(parent_id=actual.pk):
            pendientes.append(hijo)

    return ubicaciones


def obtener_alcance(request, user=None, centro_operaciones=_UNSET):
    user = user if user is not None else getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return Alcance('desconocido', set())

    grupos = set(user.groups.values_list('name', flat=True))
    if user.is_superuser:
        rol = 'jefe_de_area'
    elif 'Cliente' in grupos:
        rol = 'administrador'
    elif 'Tecnico' in grupos:
        rol = 'tecnico'
    elif 'Admin' in grupos:
        rol = 'jefe_de_area'
    elif user.is_staff:
        rol = 'jefe_de_area'
    else:
        return Alcance('desconocido', set())

    centro_seleccionado = centro_operaciones
    hay_co_en_sesion = False
    if centro_operaciones is _UNSET:
        centro_seleccionado, hay_co_en_sesion = _centro_de_sesion(request)

    if rol == 'tecnico':
        return Alcance(rol, None)

    if (hay_co_en_sesion and centro_seleccionado is None) or (
        centro_seleccionado is not None and not centro_seleccionado.activo
    ):
        return Alcance(rol, set())

    if centro_seleccionado is None:
        if rol == 'jefe_de_area':
            return Alcance(rol, None)
        return Alcance(rol, set())

    return Alcance(rol, _ubicaciones_del_centro(centro_seleccionado))


def obtener_codigo_co_actual(request, ubicacion=None):
    if ubicacion:
        if ubicacion.centro_operaciones_id:
            return ubicacion.centro_operaciones.codigo.strip()
        codigo = (ubicacion.co or '').strip() or (ubicacion.codigo or '').strip()
        if codigo:
            return codigo

    if 'centro_operaciones_id' in request.session:
        centro, _ = _centro_de_sesion(request)
        return centro.codigo.strip() if centro else ''

    codigo_sesion = (request.session.get('co') or '').strip()
    if not codigo_sesion:
        return ''
    centro = CentroOperaciones.objects.filter(
        codigo__iexact=codigo_sesion,
        activo=True,
    ).first()
    return centro.codigo.strip() if centro else codigo_sesion


def obtener_scope_ubicacion_ids(request):
    return obtener_alcance(request).ubicacion_ids


def obtener_scope_ubicaciones(request):
    ids = obtener_scope_ubicacion_ids(request)
    if ids is None:
        return Ubicacion.objects.all()
    if not ids:
        return Ubicacion.objects.none()
    return Ubicacion.objects.filter(id__in=ids)


def obtener_scope_equipos(request):
    ids = obtener_scope_ubicacion_ids(request)
    if ids is None:
        return Equipo.objects.all()
    if not ids:
        return Equipo.objects.none()
    return Equipo.objects.filter(ubicacion_id__in=ids)


def obtener_scope_solicitudes(request):
    ids = obtener_scope_ubicacion_ids(request)
    if ids is None:
        return Solicitud.objects.all()
    if not ids:
        return Solicitud.objects.none()
    return Solicitud.objects.filter(
        Q(equipo__isnull=False, equipo__ubicacion_id__in=ids)
        | Q(equipo__isnull=True, ubicacion_id__in=ids)
    )


def obtener_scope_ots(request):
    ids = obtener_scope_ubicacion_ids(request)
    if ids is None:
        return OrdenTrabajo.objects.all()
    if not ids:
        return OrdenTrabajo.objects.none()
    return OrdenTrabajo.objects.filter(
        solicitud__in=obtener_scope_solicitudes(request),
    )


def obtener_scope_tareas(request):
    ids = obtener_scope_ubicacion_ids(request)
    if ids is None:
        return TareaMantenimiento.objects.all()
    if not ids:
        return TareaMantenimiento.objects.none()
    return TareaMantenimiento.objects.filter(plan__equipo__ubicacion_id__in=ids)
