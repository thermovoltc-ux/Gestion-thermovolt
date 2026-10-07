from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import RegistroAsistencia


class RegistroAsistenciaTests(TestCase):
    def test_calcula_horas_trabajadas_automaticamente(self):
        user = get_user_model().objects.create_user(
            username='tecnico-prueba',
            password='test-password',
        )
        now = timezone.now()
        registro = RegistroAsistencia.objects.create(
            usuario=user,
            fecha=now.date(),
            hora_entrada=now - timedelta(hours=8),
            hora_salida=now,
        )

        self.assertEqual(registro.horas_trabajadas, 8.0)

    def test_no_calcula_horas_sin_entrada_y_salida(self):
        user = get_user_model().objects.create_user(
            username='tecnico-sin-horas',
            password='test-password',
        )
        registro = RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.now().date(),
        )

        self.assertIsNone(registro.horas_trabajadas)
