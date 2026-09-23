import os
import re
import zipfile
from urllib.request import urlopen
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.text import slugify
from .forms import UbicacionForm, EquipoForm
from .models import Ubicacion, Equipo, CentroOperaciones
from gestion_mantenimiento.users.models import Cliente
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.core.files.storage import default_storage
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import Image as RLImage
from PIL import Image as PILImage
from gestion_mantenimiento.Gestion_ot.models import OrdenTrabajo

def _perfil_usuario_actual(user):
    try:
        return user.perfil_usuario
    except Exception:
        return None


def _cliente_actual(user):
    perfil = _perfil_usuario_actual(user)
    if perfil is None:
        return None
    return perfil.cliente


def _centro_operaciones_actual(user):
    perfil = _perfil_usuario_actual(user)
    if perfil is None:
        return None
    return perfil.centro_operaciones


def _ubicaciones_descendientes_de_co(co_id):
    if not co_id:
        return Ubicacion.objects.none()
    ids = set(Ubicacion.objects.filter(centro_operaciones_id=co_id).values_list('id', flat=True))
    queue = list(ids)
    while queue:
        current = queue.pop(0)
        children = list(Ubicacion.objects.filter(parent_id=current).values_list('id', flat=True))
        for child_id in children:
            if child_id not in ids:
                ids.add(child_id)
                queue.append(child_id)
    return Ubicacion.objects.filter(id__in=ids)


def _cliente_tiene_acceso_a_ubicacion(cliente, ubicacion, centro=None):
    if cliente is None:
        return True
    if ubicacion is None:
        return False
    if ubicacion.centro_operaciones_id is None:
        return False
    if ubicacion.centro_operaciones.cliente_id != cliente.id:
        return False
    if centro is not None and ubicacion.centro_operaciones_id != centro.id:
        return False
    return True


def _cliente_tiene_acceso_a_equipo(cliente, equipo, centro=None):
    if cliente is None:
        return True
    if equipo is None:
        return False
    return _cliente_tiene_acceso_a_ubicacion(cliente, equipo.ubicacion, centro=centro)


def crear_ubicacion(request):
    cliente = _cliente_actual(request.user)
    centro = _centro_operaciones_actual(request.user)
    if request.method == 'POST':
        form = UbicacionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            codigo_co = (request.POST.get('centro_operaciones_codigo') or '').strip()
            ubicacion = form.save(commit=False)

            if codigo_co:
                centro_co = CentroOperaciones.objects.filter(codigo=codigo_co).first()
                if centro_co is None:
                    form.add_error('centro_operaciones_codigo', 'El código de Centro de Operaciones no existe.')
                    return render(request, 'Activos/crear_ubicacion.html', {
                        'form': form,
                        'page_title': 'Crear Ubicación',
                        'submit_text': 'Crear Ubicación',
                        'action_url': reverse('crear_ubicacion'),
                    })
                if cliente is not None and centro_co.cliente_id != cliente.id:
                    form.add_error('centro_operaciones_codigo', 'El Centro de Operaciones no corresponde al cliente permitido para este usuario.')
                    return render(request, 'Activos/crear_ubicacion.html', {
                        'form': form,
                        'page_title': 'Crear Ubicación',
                        'submit_text': 'Crear Ubicación',
                        'action_url': reverse('crear_ubicacion'),
                    })
                ubicacion.centro_operaciones = centro_co
            else:
                ubicacion.centro_operaciones = None

            if cliente is not None and not _cliente_tiene_acceso_a_ubicacion(cliente, ubicacion, centro=centro):
                return HttpResponseForbidden('No tienes permiso para usar ese centro de operaciones.')
            ubicacion.save()
            return redirect('lista_activos')
    else:
        form = UbicacionForm(user=request.user)
    context = {
        'form': form,
        'page_title': 'Crear Ubicación',
        'submit_text': 'Crear Ubicación',
        'action_url': reverse('crear_ubicacion'),
    }
    return render(request, 'Activos/crear_ubicacion.html', context)

