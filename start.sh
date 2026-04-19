#!/bin/sh
set -ex

echo "STARTUP: running all migrations"
python manage.py migrate --noinput

echo "STARTUP: ensuring default site exists"
python manage.py shell -c "
from django.contrib.sites.models import Site
from django.core.management import call_command

# Ensure default site exists
if not Site.objects.filter(id=1).exists():
    Site.objects.get_or_create(
        id=1,
        defaults={'domain': 'localhost:8000', 'name': 'Gestion Mantenimiento'}
    )
    print('Created default site')
else:
    print('Default site already exists')
"

echo "STARTUP: database path"
DJANGO_SETTINGS_MODULE=gestion_mantenimiento.settings python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_mantenimiento.settings'); django.setup(); from django.conf import settings; print(settings.DATABASES['default'].get('NAME'))"

echo "STARTUP: collecting static files"
python manage.py collectstatic --noinput

echo "STARTUP: launching gunicorn"
exec gunicorn gestion_mantenimiento.wsgi --bind 0.0.0.0:$PORT --workers 1 --threads 2
