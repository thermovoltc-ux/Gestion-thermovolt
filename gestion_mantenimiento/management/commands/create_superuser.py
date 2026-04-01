from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Create superuser if it does not exist'

    def handle(self, *args, **options):
        if not User.objects.filter(username='juanesteban01010').exists():
            User.objects.create_superuser(
                username='juanesteban01010',
                email='juanesteban01010@example.com',
                password='r3g1n4jK'
            )
            self.stdout.write(self.style.SUCCESS('Superuser created successfully'))
        else:
            user = User.objects.get(username='juanesteban01010')
            user.set_password('r3g1n4jK')
            user.save()
            self.stdout.write(self.style.SUCCESS('Superuser password updated'))