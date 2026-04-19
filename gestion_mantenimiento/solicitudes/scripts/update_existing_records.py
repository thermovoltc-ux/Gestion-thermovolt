# scripts/update_existing_records.py

import os
import django

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_mantenimiento.settings')
django.setup()

from gestion_mantenimiento.solicitudes.models import OrdenTrabajo, Solicitud

def update_existing_records():
    # Obtener todas las órdenes de trabajo
    ordenes_trabajo = OrdenTrabajo.objects.all()

    for ot in ordenes_trabajo:
        try:
            # Obtener la solicitud asociada
            solicitud = Solicitud.objects.get(consecutivo=ot.solicitud.consecutivo)
            ot.solicitud = solicitud
            ot.save()
            print(f"Actualizado OT-{ot.id} con Solicitud-{solicitud.consecutivo}")
        except Solicitud.DoesNotExist:
            print(f"Solicitud no encontrada para OT-{ot.id}")

if __name__ == "__main__":
    update_existing_records()