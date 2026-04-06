# gestion_mantenimiento/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('solicitudes/', include('solicitudes.urls')),
    path('users/', include('users.urls')),
    path('accounts/', include('allauth.urls')),  # Asegúrate de incluir esta línea
    path('Activos/', include('Activos.urls')),
    path('Gestion_ot/', include('Gestion_ot.urls')),
    path('', lambda request: redirect('accounts/login/', permanent=False)),  # Redirige la raíz al login
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
