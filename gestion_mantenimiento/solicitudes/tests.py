from django.test import TestCase

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
