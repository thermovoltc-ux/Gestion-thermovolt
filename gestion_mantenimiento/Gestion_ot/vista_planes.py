"""
Vistas para gestión de planes de mantenimiento preventivo
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import date, timedelta
from .models import PlanMantenimiento, ActividadMantenimiento, TareaMantenimiento
from gestion_mantenimiento.Activos.models import Equipo
from .forms import PlanMantenimientoForm, ActividadMantenimientoForm, TareaMantenimientoForm
from gestion_mantenimiento.users.access import obtener_scope_ubicacion_ids


def _scope_ids(request):
    return obtener_scope_ubicacion_ids(request)


def _planes_visibles(request):
    planes = PlanMantenimiento.objects.all()
    scope_ids = _scope_ids(request)
    if scope_ids is not None:
        return planes.filter(equipo__ubicacion_id__in=scope_ids)
    return planes


def _tareas_visibles(request):
    tareas = TareaMantenimiento.objects.all()
    scope_ids = _scope_ids(request)
    if scope_ids is not None:
        return tareas.filter(plan__equipo__ubicacion_id__in=scope_ids)
    return tareas


@login_required
def lista_planes_mantenimiento(request):
    """Lista todos los planes de mantenimiento"""
    equipo_id = request.GET.get('equipo_id')
    
    planes = _planes_visibles(request).select_related('equipo').prefetch_related('tareas', 'actividades')
    
    if equipo_id:
        planes = planes.filter(equipo_id=equipo_id)
    
    # Pre-procesar planes para añadir info de tareas
    for plan in planes:
        plan.tareas_pendientes = plan.tareas.filter(estado='pendiente').count()
        plan.tareas_total = plan.tareas.count()
    
    equipos = Equipo.objects.all()
    scope_ids = _scope_ids(request)
    if scope_ids is not None:
        equipos = equipos.filter(ubicacion_id__in=scope_ids)
    
    context = {
        'planes': planes,
        'equipos': equipos,
        'equipo_id_selected': int(equipo_id) if equipo_id else None,
    }
    return render(request, 'Gestion_ot/planes/lista_planes.html', context)


@login_required
def crear_plan_mantenimiento(request, equipo_id=None):
    """Crear un nuevo plan de mantenimiento"""
    # Obtener equipo_id desde parámetro URL o query string
    if not equipo_id:
        equipo_id = request.GET.get('equipo_id')

    scope_ids = _scope_ids(request)
    if scope_ids is not None and not scope_ids:
        return JsonResponse({'error': 'No tenés ubicaciones autorizadas.'}, status=403)

    equipo = None
    if equipo_id:
        equipos = Equipo.objects.all()
        if scope_ids is not None:
            equipos = equipos.filter(ubicacion_id__in=scope_ids)
        equipo = equipos.filter(id=equipo_id).first()

    error_equipo = None

    if request.method == 'POST':
        form = PlanMantenimientoForm(request.POST, scope_ids=scope_ids)
        if form.is_valid():
            plan = form.save(commit=False)
            # Validar que equipo esté presente
            if not form.cleaned_data.get('equipo') and not equipo:
                error_equipo = 'Debe seleccionar un equipo.'
            else:
                # Prioridad: lo que viene del form
                plan.equipo = form.cleaned_data.get('equipo') or equipo
                plan.save()
                # El signal post_save automáticamente genera las tareas
                return redirect(f"{reverse('lista_planes')}?equipo_id={plan.equipo_id}")
    else:
        form = PlanMantenimientoForm(
            initial={'equipo': equipo},
            scope_ids=scope_ids,
        )

    context = {
        'form': form,
        'equipo': equipo,
        'titulo': 'Crear Plan de Mantenimiento',
        'error_equipo': error_equipo,
    }
    return render(request, 'Gestion_ot/planes/form_plan.html', context)


@login_required
def editar_plan_mantenimiento(request, plan_id):
    """Editar un plan de mantenimiento"""
    plan = get_object_or_404(_planes_visibles(request), id=plan_id)
    
    if request.method == 'POST':
        form = PlanMantenimientoForm(
            request.POST,
            instance=plan,
            scope_ids=_scope_ids(request),
        )
        if form.is_valid():
            form.save()
            return redirect('detalle_plan', plan_id=plan.id)
    else:
        form = PlanMantenimientoForm(instance=plan, scope_ids=_scope_ids(request))
    
    context = {
        'form': form,
        'plan': plan,
        'titulo': f'Editar Plan: {plan.nombre}',
    }
    return render(request, 'Gestion_ot/planes/form_plan.html', context)


@login_required
def detalle_plan_mantenimiento(request, plan_id):
    """Ver detalles de un plan y sus tareas"""
    plan = get_object_or_404(_planes_visibles(request), id=plan_id)
    actividades = plan.actividades.all()
    tareas = plan.tareas.all()
    
    # Tareas pendientes/próximas
    hoy = date.today()
    tareas_proximas = tareas.filter(
        fecha_programada__gte=hoy,
        estado__in=['pendiente', 'en_progreso']
    ).order_by('fecha_programada')[:10]
    
    tareas_atrasadas = tareas.filter(
        fecha_programada__lt=hoy,
        estado__in=['pendiente', 'en_progreso']
    ).order_by('fecha_programada')
    
    tareas_completadas = tareas.filter(estado__in=['completada', 'convertido']).count()
    tareas_convertidas = tareas.filter(estado='convertido').count()

    tecnicos = User.objects.filter(groups__name='Tecnico')

    context = {
        'plan': plan,
        'actividades': actividades,
        'tareas_proximas': tareas_proximas,
        'tareas_atrasadas': tareas_atrasadas,
        'total_tareas': tareas.count(),
        'tareas_completadas': tareas_completadas,
        'tareas_convertidas': tareas_convertidas,
        'tecnicos': tecnicos,
    }
    return render(request, 'Gestion_ot/planes/detalle_plan.html', context)


@login_required
def agregar_actividad_plan(request, plan_id):
    """Agregar una actividad a un plan"""
    plan = get_object_or_404(_planes_visibles(request), id=plan_id)
    
    if request.method == 'POST':
        form = ActividadMantenimientoForm(request.POST)
        if form.is_valid():
            actividad = form.save(commit=False)
            actividad.plan = plan
            actividad.save()
            return redirect('detalle_plan', plan_id=plan.id)
    else:
        form = ActividadMantenimientoForm()
    
    context = {
        'form': form,
        'plan': plan,
        'titulo': f'Agregar Actividad a {plan.nombre}',
    }
    return render(request, 'Gestion_ot/planes/form_actividad.html', context)


@login_required
def listar_actividades_proximas(request):
    """
    Panel de próximas actividades por día
    Integra tanto tareas preventivas como OT correctivas
    """
    hoy = date.today()
    dias_adelante = int(request.GET.get('dias', 30))
    
    # Tareas de mantenimiento preventivo
    tareas_preventivas = _tareas_visibles(request).filter(
        fecha_programada__gte=hoy,
        fecha_programada__lt=hoy + timedelta(days=dias_adelante),
        estado__in=['pendiente', 'en_progreso']
    ).select_related('plan', 'plan__equipo', 'tecnico', 'actividad').order_by('fecha_programada')
    
    # Agrupar por día
    actividades_por_dia = {}
    for tarea in tareas_preventivas:
        dia = tarea.fecha_programada
        if dia not in actividades_por_dia:
            actividades_por_dia[dia] = {'tareas_preventivas': [], 'ordenes_trabajo': []}
        actividades_por_dia[dia]['tareas_preventivas'].append(tarea)
    
    # Ordenar días
    dias_ordenados = sorted(actividades_por_dia.keys())
    
    context = {
        'actividades_por_dia': actividades_por_dia,
        'dias_ordenados': dias_ordenados,
        'dias_adelante': dias_adelante,
        'hoy': hoy,
    }
    return render(request, 'Gestion_ot/planes/actividades_proximas.html', context)


@login_required
def actualizar_tarea_mantenimiento(request, tarea_id):
    """Actualizar estado de una tarea de mantenimiento (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    tarea = get_object_or_404(_tareas_visibles(request), id=tarea_id)
    
    nuevo_estado = request.POST.get('estado')
    tecnico_id = request.POST.get('tecnico_id')
    observaciones = request.POST.get('observaciones', '')
    
    if nuevo_estado in dict(TareaMantenimiento.ESTADO_CHOICES):
        tarea.estado = nuevo_estado
    
    if tecnico_id:
        tarea.tecnico_id = int(tecnico_id)
    
    if observaciones:
        tarea.observaciones = observaciones
    
    if nuevo_estado == 'completada':
        tarea.fecha_ejecutada = timezone.now().date()
    
    tarea.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Tarea actualizada a {tarea.get_estado_display()}',
        'tarea': {
            'id': tarea.id,
            'estado': tarea.estado,
            'fecha_ejecutada': str(tarea.fecha_ejecutada) if tarea.fecha_ejecutada else None,
        }
    })


@login_required
def eliminar_plan_mantenimiento(request, plan_id):
    """Eliminar un plan de mantenimiento"""
    plan = get_object_or_404(_planes_visibles(request), id=plan_id)
    equipo_id = plan.equipo_id
    
    if request.method == 'POST':
        plan.delete()
        return redirect(f"{reverse('lista_planes')}?equipo_id={equipo_id}")
    
    context = {'plan': plan}
    return render(request, 'Gestion_ot/planes/confirmar_eliminar.html', context)
