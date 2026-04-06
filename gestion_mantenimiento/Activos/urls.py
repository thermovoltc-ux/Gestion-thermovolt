from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('lista_activos', permanent=False)),  # Redirige /Activos/ a la lista
    path('crear_ubicacion/', views.crear_ubicacion, name='crear_ubicacion'),
    path('crear_equipo/', views.crear_equipo, name='crear_equipo'),
    path('crear_equipo_dinamico/', views.crear_equipo_dinamico, name='crear_equipo_dinamico'),
    path('lista_activos/', views.lista_activos, name='lista_activos'),
    # Otras rutas...
]
