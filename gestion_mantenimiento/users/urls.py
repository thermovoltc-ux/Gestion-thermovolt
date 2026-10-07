from django.urls import path
from .views import register, custom_login, dashboard, marcar_asistencia, logout_view

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', custom_login, name='custom_login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('marcar-asistencia/', marcar_asistencia, name='marcar_asistencia'),
    path('logout/', logout_view, name='logout'),
]