def editar_ubicacion(request, ubicacion_id):
    cliente = _cliente_actual(request.user)
    centro = _centro_operaciones_actual(request.user)
    ubicacion = Ubicacion.objects.filter(id=ubicacion_id).select_related('centro_operaciones__cliente').first()
    if not ubicacion:
        raise Http404('Ubicación no encontrada')
    if cliente is not None and not _cliente_tiene_acceso_a_ubicacion(cliente, ubicacion, centro=centro):
        raise Http404('Ubicación no disponible para este cliente')

    if request.method == 'POST':
        form = UbicacionForm(request.POST, request.FILES, instance=ubicacion, user=request.user)
        if form.is_valid():
            codigo_co = (request.POST.get('centro_operaciones_codigo') or '').strip()
            ubicacion_guardada = form.save(commit=False)

            if codigo_co:
                centro_co = CentroOperaciones.objects.filter(codigo=codigo_co).first()
                if centro_co is None:
                    form.add_error('centro_operaciones_codigo', 'El código de Centro de Operaciones no existe.')
                    return render(request, 'Activos/crear_ubicacion.html', {
                        'form': form,
                        'page_title': 'Editar Ubicación',
                        'submit_text': 'Actualizar Ubicación',
                        'action_url': reverse('editar_ubicacion', args=[ubicacion.id]),
                    })
                if cliente is not None and centro_co.cliente_id != cliente.id:
                    form.add_error('centro_operaciones_codigo', 'El Centro de Operaciones no corresponde al cliente permitido para este usuario.')
                    return render(request, 'Activos/crear_ubicacion.html', {
                        'form': form,
                        'page_title': 'Editar Ubicación',
                        'submit_text': 'Actualizar Ubicación',
                        'action_url': reverse('editar_ubicacion', args=[ubicacion.id]),
                    })
                ubicacion_guardada.centro_operaciones = centro_co
            else:
                ubicacion_guardada.centro_operaciones = None

            if cliente is not None and not _cliente_tiene_acceso_a_ubicacion(cliente, ubicacion_guardada, centro=centro):
                return HttpResponseForbidden('No tienes permiso para usar ese centro de operaciones.')
            ubicacion_guardada.save()
            return redirect('lista_activos')
    else:
        form = UbicacionForm(instance=ubicacion, user=request.user)

    context = {
        'form': form,
        'page_title': 'Editar Ubicación',
        'submit_text': 'Actualizar Ubicación',
        'action_url': reverse('editar_ubicacion', args=[ubicacion.id]),
    }
    return render(request, 'Activos/crear_ubicacion.html', context)

def crear_equipo(request):
    cliente = _cliente_actual(request.user)
    centro = _centro_operaciones_actual(request.user)
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            equipo = form.save(commit=False)
            if cliente is not None and not _cliente_tiene_acceso_a_ubicacion(cliente, equipo.ubicacion, centro=centro):
                return HttpResponseForbidden('No tienes permiso para crear un equipo en esa ubicación.')
            equipo.save()
            return redirect('lista_activos')
    else:
        form = EquipoForm(user=request.user)
    context = {
        'form': form,
        'page_title': 'Crear Equipo',
        'submit_text': 'Guardar',
        'action_url': reverse('crear_equipo'),
    }
    return render(request, 'Activos/crear_equipo.html', context)

def editar_equipo(request, equipo_id):
    cliente = _cliente_actual(request.user)
    centro = _centro_operaciones_actual(request.user)
    equipo = Equipo.objects.filter(id=equipo_id).select_related('ubicacion__centro_operaciones__cliente').first()
    if not equipo:
        raise Http404('Equipo no encontrado')
    if cliente is not None and not _cliente_tiene_acceso_a_equipo(cliente, equipo, centro=centro):
        raise Http404('Equipo no disponible para este cliente')

    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES, instance=equipo, user=request.user)
        if form.is_valid():
            equipo_guardado = form.save(commit=False)
            if cliente is not None and not _cliente_tiene_acceso_a_ubicacion(cliente, equipo_guardado.ubicacion, centro=centro):
                return HttpResponseForbidden('No tienes permiso para asignar esa ubicación.')
            equipo_guardado.save()
            return redirect('lista_activos')
    else:
        form = EquipoForm(instance=equipo, user=request.user)

    context = {
        'form': form,
        'page_title': 'Editar Equipo',
        'submit_text': 'Actualizar',
        'action_url': reverse('editar_equipo', args=[equipo.id]),
    }
    return render(request, 'Activos/crear_equipo.html', context)

