#!/bin/sh
set -e  # Detener en primer error

echo "STARTUP: checking and installing dependencies..."

# Update package lists
echo "Actualizando lista de paquetes..."
apt-get update || true

# Instalar dependencias necesarias para LibreOffice
echo "Instalando dependencias del sistema..."
if [ "$SKIP_SYSTEM_PACKAGES" != "true" ]; then
  # Instalar bibliotecas básicas
  apt-get install -y libssl1.1 2>/dev/null || apt-get install -y libssl3 || true
  apt-get install -y libcairo2 libcups2 libdbus-1-3 libfontconfig1 libfreetype6 2>/dev/null || true
fi

# Instalar LibreOffice PASO A PASO
echo "Instalando LibreOffice..."
if [ "$SKIP_SYSTEM_PACKAGES" != "true" ]; then
  echo "  → Instalando libreoffice-core..."
  apt-get install -y --no-install-recommends libreoffice-core 2>&1 | grep -i "setting up\|already\|done" || true
  
  echo "  → Instalando libreoffice-writer..."
  apt-get install -y --no-install-recommends libreoffice-writer 2>&1 | grep -i "setting up\|already\|done" || true
  
  echo "  → Instalando libreoffice-calc..."
  apt-get install -y --no-install-recommends libreoffice-calc 2>&1 | grep -i "setting up\|already\|done" || true
  
  echo "  → Instalando dependencias gráficas mínimas..."
  apt-get install -y libxrender1 libxext6 2>/dev/null || true
fi

# Encontrar y verificar LibreOffice
echo "Buscando LibreOffice..."
LIBREOFFICE_CMD=""

if command -v soffice >/dev/null 2>&1; then
  LIBREOFFICE_CMD="soffice"
  echo "✓ LibreOffice encontrado: soffice"
elif command -v libreoffice >/dev/null 2>&1; then
  LIBREOFFICE_CMD="libreoffice"
  echo "✓ LibreOffice encontrado: libreoffice"
else
  echo "❌ LibreOffice NO se instaló - Se usará fallback con ReportLab"
  LIBREOFFICE_CMD=""
fi

# Configurar LibreOffice
if [ -n "$LIBREOFFICE_CMD" ]; then
  echo "Configurando LibreOffice para modo headless..."
  
  # Crear directorios de configuración
  mkdir -p ~/.config/libreoffice/4/user
  mkdir -p /tmp/libreoffice-lock
  
  # Exportar variables de entorno
  export SAL_USE_VCLPLUGIN=gtk
  export HOME=/app
  
  # Verificar que LibreOffice responde
  echo "Verificando LibreOffice (timeout 10s)..."
  set +e  # No fallar si esto no funciona
  timeout 10 $LIBREOFFICE_CMD --headless --version >/dev/null 2>&1
  RESULT=$?
  set -e
  
  if [ $RESULT -eq 0 ]; then
    echo "✓ LibreOffice verificado y funcionando"
  else
    echo "⚠️ LibreOffice no respondió - pero continuamos"
  fi
else
  echo "ℹ️ Sin LibreOffice - Se usará fallback con ReportLab (PDF básico)"
fi

echo "✓ STARTUP: dependencias configuradas"



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
