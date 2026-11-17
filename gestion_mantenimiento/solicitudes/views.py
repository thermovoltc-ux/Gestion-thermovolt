from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import unicodedata
from django.utils import timezone
from datetime import timedelta
import datetime
from dateutil.parser import isoparse
from .models import Solicitud
from gestion_mantenimiento.Gestion_ot.models import Estado, OrdenTrabajo, CierreOt
from .forms import SolicitudForm
from gestion_mantenimiento.Activos.models import Activo, Ubicacion, Area, CentroCostos, Equipo
import logging
from django.utils.dateformat import DateFormat
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from gestion_mantenimiento.users.forms import CustomAuthenticationForm
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from gestion_mantenimiento.users.access import (
    obtener_alcance,
    obtener_codigo_co_actual,
    obtener_scope_solicitudes,
    obtener_scope_ubicacion_ids,
)
from gestion_mantenimiento.solicitudes.utils import enviar_correo_solicitud

# Configurar el logger
logger = logging.getLogger(__name__)


def _ubicaciones_visibles(request):
    ubicaciones = Ubicacion.objects.all()
    scope_ids = obtener_scope_ubicacion_ids(request)
    return ubicaciones if scope_ids is None else ubicaciones.filter(id__in=scope_ids)


def _equipos_visibles(request):
    equipos = Equipo.objects.all()
    scope_ids = obtener_scope_ubicacion_ids(request)
    return equipos if scope_ids is None else equipos.filter(ubicacion_id__in=scope_ids)


def _solicitudes_visibles(request):
    solicitudes = Solicitud.objects.all()
    scope_ids = obtener_scope_ubicacion_ids(request)
    if scope_ids is None:
        return solicitudes
    return solicitudes.filter(pk__in=obtener_scope_solicitudes(request).values('pk'))


def _activos_visibles(request):
    activos = Activo.objects.all()
    scope_ids = obtener_scope_ubicacion_ids(request)
    if scope_ids is None:
        return activos
    if not scope_ids:
        return activos.none()
    return activos.filter(
        Q(ubicacion_id__in=scope_ids)
        | Q(
            ubicacion__isnull=True,
            centro_costos__area__ubicacion_id__in=scope_ids,
        )
    ).distinct()


