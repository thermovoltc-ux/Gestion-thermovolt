#!/bin/bash
# Script de inicialización para Railway

echo "🚀 Iniciando configuración de Gestión de Mantenimiento..."

# Ejecutar migraciones
echo "📦 Ejecutando migraciones..."
python manage.py migrate --noinput

# Crear estados iniciales
echo "🏷️ Creando estados iniciales..."
python manage.py crear_estados

# Crear superusuario en Railway si se configuran las variables de entorno
if [ "$CREATE_SUPERUSER" = "true" ]; then
  echo "👤 Creando superusuario de producción..."
  python manage.py createsuperuser --noinput \
    --username "$DJANGO_SUPERUSER_USERNAME" \
    --email "$DJANGO_SUPERUSER_EMAIL" || echo "Superusuario ya existe o no se pudo crear"
fi

# Recopilar archivos estáticos
echo "📁 Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "✅ Configuración completada!"