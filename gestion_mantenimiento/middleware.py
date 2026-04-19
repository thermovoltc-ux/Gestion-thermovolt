"""
Middleware para redirigir 127.0.0.1 a localhost para Google OAuth
y registrar providers de OAuth en la primera solicitud
"""
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
import os
import sys


class LocalhostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._oauth_initialized = False

    def __call__(self, request):
        # Si el request viene de 127.0.0.1, reemplazar con localhost
        if request.META.get('HTTP_HOST', '').startswith('127.0.0.1'):
            request.META['HTTP_HOST'] = 'localhost:8000'
        
        # Inicializar OAuth apps en la primera solicitud
        if not self._oauth_initialized:
            self._initialize_oauth_apps()
            self._oauth_initialized = True
        
        response = self.get_response(request)
        return response
    
    def _initialize_oauth_apps(self):
        """Registra los providers de OAuth en la base de datos"""
        try:
            # Asegurar que el Site existe y tiene el dominio correcto
            site, _ = Site.objects.get_or_create(id=1)
            if site.domain != 'localhost:8000':
                site.domain = 'localhost:8000'
                site.name = 'Gestión de Mantenimiento'
                site.save()
            
            # Registrar Google OAuth
            google_client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
            google_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
            
            if google_client_id and google_secret:
                google_app, _ = SocialApp.objects.get_or_create(
                    provider='google',
                    defaults={
                        'name': 'Google',
                        'client_id': google_client_id,
                        'secret': google_secret,
                    }
                )
                
                # Actualizar si los valores cambiaron
                if google_app.client_id != google_client_id or google_app.secret != google_secret:
                    google_app.client_id = google_client_id
                    google_app.secret = google_secret
                    google_app.save()
                
                # Asegurar que está asociado con el site
                if site not in google_app.sites.all():
                    google_app.sites.add(site)
                
                print("✅ Google OAuth configurado correctamente en middleware")
        except Exception as e:
            # Silenciosamente fallar en caso de error de BD
            pass
