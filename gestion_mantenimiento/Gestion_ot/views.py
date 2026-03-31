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
from .models import  OrdenTrabajo, Estado, CierreOt, ImagenCierreOt
from .forms import GestionOtForm, OrdenTrabajoForm, CierreOtForm, ImagenCierreOtForm
from solicitudes.models import Solicitud
import logging
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from django.core.mail import send_mail
from django.conf import settings
from io import BytesIO
import os
from PIL import Image as PILImage
import base64
from django.forms import modelformset_factory

class CustomDjangoJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, models.FileField):
            return obj.url if obj else None
        return super().default(obj)


# Configurar el logger
logger = logging.getLogger(__name__)
@login_required
# Vista para gestionar órdenes de trabajo
def gestion_ot(request):
    ordenes_trabajo = OrdenTrabajo.objects.all()
    solicitudes_pendientes = Solicitud.objects.filter(gestionot__isnull=True)
    tecnicos = User.objects.filter(groups__name='Tecnico')  # Filtra los usuarios que pertenecen al grupo 'Tecnico'

    # Filtros
    filtro_fecha_inicio = request.GET.get('fecha_inicio')
    filtro_fecha_fin = request.GET.get('fecha_fin')
    filtro_pdv = request.GET.get('pdv')

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
    if filtro_pdv:
        solicitudes_pendientes = solicitudes_pendientes.filter(PDV=filtro_pdv)

    form = GestionOtForm()
    return render(request, 'Gestion_ot/gestion_ot.html', {
        'form': form,
        'ordenes_trabajo': ordenes_trabajo,
        'solicitudes': solicitudes_pendientes,
        'pdvs': pdvs,
        'filtro_fecha_inicio': filtro_fecha_inicio,
        'filtro_fecha_fin': filtro_fecha_fin,
        'filtro_pdv': filtro_pdv,
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

        if not fecha:
            logger.error("Fecha de actividad es requerida.")
            return JsonResponse({'status': 'error', 'message': 'Fecha de actividad es requerida.'}, status=400)

        solicitud = Solicitud.objects.get(consecutivo=numero_solicitud)
        logger.debug(f"Solicitud encontrada: {solicitud}")

        nuevo_estado = Estado.objects.get(nombre=nuevo_estado_nombre)
        solicitud.estado = nuevo_estado
        if tecnico:
            solicitud.tecnico_asignado = tecnico
        # Asegurarse de que fecha sea aware datetime
        fecha = isoparse(fecha)
        if timezone.is_naive(fecha):
            fecha = timezone.make_aware(fecha, timezone.get_current_timezone())
        solicitud.fecha_actividad = fecha
        solicitud.save()
        logger.debug(f"Solicitud actualizada: {solicitud}")

        # Crear o actualizar la Orden de Trabajo
        orden_trabajo, created = OrdenTrabajo.objects.update_or_create(
            solicitud=solicitud,
            defaults={
                'tecnico_asignado': tecnico,
                'fecha_actividad': fecha,
                'estado': nuevo_estado
            }
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

# Vista para listar todas las órdenes de trabajo
@login_required
def listar_ot(request):
    if request.user.groups.filter(name='Admin').exists():
        ots = OrdenTrabajo.objects.all()
    else:
        ots = OrdenTrabajo.objects.filter(tecnico_asignado=request.user.username)
    
    return render(request, 'Gestion_ot/listar_ot.html', {
        'ots': ots,
    })

# Vista para cerrar una OT
@login_required
def cierre_ot(request, ot_id):
    ot = get_object_or_404(OrdenTrabajo, id=ot_id)
    cierre_ot, created = CierreOt.objects.get_or_create(orden_trabajo=ot)
    ImagenFormSet = modelformset_factory(ImagenCierreOt, form=ImagenCierreOtForm, extra=4, can_delete=True)
    
    if request.method == 'POST':
        form = CierreOtForm(request.POST, request.FILES, instance=cierre_ot)
        formset = ImagenFormSet(request.POST, request.FILES, queryset=ImagenCierreOt.objects.filter(cierre_ot=cierre_ot))
        print(f"Form valid: {form.is_valid()}")
        print(f"Form errors: {form.errors}")
        print(f"Formset valid: {formset.is_valid()}")
        print(f"Formset errors: {formset.errors}")
        if form.is_valid() and formset.is_valid():
            cierre_ot = form.save()
            # Guardar imágenes nuevas
            for imagen_form in formset:
                if imagen_form.cleaned_data and not imagen_form.cleaned_data.get('DELETE', False):
                    imagen = imagen_form.save(commit=False)
                    imagen.cierre_ot = cierre_ot
                    imagen.save()
            # Eliminar imágenes marcadas para borrar
            for imagen_form in formset.deleted_forms:
                if imagen_form.instance.pk:
                    imagen_form.instance.delete()
            # Cambiar estados
            estado_revision = Estado.objects.get(nombre="en revision")
            ot.estado = estado_revision
            ot.save()
            cierre_ot.estado = estado_revision
            cierre_ot.save()
            solicitud = ot.solicitud
            solicitud.estado = estado_revision
            solicitud.save()
            # Generar y enviar PDF
            try:
                pdf_buffer = generar_pdf_informe(cierre_ot)
                enviar_pdf_por_email(pdf_buffer, cierre_ot)
            except Exception as e:
                print(f"Error generando/enviando PDF: {e}")
            return redirect('listar_ot')
    else:
        form = CierreOtForm(instance=cierre_ot)
        formset = ImagenFormSet(queryset=ImagenCierreOt.objects.filter(cierre_ot=cierre_ot))
    return render(request, 'Gestion_ot/cierre_ot.html', {'form': form, 'formset': formset, 'ot': ot})


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
                'documento_tecnico': cierre_ot.documento_tecnico.url if cierre_ot.documento_tecnico else None,
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


def generar_pdf_informe(cierre_ot):
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
    return buffer


def enviar_pdf_por_email(pdf_buffer, cierre_ot):
    """Envía el PDF por email"""
    subject = f"Informe de Mantenimiento OT-{cierre_ot.orden_trabajo.solicitud.consecutivo}"
    message = "Adjunto se encuentra el informe de mantenimiento."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [cierre_ot.correo_tecnico] if cierre_ot.correo_tecnico else []
    
    # Agregar email adicional si existe
    if hasattr(settings, 'EMAIL_ADICIONAL') and settings.EMAIL_ADICIONAL:
        recipient_list.append(settings.EMAIL_ADICIONAL)
    
    if recipient_list:
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            attachments=[('informe_mantenimiento.pdf', pdf_buffer.getvalue(), 'application/pdf')]
        )
