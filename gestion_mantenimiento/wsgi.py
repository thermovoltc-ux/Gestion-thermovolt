"""
WSGI config for gestion_mantenimiento project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(__file__))

sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_mantenimiento.settings')

# Ensure migrations are applied when the WSGI app starts in production.
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
    print('WSGI startup migration error:', exc, file=sys.stderr)
    raise

from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

application = get_wsgi_application()
application = WhiteNoise(application, root=os.path.join(project_root, 'staticfiles'))
