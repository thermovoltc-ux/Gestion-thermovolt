from django.test import TestCase

from gestion_mantenimiento.solicitudes.models import Solicitud
from gestion_mantenimiento.Gestion_ot.models import Estado
from gestion_mantenimiento.Activos.models import Equipo, Ubicacion


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
