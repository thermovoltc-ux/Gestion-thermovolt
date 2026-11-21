from django.urls import path

from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('', views.lista_notificaciones, name='lista'),
    path(
        '<int:notificacion_id>/abrir/',
        views.eliminar_y_redirigir,
        name='eliminar_y_redirigir',
    ),
    path('marcar-todas-leidas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('contador-no-leidas/', views.contador_no_leidas, name='contador_no_leidas'),
]
