from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.db import models, transaction, IntegrityError
from django.utils import timezone
from datetime import timedelta
import datetime
from dateutil.parser import isoparse
import re
import requests
from urllib.parse import urljoin, quote, urlparse
import os
from django.contrib import messages
import os
import smtplib
from .models import OrdenTrabajo, Estado, GestionOt, CierreOt, ImagenCierreOt, PlanMantenimiento, ActividadMantenimiento, TareaMantenimiento, CierreOtActividad, InformeDriveArchivo, ProcesoInforme
from .forms import GestionOtForm, OrdenTrabajoForm, CierreOtForm, ImagenCierreOtForm, ImagenAntesForm, ImagenDespuesForm, CierreOtActividadFormSet
from gestion_mantenimiento.solicitudes.models import Solicitud
import logging
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder
from docx import Document
try:
    from docx2pdf import convert
except ImportError:
    convert = None
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
import uuid
from PIL import Image as PILImage
import threading
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .drive_utils import subir_pdf_a_drive, subir_pdf_privado_a_drive, descargar_archivo_privado_drive, iterar_archivo_privado_drive

try:
    import pythoncom
except ImportError:
    pythoncom = None


def convertir_docx_a_pdf(docx_path, pdf_path):
    """Convierte un archivo DOCX a PDF.
    Usa docx2pdf en Windows o LibreOffice/soffice en Linux.
    """
    logger.info(f"=== INICIANDO CONVERSIÓN DOCX A PDF ===")
    logger.info(f"DOCX origen: {docx_path}, existe: {os.path.exists(docx_path)}")
    if os.path.exists(docx_path):
        docx_size = os.path.getsize(docx_path)
        logger.info(f"Tamaño DOCX: {docx_size} bytes")
    logger.info(f"PDF destino: {pdf_path}")
    
    if os.name == 'nt':
        if pythoncom is None:
            raise RuntimeError('pythoncom no disponible en Windows')
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
        finally:
            pythoncom.CoUninitialize()
        logger.info("Conversión Windows completada")
        return

    # En Linux/Unix no usamos docx2pdf porque requiere Microsoft Word.
    # Intentamos directamente usar LibreOffice/soffice.
    libreoffice = shutil.which('soffice') or shutil.which('libreoffice')
    if not libreoffice:
        raise RuntimeError('No se encontró LibreOffice/soffice para convertir DOCX a PDF')

    logger.info(f"Ejecutable LibreOffice encontrado en: {libreoffice}")
    output_dir = os.path.dirname(pdf_path)
    logger.info(f"Directorio de salida: {output_dir}")
    
    # Intentar con diferentes flags para evitar problemas con Java en headless mode
    comandos = [
        # Primera opción: con flags para evitar issues de Java
        [libreoffice, '--headless', '--norestore', '--nofirststartwizard', '--convert-to', 'pdf', '--outdir', output_dir, docx_path],
        # Segunda opción: con invisible en lugar de headless
        [libreoffice, '--invisible', '--norestore', '--convert-to', 'pdf', '--outdir', output_dir, docx_path],
        # Tercera opción: minimal (si soffice)
        [libreoffice, '--headless', '--convert-to', 'pdf', '--outdir', output_dir, docx_path],
    ]
    
    resultado_exitoso = False
    ultimo_error = None
    
    for i, cmd in enumerate(comandos, 1):
        try:
            logger.info(f'Intento {i} de {len(comandos)}: {" ".join(cmd)}')
            result = subprocess.run(cmd, check=True, timeout=120, capture_output=True, text=True)
            logger.info(f'Intento {i} exitoso - LibreOffice stdout: %s', result.stdout)
            if result.stderr and 'failed to launch javaldx' not in result.stderr:
                logger.info(f'Intento {i} - LibreOffice stderr (no crítico): %s', result.stderr)
            resultado_exitoso = True
            break
        except subprocess.CalledProcessError as e:
            ultimo_error = f"Código {e.returncode}: {e.stderr}"
            logger.warning(f'Intento {i} falló - {ultimo_error}')
            continue
        except subprocess.TimeoutExpired:
            ultimo_error = "Timeout de 120 segundos"
            logger.warning(f'Intento {i} falló - {ultimo_error}')
            continue
    
    if not resultado_exitoso:
        logger.error(f"Todos los intentos de conversión con LibreOffice fallaron. Último error: {ultimo_error}")
        raise RuntimeError(f'LibreOffice no pudo convertir el documento: {ultimo_error}')

    # Verificar dónde se generó el PDF
    alt_pdf = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
    logger.info(f"Verificando ubicaciones esperadas:")
    logger.info(f"  PDF primario ({pdf_path}): existe={os.path.exists(pdf_path)}")
    if os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        logger.info(f"  Tamaño PDF primario: {size} bytes")
        if size == 0:
            logger.error("PDF existe pero está VACÍO (0 bytes)")
        
    logger.info(f"  PDF alternativo ({alt_pdf}): existe={os.path.exists(alt_pdf)}")
    if os.path.exists(alt_pdf):
        size = os.path.getsize(alt_pdf)
        logger.info(f"  Tamaño PDF alternativo: {size} bytes")
        if size == 0:
            logger.error("PDF alternativo existe pero está VACÍO (0 bytes)")
        
    if os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        if size > 0:
            logger.info(f"✓ PDF generado exitosamente ({size} bytes)")
            return
        else:
            logger.error("✗ PDF existe pero está vacío - buscando archivos generados en el directorio...")
            # Listar archivos generados para debugging
            try:
                files = os.listdir(output_dir)
                logger.info(f"Archivos en {output_dir}: {files}")
                for f in files:
                    if f.endswith('.pdf'):
                        full_path = os.path.join(output_dir, f)
                        size = os.path.getsize(full_path)
                        logger.info(f"  Archivo PDF encontrado: {f} ({size} bytes)")
            except Exception as e:
                logger.warning(f"No se pudo listar archivos: {e}")
                
    if os.path.exists(alt_pdf):
        size = os.path.getsize(alt_pdf)
        if size > 0:
            logger.info(f"Moviendo PDF de {alt_pdf} a {pdf_path}")
            os.replace(alt_pdf, pdf_path)
            logger.info(f"✓ PDF movido exitosamente ({size} bytes)")
            return
        else:
            logger.error("PDF alternativo existe pero está vacío")

    logger.error("✗ LibreOffice no produjo el PDF esperado")
    raise RuntimeError('LibreOffice no produjo el PDF esperado')


def obtener_imagen_temporal_para_pdf(file_field):
    """Devuelve una ruta local temporal para usar en PDF.
    Intenta primero descargar desde URL remota (Cloudinary).
    Como fallback, usa path local si existe.
    """
    if not file_field or isinstance(file_field, str):
        return None, False

    try:
        file_name = getattr(file_field, 'name', None)

        if hasattr(file_field, 'url'):
            url = file_field.url
            if url and isinstance(url, str) and re.match(r'^https?://', url):
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    suffix = os.path.splitext(file_name or 'image')[1] or '.jpg'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                        temp_file.write(response.content)
                        return temp_file.name, True
                except Exception as e:
                    logger.warning('No se pudo descargar imagen remota para PDF: %s', e)

        if hasattr(file_field, 'path'):
            try:
                local_path = file_field.path
                if local_path and os.path.exists(local_path):
                    return local_path, False
            except (AttributeError, ValueError, NotImplementedError) as e:
                logger.warning('No se pudo obtener path local de file_field: %s', e)

    except Exception as e:
        logger.warning('Error al obtener imagen temporal para PDF: %s', e)

    return None, False