@login_required
def crear_solicitud(request):
    scope_ids = obtener_scope_ubicacion_ids(request)
    if request.method == 'POST':
        form = SolicitudForm(request.POST, scope_ids=scope_ids)

        if form.is_valid():
            equipo = form.cleaned_data.get('equipo')
            ubicacion_id = request.POST.get('ubicacion_id')

            if scope_ids is not None:
                if not scope_ids:
                    form.add_error(None, 'No tienes acceso a ningún alcance de CO válido.')
                    return render(request, 'solicitudes/crear_solicitud.html', {'form': form})
                if equipo and equipo.ubicacion_id not in scope_ids:
                    form.add_error(None, 'El equipo seleccionado no pertenece a tu alcance de CO.')
                    return render(request, 'solicitudes/crear_solicitud.html', {'form': form})

                if ubicacion_id:
                    ubicacion_seleccionada = Ubicacion.objects.filter(id=ubicacion_id).first()
                    if not ubicacion_seleccionada or ubicacion_seleccionada.id not in scope_ids:
                        form.add_error(None, 'La ubicación seleccionada no pertenece a tu alcance de CO.')
                        return render(request, 'solicitudes/crear_solicitud.html', {'form': form})

            if equipo:
                if ubicacion_id:
                    ubicacion_seleccionada = Ubicacion.objects.filter(id=ubicacion_id).first()
                    if not ubicacion_seleccionada:
                        form.add_error(None, 'La ubicación seleccionada no existe.')
                        return render(request, 'solicitudes/crear_solicitud.html', {'form': form})
                    if equipo.ubicacion_id != ubicacion_seleccionada.id:
                        form.add_error(None, 'La ubicación seleccionada no coincide con el equipo elegido.')
                        return render(request, 'solicitudes/crear_solicitud.html', {'form': form})
                else:
                    ubicacion_seleccionada = equipo.ubicacion

                if ubicacion_seleccionada:
                    form.instance.ubicacion = ubicacion_seleccionada

            co_solicitud = obtener_codigo_co_actual(request, ubicacion_seleccionada if equipo else None)

            nueva_solicitud = form.save(commit=False)

            ultimo_consecutivo = Solicitud.objects.aggregate(models.Max('consecutivo'))['consecutivo__max'] or 0
            nueva_solicitud.consecutivo = ultimo_consecutivo + 1
            nueva_solicitud.co = co_solicitud

            estado_solicitado, _ = Estado.objects.get_or_create(nombre='solicitado')
            nueva_solicitud.estado = estado_solicitado

            if obtener_alcance(request).rol == 'tecnico':
                nueva_solicitud.creado_por = request.user.username

            if not nueva_solicitud.fecha_creacion:
                nueva_solicitud.fecha_creacion = timezone.now()
            elif timezone.is_naive(nueva_solicitud.fecha_creacion):
                nueva_solicitud.fecha_creacion = timezone.make_aware(
                    nueva_solicitud.fecha_creacion, timezone.get_current_timezone()
                )

            try:
                nueva_solicitud.save()
                logger.info("Solicitud guardada: %s", nueva_solicitud.pk)
            except Exception as e:
                logger.error("Error al guardar solicitud: %s", e)
                form.add_error(None, 'Error interno al guardar la solicitud. Intenta nuevamente.')
                return render(request, 'solicitudes/crear_solicitud.html', {'form': form})

            if form.cleaned_data.get('enviar_email'):
                try:
                    email_enviado = enviar_correo_solicitud(
                        nueva_solicitud,
                        'creacion',
                        cuerpo_extra=(
                            f'Descripción: {nueva_solicitud.descripcion_problema}\n'
                            f'Solicitado por: {nueva_solicitud.solicitado_por}\n'
                            f'Creado por: {nueva_solicitud.creado_por}'
                        ),
                    )
                except Exception:
                    logger.exception(
                        'Solicitud %s creada, pero no se pudo enviar el correo de creación.',
                        nueva_solicitud.consecutivo,
                    )
                    messages.error(request, 'La solicitud se creó, pero no se pudo enviar el correo.')
                else:
                    if email_enviado:
                        messages.success(request, 'La solicitud se creó y se envió el correo.')
                    else:
                        messages.warning(
                            request,
                            'La solicitud se creó, pero no se envió correo porque no hay destinatarios.',
                        )

            return redirect('crear_solicitud')
        else:
            logger.warning("Errores de validación en SolicitudForm: %s", form.errors)
    else:
        equipo_id = request.GET.get('equipo')
        equipo = None
        initial = {}
        contexto_extra = {}

        try:
            equipo_id = int(equipo_id) if equipo_id else None
        except (TypeError, ValueError):
            equipo_id = None

        if equipo_id is not None:
            equipo = Equipo.objects.select_related('ubicacion').filter(id=equipo_id).first()

        if equipo and scope_ids is not None:
            if not equipo.ubicacion_id or equipo.ubicacion_id not in scope_ids:
                equipo = None

        if equipo:
            initial = {'equipo': equipo}
            contexto_extra = {
                'precarga_equipo': equipo,
                'precarga_ubicacion': equipo.ubicacion,
                'precarga_codigo': equipo.codigo,
                'precarga_numero_serie': equipo.serie or '',
                'precarga_nombre_equipo': equipo.nombre,
            }

        form = SolicitudForm(initial=initial, scope_ids=scope_ids)
        return render(
            request,
            'solicitudes/crear_solicitud.html',
            {'form': form, **contexto_extra},
        )

    return render(request, 'solicitudes/crear_solicitud.html', {'form': form})

@login_required
def lista_solicitudes(request):
    if obtener_alcance(request).rol == 'tecnico':
        solicitudes = Solicitud.objects.filter(creado_por=request.user.username)
    else:
        solicitudes = _solicitudes_visibles(request)

    return render(request, 'solicitudes/lista_solicitudes.html', {'solicitudes': solicitudes})

@login_required
def get_centro_costo(request):
    area_id = request.GET.get('area_id')
    if area_id:
        try:
            areas = Area.objects.filter(
                ubicacion_id__in=_ubicaciones_visibles(request).values('id'),
            )
            area = areas.get(id=area_id)
            centro_costo = CentroCostos.objects.filter(area=area).first()
            if centro_costo:
                return JsonResponse({'centro_costo': centro_costo.nombre})
            else:
                return JsonResponse({'error': 'No se encontró un centro de costos para esta área'})
        except Area.DoesNotExist:
            return JsonResponse({'error': 'Área no encontrada'})
    return JsonResponse({'error': 'ID de área no proporcionado'})

