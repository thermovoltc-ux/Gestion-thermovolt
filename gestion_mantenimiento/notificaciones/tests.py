from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from webpush.models import PushInformation, SubscriptionInfo

from .models import Notificacion
from .utils import crear_notificacion


class NotificacionViewsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='notifications-owner',
            password='test-password',
        )
        self.other_user = user_model.objects.create_user(
            username='notifications-other',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.own_unread = crear_notificacion(
            self.user,
            Notificacion.SOLICITUD,
            'Nueva solicitud',
            'Hay una solicitud nueva.',
            reverse('lista_solicitudes'),
        )
        self.own_read = crear_notificacion(
            self.user,
            Notificacion.MANTENIMIENTO_PREVENTIVO,
            'Preventivo',
            'Se programó mantenimiento.',
        )
        self.own_read.leida = True
        self.own_read.save(update_fields=['leida'])
        self.foreign_unread = crear_notificacion(
            self.other_user,
            Notificacion.STOCK_BAJO,
            'Stock bajo',
            'Existencia baja.',
        )

    def test_list_shows_only_notifications_for_authenticated_user(self):
        response = self.client.get(reverse('notificaciones:lista'))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            list(response.context['notificaciones']),
            [self.own_unread, self.own_read],
        )
        self.assertContains(response, 'Nueva solicitud')
        self.assertNotContains(response, 'Existencia baja.')

    def test_list_can_filter_by_notification_type(self):
        response = self.client.get(
            reverse('notificaciones:lista'),
            {'tipo': Notificacion.MANTENIMIENTO_PREVENTIVO},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['notificaciones']),
            [self.own_read],
        )

    @override_settings(WEBPUSH_SETTINGS={
        'VAPID_PUBLIC_KEY': 'public-key',
        'VAPID_PRIVATE_KEY': 'private-key',
        'VAPID_ADMIN_EMAIL': 'admin@example.com',
    })
    def test_list_renders_push_subscription_controls_when_configured(self):
        response = self.client.get(reverse('notificaciones:lista'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'webpush-subscribe-button')
        self.assertContains(response, 'service-worker-js')

    def test_unread_counter_only_counts_current_users_notifications(self):
        response = self.client.get(reverse('notificaciones:contador_no_leidas'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'count': 1})
        self.assertIn('no-store', response['Cache-Control'])

    def test_mark_all_read_updates_only_current_users_notifications(self):
        response = self.client.post(reverse('notificaciones:marcar_todas_leidas'))

        self.assertRedirects(response, reverse('notificaciones:lista'))
        self.own_unread.refresh_from_db()
        self.foreign_unread.refresh_from_db()
        self.assertTrue(self.own_unread.leida)
        self.assertFalse(self.foreign_unread.leida)


class NotificacionPushTests(TestCase):
    @override_settings(WEBPUSH_SETTINGS={
        'VAPID_PUBLIC_KEY': 'public-key',
        'VAPID_PRIVATE_KEY': 'private-key',
        'VAPID_ADMIN_EMAIL': 'admin@example.com',
    })
    @patch('gestion_mantenimiento.notificaciones.utils.send_user_notification')
    def test_creating_notification_sends_push_after_commit(self, send_push):
        user = get_user_model().objects.create_user(
            username='push-notification-user',
        )
        subscription = SubscriptionInfo.objects.create(
            browser='Chrome',
            endpoint='https://push.example.test/subscription',
            auth='auth-secret',
            p256dh='public-key',
        )
        PushInformation.objects.create(user=user, subscription=subscription)
        with self.assertLogs(
            'gestion_mantenimiento.notificaciones.utils',
            level='INFO',
        ) as logs:
            with self.captureOnCommitCallbacks(execute=True):
                notification = crear_notificacion(
                    user,
                    Notificacion.SOLICITUD,
                    'Nueva solicitud',
                    'Se creó una solicitud.',
                    '/solicitudes/',
                )

        send_push.assert_called_once_with(
            user=user,
            payload={
                'head': 'Nueva solicitud',
                'body': 'Se creó una solicitud.',
                'url': '/solicitudes/',
            },
            ttl=86400,
        )
        self.assertEqual(notification.usuario, user)
        self.assertTrue(any('[PUSH] Iniciando envío' in line for line in logs.output))
        self.assertTrue(
            any('[PUSH] send_user_notification terminó sin excepción' in line for line in logs.output)
        )

    @override_settings(WEBPUSH_SETTINGS={
        'VAPID_PUBLIC_KEY': 'public-key',
        'VAPID_PRIVATE_KEY': 'private-key',
        'VAPID_ADMIN_EMAIL': 'admin@example.com',
    })
    @patch(
        'gestion_mantenimiento.notificaciones.utils.send_user_notification',
        side_effect=RuntimeError('test send error'),
    )
    def test_push_failure_is_logged_and_reported(self, send_push):
        user = get_user_model().objects.create_user(
            username='push-failure-user',
        )
        subscription = SubscriptionInfo.objects.create(
            browser='Chrome',
            endpoint='https://push.example.test/subscription',
            auth='auth-secret',
            p256dh='public-key',
        )
        PushInformation.objects.create(user=user, subscription=subscription)

        with self.assertLogs(
            'gestion_mantenimiento.notificaciones.utils',
            level='ERROR',
        ) as logs:
            with self.captureOnCommitCallbacks(execute=True):
                crear_notificacion(
                    user,
                    Notificacion.SOLICITUD,
                    'Falla esperada',
                    'Mensaje de prueba.',
                )

        self.assertTrue(
            any('[PUSH] Falló send_user_notification' in line for line in logs.output)
        )
        send_push.assert_called_once()

    @override_settings(WEBPUSH_SETTINGS={
        'VAPID_PUBLIC_KEY': 'public-key',
        'VAPID_PRIVATE_KEY': 'private-key',
        'VAPID_ADMIN_EMAIL': 'admin@example.com',
    })
    @patch(
        'gestion_mantenimiento.notificaciones.management.commands.'
        'send_test_push.enviar_push_usuario',
        return_value=True,
    )
    def test_send_test_push_command_targets_username(self, send_push):
        user = get_user_model().objects.create_user(
            username='push-command-user',
        )
        output = StringIO()

        call_command('send_test_push', user.username, stdout=output)

        send_push.assert_called_once_with(
            user,
            'Prueba de notificaciones',
            'Esta es una notificación push de prueba.',
            '/',
            referencia='send_test_push',
        )
        self.assertIn('does not confirm device delivery', output.getvalue())
