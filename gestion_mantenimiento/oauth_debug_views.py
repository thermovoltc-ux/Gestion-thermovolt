from django.shortcuts import render
from django.conf import settings
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
import os


def oauth_debug(request):
    """Debug view para verificar la configuración de OAuth"""
    site = Site.objects.get_or_create(id=1)[0]
    
    try:
        google_app = SocialApp.objects.get(provider='google')
        has_client_id = bool(google_app.client_id)
        has_secret = bool(google_app.secret)
    except SocialApp.DoesNotExist:
        google_app = None
        has_client_id = False
        has_secret = False
    
    context = {
        'SITE_ID': settings.SITE_ID,
        'site_domain': site.domain,
        'has_client_id': has_client_id,
        'has_secret': has_secret,
        'google_app': google_app,
        'settings_google_client_id': os.environ.get('GOOGLE_CLIENT_ID', '')[:20] + '...',
        'settings_google_secret': os.environ.get('GOOGLE_CLIENT_SECRET', '')[:20] + '...',
    }
    
    return render(request, 'oauth_debug.html', context)