def _imagen_duplicada(cierre_ot, file_obj, tipo):
    try:
        name = getattr(file_obj, 'name', None)
        size = getattr(file_obj, 'size', None)
        if not name or size is None:
            return False

        for imagen in cierre_ot.imagenes.filter(tipo=tipo):
            existing_name = getattr(imagen.imagen, 'name', '')
            existing_size = None
            try:
                existing_size = imagen.imagen.size
            except Exception:
                existing_size = None
            if existing_name and existing_name.endswith(name) and existing_size == size:
                return True
    except Exception:
        pass
    return False


def _validar_firma_base64(value):
    if not value or not isinstance(value, str):
        return False
    raw_value = value.strip()
    if not raw_value:
        return False
    if raw_value.startswith('data:image'):
        if ',' not in raw_value:
            return False
        _, encoded = raw_value.split(',', 1)
    else:
        encoded = raw_value
    if len(encoded) < 100:
        return False
    try:
        base64.b64decode(encoded, validate=True)
        return True
    except Exception:
        return False


def _validar_firmas(cierre_ot):
    firmas_requeridas = ['firma_digital', 'firma_receptor']
    faltantes = []
    for firma_field in firmas_requeridas:
        valor = getattr(cierre_ot, firma_field, None)
        if not _validar_firma_base64(valor):
            faltantes.append(firma_field)
    if faltantes:
        mensaje = f"Firmas inválidas o incompletas: {', '.join(faltantes)}"
        return False, mensaje
    return True, 'Firmas validadas'


def _validar_imagenes(cierre_ot):
    imagenes = list(cierre_ot.imagenes.all())
    expected_images = len(imagenes)
    confirmed_images = 0
    errores = []
    temp_files = []

    try:
        for imagen in imagenes:
            path, is_temp = obtener_imagen_temporal_para_pdf(imagen.imagen)
            if not path:
                errores.append(f"Imagen no disponible: id={imagen.id} tipo={imagen.tipo}")
                continue
            try:
                with open(path, 'rb') as f:
                    data = f.read(16)
                    if not data:
                        raise ValueError('Archivo vacío')
                confirmed_images += 1
            except Exception as e:
                errores.append(f"No se puede leer imagen id={imagen.id}: {e}")
            finally:
                if is_temp:
                    temp_files.append(path)
    finally:
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass

    valido = expected_images == confirmed_images
    if not valido:
        mensaje = f"Imágenes inválidas o incompletas ({confirmed_images}/{expected_images})"
        if errores:
            mensaje = mensaje + ". " + "; ".join(errores[:3])
        return False, expected_images, confirmed_images, mensaje
    return True, expected_images, confirmed_images, 'Imágenes validadas'


def _validar_pdf(pdf_buffer):
    if not pdf_buffer:
        return False
    try:
        pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else bytes(pdf_buffer)
    except Exception:
        return False
    if not pdf_bytes or len(pdf_bytes) < 1024:
        return False
    if not pdf_bytes.startswith(b'%PDF'):
        return False
    if b'%EOF' not in pdf_bytes[-1024:]:
        return False
    return True


def _normalize_pdf_result(result):
    if isinstance(result, tuple) and len(result) >= 1:
        return result[0]
    return result


def _get_active_proceso_para_cierre(cierre_ot):
    return ProcesoInforme.objects.filter(cierre_ot=cierre_ot, estado__in=list(ProcesoInforme.ACTIVE_STATES)).order_by('-updated_at').first()


def _get_latest_proceso_para_cierre(cierre_ot):
    return ProcesoInforme.objects.filter(cierre_ot=cierre_ot).order_by('-updated_at').first()


def _crear_o_actualizar_proceso(cierre_ot, operation_id, expected_images=0, required_signatures=None):
    if required_signatures is None:
        required_signatures = ['firma_digital', 'firma_receptor']

    proceso = ProcesoInforme.objects.filter(operation_id=operation_id).first()
    if proceso and proceso.cierre_ot_id != cierre_ot.id:
        raise ValueError('operation_id inválido para esta OT')

    if proceso is None:
        try:
            proceso = ProcesoInforme.objects.create(
                operation_id=operation_id,
                cierre_ot=cierre_ot,
                estado=ProcesoInforme.GUARDANDO,
                mensaje='Guardando datos',
                expected_images=expected_images,
                confirmed_images=0,
                required_signatures=required_signatures,
            )
            created = True
        except IntegrityError:
            proceso = _get_active_proceso_para_cierre(cierre_ot)
            if not proceso:
                raise
            created = False
    else:
        created = False
        if proceso.estado == ProcesoInforme.PENDIENTE:
            proceso.set_state(ProcesoInforme.GUARDANDO, 'Guardando datos')
        elif proceso.estado == ProcesoInforme.ERROR and not proceso.email_enviado:
            proceso.set_state(ProcesoInforme.GUARDANDO, 'Reintentando proceso')

    if proceso.expected_images == 0 and expected_images > 0:
        proceso.expected_images = expected_images
        proceso.save(update_fields=['expected_images'])

    return proceso, created


def _guardar_imagenes_del_post(cierre_ot, request, proceso):
    total_guardadas = 0
    for tipo in ['antes', 'despues']:
        field_name = 'imagenes_antes' if tipo == 'antes' else 'imagenes_despues'
        for file in request.FILES.getlist(field_name):
            if not file:
                continue
            if _imagen_duplicada(cierre_ot, file, tipo):
                logger.info('[INFORME] operation=%s imagen duplicada ignorada: %s %s', proceso.operation_id, tipo, getattr(file, 'name', ''))
                continue
            ImagenCierreOt.objects.create(cierre_ot=cierre_ot, imagen=file, tipo=tipo)
            total_guardadas += 1

    total_imagenes = cierre_ot.imagenes.count()
    proceso.expected_images = total_imagenes
    proceso.confirmed_images = total_imagenes
    proceso.save(update_fields=['expected_images', 'confirmed_images'])
    return total_imagenes


