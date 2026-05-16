from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
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
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

# Configurar el logger
logger = logging.getLogger(__name__)

@login_required
def crear_solicitud(request):
    if request.method == 'POST':
        form = SolicitudForm(request.POST)

        if form.is_valid():
            nueva_solicitud = form.save(commit=False)

            ultima_solicitud = Solicitud.objects.count()
            nueva_solicitud.consecutivo = ultima_solicitud + 1

            estado_solicitado, _ = Estado.objects.get_or_create(nombre='solicitado')
            nueva_solicitud.estado = estado_solicitado

            if request.session.get('tipo_cuenta') == 'tecnico':
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
                enviar_correo_solicitud(nueva_solicitud)

            return redirect('crear_solicitud')
        else:
            logger.warning("Errores de validación en SolicitudForm: %s", form.errors)
    else:
        form = SolicitudForm()

    return render(request, 'solicitudes/crear_solicitud.html', {'form': form})

def enviar_correo_solicitud(solicitud):
    subject = 'Nueva Solicitud de Mantenimiento'
    message = f"""
    Se ha creado una nueva solicitud de mantenimiento.
    
    CO: {solicitud.co}
    Creado por: {solicitud.creado_por}
    PDV: {solicitud.PDV}
    Equipo: {solicitud.equipo}
    Descripción solicitud: {solicitud.descripcion_problema}
    Solicitado por: {solicitud.solicitado_por}
    Email del solicitante: {solicitud.email_solicitante}
    """
    recipient_list = [solicitud.email_solicitante, 'correo1@ejemplo.com', 'correo2@ejemplo.com']
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)

@login_required
def lista_solicitudes(request):
    tipo_cuenta = request.session.get('tipo_cuenta')
    co = request.session.get('co')

    if tipo_cuenta == 'tecnico':
        solicitudes = Solicitud.objects.filter(creado_por=request.user.username)
    elif tipo_cuenta == 'administrador' and co:
        solicitudes = Solicitud.objects.filter(co=co)
    else:
        solicitudes = Solicitud.objects.all()

    return render(request, 'solicitudes/lista_solicitudes.html', {'solicitudes': solicitudes})

@login_required
def get_centro_costo(request):
    area_id = request.GET.get('area_id')
    if area_id:
        try:
            area = Area.objects.get(id=area_id)
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
        ubicacion = Ubicacion.objects.get(codigo=codigo)
        areas = ubicacion.children.all()
        equipos = Equipo.objects.filter(ubicacion=ubicacion)

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

@login_required
def get_equipos_por_area(request):
    area_id = request.GET.get('area_id')
    if area_id:
        try:
            area = Area.objects.get(id=area_id)
            activos = Activo.objects.filter(centro_costos__area=area)
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
            ubicacion = Ubicacion.objects.get(codigo=codigo)
            activos = Activo.objects.filter(ubicacion=ubicacion, centro_costos__isnull=True)
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
            activo = Activo.objects.get(id=activo_id)
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

        solicitudes_existentes = Solicitud.objects.exclude(estado=estado_finalizada)
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
        equipo = Equipo.objects.get(codigo=codigo)
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
