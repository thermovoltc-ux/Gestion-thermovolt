"""
Custom adapter for allauth to override Site domain for local development
"""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.sites.models import Site


class LocalhostSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter that forces localhost:8000 as the callback domain
    for development/testing purposes.
    """
    
    def get_app(self, request, provider, client_id=None):
        """Override to use localhost:8000 as callback domain"""
        # Ensure the Site has the correct domain
        site, _ = Site.objects.get_or_create(id=1)
        if site.domain != 'localhost:8000':
            site.domain = 'localhost:8000'
            site.name = 'Gestión de Mantenimiento'
            site.save()
        
        return super().get_app(request, provider, client_id)
    
    def get_callback_url(self, request, app):
        """Return callback URL using localhost:8000"""
        callback = super().get_callback_url(request, app)
        # Replace any incorrect domain with localhost:8000
        callback = callback.replace('example.com', 'localhost:8000')
        return callback