def crear_equipo_dinamico(request):
    """Crea un equipo hijo dinámicamente desde el árbol"""
    cliente = _cliente_actual(request.user)
    centro = _centro_operaciones_actual(request.user)
    if request.method == 'POST':
        parent_id = request.POST.get('parent_id')
        parent_type = request.POST.get('parent_type')
        form = EquipoForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            equipo = form.save(commit=False)

            if cliente is not None:
                if parent_type == 'ubicacion' and parent_id:
                    try:
                        ubicacion_padre = Ubicacion.objects.select_related('centro_operaciones__cliente').get(id=parent_id)
                    except Ubicacion.DoesNotExist:
                        return HttpResponseForbidden('Ubicación no válida.')
                    if not _cliente_tiene_acceso_a_ubicacion(cliente, ubicacion_padre, centro=centro):
                        return HttpResponseForbidden('No tienes permiso para crear equipos bajo esa ubicación.')
                    equipo.ubicacion = ubicacion_padre

                if parent_type == 'equipo' and parent_id:
                    try:
                        parent_equipo = Equipo.objects.select_related('ubicacion__centro_operaciones__cliente').get(id=parent_id)
                    except Equipo.DoesNotExist:
                        return HttpResponseForbidden('Equipo padre no válido.')
                    if not _cliente_tiene_acceso_a_equipo(cliente, parent_equipo, centro=centro):
                        return HttpResponseForbidden('No tienes permiso para usar ese equipo como padre.')
                    equipo.parent = parent_equipo
                    if not equipo.ubicacion and parent_equipo.ubicacion:
                        equipo.ubicacion = parent_equipo.ubicacion

                if not _cliente_tiene_acceso_a_ubicacion(cliente, equipo.ubicacion, centro=centro):
                    return HttpResponseForbidden('No tienes permiso para crear un equipo en esa ubicación.')

            if parent_type == 'ubicacion' and parent_id:
                try:
                    ubicacion = Ubicacion.objects.get(id=parent_id)
                    equipo.ubicacion = ubicacion
                except Ubicacion.DoesNotExist:
                    pass

            if parent_type == 'equipo' and parent_id:
                try:
                    parent_equipo = Equipo.objects.get(id=parent_id)
                    equipo.parent = parent_equipo
                    if not equipo.ubicacion and parent_equipo.ubicacion:
                        equipo.ubicacion = parent_equipo.ubicacion
                except Equipo.DoesNotExist:
                    pass

            equipo.save()
            return redirect('lista_activos')

        return redirect('lista_activos')

    return redirect('lista_activos')

def lista_activos(request):
    perfil = _perfil_usuario_actual(request.user)
    cliente = perfil.cliente if perfil and perfil.cliente_id else None
    centro = perfil.centro_operaciones if perfil and perfil.centro_operaciones_id else None

    if cliente is not None:
        clientes = Cliente.objects.filter(id=cliente.id)
        if centro is not None:
            centros_operaciones = CentroOperaciones.objects.filter(id=centro.id, cliente=cliente, activo=True).select_related('cliente').order_by('nombre')
            ubicaciones_all = _ubicaciones_descendientes_de_co(centro.id).select_related('centro_operaciones__cliente').order_by('nombre')
        else:
            centros_operaciones = CentroOperaciones.objects.filter(cliente=cliente, activo=True).select_related('cliente').order_by('nombre')
            ubicaciones_all = Ubicacion.objects.filter(centro_operaciones__cliente=cliente).select_related('centro_operaciones__cliente').order_by('nombre')

        context = {
            'ubicaciones': ubicaciones_all.filter(parent__isnull=True),
            'ubicaciones_all': ubicaciones_all,
            'clientes': clientes,
            'centros_operaciones': centros_operaciones,
            'selected_cliente': str(cliente.id),
            'selected_co': str(centro.id) if centro else '',
            'selected_ubicacion': '',
            'usuario_cliente': True,
        }
        return render(request, 'Activos/lista_activos.html', context)

    ubicaciones = Ubicacion.objects.filter(parent__isnull=True)
    ubicaciones_all = Ubicacion.objects.all()
    context = {
        'ubicaciones': ubicaciones,
        'ubicaciones_all': ubicaciones_all,
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
        'centros_operaciones': CentroOperaciones.objects.filter(activo=True).select_related('cliente').order_by('cliente__nombre', 'nombre'),
        'selected_cliente': '',
        'selected_co': '',
        'selected_ubicacion': '',
        'usuario_cliente': False,
    }
    return render(request, 'Activos/lista_activos.html', context)


