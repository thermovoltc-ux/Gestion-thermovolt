from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.db import models
from django.utils import timezone
from datetime import timedelta
import datetime
from dateutil.parser import isoparse
import re
import requests
from urllib.parse import urljoin
import os
from django.contrib import messages
import os
from .models import OrdenTrabajo, Estado, CierreOt, ImagenCierreOt, PlanMantenimiento, ActividadMantenimiento, TareaMantenimiento, CierreOtActividad
from .forms import GestionOtForm, OrdenTrabajoForm, CierreOtForm, ImagenCierreOtForm, ImagenAntesForm, ImagenDespuesForm, CierreOtActividadFormSet
from gestion_mantenimiento.solicitudes.models import Solicitud
import logging
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder
from docx import Document
from docx2pdf import convert
from docx.shared import Inches, Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.core.mail import EmailMessage
from django.conf import settings
from io import BytesIO
import tempfile
from django.forms import modelformset_factory
import os
import base64
import shutil
import subprocess
from PIL import Image as PILImage

try:
    import pythoncom
except ImportError:
    pythoncom = None


def convertir_docx_a_pdf(docx_path, pdf_path):
    """Convierte un archivo DOCX a PDF.
    Usa docx2pdf en Windows o LibreOffice/soffice en Linux.
    """
    if os.name == 'nt':
        if pythoncom is None:
            raise RuntimeError('pythoncom no disponible en Windows')
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
        finally:
            pythoncom.CoUninitialize()
        return

    # En Linux/Unix no usamos docx2pdf porque requiere Microsoft Word.
    # Intentamos directamente usar LibreOffice/soffice.
    libreoffice = shutil.which('soffice') or shutil.which('libreoffice')
    if not libreoffice:
        raise RuntimeError('No se encontró LibreOffice/soffice para convertir DOCX a PDF')

    output_dir = os.path.dirname(pdf_path)
    cmd = [libreoffice, '--headless', '--convert-to', 'pdf', '--outdir', output_dir, docx_path]
    logger.info('Ejecutando conversión LibreOffice: %s', ' '.join(cmd))
    result = subprocess.run(cmd, check=True, timeout=120, capture_output=True, text=True)
    logger.info('LibreOffice stdout: %s', result.stdout)
    if result.stderr:
        logger.warning('LibreOffice stderr: %s', result.stderr)

    alt_pdf = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
    if os.path.exists(pdf_path):
        return
    if os.path.exists(alt_pdf):
        os.replace(alt_pdf, pdf_path)
        return

    raise RuntimeError('LibreOffice no produjo el PDF esperado')


def obtener_imagen_temporal_para_pdf(file_field):
    """Devuelve una ruta local temporal para usar en PDF.
    Intenta primero descargar desde URL remota (Cloudinary).
    Como fallback, usa path local si existe.
    """
    # Validar que file_field no sea None o cadena vacía
    if not file_field or isinstance(file_field, str):
        return None, False
    
    try:
        # Obtener el nombre del archivo de forma segura
        file_name = getattr(file_field, 'name', 'unknown')
        
        # Intentar obtener URL primero (mejor opción para Cloudinary)
        if hasattr(file_field, 'url'):
            url = file_field.url
            if url and isinstance(url, str) and re.match(r'^https?://', url):
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    suffix = os.path.splitext(file_name)[1] or '.jpg'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    temp_file.write(response.content)
                    temp_file.close()
                    return temp_file.name, True
                except Exception as e:
                    pass  # Silently fall back to local path
        
        # Fallback a path local si URL no está disponible
        if hasattr(file_field, 'path'):
            try:
                local_path = file_field.path
                if local_path and os.path.exists(local_path):
                    return local_path, False
            except (AttributeError, ValueError, NotImplementedError) as e:
                pass  # Silently continue
    except Exception as e:
        pass  # Silently continue
    return None, False

class CustomDjangoJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, models.FileField):
            return obj.url if obj else None
        return super().default(obj)


def obtener_actividades_cierre(cierre_ot):
    actividades = []
    for item in cierre_ot.actividades_cierre.select_related('actividad'):
        if item.actividad is None:
            continue
        descripcion = item.actividad.descripcion or ''
        texto = item.actividad.nombre
        if descripcion:
            texto += f": {descripcion}"
        texto += ' - Realizada' if item.realizada else ' - Pendiente'
        if item.comentario:
            texto += f" ({item.comentario})"
        actividades.append(texto)
    return actividades


