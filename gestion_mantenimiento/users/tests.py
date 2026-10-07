from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
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
            fecha=timezone.localdate(),
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
            fecha=timezone.localdate(),
        )

        self.assertIsNone(registro.horas_trabajadas)

    def test_dashboard_muestra_botones_de_asistencia_para_tecnico(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-dashboard',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'asistencia-card')
        self.assertContains(response, 'Marcar entrada')
        self.assertContains(response, 'Marcar salida')
        self.assertContains(response, 'Registro de Asistencia')

    def test_marcar_entrada_crea_registro_y_redirige_al_calendario(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.post(
            reverse('marcar_asistencia'),
            {'accion': 'entrada'},
        )

        registro = RegistroAsistencia.objects.get(usuario=user)
        self.assertIsNotNone(registro.hora_entrada)
        self.assertIsNone(registro.hora_salida)
        self.assertRedirects(
            response,
            f"{reverse('listar_ot')}?vista=calendario",
        )

    def test_marcar_salida_completa_el_dia(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-salida',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=8),
        )
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.post(
            reverse('marcar_asistencia'),
            {'accion': 'salida'},
        )

        registro = RegistroAsistencia.objects.get(
            usuario=user,
            fecha=timezone.localdate(),
        )
        self.assertIsNotNone(registro.hora_salida)
        self.assertEqual(registro.horas_trabajadas, 8.0)
        self.assertRedirects(
            response,
            f"{reverse('listar_ot')}?vista=calendario",
        )

    def test_dia_completado_muestra_mensaje(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-completo',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=8),
            hora_salida=timezone.now(),
        )
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.post(
            reverse('marcar_asistencia'),
            {'accion': 'entrada'},
            follow=True,
        )

        self.assertRedirects(
            response,
            f"{reverse('listar_ot')}?vista=calendario",
        )
        self.assertEqual(
            str(list(response.wsgi_request._messages)[0]),
            'Ya completaste el día.',
        )
