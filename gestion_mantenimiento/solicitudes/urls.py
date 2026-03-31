from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('lista_solicitudes', permanent=False)),  # Redirige /solicitudes/ a la lista
    path('crear/', views.crear_solicitud, name='crear_solicitud'),
    path('lista-solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),
    path('verificar-solicitud/', views.verificar_solicitud, name='verificar_solicitud'),
    path('get-centro-costo/', views.get_centro_costo, name='get_centro_costo'),
    path('get-equipos-por-area/', views.get_equipos_por_area, name='get_equipos_por_area'),
    path('get-ubicacion-por-codigo/', views.get_ubicacion_por_codigo, name='get-ubicacion-por-codigo'),
    path('get-numero-activo/', views.get_numero_activo, name='get_numero_activo'),
    path('get-ubicacion-equipos/', views.get_ubicacion_equipos, name='get_ubicacion_equipos'),
    path('get-equipo-por-codigo/', views.get_equipo_por_codigo, name='get_equipo_por_codigo'),  # Nueva ruta
]