def _procesar_proceso_informe(operation_id):
    try:
        proceso = ProcesoInforme.objects.select_related('cierre_ot__orden_trabajo__solicitud').get(operation_id=operation_id)
    except ProcesoInforme.DoesNotExist:
        logger.error('[INFORME] operation=%s no encontrado en background', operation_id)
        return

    if proceso.email_enviado:
        logger.info('[INFORME] operation=%s ya enviado, no se procesará de nuevo', operation_id)
        return

    cierre_ot = proceso.cierre_ot

    try:
        with transaction.atomic():
            proceso = ProcesoInforme.objects.select_for_update().get(operation_id=operation_id)
            if proceso.estado == ProcesoInforme.ENVIADO:
                logger.info('[INFORME] operation=%s ya en estado ENVIADO', operation_id)
                return
            if proceso.estado == ProcesoInforme.PDF_LISTO:
                proceso.set_state(ProcesoInforme.ENVIANDO, 'Reintentando envío')
                enviar_email = True
            elif proceso.estado == ProcesoInforme.ENVIANDO:
                proceso.set_state(ProcesoInforme.ENVIANDO, 'Continuando envío')
                enviar_email = True
            else:
                proceso.set_state(ProcesoInforme.VALIDANDO_ARCHIVOS, 'Validando archivos')
                validar_firmas_ok, mensaje_firmas = _validar_firmas(cierre_ot)
                if not validar_firmas_ok:
                    proceso.set_state(ProcesoInforme.ERROR, mensaje_firmas, last_error=mensaje_firmas)
                    return

                valid_imgs, expected_images, confirmed_images, mensaje_imgs = _validar_imagenes(cierre_ot)
                proceso.expected_images = expected_images
                proceso.confirmed_images = confirmed_images
                proceso.save(update_fields=['expected_images', 'confirmed_images'])
                if not valid_imgs:
                    proceso.set_state(ProcesoInforme.ERROR, mensaje_imgs, last_error=mensaje_imgs)
                    return

                proceso.set_state(ProcesoInforme.GENERANDO_PDF, 'Generando PDF')
                enviar_email = True

        pdf_buffer = None
        if proceso.estado in [ProcesoInforme.GENERANDO_PDF, ProcesoInforme.PDF_LISTO, ProcesoInforme.ENVIANDO]:
            result = generar_pdf_informe(cierre_ot)
            pdf_buffer = _normalize_pdf_result(result)
            if not _validar_pdf(pdf_buffer):
                proceso.set_state(ProcesoInforme.ERROR, 'PDF inválido después de generar', last_error='La salida no parece un PDF válido.')
                return
            proceso.pdf_size_bytes = len(pdf_buffer.getvalue())
            proceso.set_state(ProcesoInforme.PDF_LISTO, 'PDF listo')

        if enviar_email:
            proceso.refresh_from_db()
            if proceso.email_enviado or proceso.estado == ProcesoInforme.ENVIADO:
                logger.info('[INFORME] operation=%s ya fue enviado antes de intentar enviar otro correo', operation_id)
                return
            proceso.set_state(ProcesoInforme.ENVIANDO, 'Enviando correo')
            try:
                enviado = enviar_pdf_por_email(pdf_buffer, cierre_ot)
            except Exception as exc:
                proceso.set_state(ProcesoInforme.PDF_LISTO, f'Error enviando email: {exc}', last_error=str(exc))
                logger.error('[INFORME] operation=%s fallo envío: %s', operation_id, exc)
                return

            if enviado:
                proceso.set_state(ProcesoInforme.ENVIADO, 'Enviado')
                logger.info('[INFORME] operation=%s estado=ENVIADO', operation_id)
                # Marcar OT/CierreOt/Solicitud como 'en revision' de forma atómica
                try:
                    estado_en_revision, _ = Estado.objects.get_or_create(nombre='en revision')
                    with transaction.atomic():
                        proc = ProcesoInforme.objects.select_related('cierre_ot__orden_trabajo__solicitud').select_for_update().get(operation_id=operation_id)
                        cierre = proc.cierre_ot
                        ot_obj = cierre.orden_trabajo
                        solicitud_obj = ot_obj.solicitud

                        # Sólo actualizar si aún no están en 'en revision'
                        if not ot_obj.estado or ot_obj.estado.nombre != 'en revision':
                            ot_obj.estado = estado_en_revision
                            ot_obj.save(update_fields=['estado'])
                        if not cierre.estado or cierre.estado.nombre != 'en revision':
                            cierre.estado = estado_en_revision
                            cierre.save(update_fields=['estado'])
                        if not solicitud_obj.estado or solicitud_obj.estado.nombre != 'en revision':
                            solicitud_obj.estado = estado_en_revision
                            solicitud_obj.save(update_fields=['estado'])
                except Exception as exc:
                    # No marcar el proceso como ERROR porque el email ya fue enviado.
                    # Registrar el fallo para reintento manual/alerta.
                    logger.exception('[INFORME] operation=%s fallo al actualizar estados OT tras ENVIADO: %s', operation_id, exc)
            else:
                proceso.set_state(ProcesoInforme.PDF_LISTO, 'Error enviando email', last_error='La función enviar_pdf_por_email devolvió False')
                logger.warning('[INFORME] operation=%s email no enviado', operation_id)
    except Exception as exc:
        logger.error('[INFORME] operation=%s fallo inesperado: %s', operation_id, exc, exc_info=True)
        try:
            proceso = ProcesoInforme.objects.filter(operation_id=operation_id).first()
            if proceso:
                proceso.set_state(ProcesoInforme.ERROR, 'Fallo inesperado durante el procesamiento', last_error=str(exc))
        except Exception:
            pass


