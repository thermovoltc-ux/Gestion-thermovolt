from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from types import SimpleNamespace
from unittest.mock import patch

from gestion_mantenimiento.solicitudes.models import Solicitud
from gestion_mantenimiento.Gestion_ot.models import Estado
from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.solicitudes.forms import SolicitudForm
from gestion_mantenimiento.solicitudes.utils import enviar_correo_solicitud


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EnviarCorreoSolicitudTests(TestCase):
    def setUp(self):
        self.solicitud = SimpleNamespace(
            consecutivo=42,
            ubicacion_nombre='<Sede prueba>',
            co='CO-42',
            fecha_creacion=None,
            estado=SimpleNamespace(nombre='solicitado'),
            equipo=SimpleNamespace(nombre='Equipo prueba'),
            email_solicitante='cliente@example.com',
        )

    def test_sends_html_and_plain_text_with_inline_logo(self):
        enviado = enviar_correo_solicitud(
            self.solicitud,
            'asignacion',
            cuerpo_extra='Técnico asignado: Ana',
        )

        self.assertTrue(enviado)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.subject, '[Solicitud #42] - <Sede prueba> - CO CO-42')
        self.assertIn('Técnico asignado: Ana', mensaje.body)
        self.assertEqual(len(mensaje.alternatives), 1)
        html, content_type = mensaje.alternatives[0]
        self.assertEqual(content_type, 'text/html')
        self.assertIn('Notificación de Solicitud', html)
        self.assertIn('Técnico asignado', html)
        self.assertIn('&lt;Sede prueba&gt;', html)
        self.assertIn('cid:thermovolt-logo', html)
        self.assertEqual(len(mensaje.attachments), 1)
        self.assertEqual(mensaje.attachments[0].get('Content-ID'), '<thermovolt-logo>')

    def test_report_email_remains_plain_text_without_attachments(self):
        enviado = enviar_correo_solicitud(
            self.solicitud,
            'informe',
            cuerpo_extra='Informe disponible: https://example.com/informe.pdf',
        )

        self.assertTrue(enviado)
        mensaje = mail.outbox[0]
        self.assertIn('https://example.com/informe.pdf', mensaje.body)
        self.assertEqual(mensaje.alternatives, [])
        self.assertEqual(mensaje.attachments, [])


class SolicitudConsecutivoTests(TestCase):
    def setUp(self):
        self.ubicacion = Ubicacion.objects.create(nombre='Ubicación prueba', codigo='UBI-01')
        self.equipo = Equipo.objects.create(nombre='Equipo prueba', codigo='EQ-01', ubicacion=self.ubicacion)
        self.estado = Estado.objects.get_or_create(nombre='solicitado')[0]

    def test_crea_consecutivo_sin_chocar_con_registros_borrados(self):
        Solicitud.objects.create(
            consecutivo=10,
            creado_por='tester',
            descripcion_problema='primera',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
        )
        Solicitud.objects.create(
            consecutivo=11,
            creado_por='tester',
            descripcion_problema='segunda',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
        )

        solicitud = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='tercera',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
        )

        self.assertEqual(solicitud.consecutivo, 12)

    def test_usa_ubicacion_como_fuente_de_verdad_para_pdv_y_co(self):
        self.ubicacion.co = 'CO-99'
        self.ubicacion.save()

        solicitud = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='cuarta',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
            PDV='PDV legacy',
            co='CO legacy',
        )

        self.assertEqual(solicitud.ubicacion_nombre, 'Ubicación prueba')
        self.assertEqual(solicitud.ubicacion_co, 'CO-99')

        solicitud.PDV = 'PDV legacy actualizada'
        solicitud.co = 'CO legacy actualizada'
        solicitud.save()

        self.assertEqual(solicitud.ubicacion_nombre, 'Ubicación prueba')
        self.assertEqual(solicitud.ubicacion_co, 'CO-99')


