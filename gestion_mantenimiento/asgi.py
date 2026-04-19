"""
ASGI config for gestion_mantenimiento project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import sys
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from gestion_mantenimiento.routing import websocket_urlpatterns

project_root = os.path.dirname(os.path.dirname(__file__))

sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_mantenimiento.settings')

# Ensure migrations are applied when the ASGI app starts.
try:
    from django import setup as django_setup
    from django.core.management import call_command

    django_setup()
    call_command('migrate', '--noinput')
    call_command('migrate', 'sites', '--noinput')

    from django.conf import settings
    from django.contrib.sites.models import Site

    if not Site.objects.filter(pk=settings.SITE_ID).exists():
        Site.objects.create(
            pk=settings.SITE_ID,
            domain=os.environ.get('SITE_DOMAIN', 'localhost'),
            name='Default Site',
        )
except Exception as exc:
    print('ASGI startup migration error:', exc, file=sys.stderr)
    raise

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns),
    ),
})