def _resolve_equipo_image_bytes(equipo, request=None):
    """Resuelve la imagen del equipo a bytes para el PDF, soportando almacenamiento local y remoto."""
    if not equipo.imagen:
        return None

    try:
        if hasattr(equipo.imagen, 'path') and equipo.imagen.path and os.path.exists(equipo.imagen.path):
            with open(equipo.imagen.path, 'rb') as image_file:
                return image_file.read()
    except Exception:
        pass

    try:
        image_name = getattr(equipo.imagen, 'name', None)
        if image_name:
            with default_storage.open(image_name, 'rb') as image_file:
                return image_file.read()
    except Exception:
        pass

    try:
        image_url = getattr(equipo.imagen, 'url', None)
        if image_url:
            if image_url.startswith('http://') or image_url.startswith('https://'):
                remote_url = image_url
            elif request is not None:
                remote_url = request.build_absolute_uri(image_url)
            else:
                remote_url = None

            if remote_url:
                with urlopen(remote_url) as response:
                    return response.read()
    except Exception:
        pass

    return None


def _fit_image_dimensions(image_bytes, max_width, max_height):
    """Escala una imagen para que entre en el recuadro del PDF sin deformarla."""
    try:
        with PILImage.open(BytesIO(image_bytes)) as image:
            source_width, source_height = image.size
            if source_width <= 0 or source_height <= 0:
                return max_width, max_height

            ratio = min(max_width / source_width, max_height / source_height)
            final_width = max(1, int(source_width * ratio))
            final_height = max(1, int(source_height * ratio))
            return final_width, final_height
    except Exception:
        return max_width, max_height


