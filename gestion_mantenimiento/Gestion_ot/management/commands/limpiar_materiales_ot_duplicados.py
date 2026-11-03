from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from gestion_mantenimiento.Gestion_ot.models import MaterialOT


class Command(BaseCommand):
    help = (
        'Detecta líneas MaterialOT idénticas sin foto ni observaciones. '
        'Solo las elimina si se indica --apply.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Elimina cada repetición exacta y conserva la línea con menor ID.',
        )

    def handle(self, *args, **options):
        sin_adjuntos_ni_notas = (
            (Q(foto_factura='') | Q(foto_factura__isnull=True))
            & (Q(observaciones='') | Q(observaciones__isnull=True))
        )
        grupos = list(
            MaterialOT.objects.filter(sin_adjuntos_ni_notas)
            .values(
                'orden_trabajo_id',
                'material_id',
                'cantidad',
                'costo_real',
                'precio_venta_aplicado',
            )
            .annotate(cantidad_registros=Count('pk'))
            .filter(cantidad_registros__gt=1)
            .order_by(
                'orden_trabajo_id',
                'material_id',
                'cantidad',
                'costo_real',
                'precio_venta_aplicado',
            )
        )

        filas_eliminadas = 0
        for grupo in grupos:
            lineas = MaterialOT.objects.filter(
                orden_trabajo_id=grupo['orden_trabajo_id'],
                material_id=grupo['material_id'],
                cantidad=grupo['cantidad'],
                costo_real=grupo['costo_real'],
                precio_venta_aplicado=grupo['precio_venta_aplicado'],
            ).filter(sin_adjuntos_ni_notas)

            if options['apply']:
                with transaction.atomic():
                    ids = list(
                        lineas.select_for_update()
                        .order_by('pk')
                        .values_list('pk', flat=True)
                    )
                    duplicados = ids[1:]
                    if duplicados:
                        MaterialOT.objects.filter(pk__in=duplicados).delete()
                        filas_eliminadas += len(duplicados)
            else:
                ids = list(lineas.order_by('pk').values_list('pk', flat=True))
                duplicados = ids[1:]

            if duplicados:
                accion = 'Eliminadas' if options['apply'] else 'Se eliminarían'
                self.stdout.write(
                    f"{accion} IDs {duplicados}; se conserva ID {ids[0]} "
                    f"(OT {grupo['orden_trabajo_id']}, "
                    f"material {grupo['material_id']})."
                )

        if options['apply']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Filas duplicadas eliminadas: {filas_eliminadas}.'
                )
            )
        else:
            self.stdout.write(
                f'Filas duplicadas detectadas: {sum(g["cantidad_registros"] - 1 for g in grupos)}. '
                'No se modificó ningún registro. Usa --apply para eliminar las repeticiones exactas.'
            )
