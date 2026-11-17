from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from types import SimpleNamespace
from unittest.mock import patch

from gestion_mantenimiento.solicitudes.models import Solicitud
from gestion_mantenimiento.Gestion_ot.models import Estado
from gestion_mantenimiento.Activos.models import (
    Activo,
    Area,
    CentroCostos,
    CentroOperaciones,
    Equipo,
    Regional,
    Ubicacion,
)
from gestion_mantenimiento.solicitudes.forms import SolicitudForm
from gestion_mantenimiento.solicitudes.utils import enviar_correo_solicitud


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    THERMOVOLT_LOGO_URL='',
)
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

    def test_sends_html_and_plain_text_without_inline_logo_when_url_is_unset(self):
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
        self.assertNotIn('cid:', html)
        self.assertNotIn('<img ', html)
        self.assertEqual(mensaje.attachments, [])

    @override_settings(THERMOVOLT_LOGO_URL='https://cdn.example.com/thermovolt-logo.png')
    def test_uses_public_logo_url_when_configured(self):
        enviado = enviar_correo_solicitud(self.solicitud, 'creacion')

        self.assertTrue(enviado)
        mensaje = mail.outbox[0]
        html = mensaje.alternatives[0][0]
        self.assertIn(
            '<img src="https://cdn.example.com/thermovolt-logo.png"',
            html,
        )
        self.assertNotIn('cid:', html)
        self.assertEqual(mensaje.attachments, [])

    def test_report_email_renders_download_link_in_html_and_plain_text(self):
        download_url = 'https://example.com/informe.pdf?token=test-token'
        enviado = enviar_correo_solicitud(
            self.solicitud,
            'informe',
            cuerpo_extra='Informe disponible.',
            enlace_descarga=download_url,
        )

        self.assertTrue(enviado)
        mensaje = mail.outbox[0]
        self.assertIn(f'Descargar informe (PDF): {download_url}', mensaje.body)
        self.assertEqual(len(mensaje.alternatives), 1)
        html, content_type = mensaje.alternatives[0]
        self.assertEqual(content_type, 'text/html')
        self.assertIn(f'href="{download_url}"', html)
        self.assertIn('>Descargar informe (PDF)</a>', html)
        self.assertNotIn(f'> {download_url}<', html)
        self.assertIn('Informe de mantenimiento disponible', html)
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
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
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
        self.assertTrue(solicitud.enviar_email)
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
        solicitud = Solicitud.objects.get(equipo=self.equipo)
        self.assertFalse(solicitud.enviar_email)
        send_email.assert_not_called()


class SolicitudEndpointIsolationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cliente-solicitud-scope',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.client.force_login(self.user)
        self.allowed_center = CentroOperaciones.objects.create(
            nombre='CO solicitudes permitido',
            codigo='CO-SOL-PERMITIDO',
        )
        self.other_center = CentroOperaciones.objects.create(
            nombre='CO solicitudes ajeno',
            codigo='CO-SOL-AJENO',
        )
        self.allowed_location = Ubicacion.objects.create(
            nombre='Ubicación solicitudes permitida',
            codigo='UBI-SOL-PERMITIDA',
            centro_operaciones=self.allowed_center,
        )
        self.foreign_location = Ubicacion.objects.create(
            nombre='Ubicación solicitudes privada',
            codigo='UBI-SOL-AJENA',
            centro_operaciones=self.other_center,
        )
        self.allowed_equipment = Equipo.objects.create(
            nombre='Equipo solicitudes permitido',
            codigo='EQ-SOL-PERMITIDO',
            serie='SERIE-SOL-PERMITIDA',
            ubicacion=self.allowed_location,
        )
        self.foreign_equipment = Equipo.objects.create(
            nombre='Equipo solicitudes privado',
            codigo='EQ-SOL-AJENO',
            serie='SERIE-SOL-AJENA',
            ubicacion=self.foreign_location,
        )
        self.requested = Estado.objects.get_or_create(nombre='solicitado')[0]
        self.allowed_request = Solicitud.objects.create(
            creado_por=self.user.username,
            descripcion_problema='Solicitud CO permitida',
            equipo=self.allowed_equipment,
            ubicacion=self.allowed_location,
            estado=self.requested,
        )
        self.foreign_request = Solicitud.objects.create(
            creado_por='usuario-otro-cliente',
            descripcion_problema='Solicitud privada de otro cliente',
            equipo=self.foreign_equipment,
            ubicacion=self.foreign_location,
            estado=self.requested,
        )
        self.allowed_area = Area.objects.create(
            nombre='Área solicitudes permitida',
            ubicacion=self.allowed_location,
        )
        self.foreign_area = Area.objects.create(
            nombre='Área solicitudes privada',
            ubicacion=self.foreign_location,
        )
        self.foreign_cost_center = CentroCostos.objects.create(
            nombre='Centro costos privado',
            area=self.foreign_area,
        )
        regional = Regional.objects.create(nombre='Regional aislamiento')
        self.foreign_asset = Activo.objects.create(
            nombre='Activo solicitudes privado',
            numero_serie='ACTIVO-SOL-AJENO',
            ubicacion=self.foreign_location,
            regional=regional,
            centro_costos=self.foreign_cost_center,
        )
        session = self.client.session
        session['centro_operaciones_id'] = self.allowed_center.pk
        session['tipo_cuenta'] = 'jefe_de_area'
        session.save()

    def test_request_list_only_contains_selected_center_requests(self):
        response = self.client.get(reverse('lista_solicitudes'))

        self.assertEqual(response.status_code, 200)
        visible_ids = set(response.context['solicitudes'].values_list('pk', flat=True))
        self.assertEqual(visible_ids, {self.allowed_request.pk})

    def test_json_location_and_equipment_lookups_hide_foreign_objects(self):
        responses = [
            self.client.get(
                reverse('get-ubicacion-por-codigo'),
                {'codigo': self.foreign_location.codigo},
            ),
            self.client.get(
                reverse('get_equipos_por_ubicacion'),
                {'ubicacion_id': self.foreign_location.pk},
            ),
            self.client.get(
                reverse('get_ubicacion_equipos'),
                {'codigo': self.foreign_location.codigo},
            ),
            self.client.get(
                reverse('get_equipo_por_codigo'),
                {'codigo': self.foreign_equipment.codigo},
            ),
            self.client.get(
                reverse('get_numero_activo'),
                {'activo_id': self.foreign_asset.pk},
            ),
        ]

        self.assertTrue(
            all(response.status_code in {200, 403, 404} for response in responses),
        )
        self.assertTrue(
            all(
                self.foreign_location.nombre not in response.content.decode()
                and self.foreign_equipment.nombre not in response.content.decode()
                and str(self.foreign_location.pk) not in response.content.decode()
                and str(self.foreign_equipment.pk) not in response.content.decode()
                for response in responses
            )
        )

    def test_search_area_cost_center_and_duplicate_apis_do_not_leak_foreign_data(self):
        search_response = self.client.get(
            reverse('buscar_ubicaciones'),
            {'q': 'privada'},
        )
        area_response = self.client.get(
            reverse('get_equipos_por_area'),
            {'area_id': self.foreign_area.pk},
        )
        cost_response = self.client.get(
            reverse('get_centro_costo'),
            {'area_id': self.foreign_area.pk},
        )
        duplicate_response = self.client.get(
            reverse('verificar_solicitud'),
            {'equipo_id': self.foreign_equipment.pk},
        )

        self.assertEqual(search_response.json(), {'results': []})
        self.assertNotIn(self.foreign_asset.nombre, str(area_response.json()))
        self.assertNotIn(self.foreign_cost_center.nombre, str(cost_response.json()))
        self.assertEqual(duplicate_response.json(), {'exists': False, 'count': 0})

    def test_client_without_center_gets_empty_request_and_json_scopes(self):
        session = self.client.session
        session.pop('centro_operaciones_id', None)
        session['tipo_cuenta'] = 'jefe_de_area'
        session.save()

        list_response = self.client.get(reverse('lista_solicitudes'))
        search_response = self.client.get(
            reverse('buscar_ubicaciones'),
            {'q': 'permitida'},
        )
        json_responses = [
            self.client.get(
                reverse('get-ubicacion-por-codigo'),
                {'codigo': self.allowed_location.codigo},
            ),
            self.client.get(
                reverse('get_equipos_por_ubicacion'),
                {'ubicacion_id': self.allowed_location.pk},
            ),
            self.client.get(
                reverse('get_ubicacion_equipos'),
                {'codigo': self.allowed_location.codigo},
            ),
            self.client.get(
                reverse('get_equipo_por_codigo'),
                {'codigo': self.allowed_equipment.codigo},
            ),
            self.client.get(
                reverse('get_numero_activo'),
                {'activo_id': self.foreign_asset.pk},
            ),
            self.client.get(
                reverse('get_equipos_por_area'),
                {'area_id': self.allowed_area.pk},
            ),
            self.client.get(
                reverse('get_centro_costo'),
                {'area_id': self.allowed_area.pk},
            ),
            self.client.get(
                reverse('verificar_solicitud'),
                {'equipo_id': self.allowed_equipment.pk},
            ),
        ]

        self.assertFalse(list_response.context['solicitudes'].exists())
        self.assertEqual(search_response.json(), {'results': []})
        self.assertTrue(
            all(response.status_code in {200, 403, 404} for response in json_responses),
        )
        self.assertTrue(
            all(
                self.allowed_location.nombre not in response.content.decode()
                and self.allowed_equipment.nombre not in response.content.decode()
                for response in json_responses
            )
        )
