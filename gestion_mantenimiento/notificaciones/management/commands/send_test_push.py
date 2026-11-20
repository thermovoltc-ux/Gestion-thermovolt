from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestion_mantenimiento.notificaciones.utils import (
    enviar_push_usuario,
    webpush_configurado,
)


class Command(BaseCommand):
    help = 'Send a test Web Push notification to a user with an active subscription.'

    def add_arguments(self, parser):
        parser.add_argument('username', help='Username of the push recipient.')

    def handle(self, *args, **options):
        username = options['username']
        if not webpush_configurado():
            raise CommandError(
                'Web Push is not configured. Set all VAPID environment variables.'
            )

        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=username, is_active=True)
        except user_model.DoesNotExist as error:
            raise CommandError(
                f'No active user found with username "{username}".'
            ) from error

        sent = enviar_push_usuario(
            user,
            'Prueba de notificaciones',
            'Esta es una notificación push de prueba.',
            '/',
            referencia='send_test_push',
        )
        if not sent:
            raise CommandError(
                'The test push was not sent. Check the user subscription and application logs.'
            )

        self.stdout.write(
            self.style.SUCCESS(
                'Push send call completed. This does not confirm device delivery.'
            )
        )
