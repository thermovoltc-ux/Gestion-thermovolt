# Railway Procfile
web: python manage.py collectstatic --noinput && gunicorn gestion_mantenimiento.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 2