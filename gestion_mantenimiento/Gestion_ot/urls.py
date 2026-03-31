from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('listar_ot', permanent=False)),  # Redirige /Gestion_ot/ a la lista
    path('gestion_ot/', views.gestion_ot, name='gestion_ot'),
    path('actualizar_estado_solicitud/', views.actualizar_estado_solicitud, name='actualizar_estado_solicitud'),
    path('listar_ot/', views.listar_ot, name='listar_ot'),
    path('cierre_ot/<int:ot_id>/', views.cierre_ot, name='cierre_ot'),
    path('detalles_solicitud/<int:consecutivo>/', views.detalles_solicitud, name='detalles_solicitud'),


]
