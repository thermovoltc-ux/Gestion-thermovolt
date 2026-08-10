from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from gestion_mantenimiento.Gestion_ot.models import ProcesoInforme
from gestion_mantenimiento.Gestion_ot import views as informe_views


class Command(BaseCommand):
    help = 'Procesa ProcesoInforme pendientes de forma idempotente (worker simple)'

    def add_arguments(self, parser):
        parser.add_argument('--ttl-minutes', type=int, default=30, help='Tiempo (min) para considerar un proceso como abandonado')
        parser.add_argument('--limit', type=int, default=50, help='Número máximo de procesos a procesar en esta ejecución')

    def handle(self, *args, **options):
        ttl_minutes = options.get('ttl_minutes') or 30
        limit = options.get('limit') or 50
        now = timezone.now()
        cutoff = now - timedelta(minutes=ttl_minutes)

        self.stdout.write(f"Buscando procesos pendientes (ACTIVE_STATES) hasta {limit} (ttl={ttl_minutes}m)")

        qs = ProcesoInforme.objects.filter(estado__in=list(ProcesoInforme.ACTIVE_STATES)).order_by('created_at')[:limit]

        for proceso in qs:
            # Si fue iniciado recientemente y no supera el TTL, saltar
            if proceso.started_at and proceso.started_at > cutoff:
                self.stdout.write(f"SALTAR: {proceso.operation_id} started_at={proceso.started_at}")
                continue

            try:
                with transaction.atomic():
                    proc = ProcesoInforme.objects.select_for_update().get(pk=proceso.pk)
                    if proc.email_enviado or proc.estado == ProcesoInforme.ENVIADO:
                        self.stdout.write(f"YA_ENVIADO: {proc.operation_id}")
                        continue

                    # Marcar que este worker toma el procesamiento
                    proc.started_at = timezone.now()
                    proc.save(update_fields=['started_at'])

                self.stdout.write(f"PROCESANDO: {proc.operation_id} estado={proc.estado}")
                # Ejecutar la lógica existente (idempotente por diseño)
                informe_views._procesar_proceso_informe(proc.operation_id)

            except Exception as e:
                self.stderr.write(f"ERROR procesando {proceso.operation_id}: {e}")
                try:
                    p = ProcesoInforme.objects.filter(pk=proceso.pk).first()
                    if p:
                        p.set_state(ProcesoInforme.ERROR, 'Fallo en worker procesar_informes_pendientes', last_error=str(e))
                except Exception:
                    pass

        self.stdout.write('Ejecución finalizada')