# Configurar el logger
logger = logging.getLogger(__name__)
@login_required
# Vista para gestionar órdenes de trabajo
def gestion_ot(request):
    ordenes_trabajo = OrdenTrabajo.objects.all()
    solicitudes_pendientes = Solicitud.objects.filter(gestionot__isnull=True)
    tareas_mantenimiento = TareaMantenimiento.objects.filter(
        estado__in=['pendiente', 'en_progreso']
    ).select_related('plan', 'actividad', 'tecnico').order_by('fecha_programada')
    tecnicos = User.objects.filter(groups__name='Tecnico')

    # Filtros
    filtro_fecha_inicio = request.GET.get('fecha_inicio')
    filtro_fecha_fin = request.GET.get('fecha_fin')
    filtro_pdv = request.GET.get('pdv')
    filtro_estado = request.GET.get('estado')
    filtro_atrasadas = request.GET.get('atrasadas')

    pdvs = Solicitud.objects.values_list('PDV', flat=True).distinct()

    # Si no hay filtros aplicados, mostrar las solicitudes del mes actual
    if not filtro_fecha_inicio and not filtro_fecha_fin:
        now = timezone.now()
        first_day_of_month = now.replace(day=1)
        last_day_of_month = (first_day_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        filtro_fecha_inicio = first_day_of_month.date()
        filtro_fecha_fin = last_day_of_month.date()

    if filtro_fecha_inicio and filtro_fecha_fin:
        if isinstance(filtro_fecha_inicio, str):
            filtro_fecha_inicio = timezone.make_aware(datetime.datetime.strptime(filtro_fecha_inicio, '%Y-%m-%d'), timezone.get_current_timezone())
        if isinstance(filtro_fecha_fin, str):
            filtro_fecha_fin = timezone.make_aware(datetime.datetime.strptime(filtro_fecha_fin, '%Y-%m-%d'), timezone.get_current_timezone())
        solicitudes_pendientes = solicitudes_pendientes.filter(fecha_creacion__range=[filtro_fecha_inicio, filtro_fecha_fin])
        tareas_mantenimiento = tareas_mantenimiento.filter(fecha_programada__range=[filtro_fecha_inicio, filtro_fecha_fin])
    if filtro_pdv:
        solicitudes_pendientes = solicitudes_pendientes.filter(PDV=filtro_pdv)

    filter_label = None
    if filtro_estado:
        solicitudes_pendientes = solicitudes_pendientes.filter(estado__nombre=filtro_estado)
        tarea_estado = filtro_estado
        if filtro_estado == 'en proceso':
            tarea_estado = 'en_progreso'
        tareas_mantenimiento = tareas_mantenimiento.filter(estado=tarea_estado)
        filter_label = f'Filtrado por estado: {filtro_estado}'
    elif filtro_atrasadas:
        tareas_mantenimiento = tareas_mantenimiento.filter(fecha_programada__lt=timezone.now().date())
        filter_label = 'Tareas con atraso'

    form = GestionOtForm()
    return render(request, 'Gestion_ot/gestion_ot.html', {
        'form': form,
        'ordenes_trabajo': ordenes_trabajo,
        'solicitudes': solicitudes_pendientes,
        'tareas_mantenimiento': tareas_mantenimiento,
        'pdvs': pdvs,
        'filtro_fecha_inicio': filtro_fecha_inicio,
        'filtro_fecha_fin': filtro_fecha_fin,
        'filtro_pdv': filtro_pdv,
        'filtro_estado': filtro_estado,
        'filtro_atrasadas': filtro_atrasadas,
        'filter_label': filter_label,
        'tecnicos': tecnicos,
    })


# Vista para actualizar el estado de una solicitud
@csrf_exempt
@require_POST
@login_required
def actualizar_estado_solicitud(request):
    try:
        data = json.loads(request.body)
        logger.debug(f"Datos recibidos: {data}")
        
        numero_solicitud = data.get('numero')
        nuevo_estado_nombre = data.get('estado')
        tecnico = data.get('tecnico')
        fecha = data.get('fecha')

        logger.debug(f"Numero de Solicitud: {numero_solicitud}")
        logger.debug(f"Nuevo Estado: {nuevo_estado_nombre}")
        logger.debug(f"Tecnico: {tecnico}")
        logger.debug(f"Fecha: {fecha}")

        if not numero_solicitud or not nuevo_estado_nombre:
            logger.error("Número y estado son requeridos.")
            return JsonResponse({'status': 'error', 'message': 'Número y estado son requeridos.'}, status=400)

        # Fecha es requerida solo si el estado no es "finalizada"
        if not fecha and nuevo_estado_nombre != "finalizada":
            logger.error("Fecha de actividad es requerida.")
            return JsonResponse({'status': 'error', 'message': 'Fecha de actividad es requerida.'}, status=400)

        solicitud = Solicitud.objects.get(consecutivo=numero_solicitud)
        logger.debug(f"Solicitud encontrada: {solicitud}")

        nuevo_estado, _ = Estado.objects.get_or_create(nombre=nuevo_estado_nombre)
        solicitud.estado = nuevo_estado
        
        if fecha:
            try:
                try:
                    fecha_dt = isoparse(fecha)
                except ValueError:
                    fecha_dt = datetime.datetime.strptime(fecha, '%d/%m/%Y')
                if timezone.is_naive(fecha_dt):
                    fecha_dt = timezone.make_aware(fecha_dt, timezone.get_current_timezone())
                solicitud.fecha_actividad = fecha_dt
            except ValueError as parse_error:
                logger.error(f"No se pudo parsear la fecha: {fecha}")
                return JsonResponse({'status': 'error', 'message': f'Fecha inválida: {fecha}'}, status=400)

        solicitud.save()
        logger.debug(f"Solicitud actualizada: {solicitud}")

        # Crear o actualizar la Orden de Trabajo
        orden_trabajo_data = {
            'tecnico_asignado': tecnico or '',
            'estado': nuevo_estado
        }
        if fecha:
            try:
                try:
                    fecha_dt = isoparse(fecha)
                except ValueError:
                    fecha_dt = datetime.datetime.strptime(fecha, '%d/%m/%Y')
                if timezone.is_naive(fecha_dt):
                    fecha_dt = timezone.make_aware(fecha_dt, timezone.get_current_timezone())
                orden_trabajo_data['fecha_actividad'] = fecha_dt
            except ValueError as parse_error:
                logger.error(f"No se pudo parsear la fecha para orden de trabajo: {fecha}")
                return JsonResponse({'status': 'error', 'message': f'Fecha inválida: {fecha}'}, status=400)

        orden_trabajo, created = OrdenTrabajo.objects.update_or_create(
            solicitud=solicitud,
            defaults=orden_trabajo_data
        )
        logger.debug(f"Orden de Trabajo {'creada' if created else 'actualizada'}: {orden_trabajo}")

        return JsonResponse({'status': 'ok', 'message': 'Solicitud y Orden de Trabajo actualizadas correctamente'})

    except Solicitud.DoesNotExist:
        logger.error("Solicitud no encontrada.")
        return JsonResponse({'status': 'error', 'message': 'Solicitud no encontrada'}, status=404)
    except Exception as e:
        logger.exception("Error al actualizar la solicitud.")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# Vista para asignar un técnico a un preventivo y crear una solicitud/OT vinculada
@csrf_exempt
@require_POST
@login_required
def asignar_tarea_preventiva(request, tarea_id):
    try:
        data = json.loads(request.body)
        tecnico = data.get('tecnico')
        fecha = data.get('fecha')
        estado = data.get('estado', 'en_progreso')

        if not tecnico or not fecha:
            return JsonResponse({'status': 'error', 'message': 'Técnico y fecha son requeridos.'}, status=400)

        tarea = TareaMantenimiento.objects.select_related('plan__equipo', 'actividad').get(id=tarea_id)
        equipo = tarea.plan.equipo
        if not equipo:
            return JsonResponse({'status': 'error', 'message': 'La tarea no tiene equipo asociado.'}, status=400)

        descripcion = f"Preventivo: {tarea.plan.nombre}"
        if tarea.actividad:
            descripcion += f" - {tarea.actividad.nombre}"

        ubicacion = equipo.ubicacion
        estado_nombre = 'en proceso' if estado == 'en_progreso' else estado
        estado_obj, _ = Estado.objects.get_or_create(nombre=estado_nombre)

        solicitud = Solicitud.objects.create(
            creado_por=request.user.username,
            descripcion_problema=descripcion,
            equipo=equipo,
            fecha_creacion=timezone.now(),
            estado=estado_obj,
            PDV=ubicacion.nombre if ubicacion else equipo.nombre,
            solicitado_por=request.user.username,
            prioridad='media',
            ubicacion=ubicacion
        )

        fecha_dt = datetime.datetime.strptime(fecha, '%Y-%m-%d')
        fecha_dt = timezone.make_aware(fecha_dt, timezone.get_current_timezone())

        OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado=tecnico,
            fecha_actividad=fecha_dt,
            estado=estado_obj
        )

        tarea.tecnico = User.objects.filter(username=tecnico).first()
        tarea.estado = 'convertido'
        tarea.observaciones = f"Convertido en solicitud {solicitud.consecutivo}"
        tarea.save()

        return JsonResponse({'status': 'ok', 'message': 'Preventivo convertido en solicitud correctamente.', 'consecutivo': solicitud.consecutivo})

    except TareaMantenimiento.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Tarea no encontrada.'}, status=404)
    except Exception as e:
        logger.exception('Error al asignar preventivo.')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Vista para listar todas las órdenes de trabajo