@login_required
def estado_proceso_informe(request, ot_id, operation_id):
    ot = get_object_or_404(OrdenTrabajo, id=ot_id)
    cierre_ot = get_object_or_404(CierreOt, orden_trabajo=ot)
    proceso = get_object_or_404(ProcesoInforme, operation_id=operation_id, cierre_ot=cierre_ot)
    return JsonResponse({
        'operation_id': proceso.operation_id,
        'estado': proceso.estado,
        'mensaje': proceso.mensaje,
        'expected_images': proceso.expected_images,
        'confirmed_images': proceso.confirmed_images,
        'required_signatures': proceso.required_signatures,
        'email_enviado': proceso.email_enviado,
        'created_at': proceso.created_at.isoformat(),
        'updated_at': proceso.updated_at.isoformat(),
    })


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

    default_month_filter = False
    if not filtro_fecha_inicio and not filtro_fecha_fin:
        default_month_filter = True
        now = timezone.now()
        first_day_of_month = now.replace(day=1)
        last_day_of_month = (first_day_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        filtro_fecha_inicio = first_day_of_month.date()
        filtro_fecha_fin = last_day_of_month.date()

    if filtro_fecha_inicio and filtro_fecha_fin:
        if isinstance(filtro_fecha_inicio, str):
            filtro_fecha_inicio = datetime.datetime.strptime(filtro_fecha_inicio, '%Y-%m-%d')
        if isinstance(filtro_fecha_fin, str):
            filtro_fecha_fin = datetime.datetime.strptime(filtro_fecha_fin, '%Y-%m-%d')

        if isinstance(filtro_fecha_inicio, datetime.date) and not isinstance(filtro_fecha_inicio, datetime.datetime):
            filtro_fecha_inicio = datetime.datetime.combine(filtro_fecha_inicio, datetime.time.min)
        if isinstance(filtro_fecha_fin, datetime.date) and not isinstance(filtro_fecha_fin, datetime.datetime):
            filtro_fecha_fin = datetime.datetime.combine(filtro_fecha_fin, datetime.time.max)

        if filtro_fecha_inicio and timezone.is_naive(filtro_fecha_inicio):
            filtro_fecha_inicio = timezone.make_aware(filtro_fecha_inicio, timezone.get_current_timezone())
        if filtro_fecha_fin and timezone.is_naive(filtro_fecha_fin):
            filtro_fecha_fin = timezone.make_aware(filtro_fecha_fin, timezone.get_current_timezone())

        if default_month_filter:
            solicitudes_pendientes = solicitudes_pendientes.filter(
                models.Q(fecha_creacion__range=[filtro_fecha_inicio, filtro_fecha_fin]) |
                (models.Q(fecha_creacion__lt=filtro_fecha_inicio) & ~models.Q(estado__nombre='finalizada')) |
                models.Q(fecha_creacion__isnull=True)
            )
            tareas_mantenimiento = tareas_mantenimiento.filter(
                models.Q(fecha_programada__range=[filtro_fecha_inicio, filtro_fecha_fin]) |
                models.Q(fecha_programada__lt=filtro_fecha_inicio)
            )
        else:
            solicitudes_pendientes = solicitudes_pendientes.filter(
                models.Q(fecha_creacion__range=[filtro_fecha_inicio, filtro_fecha_fin]) |
                models.Q(fecha_creacion__isnull=True)
            )
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
        tecnico = data.get('tecnico') or data.get('tecnico_asignado')
        fecha = data.get('fecha') or data.get('fecha_creacion') or data.get('fecha_actividad')

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
                if hasattr(solicitud, 'fecha_actividad'):
                    solicitud.fecha_actividad = fecha_dt
            except ValueError as parse_error:
                logger.error(f"No se pudo parsear la fecha: {fecha}")
                return JsonResponse({'status': 'error', 'message': f'Fecha inválida: {fecha}'}, status=400)

        solicitud.save()
        logger.debug(f"Solicitud actualizada: {solicitud}")

        fecha_dt = None
        if fecha:
            try:
                try:
                    fecha_dt = isoparse(fecha)
                except ValueError:
                    fecha_dt = datetime.datetime.strptime(fecha, '%d/%m/%Y')
                if timezone.is_naive(fecha_dt):
                    fecha_dt = timezone.make_aware(fecha_dt, timezone.get_current_timezone())
            except ValueError as parse_error:
                logger.error(f"No se pudo parsear la fecha para orden de trabajo: {fecha}")
                return JsonResponse({'status': 'error', 'message': f'Fecha inválida: {fecha}'}, status=400)

        orden_trabajo = OrdenTrabajo.objects.filter(solicitud=solicitud).first()
        if orden_trabajo:
            if tecnico:
                orden_trabajo.tecnico_asignado = tecnico
            if fecha_dt is not None:
                orden_trabajo.fecha_actividad = fecha_dt
            orden_trabajo.estado = nuevo_estado
            orden_trabajo.save()
            created = False
        else:
            fallback_tecnico = None
            gestion_ot = GestionOt.objects.filter(solicitud=solicitud).first()
            if gestion_ot and gestion_ot.tecnico:
                fallback_tecnico = gestion_ot.tecnico
            else:
                cierre_ot = CierreOt.objects.filter(orden_trabajo__solicitud=solicitud).first()
                if cierre_ot and cierre_ot.nombre_tecnico:
                    fallback_tecnico = cierre_ot.nombre_tecnico

            orden_trabajo = OrdenTrabajo.objects.create(
                solicitud=solicitud,
                tecnico_asignado=tecnico or fallback_tecnico or '',
                estado=nuevo_estado,
                fecha_actividad=fecha_dt
            )
            created = True

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

    # Ordenar de mayor a menor consecutivo de la solicitud
    ots = ots.order_by('-solicitud__consecutivo')

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

    def get_ot_event_color(estado_nombre):
        if estado_nombre == 'solicitado':
            return '#6c757d'
        if estado_nombre == 'en proceso':
            return '#fd7e14'
        if estado_nombre == 'en revision':
            return '#0d6efd'
        if estado_nombre == 'finalizada':
            return '#198754'
        return '#212529'

    calendar_events = []
    for ot in ots:
        if ot.fecha_actividad:
            estado_nombre = ot.estado.nombre if ot.estado else ''
            event_color = get_ot_event_color(estado_nombre)
            calendar_events.append({
                'title': f"OT-{ot.solicitud.consecutivo} - {ot.tecnico_asignado}",
                'start': ot.fecha_actividad.date().isoformat(),
                'url': reverse('cierre_ot', args=[ot.id]),
                'backgroundColor': event_color,
                'borderColor': event_color,
                'textColor': '#ffffff',
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
    read_only = ot.estado and ot.estado.nombre in ['en revision', 'finalizada']
    existing_proceso = _get_active_proceso_para_cierre(cierre_ot)
    operation_id = existing_proceso.operation_id if existing_proceso else ''
    form_antes = ImagenAntesForm()
    form_despues = ImagenDespuesForm()

    if request.method == 'POST':
        if read_only:
            messages.warning(request, 'Esta OT ya fue enviada a revisión y no puede modificarse.')
            form = CierreOtForm(instance=cierre_ot)
            actividad_formset = CierreOtActividadFormSet(instance=cierre_ot)
            form_antes = ImagenAntesForm()
            form_despues = ImagenDespuesForm()

            for field in form.fields.values():
                field.disabled = True
            for subform in actividad_formset.forms:
                for field in subform.fields.values():
                    field.disabled = True
            form_antes.fields['imagenes_antes'].disabled = True
            form_despues.fields['imagenes_despues'].disabled = True

            return render(request, 'Gestion_ot/cierre_ot.html', {
                'form': form,
                'actividad_formset': actividad_formset,
                'form_antes': form_antes,
                'form_despues': form_despues,
                'ot': ot,
                'read_only': read_only,
                'operation_id': operation_id
            })

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
                'ot': ot,
                'operation_id': operation_id
            })

        operation_id = request.POST.get('operation_id', '').strip()
        if not operation_id or not re.match(r'^[0-9a-fA-F\-]{32,64}$', operation_id):
            operation_id = uuid.uuid4().hex
        logger.debug('Operation ID para informe: %s', operation_id)

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

        existing_active = _get_active_proceso_para_cierre(cierre_ot)
        if existing_active and existing_active.operation_id != operation_id:
            logger.info('[INFORME] Se detecta proceso activo previo para cierre_ot=%s operation=%s existente=%s', cierre_ot.id, operation_id, existing_active.operation_id)
            operation_id = existing_active.operation_id
            proceso = existing_active
        else:
            proceso, _ = _crear_o_actualizar_proceso(cierre_ot, operation_id)

        latest_proceso = _get_latest_proceso_para_cierre(cierre_ot)
        if not existing_active and latest_proceso and latest_proceso.operation_id != operation_id and (latest_proceso.estado == ProcesoInforme.ENVIADO or latest_proceso.email_enviado):
            logger.info('[INFORME] Se reutiliza informe ya enviado para cierre_ot=%s operation=%s', cierre_ot.id, latest_proceso.operation_id)
            operation_id = latest_proceso.operation_id
            proceso = latest_proceso

        # Guardar imágenes y actualizar proceso
        total_images = _guardar_imagenes_del_post(cierre_ot, request, proceso)
        logger.info("Imágenes guardadas para operación %s: %s", proceso.operation_id, total_images)

        # Nota: no cambiar el estado de la OT aquí. El proceso de informe se
        # realizará de forma persistente por un worker/management command.
        # Dejar la OT sin marcar como "en revision" hasta que el informe
        # haya finalizado correctamente y la tarea marque el proceso como ENVIADO.

        if proceso.email_enviado or proceso.estado == ProcesoInforme.ENVIADO:
            logger.info('[INFORME] operation=%s ya enviado, no se iniciará un nuevo proceso', proceso.operation_id)
            messages.info(request, 'El informe ya fue enviado. No se generará un segundo correo.')
            return redirect('listar_ot')

        # Encolar el proceso para que un worker/management command lo procese.
        with transaction.atomic():
            proceso = ProcesoInforme.objects.select_for_update().get(pk=proceso.pk)
            if proceso.email_enviado or proceso.estado == ProcesoInforme.ENVIADO:
                logger.info('[INFORME] operation=%s ya enviado tras bloquear en DB', proceso.operation_id)
                messages.info(request, 'El informe ya fue enviado. No se generará un segundo correo.')
                return redirect('listar_ot')

            if proceso.estado in ProcesoInforme.ACTIVE_STATES and proceso.started_at is not None:
                logger.info('[INFORME] operation=%s ya está siendo procesado en estado=%s', proceso.operation_id, proceso.estado)
                messages.info(request, 'El informe ya está en proceso. No presione el botón nuevamente.')
                return redirect('listar_ot')

            if proceso.estado == ProcesoInforme.ERROR and not proceso.email_enviado:
                proceso.set_state(ProcesoInforme.GUARDANDO, 'Reintentando proceso')

            # No establecer `started_at` ni lanzar hilos en memoria. El worker
            # se encargará de marcar `started_at` al tomar el proceso.

        proceso.set_state(ProcesoInforme.GUARDANDO, f'Guardado y enqueued para procesamiento (imagenes={total_images})')
        messages.success(request, 'OT cerrada exitosamente. El informe se ha encolado para procesamiento en background.')
        return redirect('listar_ot')

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

    if read_only:
        for field in form.fields.values():
            field.disabled = True
        for subform in actividad_formset.forms:
            for field in subform.fields.values():
                field.disabled = True
        form_antes.fields['imagenes_antes'].disabled = True
        form_despues.fields['imagenes_despues'].disabled = True

    return render(request, 'Gestion_ot/cierre_ot.html', {
        'form': form,
        'actividad_formset': actividad_formset,
        'form_antes': form_antes,
        'form_despues': form_despues,
        'ot': ot,
        'read_only': read_only,
        'operation_id': operation_id
    })


# Detalles de la solicitud
@login_required
def detalles_solicitud(request, consecutivo):
    solicitud = get_object_or_404(Solicitud.objects.select_related('equipo__ubicacion'), consecutivo=consecutivo)
    ordenes_trabajo = solicitud.ordenes_trabajo.all()
    logger.info(f"[DETALLES_SOLICITUD] consecutivo={solicitud.consecutivo} equipo_obj={solicitud.equipo} equipo_id={getattr(solicitud.equipo, 'id', None)} display_label={getattr(solicitud.equipo, 'display_label', None)}")
    # Construir label del equipo: intentar display_label, sino construir manualmente
    equipo_label = 'Sin equipo asignado'
    if solicitud.equipo:
        # Intentar usar display_label primero
        try:
            equipo_label = getattr(solicitud.equipo, 'display_label', None)
            if not equipo_label or equipo_label.strip() == '':
                # Fallback: construir manualmente
                parts = []
                if hasattr(solicitud.equipo, 'codigo') and solicitud.equipo.codigo:
                    parts.append(str(solicitud.equipo.codigo).strip())
                if hasattr(solicitud.equipo, 'ubicacion') and solicitud.equipo.ubicacion and hasattr(solicitud.equipo.ubicacion, 'nombre') and solicitud.equipo.ubicacion.nombre:
                    parts.append(str(solicitud.equipo.ubicacion.nombre).strip())
                if hasattr(solicitud.equipo, 'nombre') and solicitud.equipo.nombre:
                    parts.append(str(solicitud.equipo.nombre).strip())
                
                equipo_label = ' / '.join([p for p in parts if p]) if parts else 'Equipo sin nombre'
        except Exception as e:
            logger.error(f"Error al construir equipo_label para solicitud {solicitud.consecutivo}: {e}")
            equipo_label = 'Error al cargar equipo'
    
    data = {
        'consecutivo': solicitud.consecutivo,
        'pdv': solicitud.PDV,
        'descripcion': solicitud.descripcion_problema,
        'fecha_creacion': solicitud.fecha_creacion,
        'estado': solicitud.estado.nombre,
        'equipo': equipo_label,
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
    """Genera un PDF desde plantilla DOCX si existe, sino usa ReportLab como fallback"""
    from .plantilla_utils import generar_pdf_desde_plantilla as generar_desde_plantilla
    
    logger.info(f"📝 Generando PDF para OT {cierre_ot.orden_trabajo.solicitud.consecutivo}")
    
    # Intentar con plantilla primero
    try:
        pdf_buffer = generar_desde_plantilla(cierre_ot)
        if pdf_buffer:
            logger.info("✅ PDF generado EXITOSAMENTE desde plantilla DOCX")
            return pdf_buffer
    except Exception as e:
        logger.warning(f"⚠️  Error generando desde plantilla: {e}")
    
    # Fallback a ReportLab
    logger.info("📋 Usando ReportLab como fallback")
    return generar_pdf_reportlab(cierre_ot)


def generar_pdf_reportlab(cierre_ot):
    """Genera un PDF de informe similar al de Google Docs"""
    logger.info("=== GENERANDO PDF CON REPORTLAB (FALLBACK) ===")
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
    
    # Crear estructura de datos más simple sin firmas (las agregaremos después)
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
    }
    
    # Agregar párrafos con los datos principales
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

    # Sección de receptor con firma debajo
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>RECEPCIÓN DEL TRABAJO</b>", styles['Heading2']))
    story.append(Spacer(1, 6))
    
    p_recibido = Paragraph(f"<b>Recibido por:</b> {cierre_ot.nombre_tecnico or ''}", styles['Normal'])
    story.append(p_recibido)
    story.append(Spacer(1, 4))
    
    p_doc_receptor = Paragraph(f"<b>Documento de Identidad:</b> {cierre_ot.documento_tecnico or ''}", styles['Normal'])
    story.append(p_doc_receptor)
    story.append(Spacer(1, 6))
    
    # Agregar firma del receptor AQUÍ si existe
    try:
        logger.info(f"Verificando firma receptor - Valor: {repr(cierre_ot.firma_receptor)}, Tipo: {type(cierre_ot.firma_receptor)}")
        if cierre_ot.firma_receptor and str(cierre_ot.firma_receptor).strip():
            logger.info("Procesando firma del receptor en ReportLab")
            story.append(Paragraph("<b>Firma:</b>", styles['Normal']))
            story.append(Spacer(1, 4))
            
            try:
                header, encoded = cierre_ot.firma_receptor.split(",", 1)
                logger.info("Firma receptor decodificada correctamente")
            except ValueError:
                encoded = cierre_ot.firma_receptor
                logger.info("Firma receptor sin header, usando directamente")
            image_data = base64.b64decode(encoded)
            img_buffer = BytesIO(image_data)
            img = PILImage.open(img_buffer)
            logger.info(f"Imagen firma receptor cargada: {img.size}, mode: {img.mode}")
            
            if img.mode != 'RGB':
                img = img.convert('RGB')
                logger.info("Imagen firma receptor convertida a RGB")
            
            temp_img_path = f"/tmp/firma_rec_{cierre_ot.id}.png"
            img.save(temp_img_path)
            temp_files.append(temp_img_path)
            logger.info(f"Imagen firma receptor guardada en: {temp_img_path}")
            
            firma_rec_img = Image(temp_img_path, width=200, height=100)
            story.append(firma_rec_img)
            logger.info("Firma receptor agregada al PDF")
        else:
            logger.warning(f"Firma receptor no disponible o vacía")
    except Exception as e:
        logger.error("Error agregando firma del receptor: %s", e)
        raise RuntimeError(f"Error al procesar firma receptor: {e}") from e

    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>REALIZADO POR</b>", styles['Heading2']))
    story.append(Spacer(1, 6))
    
    p_tecnico = Paragraph(f"<b>Realizado por:</b> {cierre_ot.nombre_tecnico or ''}", styles['Normal'])
    story.append(p_tecnico)
    story.append(Spacer(1, 4))
    
    p_doc_tecnico = Paragraph(f"<b>Documento de Identidad:</b> {cierre_ot.documento_tecnico or ''}", styles['Normal'])
    story.append(p_doc_tecnico)
    story.append(Spacer(1, 6))
    
    # Agregar firma del técnico AQUÍ si existe
    try:
        logger.info(f"Verificando firma técnica - Valor: {repr(cierre_ot.firma_digital)}, Tipo: {type(cierre_ot.firma_digital)}")
        if cierre_ot.firma_digital and str(cierre_ot.firma_digital).strip():
            logger.info("Procesando firma técnica en ReportLab")
            story.append(Paragraph("<b>Firma:</b>", styles['Normal']))
            story.append(Spacer(1, 4))
            
            try:
                header, encoded = cierre_ot.firma_digital.split(",", 1)
                logger.info("Firma técnica decodificada correctamente")
            except ValueError:
                encoded = cierre_ot.firma_digital
                logger.info("Firma técnica sin header, usando directamente")
            image_data = base64.b64decode(encoded)
            img_buffer = BytesIO(image_data)
            img = PILImage.open(img_buffer)
            logger.info(f"Imagen firma técnica cargada: {img.size}, mode: {img.mode}")
            
            if img.mode != 'RGB':
                img = img.convert('RGB')
                logger.info("Imagen convertida a RGB")
            
            temp_img_path = f"/tmp/firma_{cierre_ot.id}.png"
            img.save(temp_img_path)
            temp_files.append(temp_img_path)  # Rastrear para limpiar después
            logger.info(f"Imagen firma técnica guardada en: {temp_img_path}")
            
            # Agregar al PDF
            firma_img = Image(temp_img_path, width=200, height=100)
            story.append(firma_img)
            logger.info("Firma técnica agregada al PDF")
        else:
            logger.warning(f"Firma técnica no disponible o vacía")
    except Exception as e:
        logger.error("Error agregando firma técnica: %s", e)
        raise RuntimeError(f"Error al procesar firma técnica: {e}") from e
    
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
            img_path, is_temp = obtener_imagen_temporal_para_pdf(img.imagen)
            if not img_path:
                raise RuntimeError(f"No se pudo obtener imagen antes id={img.id} tipo={img.tipo}")
            try:
                if is_temp:
                    temp_files.append(img_path)  # Rastrear para limpiar después
                img_reportlab = Image(img_path, width=150, height=100)
                row.append(img_reportlab)
                if len(row) == 2 or i == len(imagenes_antes) - 1:
                    data.append(row)
                    row = []
            except Exception as e:
                raise RuntimeError(f"Error generando imagen antes id={img.id}: {e}") from e
        
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
            img_path, is_temp = obtener_imagen_temporal_para_pdf(img.imagen)
            if not img_path:
                raise RuntimeError(f"No se pudo obtener imagen despues id={img.id} tipo={img.tipo}")
            try:
                if is_temp:
                    temp_files.append(img_path)  # Rastrear para limpiar después
                img_reportlab = Image(img_path, width=150, height=100)
                row.append(img_reportlab)
                if len(row) == 2 or i == len(imagenes_despues) - 1:
                    data.append(row)
                    row = []
            except Exception as e:
                raise RuntimeError(f"Error generando imagen despues id={img.id}: {e}") from e
        
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
    logger.info("=== PDF REPORTLAB COMPLETADO ===")
    return buffer, False, False


def guardar_copia_pdf_envio(pdf_buffer, cierre_ot):
    """Guarda una copia local del PDF enviado para auditoría y revisión."""
    try:
        output_dir = os.path.join(settings.MEDIA_ROOT, 'email_copies', 'informes')
        os.makedirs(output_dir, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"informe_ot_{cierre_ot.orden_trabajo.solicitud.consecutivo}_{timestamp}.pdf"
        path = os.path.join(output_dir, filename)
        with open(path, 'wb') as output_file:
            output_file.write(pdf_buffer.getvalue())
        logger.info("Guardada copia local del PDF enviado: %s", path)
        return path
    except Exception as exc:
        logger.warning("No se pudo guardar la copia local del PDF: %s", exc)
        return None


def _is_local_host(hostname):
    """Devuelve True si el hostname es localhost/127.0.0.1."""
    if not hostname:
        return False
    normalized = hostname.lower().strip()
    return normalized in ('127.0.0.1', 'localhost')


def _build_download_url(filename):
    """Genera una URL pública para descargar un informe guardado localmente."""
    if not filename:
        return None
    safe_filename = quote(filename)
    public_host = os.environ.get('PUBLIC_HOST')
    if public_host:
        host = public_host.strip()
        if host.startswith('http://') or host.startswith('https://'):
            host = urlparse(host).netloc or host
        if _is_local_host(host):
            logger.warning("PUBLIC_HOST configurado como localhost/127.0.0.1; no se generará enlace de descarga público.")
            return None
    else:
        allowed_hosts = [h for h in settings.ALLOWED_HOSTS if not _is_local_host(h)]
        if not allowed_hosts:
            logger.warning("No hay PUBLIC_HOST ni ALLOWED_HOSTS públicos válidos; no se generará enlace de descarga público.")
            return None
        host = allowed_hosts[0].strip()

    scheme = 'https' if not settings.DEBUG else 'http'
    url = f"{scheme}://{host.rstrip('/')}{reverse('descargar_informe_pdf', args=[safe_filename])}"
    logger.info("URL de descarga generada: %s (host=%s scheme=%s)", url, host, scheme)
    return url


def _build_media_url(relative_url):
    """Devuelve una URL absoluta válida para un recurso dentro de MEDIA_URL."""
    if not relative_url:
        return None

    relative_url = relative_url.replace('\\', '/')
    if relative_url.startswith('http://') or relative_url.startswith('https://'):
        return relative_url

    media_url = settings.MEDIA_URL or '/media/'
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return urljoin(media_url, relative_url.lstrip('/'))

    host = os.environ.get('PUBLIC_HOST') or (settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000')
    scheme = 'https' if not settings.DEBUG else 'http'
    if media_url.startswith('/'):
        return f"{scheme}://{host.rstrip('/')}{media_url.rstrip('/')}/{relative_url.lstrip('/')}"
    return f"{scheme}://{host.rstrip('/')}/{media_url.rstrip('/')}/{relative_url.lstrip('/')}"


def _build_private_download_url(token):
    """Construye la URL interna de Django para un PDF privado asociado a un token."""
    if not token:
        return None
    public_host = os.environ.get('PUBLIC_HOST')
    if public_host:
        host = public_host.strip()
        if host.startswith('http://') or host.startswith('https://'):
            host = urlparse(host).netloc or host
        if _is_local_host(host):
            logger.warning('PUBLIC_HOST configurado como localhost/127.0.0.1; no se generará enlace privado de descarga.')
            return None
    else:
        allowed_hosts = [h for h in settings.ALLOWED_HOSTS if not _is_local_host(h)]
        if not allowed_hosts:
            logger.warning('No hay PUBLIC_HOST ni ALLOWED_HOSTS públicos válidos; no se generará enlace privado de descarga.')
            return None
        host = allowed_hosts[0].strip()

    scheme = 'https' if not settings.DEBUG else 'http'
    return f"{scheme}://{host.rstrip('/')}{reverse('descargar_informe_token', args=[token])}"


def _crear_o_actualizar_informe_drive_archivo(cierre_ot, pdf_bytes, filename, pdf_mime_type='application/pdf'):
    """Crea o actualiza el registro privado de un PDF en Drive asociado al cierre de OT."""
    drive_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '').strip()
    if not drive_folder_id:
        raise RuntimeError('GOOGLE_DRIVE_FOLDER_ID no está configurado.')

    metadata = subir_pdf_privado_a_drive(pdf_bytes, filename, folder_id=drive_folder_id)
    record, created = InformeDriveArchivo.objects.update_or_create(
        cierre_ot=cierre_ot,
        defaults={
            'drive_file_id': metadata['drive_file_id'],
            'nombre_archivo': metadata['nombre_archivo'],
            'mime_type': metadata.get('mime_type') or pdf_mime_type,
            'file_size_bytes': metadata.get('file_size_bytes') or len(pdf_bytes),
            'download_enabled': True,
        },
    )
    if created or not record.download_token:
        record.download_token = uuid.uuid4().hex
        record.save(update_fields=['download_token'])
    return record


def guardar_pdf_en_media(pdf_buffer, cierre_ot):
    """Compatibilidad: conserva el comportamiento anterior de guardar copia local y publicar una URL cuando el storage lo permite."""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"informe_ot_{cierre_ot.orden_trabajo.solicitud.consecutivo}_{timestamp}.pdf"
    relative_path = os.path.join('email_copies', 'informes', filename)

    pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else bytes(pdf_buffer)

    drive_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '').strip()
    drive_credentials = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON') or os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON_PATH') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if drive_folder_id and drive_credentials:
        try:
            public_url = subir_pdf_a_drive(pdf_bytes, filename, folder_id=drive_folder_id)
            logger.info("PDF guardado en Google Drive: %s", public_url)
            return public_url
        except Exception as drive_exc:
            logger.warning("No se pudo guardar el PDF en Google Drive: %s", drive_exc)

    try:
        content = ContentFile(pdf_bytes)
        saved_name = default_storage.save(relative_path, content)
        url = default_storage.url(saved_name)
        public_url = _build_media_url(url)
        logger.info("PDF guardado en storage: %s -> URL: %s", saved_name, public_url)
        return public_url
    except Exception as exc:
        logger.warning("No se pudo guardar el PDF en storage: %s", exc)

    try:
        local_dir = os.path.join(settings.MEDIA_ROOT, 'email_copies', 'informes')
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, filename)
        with open(local_path, 'wb') as local_file:
            local_file.write(pdf_bytes)

        public_url = _build_download_url(filename)
        logger.info("PDF guardado localmente en MEDIA_ROOT: %s -> URL de descarga: %s", local_path, public_url)
        return public_url
    except Exception as exc2:
        logger.warning("No se pudo guardar el PDF localmente en MEDIA_ROOT: %s", exc2)

    logger.error("No fue posible generar una URL pública para el PDF.")
    return None