class SolicitudEquipoActivoTests(TestCase):
    def setUp(self):
        self.ubicacion = Ubicacion.objects.create(
            nombre='Ubicación solicitudes',
            codigo='UBI-SOL-ACTIVA',
        )
        self.equipo = Equipo.objects.create(
            nombre='Equipo solicitudes',
            codigo='EQ-SOL-ACTIVA',
            ubicacion=self.ubicacion,
        )
        self.solicitado, _ = Estado.objects.get_or_create(nombre='solicitado')
        self.finalizada, _ = Estado.objects.get_or_create(nombre='finalizada')

    def _form(self):
        return SolicitudForm(data={
            'creado_por': 'tester',
            'descripcion_problema': 'Prueba de solicitud activa',
            'email_solicitante': 'tester@example.com',
            'equipo': self.equipo.pk,
            'solicitado_por': 'tester',
            'prioridad': 'media',
            'enviar_email': '',
        })

    def test_existing_non_finalized_request_blocks_another_for_same_equipment(self):
        Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Solicitud activa',
            equipo=self.equipo,
            estado=self.solicitado,
        )

        form = self._form()

        self.assertFalse(form.is_valid())
        self.assertIn(
            'Ya existe una solicitud activa para este equipo.',
            str(form.non_field_errors()),
        )

    def test_finalized_request_does_not_block_another_for_same_equipment(self):
        Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Solicitud finalizada',
            equipo=self.equipo,
            estado=self.finalizada,
        )

        form = self._form()

        self.assertTrue(form.is_valid(), form.errors)


class CrearSolicitudCoTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='creador-solicitud',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()
        self.ubicacion = Ubicacion.objects.create(
            nombre='Ubicación con CO',
            codigo='UBI-CO-TEST',
            co='CO-TEST',
        )
        self.equipo = Equipo.objects.create(
            nombre='Equipo con CO',
            codigo='EQ-CO-TEST',
            ubicacion=self.ubicacion,
        )

    def _post_solicitud(self, equipo, enviar_email=False):
        return self.client.post(reverse('crear_solicitud'), {
            'creado_por': self.user.username,
            'descripcion_problema': 'Prueba de CO',
            'email_solicitante': 'solicitante@example.com',
            'equipo': equipo.pk,
            'solicitado_por': self.user.username,
            'prioridad': 'media',
            'enviar_email': '1' if enviar_email else '',
        })

    def test_creation_saves_co_from_equipment_location(self):
        response = self._post_solicitud(self.equipo)

        self.assertEqual(response.status_code, 302)
        solicitud = Solicitud.objects.get(equipo=self.equipo)
        self.assertEqual(solicitud.co, 'CO-TEST')

    def test_creation_uses_location_code_when_location_has_no_co(self):
        self.ubicacion.co = ''
        self.ubicacion.save()

        response = self._post_solicitud(self.equipo)

        self.assertEqual(response.status_code, 302)
        solicitud = Solicitud.objects.get(equipo=self.equipo)
        self.assertEqual(solicitud.co, 'UBI-CO-TEST')

    def test_creation_allows_missing_co_when_location_and_session_have_none(self):
        equipo_sin_ubicacion = Equipo.objects.create(
            nombre='Equipo sin ubicación',
            codigo='EQ-SIN-UBICACION',
        )

        response = self._post_solicitud(equipo_sin_ubicacion)

        self.assertEqual(response.status_code, 302)
        solicitud = Solicitud.objects.get(equipo=equipo_sin_ubicacion)
        self.assertEqual(solicitud.co, '')

    def test_creation_uses_session_co_when_equipment_has_no_location(self):
        equipo_sin_ubicacion = Equipo.objects.create(
            nombre='Equipo con CO en sesión',
            codigo='EQ-CO-SESION',
        )
        session = self.client.session
        session['co'] = 'CO-SESION'
        session.save()

        response = self._post_solicitud(equipo_sin_ubicacion)

        self.assertEqual(response.status_code, 302)
        solicitud = Solicitud.objects.get(equipo=equipo_sin_ubicacion)
        self.assertEqual(solicitud.co, 'CO-SESION')

    @patch('gestion_mantenimiento.solicitudes.views.enviar_correo_solicitud')
    def test_creation_sends_notification_only_when_checkbox_is_selected(self, send_email):
        response = self._post_solicitud(self.equipo, enviar_email=True)

        self.assertEqual(response.status_code, 302)
        solicitud = Solicitud.objects.get(equipo=self.equipo)
        send_email.assert_called_once_with(
            solicitud,
            'creacion',
            cuerpo_extra=(
                'Descripción: Prueba de CO\n'
                f'Solicitado por: {self.user.username}\n'
                f'Creado por: {self.user.username}'
            ),
        )

    @patch('gestion_mantenimiento.solicitudes.views.enviar_correo_solicitud')
    def test_creation_does_not_send_notification_when_checkbox_is_unselected(self, send_email):
        response = self._post_solicitud(self.equipo)

        self.assertEqual(response.status_code, 302)
        send_email.assert_not_called()