@login_required
def listar_ot(request):
    equipo_id = request.GET.get('equipo_id')
    ubicacion_id = request.GET.get('ubicacion_id')

    if request.user.groups.filter(name='Admin').exists():
        ots = OrdenTrabajo.objects.all()
    else:
        ots = OrdenTrabajo.objects.filter(tecnico_asignado=request.user.username)

    filter_label = None
    estado = request.GET.get('estado')

    if estado:
        estado_nombre = 'en proceso' if estado == 'en_proceso' else estado
        ots = ots.filter(estado__nombre=estado_nombre)
        filter_label = f'Filtrado por estado: {estado_nombre}'

    if equipo_id:
        ots = ots.filter(solicitud__equipo_id=equipo_id)
        filter_label = f'Historial de OT para Equipo ID {equipo_id}'
    elif ubicacion_id:
        from gestion_mantenimiento.Activos.models import Ubicacion

        def get_descendant_ids(ubicacion):
            ids = [ubicacion.id]
            for child in ubicacion.children.all():
                ids.extend(get_descendant_ids(child))
            return ids

        ubicacion = Ubicacion.objects.filter(id=ubicacion_id).first()
        if ubicacion:
            ubicacion_ids = get_descendant_ids(ubicacion)
            ots = ots.filter(solicitud__equipo__ubicacion_id__in=ubicacion_ids)
            filter_label = f'Historial de OT para Ubicación {ubicacion.nombre} (ID {ubicacion.id})'
        else:
            filter_label = f'Historial de OT para Ubicación ID {ubicacion_id}'

    calendar_events = []
    for ot in ots:
        if ot.fecha_actividad:
            calendar_events.append({
                'title': f"OT-{ot.solicitud.consecutivo} - {ot.tecnico_asignado}",
                'start': ot.fecha_actividad.date().isoformat(),
                'url': reverse('cierre_ot', args=[ot.id]),
            })

    return render(request, 'Gestion_ot/listar_ot.html', {
        'ots': ots,
        'filter_label': filter_label,
        'calendar_events_json': json.dumps(calendar_events),
    })

