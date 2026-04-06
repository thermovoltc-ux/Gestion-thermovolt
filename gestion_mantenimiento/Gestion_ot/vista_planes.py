"""
Vistas para gestión de planes de mantenimiento preventivo
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, timedelta
from .models import PlanMantenimiento, ActividadMantenimiento, TareaMantenimiento
from Activos.models import Equipo
from .forms import PlanMantenimientoForm, ActividadMantenimientoForm, TareaMantenimientoForm


@login_required
def lista_planes_mantenimiento(request):
    """Lista todos los planes de mantenimiento"""
    equipo_id = request.GET.get('equipo_id')
    
    planes = PlanMantenimiento.objects.all().select_related('equipo').prefetch_related('tareas', 'actividades')
    
    if equipo_id:
        planes = planes.filter(equipo_id=equipo_id)
    
    # Pre-procesar planes para añadir info de tareas
    for plan in planes:
        plan.tareas_pendientes = plan.tareas.filter(estado='pendiente').count()
        plan.tareas_total = plan.tareas.count()
    
    equipos = Equipo.objects.all()
    
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
    
    equipo = None
    if equipo_id:
        equipo = get_object_or_404(Equipo, id=equipo_id)
    
    if request.method == 'POST':
        form = PlanMantenimientoForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            if equipo:
                plan.equipo = equipo
            plan.save()
            # El signal post_save automáticamente genera las tareas
            return redirect(f"{reverse('lista_planes')}?equipo_id={plan.equipo_id}")
    else:
        form = PlanMantenimientoForm(initial={'equipo': equipo})
    
    context = {
        'form': form,
        'equipo': equipo,
        'titulo': 'Crear Plan de Mantenimiento',
    }
    return render(request, 'Gestion_ot/planes/form_plan.html', context)


@login_required
def editar_plan_mantenimiento(request, plan_id):
    """Editar un plan de mantenimiento"""
    plan = get_object_or_404(PlanMantenimiento, id=plan_id)
    
    if request.method == 'POST':
        form = PlanMantenimientoForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            return redirect('detalle_plan', plan_id=plan.id)
    else:
        form = PlanMantenimientoForm(instance=plan)
    
    context = {
        'form': form,
        'plan': plan,
        'titulo': f'Editar Plan: {plan.nombre}',
    }
    return render(request, 'Gestion_ot/planes/form_plan.html', context)


@login_required
def detalle_plan_mantenimiento(request, plan_id):
    """Ver detalles de un plan y sus tareas"""
    plan = get_object_or_404(PlanMantenimiento, id=plan_id)
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
    
    context = {
        'plan': plan,
        'actividades': actividades,
        'tareas_proximas': tareas_proximas,
        'tareas_atrasadas': tareas_atrasadas,
        'total_tareas': tareas.count(),
        'tareas_completadas': tareas.filter(estado='completada').count(),
    }
    return render(request, 'Gestion_ot/planes/detalle_plan.html', context)


@login_required
def agregar_actividad_plan(request, plan_id):
    """Agregar una actividad a un plan"""
    plan = get_object_or_404(PlanMantenimiento, id=plan_id)
    
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
    tareas_preventivas = TareaMantenimiento.objects.filter(
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
    
    tarea = get_object_or_404(TareaMantenimiento, id=tarea_id)
    
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
    plan = get_object_or_404(PlanMantenimiento, id=plan_id)
    equipo_id = plan.equipo_id
    
    if request.method == 'POST':
        plan.delete()
        return redirect(f"{reverse('lista_planes')}?equipo_id={equipo_id}")
    
    context = {'plan': plan}
    return render(request, 'Gestion_ot/planes/confirmar_eliminar.html', context)
