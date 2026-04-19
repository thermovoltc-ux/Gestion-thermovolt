from django.core.management.base import BaseCommand
from gestion_mantenimiento.Gestion_ot.models import Estado

class Command(BaseCommand):
    help = 'Crea los estados iniciales para las OT'

    def handle(self, *args, **options):
        estados = [
            ('solicitado', 'Solicitado'),
            ('en proceso', 'OT en Proceso'),
            ('en revision', 'OT en Revisión'),
            ('finalizada', 'OT Finalizada')
        ]

        for nombre, descripcion in estados:
            estado, created = Estado.objects.get_or_create(
                nombre=nombre,
                defaults={'nombre': nombre}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Estado "{descripcion}" creado')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Estado "{descripcion}" ya existe')
                )