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
from django.core.mail import EmailMessage
from django.conf import settings
from io import BytesIO
import tempfile
from django.forms import modelformset_factory
import os
import base64
from PIL import Image as PILImage

try:
    import pythoncom
except ImportError:
    pythoncom = None

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
    print(f"Vista cierre_ot llamada para ot_id: {ot_id}, método: {request.method}")
    ot = get_object_or_404(OrdenTrabajo, id=ot_id)
    cierre_ot, created = CierreOt.objects.get_or_create(orden_trabajo=ot)
    form_antes = ImagenAntesForm()
    form_despues = ImagenDespuesForm()

    if request.method == 'POST':
        print(f"POST data keys: {list(request.POST.keys())}")
        print(f"FILES keys: {list(request.FILES.keys())}")

        form = CierreOtForm(request.POST, request.FILES, instance=cierre_ot)
        actividad_formset = CierreOtActividadFormSet(request.POST, instance=cierre_ot)
        form_antes = ImagenAntesForm(request.POST, request.FILES)
        form_despues = ImagenDespuesForm(request.POST, request.FILES)

        is_valid_form = form.is_valid()
        is_valid_formset = actividad_formset.is_valid()
        print(f"Form is_valid: {is_valid_form}")
        print(f"Actividad formset is_valid: {is_valid_formset}")
        if not is_valid_form or not is_valid_formset:
            if not is_valid_form:
                print(f"Form errors: {form.errors}")
            if not is_valid_formset:
                print(f"Formset errors: {actividad_formset.errors}")
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

        print(f"Firma técnico recibida: {firma_tecnico[:100] if firma_tecnico else 'None'}")
        print(f"Firma receptor recibida: {firma_receptor[:100] if firma_receptor else 'None'}")

        cierre_ot.firma_digital = firma_tecnico
        cierre_ot.firma_receptor = firma_receptor

        # Guardar el formulario y las actividades del cierre
        cierre_ot = form.save()
        actividad_formset.instance = cierre_ot
        actividad_formset.save()
        print(f"Cierre OT guardado con ID: {cierre_ot.id}")

        # Guardar imágenes antes
        imagenes_antes_count = 0
        for file in request.FILES.getlist('imagenes_antes'):
            if file:
                ImagenCierreOt.objects.create(cierre_ot=cierre_ot, imagen=file, tipo='antes')
                imagenes_antes_count += 1
        print(f"Imágenes antes guardadas: {imagenes_antes_count}")

        # Guardar imágenes después
        imagenes_despues_count = 0
        for file in request.FILES.getlist('imagenes_despues'):
            if file:
                ImagenCierreOt.objects.create(cierre_ot=cierre_ot, imagen=file, tipo='despues')
                imagenes_despues_count += 1
        print(f"Imágenes después guardadas: {imagenes_despues_count}")

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
            print("Estados actualizados correctamente")
        except Exception as e:
            print(f"Error actualizando estados: {e}")
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
            print(f"PDF generado correctamente, tamaño: {len(pdf_buffer.getvalue())} bytes")

            print(f"Correo técnico: {cierre_ot.correo_tecnico}")
            enviar_pdf_por_email(pdf_buffer, cierre_ot)
            print("Email enviado correctamente")

            success_msg = f"OT cerrada exitosamente. PDF generado. Email enviado. Firma tec agregada: {firma_tec_agregada}, Firma rec agregada: {firma_rec_agregada}"
            messages.success(request, success_msg)
            return redirect('listar_ot')
        except Exception as e:
            print(f"Error generando PDF o enviando email: {e}")
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
    doc = Document(template_path)
    
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
    
    # Reemplazar en párrafos manteniendo formato
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            for key, value in replacements.items():
                if key in run.text:
                    run.text = run.text.replace(key, value)
    
    # Reemplazar en tablas manteniendo formato
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        for key, value in replacements.items():
                            if key in run.text:
                                run.text = run.text.replace(key, value)
    
    # Agregar firmas al final del documento (siempre, sin depender de tags)
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
        except Exception as e:
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
        except Exception as e:
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
            run = cell.paragraphs[0].add_run()
            run.add_picture(img.imagen.path, width=Inches(2))
            cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
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
            run = cell.paragraphs[0].add_run()
            run.add_picture(img.imagen.path, width=Inches(2))
            cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            col_idx += 1
            if col_idx == 2:
                col_idx = 0
                row_idx += 1
    
    # Guardar documento temporal
    temp_docx = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    temp_docx.close()
    doc.save(temp_docx.name)
    
    # Convertir a PDF
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_pdf.close()
    if pythoncom is not None and os.name == 'nt':
        pythoncom.CoInitialize()
        convert(temp_docx.name, temp_pdf.name)
        pythoncom.CoUninitialize()
        with open(temp_pdf.name, 'rb') as f:
            buffer = BytesIO(f.read())
        os.unlink(temp_docx.name)
        os.unlink(temp_pdf.name)
    else:
        # En entornos no Windows, fallback a ReportLab para generar PDF
        os.unlink(temp_docx.name)
        os.unlink(temp_pdf.name)
        return generar_pdf_reportlab(cierre_ot), firma_tec_agregada, firma_rec_agregada
    
    buffer.seek(0)
    return buffer, firma_tec_agregada, firma_rec_agregada