@login_required
def get_ubicacion_por_codigo(request):
    codigo = request.GET.get('codigo')
    if not codigo:
        return JsonResponse({'error': 'Código no proporcionado'}, status=400)

    try:
        ubicacion = _ubicaciones_visibles(request).get(codigo=codigo)
        areas = ubicacion.children.filter(
            id__in=_ubicaciones_visibles(request).values('id'),
        )
        equipos = _equipos_visibles(request).filter(ubicacion=ubicacion)

        response_data = {
            'ubicacion': ubicacion.nombre,
            'areas': [{'id': area.id, 'nombre': area.nombre} for area in areas],
            'activos': [{'id': equipo.id, 'nombre': equipo.nombre} for equipo in equipos]
        }

        # Agregar mensajes de depuración
        print(f"Ubicación encontrada: {ubicacion.nombre}")
        print(f"Áreas encontradas: {[area.nombre for area in areas]}")
        print(f"Equipos encontrados: {[equipo.nombre for equipo in equipos]}")

        return JsonResponse(response_data)
    except Ubicacion.DoesNotExist:
        return JsonResponse({'error': 'Ubicación no encontrada'}, status=404)

def _normalizar_texto(value):
    if value is None:
        return ''
    texto = str(value).casefold()
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(ch for ch in texto if not unicodedata.combining(ch))

@login_required
def buscar_ubicaciones(request):
    logger.info('[UBICACION-SEARCH] Endpoint recibido')
    query = (request.GET.get('q') or '').strip()
    logger.info('[UBICACION-SEARCH] q=%s', query)

    ubicaciones_base = _ubicaciones_visibles(request)

    if not query:
        logger.info('[UBICACION-SEARCH] Resultados vacíos')
        return JsonResponse({'results': []})

    query_normalizado = _normalizar_texto(query)
    logger.info('[UBICACION-SEARCH] query_normalizado=%s', query_normalizado)

    if not query_normalizado:
        logger.info('[UBICACION-SEARCH] Resultados vacíos')
        return JsonResponse({'results': []})

    resultados = []
    ubicaciones_totales = list(ubicaciones_base.order_by('nombre'))
    logger.info('[UBICACION-SEARCH] Total ubicaciones consultadas: %s', len(ubicaciones_totales))

    for ubicacion in ubicaciones_totales:
        nombre = ubicacion.nombre or ''
        nombre_normalizado = _normalizar_texto(nombre)
        if query_normalizado in nombre_normalizado:
            resultado = {
                'id': ubicacion.id,
                'nombre': ubicacion.nombre,
                'codigo': ubicacion.codigo,
            }
            resultados.append(resultado)
            logger.info('[UBICACION-SEARCH] Match: id=%s nombre=%s', ubicacion.id, ubicacion.nombre)
            if len(resultados) >= 10:
                break

    logger.info('[UBICACION-SEARCH] Resultados devueltos: %s', len(resultados))
    if not resultados:
        logger.info('[UBICACION-SEARCH] Resultados vacíos')

    return JsonResponse({'results': resultados})

@login_required
def get_equipos_por_ubicacion(request):
    ubicacion_id = request.GET.get('ubicacion_id')
    query = (request.GET.get('q') or '').strip()

    if not ubicacion_id:
        return JsonResponse({'error': 'ubicacion_id no proporcionado'}, status=400)

    try:
        ubicacion_id = int(ubicacion_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'ubicacion_id no es válido'}, status=400)

    ubicacion = get_object_or_404(_ubicaciones_visibles(request), id=ubicacion_id)
    equipos_qs = _equipos_visibles(request).filter(ubicacion_id=ubicacion.id)
    if query:
        equipos_qs = equipos_qs.filter(nombre__icontains=query)
    equipos_qs = equipos_qs.order_by('nombre')[:20]

    return JsonResponse({
        'ubicacion': {
            'id': ubicacion.id,
            'nombre': ubicacion.nombre,
            'codigo': ubicacion.codigo,
        },
        'results': [
            {'id': equipo.id, 'nombre': equipo.nombre, 'codigo': equipo.codigo}
            for equipo in equipos_qs
        ]
    })

