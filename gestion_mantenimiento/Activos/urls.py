from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('lista_activos', permanent=False)),  # Redirige /Activos/ a la lista
    path('crear_ubicacion/', views.crear_ubicacion, name='crear_ubicacion'),
    path('editar_ubicacion/<int:ubicacion_id>/', views.editar_ubicacion, name='editar_ubicacion'),
    path('crear_equipo/', views.crear_equipo, name='crear_equipo'),
    path('editar_equipo/<int:equipo_id>/', views.editar_equipo, name='editar_equipo'),
    path('crear_equipo_dinamico/', views.crear_equipo_dinamico, name='crear_equipo_dinamico'),
    path('lista_activos/', views.lista_activos, name='lista_activos'),
    path('hoja_vida/<int:equipo_id>/', views.hoja_vida_equipo, name='hoja_vida_equipo'),
    path('zip_hojas_vida/<int:ubicacion_id>/', views.descargar_hojas_vida_ubicacion, name='descargar_hojas_vida_ubicacion'),
    # Otras rutas...
]