# Vista para cerrar una OT
@login_required
def cierre_ot(request, ot_id):
    logger.info("cierre_ot called ot_id=%s method=%s", ot_id, request.method)
    ot = get_object_or_404(OrdenTrabajo, id=ot_id)
    cierre_ot, created = CierreOt.objects.get_or_create(orden_trabajo=ot)
    form_antes = ImagenAntesForm()
    form_despues = ImagenDespuesForm()

    if request.method == 'POST':
        logger.debug("cierre_ot POST data keys=%s files keys=%s", list(request.POST.keys()), list(request.FILES.keys()))

        form = CierreOtForm(request.POST, request.FILES, instance=cierre_ot)
        actividad_formset = CierreOtActividadFormSet(request.POST, instance=cierre_ot)
        form_antes = ImagenAntesForm(request.POST, request.FILES)
        form_despues = ImagenDespuesForm(request.POST, request.FILES)

        is_valid_form = form.is_valid()
        is_valid_formset = actividad_formset.is_valid()
        logger.debug("cierre_ot form valid=%s formset valid=%s", is_valid_form, is_valid_formset)
        if not is_valid_form or not is_valid_formset:
            if not is_valid_form:
                logger.error("cierre_ot form errors=%s", form.errors)
            if not is_valid_formset:
                logger.error("cierre_ot formset errors=%s", actividad_formset.errors)
            messages.error(request, f"Errores en el formulario: {form.errors} {actividad_formset.errors}")
            return render(request, 'Gestion_ot/cierre_ot.html', {
                'form': form,
                'actividad_formset': actividad_formset,
                'form_antes': form_antes,
                'form_despues': form_despues,
                'ot': ot
            })

        # Guardar las firmas desde los textareas ocultos
        firma_tecnico = request.POST.get('firma_digital', '')
        firma_receptor = request.POST.get('firma_receptor', '')

        logger.debug("firma_tecnico recibida length=%s firma_receptor length=%s", len(firma_tecnico), len(firma_receptor))

        cierre_ot.firma_digital = firma_tecnico
        cierre_ot.firma_receptor = firma_receptor

        # Guardar el formulario y las actividades del cierre
        cierre_ot = form.save()
        actividad_formset.instance = cierre_ot
        actividad_formset.save()
        logger.info("Cierre OT guardado con ID: %s", cierre_ot.id)

        # Guardar imágenes antes
        imagenes_antes_count = 0
        for file in request.FILES.getlist('imagenes_antes'):
            if file:
                ImagenCierreOt.objects.create(cierre_ot=cierre_ot, imagen=file, tipo='antes')
                imagenes_antes_count += 1
        logger.info("Imágenes antes guardadas: %s", imagenes_antes_count)

        # Guardar imágenes después
        imagenes_despues_count = 0
        for file in request.FILES.getlist('imagenes_despues'):
            if file:
                ImagenCierreOt.objects.create(cierre_ot=cierre_ot, imagen=file, tipo='despues')
                imagenes_despues_count += 1
        logger.info("Imágenes después guardadas: %s", imagenes_despues_count)

        # Cambiar estados
        try:
            estado_revision, _ = Estado.objects.get_or_create(nombre="en revision")
            ot.estado = estado_revision
            ot.save()
            cierre_ot.estado = estado_revision
            cierre_ot.save()
            solicitud = ot.solicitud
            solicitud.estado = estado_revision
            solicitud.save()
            logger.info("Estados actualizados correctamente")
        except Exception as e:
            logger.error("Error actualizando estados: %s", e)
            messages.error(request, f"Error actualizando estados: {e}")
            return render(request, 'Gestion_ot/cierre_ot.html', {
                'form': form,
                'actividad_formset': actividad_formset,
                'form_antes': form_antes,
                'form_despues': form_despues,
                'ot': ot
            })

        # Generar y enviar PDF
        try:
            result = generar_pdf_informe(cierre_ot, request)
            firma_tec_agregada = False
            firma_rec_agregada = False
            if isinstance(result, tuple) and len(result) == 3:
                pdf_buffer, firma_tec_agregada, firma_rec_agregada = result
            else:
                pdf_buffer = result
            logger.info("PDF generado correctamente, tamaño=%s bytes", len(pdf_buffer.getvalue()))

            logger.info("Correo técnico: %s", cierre_ot.correo_tecnico)
            email_enviado = enviar_pdf_por_email(pdf_buffer, cierre_ot)
            
            if email_enviado:
                logger.info("Email enviado correctamente")
                success_msg = f"OT cerrada exitosamente. PDF generado y email enviado. Firma tec agregada: {firma_tec_agregada}, Firma rec agregada: {firma_rec_agregada}"
            else:
                logger.warning("Advertencia: PDF generado pero email no se pudo enviar")
                success_msg = f"OT cerrada exitosamente. PDF generado pero EMAIL NO SE ENVIÓ (revisar configuración). Firma tec agregada: {firma_tec_agregada}, Firma rec agregada: {firma_rec_agregada}"
            
            messages.success(request, success_msg)
            return redirect('listar_ot')
        except Exception as e:
            logger.error("Error generando PDF: %s", e)
            messages.error(request, f"Error procesando cierre: {e}")
            return render(request, 'Gestion_ot/cierre_ot.html', {
                'form': form,
                'actividad_formset': actividad_formset,
                'form_antes': form_antes,
                'form_despues': form_despues,
                'ot': ot
            })

    else:
        form = CierreOtForm(instance=cierre_ot)
        form_antes = ImagenAntesForm()
        form_despues = ImagenDespuesForm()
        if not cierre_ot.actividades_cierre.exists():
            plan = PlanMantenimiento.objects.filter(equipo=ot.solicitud.equipo, activo=True).first()
            if plan:
                for actividad in plan.actividades.all():
                    CierreOtActividad.objects.get_or_create(cierre_ot=cierre_ot, actividad=actividad)
        actividad_formset = CierreOtActividadFormSet(instance=cierre_ot)
    return render(request, 'Gestion_ot/cierre_ot.html', {
        'form': form,
        'actividad_formset': actividad_formset,
        'form_antes': form_antes,
        'form_despues': form_despues,
        'ot': ot
    })


