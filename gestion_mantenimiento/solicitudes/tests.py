from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from gestion_mantenimiento.solicitudes.models import Solicitud
from gestion_mantenimiento.Gestion_ot.models import Estado
from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.solicitudes.forms import SolicitudForm


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

    def _post_solicitud(self, equipo):
        return self.client.post(reverse('crear_solicitud'), {
            'creado_por': self.user.username,
            'descripcion_problema': 'Prueba de CO',
            'email_solicitante': 'solicitante@example.com',
            'equipo': equipo.pk,
            'solicitado_por': self.user.username,
            'prioridad': 'media',
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