@login_required
def get_equipos_por_area(request):
    area_id = request.GET.get('area_id')
    if area_id:
        try:
            areas = Area.objects.filter(
                ubicacion_id__in=_ubicaciones_visibles(request).values('id'),
            )
            area = areas.get(id=area_id)
            activos = _activos_visibles(request).filter(centro_costos__area=area)
            activos_data = [{'id': activo.id, 'nombre': activo.nombre} for activo in activos]
            return JsonResponse({'activos': activos_data})
        except Area.DoesNotExist:
            return JsonResponse({'error': 'Área no encontrada'})
    return JsonResponse({'error': 'ID de área no proporcionado'})

@login_required
def get_ubicacion_equipos(request):
    codigo = request.GET.get('codigo')
    if codigo:
        try:
            ubicacion = _ubicaciones_visibles(request).get(codigo=codigo)
            activos = _activos_visibles(request).filter(
                ubicacion=ubicacion,
                centro_costos__isnull=True,
            )
            activos_data = [{'id': activo.id, 'nombre': activo.nombre} for activo in activos]
            return JsonResponse({'ubicacion': ubicacion.nombre, 'activos': activos_data})
        except Ubicacion.DoesNotExist:
            return JsonResponse({'error': 'Ubicación no encontrada'})
    return JsonResponse({'error': 'CO no proporcionado'})

@login_required
def get_numero_activo(request):
    activo_id = request.GET.get('activo_id')
    if activo_id:
        try:
            activo = _activos_visibles(request).get(id=activo_id)
            return JsonResponse({'numero_serie': activo.numero_serie})
        except Activo.DoesNotExist:
            return JsonResponse({'error': 'Activo no encontrado'})
    return JsonResponse({'error': 'ID de activo no proporcionado'})

@login_required
def verificar_solicitud(request):
    codigo = request.GET.get('codigo')
    equipo_id = request.GET.get('equipo_id')
    equipo_nombre = request.GET.get('equipo')

    if codigo or equipo_id or equipo_nombre:
        try:
            estado_finalizada, _ = Estado.objects.get_or_create(nombre='finalizada')
        except Exception as e:
            print(f"DEBUG verificar_solicitud: Error al obtener estado finalizada: {e}")
            return JsonResponse({'error': str(e)}, status=500)

        solicitudes_existentes = _solicitudes_visibles(request).exclude(
            estado=estado_finalizada,
        )
        if equipo_id:
            try:
                equipo_id_int = int(equipo_id)
                solicitudes_existentes = solicitudes_existentes.filter(equipo_id=equipo_id_int)
            except (ValueError, TypeError):
                solicitudes_existentes = solicitudes_existentes.none()
        elif codigo:
            solicitudes_existentes = solicitudes_existentes.filter(equipo__codigo=codigo)
        elif equipo_nombre:
            solicitudes_existentes = solicitudes_existentes.filter(equipo__nombre=equipo_nombre)

        count = solicitudes_existentes.count()
        print(f"DEBUG verificar_solicitud: codigo={codigo} equipo_id={equipo_id} equipo_nombre={equipo_nombre} count={count}")
        if count > 0:
            return JsonResponse({'exists': True, 'count': count})

    return JsonResponse({'exists': False, 'count': 0})

@login_required
def get_equipo_por_codigo(request):
    codigo = request.GET.get('codigo')
    if not codigo:
        return JsonResponse({'error': 'Código no proporcionado'}, status=400)

    try:
        equipo = _equipos_visibles(request).get(codigo=codigo)
        ubicacion = equipo.ubicacion

        response_data = {
            'equipo_id': equipo.id,  # Agregar el ID del equipo
            'equipo': equipo.nombre,
            'ubicacion': ubicacion.nombre if ubicacion else '',
            'areas': [{'id': area.id, 'nombre': area.nombre} for area in ubicacion.children.all()] if ubicacion else [],
            'centro_costo': ubicacion.centro_costos.nombre if ubicacion and hasattr(ubicacion, 'centro_costos') else '',
            'numero_serie': equipo.serie
        }

        # Agregar mensajes de depuración
        print(f"Equipo encontrado: {equipo.nombre}")
        if ubicacion:
            print(f"Ubicación encontrada: {ubicacion.nombre}")
            print(f"Áreas encontradas: {[area.nombre for area in ubicacion.children.all()]}")
            print(f"Centro de costos: {ubicacion.centro_costos.nombre if hasattr(ubicacion, 'centro_costos') else 'No tiene centro de costos'}")

        return JsonResponse(response_data)
    except Equipo.DoesNotExist:
        return JsonResponse({'error': 'Equipo no encontrado'}, status=404)