# Detalles de la solicitud
@login_required
def detalles_solicitud(request, consecutivo):
    solicitud = get_object_or_404(Solicitud, consecutivo=consecutivo)
    ordenes_trabajo = solicitud.ordenes_trabajo.all()
    data = {
        'consecutivo': solicitud.consecutivo,
        'pdv': solicitud.PDV,
        'descripcion': solicitud.descripcion_problema,
        'fecha_creacion': solicitud.fecha_creacion,
        'estado': solicitud.estado.nombre,
        'ordenes_trabajo': []
    }
    for ot in ordenes_trabajo:
        try:
            cierre_ot = CierreOt.objects.get(orden_trabajo=ot)
            data['ordenes_trabajo'].append({
                'tecnico_asignado': ot.tecnico_asignado,
                'estado__nombre': ot.estado.nombre,
                'fecha_actividad': ot.fecha_actividad,
                'causa_falla': cierre_ot.causa_falla,
                'correo_tecnico': cierre_ot.correo_tecnico,
                'descripcion_falla': cierre_ot.descripcion_falla,
                'documento_tecnico': cierre_ot.documento_tecnico or None,
                'fecha_inicio_actividad': cierre_ot.fecha_inicio_actividad,
                'hora_fin': cierre_ot.hora_fin,
                'hora_inicio': cierre_ot.hora_inicio,
                'materiales_utilizados': cierre_ot.materiales_utilizados,
                'nombre_tecnico': cierre_ot.nombre_tecnico,
                'observaciones': cierre_ot.observaciones,
                'tipo_intervencion': cierre_ot.tipo_intervencion,
                'tipo_mantenimiento': cierre_ot.tipo_mantenimiento,
            })
        except CierreOt.DoesNotExist:
            data['ordenes_trabajo'].append({
                'tecnico_asignado': ot.tecnico_asignado,
                'estado__nombre': ot.estado.nombre,
                'fecha_actividad': ot.fecha_actividad,
                # Otros campos de OrdenTrabajo que sean necesarios
            })
    
    return JsonResponse(data, encoder=CustomDjangoJSONEncoder)


def generar_pdf_informe(cierre_ot, request=None):
    """Genera un PDF usando plantilla Word si existe, sino usa ReportLab"""
    template_path = os.path.join(settings.BASE_DIR, 'gestion_mantenimiento', 'static', 'plantilla_ot.docx')
    
    if os.path.exists(template_path):
        firma_tec = request.POST.get('firma_digital') if request else None
        firma_rec = request.POST.get('firma_receptor') if request else None
        return generar_pdf_desde_plantilla(cierre_ot, template_path, firma_tec, firma_rec)
    else:
        return generar_pdf_reportlab(cierre_ot)

