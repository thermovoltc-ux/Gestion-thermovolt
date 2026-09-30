from datetime import datetime, timezone as datetime_timezone
from io import BytesIO
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import CierreOt, Estado, OrdenTrabajo, ProcesoInforme
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
        with patch.object(views, 'guardar_copia_pdf_envio'):
            return views.enviar_pdf_por_email(self.pdf_buffer, self.cierre_ot, drive_link)

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


class ProcesoInformeRetryTests(TestCase):
    def setUp(self):
        ubicacion = Ubicacion.objects.create(nombre='Ubicación retry', codigo='UBI-RETRY')
        equipo = Equipo.objects.create(nombre='Equipo retry', codigo='EQ-RETRY', ubicacion=ubicacion)
        estado, _ = Estado.objects.get_or_create(nombre='solicitado')
        solicitud = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Prueba retry',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        orden = OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado='Técnico retry',
            estado=estado,
        )
        self.cierre_ot = CierreOt.objects.create(orden_trabajo=orden)

    def crear_proceso(self, operation_id, intentos):
        return ProcesoInforme.objects.create(
            operation_id=operation_id,
            cierre_ot=self.cierre_ot,
            estado=ProcesoInforme.ERROR,
            intentos=intentos,
        )

    def test_processing_increments_attempt_and_records_validation_error(self):
        proceso = self.crear_proceso('retry-validation', 0)

        with patch.object(views, '_validar_firmas', return_value=(False, 'Falta una firma')):
            views._procesar_proceso_informe(proceso.operation_id)

        proceso.refresh_from_db()
        self.assertEqual(proceso.intentos, 1)
        self.assertEqual(proceso.estado, ProcesoInforme.ERROR)

    def test_processing_stops_at_four_attempts(self):
        proceso = self.crear_proceso('retry-limit', 4)

        with patch.object(views, '_validar_firmas') as validar_firmas:
            views._procesar_proceso_informe(proceso.operation_id)

        proceso.refresh_from_db()
        self.assertEqual(proceso.intentos, 4)
        validar_firmas.assert_not_called()

    def test_worker_selects_only_errors_below_attempt_limit(self):
        reintentable = self.crear_proceso('retry-eligible', 0)
        self.crear_proceso('retry-exhausted', 4)

        with patch.object(views, '_procesar_proceso_informe') as procesar:
            call_command('procesar_informes_pendientes', stdout=StringIO(), stderr=StringIO())

        procesar.assert_called_once_with(reintentable.operation_id)


class ProcesoInformePersistenciaTests(TestCase):
    def setUp(self):
        ubicacion = Ubicacion.objects.create(nombre='Ubicación persistencia', codigo='UBI-PERSIST')
        equipo = Equipo.objects.create(nombre='Equipo persistencia', codigo='EQ-PERSIST', ubicacion=ubicacion)
        estado, _ = Estado.objects.get_or_create(nombre='solicitado')
        solicitud = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Prueba persistencia PDF',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        orden = OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado='Técnico persistencia',
            estado=estado,
        )
        self.cierre_ot = CierreOt.objects.create(orden_trabajo=orden)
        self.proceso = ProcesoInforme.objects.create(cierre_ot=self.cierre_ot)

    def test_pdf_path_and_size_are_persisted_before_sending(self):
        pdf_buffer = BytesIO(b'%PDF-1.4\n' + b'x' * 1024 + b'\n%%EOF')
        with patch.object(views, '_validar_firmas', return_value=(True, 'OK')), patch.object(
            views, '_validar_imagenes', return_value=(True, 0, 0, 'OK')
        ), patch.object(views, 'generar_pdf_informe', return_value=pdf_buffer), patch.object(
            views, 'guardar_pdf_en_media', return_value=(
                'https://reports.example/ot-42.pdf', 'email_copies/informes/ot-42.pdf'
            )
        ), patch.object(views, 'enviar_pdf_por_email', return_value=True) as enviar_email:
            views._procesar_proceso_informe(self.proceso.operation_id)

        self.proceso.refresh_from_db()
        self.assertEqual(self.proceso.pdf_path, 'https://reports.example/ot-42.pdf')
        self.assertEqual(self.proceso.pdf_size_bytes, len(pdf_buffer.getvalue()))
        self.assertEqual(self.proceso.estado, ProcesoInforme.ENVIADO)
        enviar_email.assert_called_once_with(
            pdf_buffer, self.cierre_ot, 'https://reports.example/ot-42.pdf'
        )

    def test_local_storage_path_is_persisted_when_public_url_is_unavailable(self):
        pdf_buffer = BytesIO(b'%PDF-1.4\n' + b'x' * 1024 + b'\n%%EOF')
        local_path = '/app/media/email_copies/informes/ot-42.pdf'
        with patch.object(views, '_validar_firmas', return_value=(True, 'OK')), patch.object(
            views, '_validar_imagenes', return_value=(True, 0, 0, 'OK')
        ), patch.object(views, 'generar_pdf_informe', return_value=pdf_buffer), patch.object(
            views, 'guardar_pdf_en_media', return_value=(None, local_path)
        ), patch.object(views, 'enviar_pdf_por_email', return_value=True) as enviar_email:
            views._procesar_proceso_informe(self.proceso.operation_id)

        self.proceso.refresh_from_db()
        self.assertEqual(self.proceso.pdf_path, local_path)
        self.assertEqual(self.proceso.pdf_size_bytes, len(pdf_buffer.getvalue()))
        enviar_email.assert_called_once_with(pdf_buffer, self.cierre_ot, None)
