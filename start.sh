#!/bin/sh
set -ex

echo "STARTUP: running all migrations"
python manage.py migrate --noinput

echo "STARTUP: creating initial states"
python manage.py crear_estados

if [ "$CREATE_SUPERUSER" = "true" ]; then
  echo "STARTUP: creating superuser if needed"
  python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if username and email and password:
    user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'is_superuser': True, 'is_staff': True, 'is_active': True})
    if created:
        user.set_password(password)
        user.save()
        print('Superusuario creado:', username)
    else:
        print('Superusuario ya existe:', username, '- no se actualiza')
else:
    print('Superuser vars missing: DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD')
"
fi

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

echo "STARTUP: checking static directories"
echo "Current directory: $(pwd)"
echo "BASE_DIR would be: $(dirname $(dirname $(readlink -f manage.py)))"
echo "Checking if gestion_mantenimiento/static exists:"
ls -la gestion_mantenimiento/static/ 2>/dev/null || echo "Directory gestion_mantenimiento/static/ does not exist"
echo "Checking if static exists:"
ls -la static/ 2>/dev/null || echo "Directory static/ does not exist"
echo "Listing gestion_mantenimiento/static/fullcalendar/lib/:"
ls -la gestion_mantenimiento/static/fullcalendar/lib/ 2>/dev/null | head -5 || echo "Directory not found"
echo "Listing gestion_mantenimiento/static/dist/:"
ls -la gestion_mantenimiento/static/dist/ 2>/dev/null | head -5 || echo "Directory not found"

echo "STARTUP: collecting static files"
python manage.py collectstatic --noinput --clear --verbosity=2

echo "STARTUP: launching gunicorn"
exec gunicorn gestion_mantenimiento.wsgi --bind 0.0.0.0:$PORT --workers 1 --threads 2