def generar_pdf_desde_plantilla(cierre_ot, template_path, firma_tec=None, firma_rec=None):
    """Genera PDF desde plantilla Word"""
    logger.info(f"Generando PDF desde plantilla: {template_path}")
    logger.info(f"Plantilla existe: {os.path.exists(template_path)}")

    doc = Document(template_path)
    logger.info("Documento Word cargado exitosamente")

    # Inicializar variables de firmas
    firma_tec_agregada = False
    firma_rec_agregada = False

    # Usar firma_tec si proporcionado, sino de cierre_ot
    firma_tec = firma_tec or cierre_ot.firma_digital
    firma_rec = firma_rec or cierre_ot.firma_receptor

    # Datos para reemplazar
    ot = cierre_ot.orden_trabajo
    solicitud = ot.solicitud

    imagenes_antes = cierre_ot.imagenes.filter(tipo='antes')
    imagenes_despues = cierre_ot.imagenes.filter(tipo='despues')

    actividades_info = obtener_actividades_cierre(cierre_ot)
    descripcion_base = cierre_ot.descripcion_falla or ''
    if actividades_info:
        actividades_text = '\n'.join(f"- {texto}" for texto in actividades_info)
        if descripcion_base:
            descripcion_y_actividades = f"{descripcion_base}\n\n{actividades_text}"
        else:
            descripcion_y_actividades = actividades_text
    else:
        descripcion_y_actividades = descripcion_base

    replacements = {
        '<<OT>>': str(solicitud.consecutivo),
        '<<equipo>>': cierre_ot.orden_trabajo.solicitud.equipo.nombre if cierre_ot.orden_trabajo.solicitud.equipo else '',
        '<<cliente>>': solicitud.PDV,
        '<<fecha>>': cierre_ot.fecha_inicio_actividad.strftime('%d/%m/%Y') if cierre_ot.fecha_inicio_actividad else '',
        '<<tipomtto>>': cierre_ot.tipo_mantenimiento or '',
        '<<tipointervencion>>': cierre_ot.tipo_intervencion or '',
        '<<causafalla>>': cierre_ot.causa_falla or '',
        '<<sesoluciono>>': 'Sí' if cierre_ot.se_soluciono else 'No',
        '<<descripcion>>': descripcion_y_actividades,
        '<<observacion>>': cierre_ot.observaciones or '',
        '<<recibido>>': cierre_ot.nombre_receptor or '',
        '<<nombret>>': cierre_ot.nombre_tecnico or '',
        '<<cc>>': cierre_ot.documento_receptor or '',
        '<<cct>>': cierre_ot.documento_tecnico or '',
        '<<actividades_plan>>': '\n'.join(actividades_info) if actividades_info else '',
    }

    logger.info(f"Tags a reemplazar: {list(replacements.keys())}")
    logger.info(f"Valores de ejemplo: OT={replacements['<<OT>>']}, equipo={replacements['<<equipo>>']}")

    replacements_count = 0
    firmas_en_plantilla = False

    def add_signature_image_to_paragraph(paragraph, image_base64):
        try:
            header, encoded = image_base64.split(",", 1)
        except ValueError:
            encoded = image_base64
        image_data = base64.b64decode(encoded)
        temp_firma_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_firma_path.write(image_data)
        temp_firma_path.close()
        run = paragraph.add_run()
        run.add_break()
        run.add_picture(temp_firma_path.name, width=Inches(2))
        paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        os.unlink(temp_firma_path.name)
        return True

    def replace_paragraph_text(paragraph):
        nonlocal replacements_count, firma_tec_agregada, firma_rec_agregada, firmas_en_plantilla
        original_text = paragraph.text
        if not any(key in original_text for key in replacements):
            return

        updated_text = original_text
        for key, value in replacements.items():
            if key in updated_text:
                updated_text = updated_text.replace(key, value)
                replacements_count += original_text.count(key)

        if updated_text != original_text:
            for run in paragraph.runs[::-1]:
                paragraph._p.remove(run._r)
            paragraph.add_run(updated_text)

        if '<<recibido>>' in original_text:
            firmas_en_plantilla = True
            if firma_rec:
                try:
                    if add_signature_image_to_paragraph(paragraph, firma_rec):
                        firma_rec_agregada = True
                except Exception:
                    pass

        if '<<nombret>>' in original_text:
            firmas_en_plantilla = True
            if firma_tec:
                try:
                    if add_signature_image_to_paragraph(paragraph, firma_tec):
                        firma_tec_agregada = True
                except Exception:
                    pass

    def process_cell(cell):
        for paragraph in cell.paragraphs:
            replace_paragraph_text(paragraph)
        for nested_table in cell.tables:
            for row in nested_table.rows:
                for nested_cell in row.cells:
                    process_cell(nested_cell)

    for paragraph in doc.paragraphs:
        replace_paragraph_text(paragraph)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                process_cell(cell)

    logger.info(f"Total de reemplazos realizados: {replacements_count}")

    if not firmas_en_plantilla:
        # Agregar firmas al final del documento solo si no hay campos en la plantilla
        table_firmas = doc.add_table(rows=1, cols=2)
        
        # Firma técnico
        cell_tec = table_firmas.cell(0, 0)
        cell_tec.text = 'Firma Técnico'
        cell_tec.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        if firma_tec:
            try:
                header, encoded = firma_tec.split(",", 1)
                image_data = base64.b64decode(encoded)
                temp_firma_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                temp_firma_path.write(image_data)
                temp_firma_path.close()
                p = cell_tec.add_paragraph()
                p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                run = p.add_run()
                run.add_picture(temp_firma_path.name, width=Inches(2))
                os.unlink(temp_firma_path.name)
                firma_tec_agregada = True
            except Exception:
                firma_tec_agregada = False
        
        # Firma receptor
        cell_rec = table_firmas.cell(0, 1)
        cell_rec.text = 'Firma Receptor'
        cell_rec.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        if firma_rec:
            try:
                header, encoded = firma_rec.split(",", 1)
                image_data = base64.b64decode(encoded)
                temp_firma_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                temp_firma_path.write(image_data)
                temp_firma_path.close()
                p = cell_rec.add_paragraph()
                p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                run = p.add_run()
                run.add_picture(temp_firma_path.name, width=Inches(2))
                os.unlink(temp_firma_path.name)
                firma_rec_agregada = True
            except Exception:
                firma_rec_agregada = False

    # Agregar imágenes al final del documento
    if imagenes_antes.exists():
        heading_antes = doc.add_heading('Antes', level=2)
        heading_antes.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        num_images = imagenes_antes.count()
        num_rows = (num_images + 1) // 2
        table = doc.add_table(rows=num_rows, cols=2)
        row_idx = 0
        col_idx = 0
        for img in imagenes_antes:
            cell = table.cell(row_idx, col_idx)
            image_path, is_temp = obtener_imagen_temporal_para_pdf(img.imagen)
            if image_path:
                run = cell.paragraphs[0].add_run()
                run.add_picture(image_path, width=Inches(2))
                cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                if is_temp:
                    os.unlink(image_path)
            col_idx += 1
            if col_idx == 2:
                col_idx = 0
                row_idx += 1
    
    if imagenes_despues.exists():
        heading_despues = doc.add_heading('Después', level=2)
        heading_despues.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        num_images = imagenes_despues.count()
        num_rows = (num_images + 1) // 2
        table = doc.add_table(rows=num_rows, cols=2)
        row_idx = 0
        col_idx = 0
        for img in imagenes_despues:
            cell = table.cell(row_idx, col_idx)
            image_path, is_temp = obtener_imagen_temporal_para_pdf(img.imagen)
            if image_path:
                run = cell.paragraphs[0].add_run()
                run.add_picture(image_path, width=Inches(2))
                cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                if is_temp:
                    os.unlink(image_path)
            col_idx += 1
            if col_idx == 2:
                col_idx = 0
                row_idx += 1
    
    # Guardar documento temporal
    temp_docx = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    temp_docx.close()
    doc.save(temp_docx.name)
    logger.info("DOCX temporal guardado en: %s", temp_docx.name)
    
    # Convertir a PDF
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_pdf.close()
    
    try:
        convertir_docx_a_pdf(temp_docx.name, temp_pdf.name)
        if os.path.exists(temp_pdf.name):
            pdf_size = os.path.getsize(temp_pdf.name)
            logger.info("PDF generado exitosamente, tamaño: %d bytes", pdf_size)
            if pdf_size == 0:
                logger.error("PDF generado pero está vacío - usando ReportLab")
                raise RuntimeError("PDF generado está vacío")
            if pdf_size > 20 * 1024 * 1024:  # 20MB límite
                logger.warning("PDF muy grande (%d bytes) - usando ReportLab", pdf_size)
                raise RuntimeError("PDF demasiado grande")
            with open(temp_pdf.name, 'rb') as f:
                buffer = BytesIO(f.read())
        else:
            logger.error("PDF no se generó, archivo no existe: %s", temp_pdf.name)
            raise RuntimeError("PDF no se generó")
    except Exception as e:
        logger.warning("Error al convertir DOCX a PDF: %s - usando ReportLab", e)
        os.unlink(temp_docx.name)
        if os.path.exists(temp_pdf.name):
            os.unlink(temp_pdf.name)
        buffer, _, _ = generar_pdf_reportlab(cierre_ot)
        return buffer, firma_tec_agregada, firma_rec_agregada
    
    # Limpiar archivos temporales
    os.unlink(temp_docx.name)
    os.unlink(temp_pdf.name)
    
    buffer.seek(0)
    return buffer, firma_tec_agregada, firma_rec_agregada

