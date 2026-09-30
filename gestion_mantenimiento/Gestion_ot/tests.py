from django.db import IntegrityError
from django.test import TestCase

from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import Estado, OrdenTrabajo
from gestion_mantenimiento.solicitudes.models import Solicitud


class OrdenTrabajoIntegridadTests(TestCase):
    def setUp(self):
        self.ubicacion = Ubicacion.objects.create(nombre='Ubicación prueba', codigo='UBI-01')
        self.equipo = Equipo.objects.create(nombre='Equipo prueba', codigo='EQ-01', ubicacion=self.ubicacion)
        self.estado = Estado.objects.get_or_create(nombre='solicitado')[0]
        self.solicitud = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Falla de prueba',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
        )

    def test_una_solicitud_no_puede_tener_multiples_ordenes(self):
        OrdenTrabajo.objects.create(
            solicitud=self.solicitud,
            tecnico_asignado='Tecnico 1',
            estado=self.estado,
        )

        with self.assertRaises(IntegrityError):
            OrdenTrabajo.objects.create(
                solicitud=self.solicitud,
                tecnico_asignado='Tecnico 2',
                estado=self.estado,
            )
