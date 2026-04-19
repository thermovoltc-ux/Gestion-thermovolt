# gestion_mantenimiento/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('solicitudes/', include('gestion_mantenimiento.solicitudes.urls')),
    path('users/', include('gestion_mantenimiento.users.urls')),
    path('accounts/login/', lambda request: redirect('custom_login', permanent=False)),
    path('accounts/', include('allauth.urls')),  # Asegúrate de incluir esta línea
    path('Activos/', include('gestion_mantenimiento.Activos.urls')),
    path('Gestion_ot/', include('gestion_mantenimiento.Gestion_ot.urls')),
    path('', lambda request: redirect('custom_login', permanent=False)),  # Redirige la raíz al login personalizado
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
