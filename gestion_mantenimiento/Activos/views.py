from django.shortcuts import render, redirect
from .forms import UbicacionForm, EquipoForm
from .models import Ubicacion, Equipo
from django.http import FileResponse, Http404
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from gestion_mantenimiento.Gestion_ot.models import OrdenTrabajo

def crear_ubicacion(request):
    if request.method == 'POST':
        form = UbicacionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('lista_activos')
    else:
        form = UbicacionForm()
    return render(request, 'Activos/crear_ubicacion.html', {'form': form})

def crear_equipo(request):
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('lista_activos')
    else:
        form = EquipoForm()
    return render(request, 'Activos/crear_equipo.html', {'form': form})

def crear_equipo_dinamico(request):
    """Crea un equipo hijo dinámicamente desde el árbol"""
    if request.method == 'POST':
        parent_id = request.POST.get('parent_id')
        parent_type = request.POST.get('parent_type')
        form = EquipoForm(request.POST, request.FILES)

        if form.is_valid():
            equipo = form.save(commit=False)

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

        # Si el formulario no es válido, se redirige igual para evitar bloquear la vista de árbol
        return redirect('lista_activos')

    return redirect('lista_activos')

def lista_activos(request):
    ubicaciones = Ubicacion.objects.filter(parent__isnull=True)
    ubicaciones_all = Ubicacion.objects.all()
    context = {
        'ubicaciones': ubicaciones,
        'ubicaciones_all': ubicaciones_all,
    }
    return render(request, 'Activos/lista_activos.html', context)


def hoja_vida_equipo(request, equipo_id):
    """Genera y devuelve una Hoja de Vida (PDF) para un `Equipo` con su historial de OTs."""
    equipo = Equipo.objects.filter(id=equipo_id).first()
    if not equipo:
        raise Http404("Equipo no encontrado")

    # Obtener OTs relacionadas
    ots = OrdenTrabajo.objects.filter(solicitud__equipo=equipo).select_related('solicitud', 'estado').order_by('-solicitud__consecutivo')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(f"Hoja de vida - {equipo.nombre}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Datos básicos del equipo
    equipo_data = [
        ['Nombre', equipo.nombre or ''],
        ['Código', equipo.codigo or ''],
        ['Ubicación', equipo.ubicacion.nombre if equipo.ubicacion else ''],
        ['Descripción', equipo.descripcion or ''],
    ]
    table = Table(equipo_data, colWidths=[120, 360])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f3f4f6')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    # Intervenciones (OTs)
    story.append(Paragraph('<b>Intervenciones / Historial de OT</b>', styles['Heading2']))
    story.append(Spacer(1, 8))

    data = [['Nº OT', 'Fecha', 'Responsable', 'Tipo / Estado', 'Observación']]
    for ot in ots:
        fecha = ot.fecha_actividad.strftime('%d/%m/%Y') if ot.fecha_actividad else ''
        responsable = ot.tecnico_asignado or (ot.solicitud.solicitado_por if hasattr(ot, 'solicitud') else '')
        estado = ot.estado.nombre if ot.estado else ''
        observacion = ''
        # Intentar extraer observación desde cierre si existe
        try:
            cierre = ot.cierreot
            observacion = cierre.observaciones or ''
        except Exception:
            observacion = ''
        data.append([f"OT-{ot.solicitud.consecutivo}", fecha, responsable, estado, observacion])

    ot_table = Table(data, colWidths=[70, 80, 120, 100, 110])
    ot_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(ot_table)

    doc.build(story)
    buffer.seek(0)

    filename = f"hoja_vida_{equipo.codigo or equipo.id}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)