def descargar_informe_token(request, token):
    """Descarga el PDF privado asociado a un token de Django sin exponer Google Drive al cliente."""
    record = get_object_or_404(InformeDriveArchivo, download_token=token)
    if not record.download_enabled:
        raise Http404('Este enlace de descarga no está habilitado.')

    try:
        response = StreamingHttpResponse(
            iterar_archivo_privado_drive(record.drive_file_id),
            content_type=record.mime_type or 'application/pdf',
        )
        response['Content-Type'] = record.mime_type or 'application/pdf'
        response['Content-Disposition'] = f'attachment; filename="{record.nombre_archivo}"'
        response['X-Accel-Buffering'] = 'no'
        if record.file_size_bytes:
            response['Content-Length'] = str(record.file_size_bytes)
        return response
    except Exception as exc:
        logger.error('Error devolviendo PDF privado desde Drive por streaming: %s', exc)
        raise Http404('No se pudo descargar el informe solicitado.')


def descargar_informe_pdf(request, filename):
    """Sirve un informe PDF guardado localmente en MEDIA_ROOT/email_copies/informes."""
    if not filename or '..' in filename or filename.startswith('/'):
        raise Http404("Nombre de archivo inválido")

    allowed_dir = os.path.normpath(os.path.join(settings.MEDIA_ROOT, 'email_copies', 'informes'))
    file_path = os.path.normpath(os.path.join(allowed_dir, filename))
    if not file_path.startswith(allowed_dir):
        raise Http404("Ruta de archivo inválida")
    if not os.path.exists(file_path):
        raise Http404("Archivo no encontrado")
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf', filename=filename)
    except Exception as exc:
        logger.error("Error abriendo el archivo PDF para descarga: %s", exc)
        raise Http404("No se pudo abrir el archivo")