def generar_pdf_reportlab(cierre_ot):
    """Genera un PDF de informe similar al de Google Docs"""
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    temp_files = []  # Rastrear archivos para limpiar después
    
    # Título
    title = Paragraph("INFORME DE MANTENIMIENTO", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Datos del informe
    ot = cierre_ot.orden_trabajo
    solicitud = ot.solicitud
    
    data = {
        'OT': str(solicitud.consecutivo),
        'Equipo': getattr(solicitud.equipo, 'nombre', '') if hasattr(solicitud, 'equipo') else '',
        'Cliente': solicitud.PDV,
        'Fecha': cierre_ot.fecha_inicio_actividad.strftime('%d/%m/%Y') if cierre_ot.fecha_inicio_actividad else '',
        'Tipo de Mantenimiento': cierre_ot.tipo_mantenimiento or '',
        'Tipo de Intervención': cierre_ot.tipo_intervencion or '',
        'Causa de la Falla': cierre_ot.causa_falla or '',
        '¿Se solucionó la falla?': 'Sí' if cierre_ot.se_soluciono else 'No',
        'Descripción': cierre_ot.descripcion_falla or '',
        'Observaciones': cierre_ot.observaciones or '',
        'Recibido por': cierre_ot.nombre_tecnico or '',
        'Documento de Identidad': cierre_ot.documento_tecnico or '',
        'Nombre del Técnico': cierre_ot.nombre_tecnico or '',
    }
    
    # Agregar párrafos con los datos
    for key, value in data.items():
        p = Paragraph(f"<b>{key}:</b> {value}", styles['Normal'])
        story.append(p)
        story.append(Spacer(1, 6))

    actividades_info = obtener_actividades_cierre(cierre_ot)
    if actividades_info:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Actividades del Plan:</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        for texto in actividades_info:
            story.append(Paragraph(f"- {texto}", styles['Normal']))
            story.append(Spacer(1, 4))

    # Agregar firma si existe
    if cierre_ot.firma_digital:
        story.append(Spacer(1, 12))
        firma_title = Paragraph("<b>Firma Digital del Técnico:</b>", styles['Normal'])
        story.append(firma_title)
        story.append(Spacer(1, 6))
        
        # Convertir data URL a imagen
        try:
            header, encoded = cierre_ot.firma_digital.split(",", 1)
        except ValueError:
            encoded = cierre_ot.firma_digital
        image_data = base64.b64decode(encoded)
        img_buffer = BytesIO(image_data)
        img = PILImage.open(img_buffer)
        
        # Convertir a RGB si es necesario
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Guardar temporalmente
        temp_img_path = f"/tmp/firma_{cierre_ot.id}.png"
        img.save(temp_img_path)
        temp_files.append(temp_img_path)  # Rastrear para limpiar después
        
        # Agregar al PDF
        firma_img = Image(temp_img_path, width=200, height=100)
        story.append(firma_img)
    except Exception as e:
        logger.warning("Error agregando firma técnica: %s", e)
        pass  # Silently continue with PDF

    # Agregar firma del receptor si existe
    if cierre_ot.firma_receptor:
        story.append(Spacer(1, 12))
        firma_rec_title = Paragraph("<b>Firma Digital del Receptor:</b>", styles['Normal'])
        story.append(firma_rec_title)
        story.append(Spacer(1, 6))
        
        try:
            header, encoded = cierre_ot.firma_receptor.split(",", 1)
        except ValueError:
            encoded = cierre_ot.firma_receptor
        image_data = base64.b64decode(encoded)
        img_buffer = BytesIO(image_data)
        img = PILImage.open(img_buffer)
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        temp_img_path = f"/tmp/firma_rec_{cierre_ot.id}.png"
        img.save(temp_img_path)
        temp_files.append(temp_img_path)
        
        firma_rec_img = Image(temp_img_path, width=200, height=100)
        story.append(firma_rec_img)
    except Exception as e:
        logger.warning("Error agregando firma del receptor: %s", e)
        pass
            
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Guardar temporalmente
            temp_img_path = f"/tmp/firma_{cierre_ot.id}.png"
            img.save(temp_img_path)
            temp_files.append(temp_img_path)  # Rastrear para limpiar después
            
            # Agregar al PDF
            firma_img = Image(temp_img_path, width=200, height=100)
            story.append(firma_img)
        except Exception as e:
            pass  # Silently continue with PDF
    
    # Agregar imágenes antes si existen
    imagenes_antes = cierre_ot.imagenes.filter(tipo='antes')
    if imagenes_antes.exists():
        story.append(Spacer(1, 12))
        antes_title = Paragraph("<b>━━━ EVIDENCIA - ANTES ━━━</b>", styles['Normal'])
        story.append(antes_title)
        story.append(Spacer(1, 6))
        
        # Crear tabla de imágenes (2 por fila)
        data = []
        row = []
        for i, img in enumerate(imagenes_antes):
            try:
                img_path, is_temp = obtener_imagen_temporal_para_pdf(img.imagen)
                if not img_path:
                    continue
                if is_temp:
                    temp_files.append(img_path)  # Rastrear para limpiar después
                img_reportlab = Image(img_path, width=150, height=100)
                row.append(img_reportlab)
                if len(row) == 2 or i == len(imagenes_antes) - 1:
                    data.append(row)
                    row = []
            except Exception as e:
                pass  # Silently skip image
        
        if data:
            table = Table(data)
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))
    
    # Agregar imágenes después si existen
    imagenes_despues = cierre_ot.imagenes.filter(tipo='despues')
    if imagenes_despues.exists():
        story.append(Spacer(1, 12))
        despues_title = Paragraph("<b>━━━ EVIDENCIA - DESPUÉS ━━━</b>", styles['Normal'])
        story.append(despues_title)
        story.append(Spacer(1, 6))
        
        # Crear tabla de imágenes (2 por fila)
        data = []
        row = []
        for i, img in enumerate(imagenes_despues):
            try:
                img_path, is_temp = obtener_imagen_temporal_para_pdf(img.imagen)
                if not img_path:
                    continue
                if is_temp:
                    temp_files.append(img_path)  # Rastrear para limpiar después
                img_reportlab = Image(img_path, width=150, height=100)
                row.append(img_reportlab)
                if len(row) == 2 or i == len(imagenes_despues) - 1:
                    data.append(row)
                    row = []
            except Exception as e:
                pass  # Silently skip image
        
        if data:
            table = Table(data)
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))
    
    try:
        doc.build(story)
    finally:
        # Limpiar archivos temporales DESPUÉS de que se construya el PDF
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                pass  # Silently continue cleanup
    
    buffer.seek(0)
    return buffer, False, False