def _build_hoja_vida_pdf_bytes(equipo, request=None):
    """Genera el PDF de hoja de vida para un equipo y devuelve un BytesIO listo para responder."""
    ots = OrdenTrabajo.objects.filter(solicitud__equipo=equipo).select_related('solicitud', 'estado').order_by('-solicitud__consecutivo')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle('Label', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=9, leading=12)
    value_style = ParagraphStyle('Value', parent=styles['BodyText'], fontSize=9, leading=12)
    type_state_style = ParagraphStyle('TypeState', parent=styles['BodyText'], fontSize=9, leading=11)
    header_style = ParagraphStyle('Header', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.whitesmoke)
    story = []

    title = Paragraph(f"Hoja de vida - {equipo.nombre}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    description_text = equipo.descripcion or ''
    attr_rows = [
        [Paragraph('INFORMACIÓN BÁSICA', header_style), '', '', ''],
        [Paragraph('Código', label_style), Paragraph(equipo.codigo or '', value_style), Paragraph('Modelo', label_style), Paragraph(equipo.modelo or '', value_style)],
        [Paragraph('Nombre', label_style), Paragraph(equipo.nombre or '', value_style), Paragraph('H. de uso', label_style), Paragraph(str(equipo.horas_uso) if equipo.horas_uso is not None else '', value_style)],
        [Paragraph('Ubicación', label_style), Paragraph(equipo.ubicacion.nombre if equipo.ubicacion else '', value_style), Paragraph('Prioridad', label_style), Paragraph(equipo.prioridad or '', value_style)],
        [Paragraph('Fabricante', label_style), Paragraph(equipo.fabricante or '', value_style), Paragraph('Val. compra', label_style), Paragraph(f"{equipo.valor_compra:.2f}" if equipo.valor_compra is not None else '', value_style)],
        [Paragraph('Serie', label_style), Paragraph(equipo.serie or '', value_style), Paragraph('Valor actual', label_style), Paragraph(f"{equipo.valor_actual:.2f}" if equipo.valor_actual is not None else '', value_style)],
        [Paragraph('F. de Adq.', label_style), Paragraph(equipo.fecha_adquisicion.strftime('%d/%m/%Y') if equipo.fecha_adquisicion else '', value_style), '', ''],
        [Paragraph('Descripción', label_style), Paragraph(description_text, value_style), '', ''],
    ]

    attrs_table = Table(attr_rows, colWidths=[70, 120, 70, 120])
    attrs_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.4, colors.black),
        ('BACKGROUND', (0,0), (3,0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0,0), (3,0), colors.whitesmoke),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,1), (-1,-1), 'LEFT'),
        ('SPAN', (0,0), (3,0)),
        ('SPAN', (1,7), (3,7)),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    _, attrs_height = attrs_table.wrap(360, 0)
    photo_col_width = 190
    photo_width = 112
    photo_height = 146
    main_row_height = max(attrs_height, photo_height)
    photo_flowable = None
    try:
        image_bytes = _resolve_equipo_image_bytes(equipo, request=request)
        if image_bytes:
            fitted_width, fitted_height = _fit_image_dimensions(image_bytes, photo_width, photo_height - 20)
            photo_flowable = RLImage(BytesIO(image_bytes), width=fitted_width, height=fitted_height)
            photo_flowable.hAlign = 'CENTER'
    except Exception:
        photo_flowable = None

    if not photo_flowable:
        placeholder = Table([[ ' ' ]], colWidths=[photo_width], rowHeights=[photo_height])
        placeholder.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        photo_flowable = placeholder

    photo_box = Table([[photo_flowable]], colWidths=[photo_col_width], rowHeights=[main_row_height])
    photo_box.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEABOVE', (0,0), (-1,0), 0.5, colors.black),
        ('LINERIGHT', (0,0), (-1,-1), 0.5, colors.black),
        ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.black),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    main_table = Table(
        [[attrs_table, photo_box]],
        colWidths=[360, photo_col_width],
        rowHeights=[main_row_height],
    )
    main_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LINEAFTER', (1,0), (1,0), 0.5, colors.black),
    ]))
    story.append(main_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph('<b>Intervenciones / Historial de OT</b>', styles['Heading2']))
    story.append(Spacer(1, 8))

    data = [[
        Paragraph('Nº OT', header_style),
        Paragraph('Fecha', header_style),
        Paragraph('Responsable', header_style),
        Paragraph('Tipo / Estado', header_style),
        Paragraph('Observación', header_style),
    ]]

    for ot in ots:
        fecha = ot.fecha_actividad.strftime('%d/%m/%Y') if ot.fecha_actividad else ''
        responsable = ''
        tipo_txt = ''
        estado_txt = ot.estado.nombre if ot.estado else ''
        observacion = ''
        try:
            cierre = ot.cierreot
            responsable = cierre.nombre_tecnico or ''
            tipo_txt = cierre.tipo_mantenimiento or (cierre.tipo_intervencion if hasattr(cierre, 'tipo_intervencion') else '')
            observacion = cierre.observaciones or ''
        except Exception:
            cierre = None
        if not responsable:
            responsable = ot.tecnico_asignado or ''

        tipo_estado = Paragraph(f"<b>{tipo_txt}</b><br/>{estado_txt}", type_state_style)

        data.append([
            Paragraph(f"OT-{ot.solicitud.consecutivo}", value_style),
            Paragraph(fecha, value_style),
            Paragraph(responsable, value_style),
            tipo_estado,
            Paragraph(observacion, value_style),
        ])

    ot_table = Table(data, colWidths=[70, 70, 110, 130, 120])
    ot_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(ot_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def hoja_vida_equipo(request, equipo_id):
    """Genera y devuelve una Hoja de Vida (PDF) para un `Equipo` con su historial de OTs."""
    equipo = Equipo.objects.filter(id=equipo_id).first()
    if not equipo:
        raise Http404("Equipo no encontrado")

    buffer = _build_hoja_vida_pdf_bytes(equipo, request=request)
    filename = f"hoja_vida_{equipo.codigo or equipo.id}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def _collect_ubicacion_descendants(ubicacion):
    ids = []
    stack = [ubicacion]
    while stack:
        current = stack.pop()
        ids.append(current.id)
        stack.extend(list(current.children.all()))
    return ids


def descargar_hojas_vida_ubicacion(request, ubicacion_id):
    """Genera un ZIP con todas las hojas de vida de los equipos bajo una ubicación y sus sububicaciones."""
    ubicacion = Ubicacion.objects.filter(id=ubicacion_id).first()
    if not ubicacion:
        raise Http404("Ubicación no encontrada")

    ubicacion_ids = _collect_ubicacion_descendants(ubicacion)
    equipos = Equipo.objects.filter(ubicacion_id__in=ubicacion_ids).select_related('ubicacion').order_by('ubicacion__nombre', 'nombre')
    if not equipos.exists():
        raise Http404("No hay equipos asociados a esta ubicación para exportar")

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for equipo in equipos:
            safe_name = f"{slugify(equipo.codigo or str(equipo.id))}_{slugify(equipo.nombre)}.pdf"
            safe_name = re.sub(r'[-_]+', '-', safe_name)
            pdf_buffer = _build_hoja_vida_pdf_bytes(equipo, request=request)
            archive.writestr(safe_name, pdf_buffer.getvalue())

    archive_buffer.seek(0)
    return FileResponse(
        archive_buffer,
        as_attachment=True,
        filename=f"{slugify(ubicacion.nombre)}_hojas_vida.zip",
        content_type='application/zip',
    )
