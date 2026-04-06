from django.urls import path
from . import views
from . import vista_planes
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('listar_ot', permanent=False)),  # Redirige /Gestion_ot/ a la lista
    path('gestion_ot/', views.gestion_ot, name='gestion_ot'),
    path('actualizar_estado_solicitud/', views.actualizar_estado_solicitud, name='actualizar_estado_solicitud'),
    path('listar_ot/', views.listar_ot, name='listar_ot'),
    path('cierre_ot/<int:ot_id>/', views.cierre_ot, name='cierre_ot'),
    path('detalles_solicitud/<int:consecutivo>/', views.detalles_solicitud, name='detalles_solicitud'),
    
    # Rutas para planes de mantenimiento
    path('planes/', vista_planes.lista_planes_mantenimiento, name='lista_planes'),
    path('planes/crear/', vista_planes.crear_plan_mantenimiento, name='crear_plan'),
    path('planes/crear/<int:equipo_id>/', vista_planes.crear_plan_mantenimiento, name='crear_plan_equipo'),
    path('planes/<int:plan_id>/', vista_planes.detalle_plan_mantenimiento, name='detalle_plan'),
    path('planes/<int:plan_id>/editar/', vista_planes.editar_plan_mantenimiento, name='editar_plan'),
    path('planes/<int:plan_id>/eliminar/', vista_planes.eliminar_plan_mantenimiento, name='eliminar_plan'),
    path('planes/<int:plan_id>/actividad/', vista_planes.agregar_actividad_plan, name='agregar_actividad'),
    path('actividades-proximas/', vista_planes.listar_actividades_proximas, name='actividades_proximas'),
    path('tarea/<int:tarea_id>/actualizar/', vista_planes.actualizar_tarea_mantenimiento, name='actualizar_tarea'),
    path('tarea/<int:tarea_id>/asignar/', views.asignar_tarea_preventiva, name='asignar_tarea_preventiva'),
]