def enviar_pdf_por_email(pdf_buffer, cierre_ot):
    """Envía el PDF por email usando Gmail SMTP - retorna True si es exitoso, False si falla"""
    subject = f"Informe de Mantenimiento OT-{cierre_ot.orden_trabajo.solicitud.consecutivo}"
    message = "Adjunto se encuentra el informe de mantenimiento."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [cierre_ot.correo_tecnico] if cierre_ot.correo_tecnico else []
    
    # Agregar email adicional si existe
    if hasattr(settings, 'EMAIL_ADICIONAL') and settings.EMAIL_ADICIONAL:
        recipient_list.append(settings.EMAIL_ADICIONAL)
    
    if not recipient_list:
        logger.warning("No hay destinatarios para enviar el email")
        return False
    
    try:
        # Usar API de SendGrid directamente para evitar bloqueo SMTP de Railway
        if hasattr(settings, 'SENDGRID_API_KEY') and settings.SENDGRID_API_KEY:
            import base64
            import io

            # Crear payload para SendGrid API
            pdf_content = pdf_buffer.getvalue()
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

            # Verificar tamaño del PDF (SendGrid tiene límite de ~30MB por email)
            pdf_size_mb = len(pdf_content) / (1024 * 1024)
            if pdf_size_mb > 25:
                logger.warning("PDF muy grande (%.2f MB) - podría fallar en SendGrid", pdf_size_mb)

            payload = {
                "personalizations": [{
                    "to": [{"email": email} for email in recipient_list],
                    "subject": subject
                }],
                "from": {"email": from_email},
                "content": [{"type": "text/plain", "value": message}],
                "attachments": [{
                    "content": pdf_base64,
                    "type": "application/pdf",
                    "filename": "informe_mantenimiento.pdf",
                    "disposition": "attachment"
                }]
            }

            headers = {
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json"
            }

            logger.info("Enviando email via SendGrid API from=%s to=%s, PDF=%.2f MB", from_email, recipient_list, pdf_size_mb)
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code in (200, 202):
                logger.info("Email enviado exitosamente via SendGrid API")
                logger.info("SendGrid response headers: %s", response.headers)
                return True
            else:
                logger.error("SendGrid API error %s: %s", response.status_code, response.text)
                return False

        # Fallback a SMTP local (desarrollo)
        else:
            email = EmailMessage(subject, message, from_email, recipient_list)
            email.attach('informe_mantenimiento.pdf', pdf_buffer.getvalue(), 'application/pdf')
            email.send(fail_silently=False)
            logger.info("Email enviado exitosamente via SMTP local")
            return True

    except Exception as e:
        logger.error("Error enviando email: %s", e)
        logger.error("Tipo de error: %s", type(e).__name__)
        import traceback
        logger.error("Traceback completo: %s", traceback.format_exc())
        return False
