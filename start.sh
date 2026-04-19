#!/bin/sh
set -ex

echo "STARTUP: running all migrations"
python manage.py migrate --noinput

echo "STARTUP: running sites migrations"
python manage.py migrate sites --noinput

echo "STARTUP: database path"
DJANGO_SETTINGS_MODULE=gestion_mantenimiento.settings python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_mantenimiento.settings'); django.setup(); from django.conf import settings; print(settings.DATABASES['default'].get('NAME'))"

echo "STARTUP: collecting static files"
python manage.py collectstatic --noinput

echo "STARTUP: launching gunicorn"
exec gunicorn gestion_mantenimiento.wsgi --bind 0.0.0.0:$PORT --workers 1 --threads 2