def enviar_pdf_por_email(pdf_buffer, cierre_ot):
    """Envía el PDF por email usando Brevo API con formato HTML presentable."""
    from django.core.mail import EmailMultiAlternatives
    
    solicitud = cierre_ot.orden_trabajo.solicitud
    consecutivo = solicitud.consecutivo
    equipo_nombre = solicitud.equipo.nombre if solicitud.equipo else "N/A"
    
    # Usar PDV como nombre del cliente
    cliente_nombre = solicitud.PDV if solicitud.PDV else "N/A"
    
    fecha_str = cierre_ot.fecha_inicio_actividad.strftime('%d/%m/%Y') if cierre_ot.fecha_inicio_actividad else datetime.datetime.now().strftime('%d/%m/%Y')
    
    subject = f"Informe de Mantenimiento OT-{consecutivo}"
    
    # Nombre del PDF: OT - 115 - 20/6/2026 8:51:39
    fecha_obj = cierre_ot.fecha_inicio_actividad or datetime.datetime.now()
    fecha_hora_str = fecha_obj.strftime('%d/%m/%Y %H:%M:%S')
    pdf_filename = f"OT - {consecutivo} - {fecha_hora_str}.pdf"
    
    from_email = "thermovoltc@gmail.com"
    
    # Build recipient list
    recipient_list = []
    if cierre_ot.correo_tecnico:
        recipient_list.append(cierre_ot.correo_tecnico)

    # Try to resolve client/PDV email
    pdv_name = None
    try:
        pdv_name = solicitud.PDV or (solicitud.equipo.ubicacion.nombre if solicitud.equipo and solicitud.equipo.ubicacion else None)
    except Exception:
        pdv_name = None

    client_emails = []
    client_map = getattr(settings, 'CLIENT_EMAIL_MAP', {})
    if isinstance(client_map, str):
        try:
            client_map = json.loads(client_map)
        except Exception:
            client_map = {}

    if pdv_name and client_map:
        key = pdv_name.strip().lower()
        email_val = client_map.get(key)
        if email_val:
            if isinstance(email_val, str):
                client_emails = [e.strip() for e in email_val.split(',') if e.strip()]
            else:
                client_emails = list(email_val)
        else:
            for k, v in client_map.items():
                try:
                    if k and k.lower() in key:
                        if isinstance(v, str):
                            client_emails = [e.strip() for e in v.split(',') if e.strip()]
                        else:
                            client_emails = list(v)
                        break
                except Exception:
                    continue

    # Fallback to solicitud.email_solicitante
    if not client_emails:
        try:
            if getattr(solicitud, 'email_solicitante', None):
                client_emails = [solicitud.email_solicitante]
        except Exception:
            pass

    for e in client_emails:
        if e and e not in recipient_list:
            recipient_list.append(e)
    
    bcc_list = []
    copy_address = getattr(settings, 'EMAIL_ADICIONAL', None)
    if copy_address:
        if isinstance(copy_address, str):
            copy_addresses = [email.strip() for email in copy_address.split(',') if email.strip()]
        else:
            copy_addresses = list(copy_address)
        for email in copy_addresses:
            if email and email not in recipient_list:
                bcc_list.append(email)

    if not recipient_list:
        logger.warning("No hay destinatarios principales para enviar el email")
        return False

    guardar_copia_pdf_envio(pdf_buffer, cierre_ot)

    try:
        # Crear mensaje HTML presentable
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                <!-- Header -->
                <div style="background-color: #1a3a52; color: white; padding: 30px 20px; text-align: center;">
                    <h2 style="margin: 0; font-size: 24px;">Informe de Mantenimiento</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Thermovolt Servicios</p>
                </div>
                
                <!-- Body -->
                <div style="padding: 30px 20px;">
                    <p style="margin-top: 0;">Cordial saludo,</p>
                    
                    <p>Adjunto se encuentra el informe de los trabajos realizados en <strong>{cliente_nombre}</strong>.</p>
                    
                    <!-- Info Box -->
                    <div style="background-color: #f5f5f5; border-left: 4px solid #2c5aa0; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <p style="margin: 5px 0;"><strong>Orden de Trabajo:</strong> OT-{consecutivo}</p>
                        <p style="margin: 5px 0;"><strong>Equipo:</strong> {equipo_nombre}</p>
                        <p style="margin: 5px 0;"><strong>Cliente:</strong> {cliente_nombre}</p>
                        <p style="margin: 5px 0;"><strong>Fecha:</strong> {fecha_str}</p>
                        <p style="margin: 5px 0;"><strong>Documento:</strong> {pdf_filename}</p>
                    </div>
                    
                    <p>El archivo PDF adjunto contiene todos los detalles de la intervención realizada, incluyendo descripción del trabajo, materiales utilizados y confirmación de recepción.</p>
                    
                    <p>Si tiene preguntas o necesita aclaraciones adicionales, no dude en contactarnos.</p>
                </div>
                
                <!-- Footer -->
                <div style="background-color: #f9f9f9; padding: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                    <p style="margin: 0; text-align: center;">
                        <strong>Thermovolt</strong> | Servicios de Mantenimiento Industrial<br>
                        <a href="mailto:info@thermovolt.com" style="color: #2c5aa0; text-decoration: none;">info@thermovolt.com</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Crear email con versión texto y HTML
        text_content = f"Cordial saludo,\n\nAdjunto se encuentra el informe de los trabajos realizados en {cliente_nombre}.\n\nOT-{consecutivo}\nEquipo: {equipo_nombre}\nCliente: {cliente_nombre}\nFecha: {fecha_str}\n\nThermovolt Servicios"

        pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else bytes(pdf_buffer)
        attachment_size_mb = len(pdf_bytes) / (1024 * 1024)
        logger.info(f"📬 Enviando email via Brevo")
        logger.info(f"   - Destinatarios: {recipient_list}")
        logger.info(f"   - Archivo: {pdf_filename} ({attachment_size_mb:.2f} MB)")

        if len(pdf_bytes) <= 4 * 1024 * 1024:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipient_list,
                bcc=bcc_list
            )
            email.attach(pdf_filename, pdf_bytes, 'application/pdf')
            logger.info("📎 PDF adjuntado al email")
        else:
            logger.warning(
                "⚠️ El PDF supera el umbral seguro para Brevo (%s MB). Se sube a Google Drive privado y el email envía un enlace interno de Django.",
                round(attachment_size_mb, 2),
            )
            try:
                guardar_copia_pdf_envio(pdf_buffer, cierre_ot)
            except Exception:
                pass

            try:
                registro_drive = _crear_o_actualizar_informe_drive_archivo(cierre_ot, pdf_bytes, pdf_filename)
                download_url = _build_private_download_url(registro_drive.download_token)
                if download_url:
                    download_block = f"<div style=\"background:#f5f5f5;padding:15px;border:1px solid #d1d5db;border-radius:6px;margin:20px 0;\"><p>El informe completo está disponible para descarga aquí: <a href=\"{download_url}\">Descargar informe (PDF)</a></p></div>"
                    if '</body>' in html_content:
                        html_content = html_content.replace('</body>', f"{download_block}</body>")
                    else:
                        html_content += download_block
                    text_content += f"\n\nInforme disponible: {download_url}\n"
                    logger.info("Link privado de descarga agregado al email: %s", download_url)
                else:
                    logger.warning('No se pudo construir el enlace interno privado para el email.')
            except Exception as drive_exc:
                logger.warning('No se pudo elevar el PDF a Drive privado para el email: %s', drive_exc)
                download_url = None

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipient_list,
                bcc=bcc_list
            )

        # Agregar versión HTML con el contenido final, incluyendo posible enlace.
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info("✅ Email enviado EXITOSAMENTE via Brevo")
        return True

    except Exception as e:
        logger.error("❌ Error enviando email: %s", str(e))
        logger.error("   - Tipo: %s", type(e).__name__)
        return False


