from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