def generar_pdf_reportlab(cierre_ot):
    """Genera un PDF de informe similar al de Google Docs"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
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
        'Documento de Identidad': cierre_ot.documento_tecnico.name if cierre_ot.documento_tecnico else '',
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
            image_data = base64.b64decode(encoded)
            img_buffer = BytesIO(image_data)
            img = PILImage.open(img_buffer)
            
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Guardar temporalmente
            temp_img_path = f"/tmp/firma_{cierre_ot.id}.png"
            img.save(temp_img_path)
            
            # Agregar al PDF
            firma_img = Image(temp_img_path, width=200, height=100)
            story.append(firma_img)
            
            # Limpiar archivo temporal
            os.remove(temp_img_path)
        except Exception as e:
            print(f"Error procesando firma: {e}")
    
    # Agregar imágenes antes si existen
    imagenes_antes = cierre_ot.imagenes.filter(tipo='antes')
    if imagenes_antes.exists():
        story.append(Spacer(1, 12))
        antes_title = Paragraph("<b>━━━ EVIDENCIA - ANTES ━━━</b>", styles['Normal'])
        story.append(antes_title)
        story.append(Spacer(1, 6))
        
        # Crear tabla de imágenes (2 por fila)
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        
        data = []
        row = []
        for i, img in enumerate(imagenes_antes):
            try:
                img_path = img.imagen.path
                img_reportlab = Image(img_path, width=150, height=100)
                row.append(img_reportlab)
                if len(row) == 2 or i == len(imagenes_antes) - 1:
                    data.append(row)
                    row = []
            except Exception as e:
                print(f"Error cargando imagen antes: {e}")
        
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
                img_path = img.imagen.path
                img_reportlab = Image(img_path, width=150, height=100)
                row.append(img_reportlab)
                if len(row) == 2 or i == len(imagenes_despues) - 1:
                    data.append(row)
                    row = []
            except Exception as e:
                print(f"Error cargando imagen después: {e}")
        
        if data:
            table = Table(data)
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))
    
    doc.build(story)
    buffer.seek(0)
    return buffer, False, False


def enviar_pdf_por_email(pdf_buffer, cierre_ot):
    """Envía el PDF por email"""
    subject = f"Informe de Mantenimiento OT-{cierre_ot.orden_trabajo.solicitud.consecutivo}"
    message = "Adjunto se encuentra el informe de mantenimiento."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [cierre_ot.correo_tecnico] if cierre_ot.correo_tecnico else []
    
    # Agregar email adicional si existe
    if hasattr(settings, 'EMAIL_ADICIONAL') and settings.EMAIL_ADICIONAL:
        recipient_list.append(settings.EMAIL_ADICIONAL)
    
    print(f"Intentando enviar email a: {recipient_list}")
    print(f"Asunto: {subject}")
    print(f"Desde: {from_email}")
    print(f"Tamaño del PDF: {len(pdf_buffer.getvalue())} bytes")
    
    if recipient_list:
        try:
            email = EmailMessage(
                subject,
                message,
                from_email,
                recipient_list,
            )
            email.attach('informe_mantenimiento.pdf', pdf_buffer.getvalue(), 'application/pdf')
            email.send()
            print("Email enviado exitosamente via EmailMessage")
        except Exception as e:
            print(f"Error enviando email con EmailMessage: {e}")
            raise
    else:
        print("No hay destinatarios para enviar el email")
