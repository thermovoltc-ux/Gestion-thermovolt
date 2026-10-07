from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import Estado, OrdenTrabajo
from gestion_mantenimiento.solicitudes.models import Solicitud

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
        self.assertNotContains(response, 'Marcar salida')
        self.assertContains(response, 'Registro de Asistencia')

    def test_dashboard_muestra_solo_la_accion_correspondiente_al_estado(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-estados',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Marcar salida')
        self.assertNotContains(response, 'Marcar entrada')

        RegistroAsistencia.objects.filter(usuario=user).update(
            hora_salida=timezone.now(),
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Jornada completa')
        self.assertNotContains(response, 'Marcar entrada')
        self.assertNotContains(response, 'Marcar salida')

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
            f"{reverse('listar_ot')}?vista=calendario&tecnico={user.username}",
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
            f"{reverse('listar_ot')}?vista=calendario&tecnico={user.username}",
        )

    def test_calendario_filtra_ots_por_tecnico(self):
        user = get_user_model().objects.create_user(
            username='Hiller01',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        ubicacion = Ubicacion.objects.create(
            nombre='Ubicación prueba',
            codigo='UBI-01',
        )
        equipo = Equipo.objects.create(
            nombre='Equipo prueba',
            codigo='EQ-01',
            ubicacion=ubicacion,
        )
        estado = Estado.objects.get_or_create(nombre='solicitado')[0]
        solicitud_hiller = Solicitud.objects.create(
            creado_por=user.username,
            descripcion_problema='OT de Hiller01',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        solicitud_otero = Solicitud.objects.create(
            creado_por=user.username,
            descripcion_problema='OT de otro técnico',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        OrdenTrabajo.objects.create(
            solicitud= solicitud_hiller,
            tecnico_asignado='Hiller01',
            fecha_actividad=timezone.now(),
            estado=estado,
        )
        OrdenTrabajo.objects.create(
            solicitud= solicitud_otero,
            tecnico_asignado='Otro Tecnico',
            fecha_actividad=timezone.now(),
            estado=estado,
        )

        response = self.client.get(
            reverse('listar_ot'),
            {'vista': 'calendario', 'tecnico': 'Hiller01'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ots'].count(), 1)
        self.assertEqual(response.context['ots'].first().tecnico_asignado, 'Hiller01')

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
            f"{reverse('listar_ot')}?vista=calendario&tecnico={user.username}",
        )
        self.assertEqual(
            str(list(response.wsgi_request._messages)[0]),
            'Ya completaste el día.',
        )


class DashboardTecnicoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tecnico-dashboard-h3',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(self.user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

    def test_dashboard_muestra_resumen_semanal(self):
        RegistroAsistencia.objects.create(
            usuario=self.user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=4),
            hora_salida=timezone.now(),
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('horas_semana', response.context)
        self.assertGreaterEqual(response.context['horas_semana'], 4)
        self.assertContains(response, 'Esta semana')

    def test_dashboard_muestra_historial_asistencia(self):
        RegistroAsistencia.objects.create(
            usuario=self.user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=4),
            hora_salida=timezone.now(),
        )

        response = self.client.get(reverse('dashboard'))

        self.assertIn('historial_asistencia', response.context)
        self.assertGreaterEqual(len(response.context['historial_asistencia']), 1)
        self.assertContains(response, 'Últimos 7 días')

    def test_dashboard_muestra_agenda_de_hoy(self):
        ubicacion = Ubicacion.objects.create(
            nombre='Ubicación prueba',
            codigo='UBI-H3',
        )
        equipo = Equipo.objects.create(
            nombre='Equipo prueba',
            codigo='EQ-H3',
            ubicacion=ubicacion,
        )
        estado = Estado.objects.get_or_create(nombre='en proceso')[0]
        solicitud = Solicitud.objects.create(
            creado_por=self.user.username,
            descripcion_problema='Agenda del técnico',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        OrdenTrabajo.objects.create(
            solicitud= solicitud,
            tecnico_asignado=self.user.username,
            fecha_actividad=timezone.now(),
            estado=estado,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertIn('ots_hoy', response.context)
        self.assertGreaterEqual(len(response.context['ots_hoy']), 1)
        self.assertContains(response, 'Mi agenda de hoy')
        self.assertContains(response, 'OT-')
