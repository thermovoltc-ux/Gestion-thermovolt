from datetime import datetime, timezone as datetime_timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.core import mail
from django.test import TestCase, override_settings

from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import Estado, OrdenTrabajo
from gestion_mantenimiento.Gestion_ot import views
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


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CLIENT_EMAIL_MAP={},
)
class EnviarPdfPorEmailTests(TestCase):
    def setUp(self):
        ubicacion = SimpleNamespace(nombre='PDV prueba')
        equipo = SimpleNamespace(nombre='Equipo prueba', ubicacion=ubicacion)
        solicitud = SimpleNamespace(
            consecutivo=42,
            equipo=equipo,
            ubicacion_nombre='PDV prueba',
            email_solicitante=None,
        )
        self.cierre_ot = SimpleNamespace(
            orden_trabajo=SimpleNamespace(solicitud=solicitud),
            fecha_inicio_actividad=datetime(2026, 9, 30, tzinfo=datetime_timezone.utc),
            correo_tecnico='tecnico@example.com',
        )
        self.pdf_buffer = BytesIO(b'%PDF-test')

    def _send_with_link(self, drive_link):
        with patch.object(views, 'guardar_copia_pdf_envio'), patch.object(
            views, 'guardar_pdf_en_media', return_value=drive_link
        ):
            return views.enviar_pdf_por_email(self.pdf_buffer, self.cierre_ot)

    def test_sends_link_in_plain_text_and_html_without_bcc_or_attachment(self):
        self.assertTrue(self._send_with_link('https://reports.example/informe.pdf'))

        message = mail.outbox[0]
        self.assertIn('https://reports.example/informe.pdf', message.body)
        self.assertEqual(message.bcc, [])
        self.assertEqual(message.attachments, [])
        self.assertTrue(any(
            mimetype == 'text/html' and 'https://reports.example/informe.pdf' in content
            for content, mimetype in message.alternatives
        ))

    def test_reports_unavailable_without_fallback_attachment(self):
        self.assertTrue(self._send_with_link(None))

        message = mail.outbox[0]
        self.assertIn('El informe no está disponible por el momento', message.body)
        self.assertEqual(message.bcc, [])
        self.assertEqual(message.attachments, [])
        self.assertTrue(any(
            mimetype == 'text/html' and 'El informe no está disponible por el momento' in content
            for content, mimetype in message.alternatives
        ))
