from django.urls import path
from . import views
from .views import register, custom_login, dashboard, marcar_asistencia, logout_view

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', custom_login, name='custom_login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('marcar-asistencia/', marcar_asistencia, name='marcar_asistencia'),
    path('logout/', logout_view, name='logout'),
    path('nomina/configuracion/', views.nomina_configuracion, name='nomina_configuracion'),
    path('nomina/configuracion/<int:user_id>/', views.nomina_configurar_tecnico, name='nomina_configurar_tecnico'),
    path('nomina/descuentos/', views.nomina_descuentos, name='nomina_descuentos'),
    path('nomina/descuentos/nuevo/', views.nomina_descuento_form, name='nomina_descuento_nuevo'),
    path('nomina/descuentos/<int:descuento_id>/', views.nomina_descuento_form, name='nomina_descuento_editar'),
    path('nomina/calendario/', views.nomina_calendario, name='nomina_calendario'),
    path('nomina/calendario/nuevo/', views.nomina_calendario_form, name='nomina_calendario_nuevo'),
    path('nomina/calendario/<int:dia_id>/', views.nomina_calendario_form, name='nomina_calendario_editar'),
]