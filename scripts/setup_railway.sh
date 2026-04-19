#!/bin/bash
# Script de inicialización para Railway

echo "🚀 Iniciando configuración de Gestión de Mantenimiento..."

# Ejecutar migraciones
echo "📦 Ejecutando migraciones..."
python manage.py migrate --noinput

# Crear superusuario si no existe (opcional - descomenta si quieres)
# echo "👤 Creando superusuario..."
# python manage.py createsuperuser --noinput --username admin --email admin@example.com || echo "Superusuario ya existe"

# Recopilar archivos estáticos
echo "📁 Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "✅ Configuración completada!"