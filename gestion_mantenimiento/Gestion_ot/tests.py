from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from io import BytesIO
from io import StringIO
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.core import mail
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files import File
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import (
    CierreOt,
    Estado,
    Material,
    MaterialOT,
    OrdenTrabajo,
    PlanMantenimiento,
    ProcesoInforme,
    ServicioOT,
    TareaMantenimiento,
)
from gestion_mantenimiento.Gestion_ot import views
from gestion_mantenimiento.Gestion_ot.plantilla_utils import _obtener_imagen_temporal
from gestion_mantenimiento.Gestion_ot.storage import GoogleDriveMediaStorage
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


class GestionOtFilterRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = self._create_user('tester', 'contraseña123')
        self.client.force_login(self.user)
        self.ubicacion_a = Ubicacion.objects.create(nombre='Ubicación A', codigo='UBI-A')
        self.ubicacion_b = Ubicacion.objects.create(nombre='Ubicación B', codigo='UBI-B')
        self.equipo_a = Equipo.objects.create(nombre='Equipo A', codigo='EQ-A', ubicacion=self.ubicacion_a)
        self.equipo_b = Equipo.objects.create(nombre='Equipo B', codigo='EQ-B', ubicacion=self.ubicacion_b)
        self.estado_solicitado, _ = Estado.objects.get_or_create(nombre='solicitado')
        self.estado_finalizada, _ = Estado.objects.get_or_create(nombre='finalizada')

        self.ot_actual = self._crear_ot(
            'Actual',
            self.ubicacion_a,
            self.equipo_a,
            self.estado_solicitado,
            timezone.now(),
        )
        self.ot_pasada = self._crear_ot(
            'Pasada',
            self.ubicacion_a,
            self.equipo_a,
            self.estado_solicitado,
            timezone.now() - relativedelta(months=2),
        )
        self.ot_otra_ubicacion = self._crear_ot(
            'Otra',
            self.ubicacion_b,
            self.equipo_b,
            self.estado_solicitado,
            timezone.now(),
        )
        self.ot_finalizada = self._crear_ot(
            'Finalizada',
            self.ubicacion_a,
            self.equipo_a,
            self.estado_finalizada,
            timezone.now() - relativedelta(months=2),
        )

    def _create_user(self, username, password):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.create_user(username=username, password=password)

    def _crear_ot(self, descripcion, ubicacion, equipo, estado, fecha_creacion):
        solicitud = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema=descripcion,
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
            fecha_creacion=fecha_creacion,
        )
        return OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado='Tecnico filtro',
            estado=estado,
            fecha_actividad=fecha_creacion,
        )

    def test_kanban_filters_by_ubicacion_and_keeps_older_unresolved_ots_by_default(self):
        response = self.client.get(reverse('gestion_ot'), {'ubicacion_id': self.ubicacion_a.id})

        self.assertEqual(response.status_code, 200)
        ordenes = list(response.context['ordenes_trabajo'])
        self.assertCountEqual(
            [ot.solicitud.consecutivo for ot in ordenes],
            [self.ot_actual.solicitud.consecutivo, self.ot_pasada.solicitud.consecutivo],
        )
        self.assertNotIn(self.ot_otra_ubicacion.solicitud.consecutivo, [ot.solicitud.consecutivo for ot in ordenes])
        self.assertNotIn(self.ot_finalizada.solicitud.consecutivo, [ot.solicitud.consecutivo for ot in ordenes])

    def test_dashboard_late_filter_combines_with_pending_state(self):
        plan = PlanMantenimiento.objects.create(
            equipo=self.equipo_a,
            nombre='Plan preventivo filtros',
            fecha_inicio=timezone.localdate() - timedelta(days=30),
        )
        tarea_atrasada = TareaMantenimiento.objects.create(
            plan=plan,
            fecha_programada=timezone.localdate() - timedelta(days=1),
            estado='pendiente',
        )
        tarea_hoy = TareaMantenimiento.objects.create(
            plan=plan,
            fecha_programada=timezone.localdate(),
            estado='pendiente',
        )
        tarea_en_progreso = TareaMantenimiento.objects.create(
            plan=plan,
            fecha_programada=timezone.localdate() - timedelta(days=2),
            estado='en_progreso',
        )

        response = self.client.get(
            reverse('gestion_ot'),
            {'estado': 'pendiente', 'atrasadas': '1'},
        )

        self.assertEqual(response.status_code, 200)
        tareas = list(
            response.context['tareas_mantenimiento'].filter(plan=plan)
        )
        self.assertIn(tarea_atrasada, tareas)
        self.assertTrue(all(
            tarea.estado == 'pendiente'
            and tarea.fecha_programada < timezone.localdate()
            for tarea in tareas
        ))
        self.assertNotIn(tarea_hoy.pk, [tarea.pk for tarea in tareas])
        self.assertNotIn(tarea_en_progreso.pk, [tarea.pk for tarea in tareas])
        self.assertCountEqual(
            [ot.pk for ot in response.context['ordenes_trabajo']],
            [self.ot_pasada.pk],
        )
        self.assertEqual(response.context['filter_label'], 'Estado: pendiente | Tareas y OTs con atraso')
        self.assertContains(response, 'Estado: pendiente | Tareas y OTs con atraso')
        self.assertContains(response, reverse('gestion_ot'))

    def test_kanban_state_filter_only_applies_valid_ot_states(self):
        estado_en_proceso, _ = Estado.objects.get_or_create(nombre='en proceso')
        ot_en_proceso = self._crear_ot(
            'En proceso',
            self.ubicacion_a,
            self.equipo_a,
            estado_en_proceso,
            timezone.now(),
        )

        response = self.client.get(reverse('gestion_ot'), {'estado': 'en proceso'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['ordenes_trabajo']),
            [ot_en_proceso],
        )


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


class MaterialOTAjaxTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username='tecnico-materiales',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()
        self.estado_abierta, _ = Estado.objects.get_or_create(nombre='solicitado')
        self.estado_en_proceso, _ = Estado.objects.get_or_create(nombre='en proceso')
        self.estado_finalizada, _ = Estado.objects.get_or_create(nombre='finalizada')
        self.ot = self._crear_ot('tecnico-materiales', self.estado_abierta, 'OT propia')
        self.ot_ajena = self._crear_ot('otro-tecnico', self.estado_abierta, 'OT ajena')
        self.material = Material.objects.create(
            codigo='MAT-001',
            nombre='Rodamiento',
            costo_base='10.00',
            precio_venta_sugerido='14.29',
        )

    def _crear_ot(self, tecnico, estado, descripcion):
        ubicacion = Ubicacion.objects.create(
            nombre=f'Ubicación {descripcion}',
            codigo=f'UBI-{descripcion.replace(" ", "-")}',
        )
        equipo = Equipo.objects.create(
            nombre=f'Equipo {descripcion}',
            codigo=f'EQ-{descripcion.replace(" ", "-")}',
            ubicacion=ubicacion,
        )
        solicitud = Solicitud.objects.create(
            creado_por=tecnico,
            descripcion_problema=descripcion,
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        return OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado=tecnico,
            estado=estado,
        )

    def test_adds_material_and_calculates_historical_sale_price(self):
        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '2.00',
                'costo_real': '10.00',
            },
        )

        self.assertEqual(response.status_code, 201)
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot)
        self.assertEqual(material_ot.precio_venta_aplicado, Decimal('14.29'))
        self.assertEqual(material_ot.cantidad, Decimal('2.00'))
        self.assertIsNotNone(material_ot.fecha_registro)

    def test_quick_add_saves_observations_for_the_assigned_technician(self):
        self.ot.estado = self.estado_en_proceso
        self.ot.save(update_fields=['estado'])
        response = self.client.post(
            reverse('agregar_material_rapido_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '2.00',
                'costo_real': '10.00',
                'observaciones': 'Dos unidades corresponden a esta OT.',
            },
        )

        self.assertEqual(response.status_code, 201)
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot)
        self.assertEqual(
            material_ot.observaciones,
            'Dos unidades corresponden a esta OT.',
        )
        self.assertEqual(
            response.json()['observaciones'],
            'Dos unidades corresponden a esta OT.',
        )

    def test_quick_add_accepts_same_invoice_for_two_assigned_orders(self):
        from tempfile import TemporaryDirectory
        from PIL import Image

        self.ot.estado = self.estado_en_proceso
        self.ot.save(update_fields=['estado'])
        self.ot_ajena.tecnico_asignado = self.user.username
        self.ot_ajena.estado = self.estado_en_proceso
        self.ot_ajena.save(update_fields=['tecnico_asignado', 'estado'])
        self.ot_ajena.refresh_from_db()

        image_buffer = BytesIO()
        Image.new('RGB', (1, 1), color='white').save(image_buffer, format='PNG')
        image_content = image_buffer.getvalue()

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                for order in (self.ot, self.ot_ajena):
                    response = self.client.post(
                        reverse('agregar_material_rapido_ot', args=[order.pk]),
                        {
                            'material': self.material.pk,
                            'cantidad': '1',
                            'costo_real': '10.00',
                            'foto_factura': SimpleUploadedFile(
                                'factura.png',
                                image_content,
                                content_type='image/png',
                            ),
                        },
                    )
                    self.assertEqual(response.status_code, 201)

                records = list(MaterialOT.objects.order_by('orden_trabajo_id'))
                self.assertEqual(len(records), 2)
                self.assertNotEqual(
                    records[0].foto_factura.name,
                    records[1].foto_factura.name,
                )

    def test_quick_add_requires_assigned_technician_and_in_process_status(self):
        response = self.client.post(
            reverse('agregar_material_rapido_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1',
                'costo_real': '10.00',
            },
        )
        self.assertEqual(response.status_code, 404)

        self.ot.estado = self.estado_en_proceso
        self.ot.save(update_fields=['estado'])
        response = self.client.post(
            reverse('agregar_material_rapido_ot', args=[self.ot_ajena.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1',
                'costo_real': '10.00',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(MaterialOT.objects.exists())

    def test_rejects_invalid_quantity(self):
        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '0',
                'costo_real': '10.00',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('cantidad', response.json()['errors'])
        self.assertFalse(MaterialOT.objects.exists())

    def test_cannot_add_material_to_another_technicians_order(self):
        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot_ajena.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1',
                'costo_real': '10.00',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(MaterialOT.objects.exists())

    def test_cannot_add_material_to_read_only_order(self):
        self.ot.estado = self.estado_finalizada
        self.ot.save(update_fields=['estado'])

        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1',
                'costo_real': '10.00',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MaterialOT.objects.exists())

        response = self.client.post(
            reverse('crear_material_ajax', args=[self.ot.pk]),
            data='{"categoria":"repuestos","nombre":"Material no permitido","costo_base":"10.00"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Material.objects.filter(codigo='MAT-READONLY').exists())

    def test_catalog_material_suggested_price_applies_markup_only_to_spare_parts(self):
        response = self.client.post(
            reverse('crear_material_ajax', args=[self.ot.pk]),
            data='{"categoria":"servicios","nombre":"Correa","costo_base":"7.00"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        material = Material.objects.get(codigo='SCOR01')
        self.assertEqual(material.precio_venta_sugerido, Decimal('7.00'))
        self.assertEqual(material.categoria, 'servicios')

    def test_catalog_price_field_fits_the_full_supported_base_cost(self):
        response = self.client.post(
            reverse('crear_material_ajax', args=[self.ot.pk]),
            data='{"categoria":"repuestos","nombre":"Material costo alto","costo_base":"9999999999.99"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        material = Material.objects.get(codigo='RMC01')
        self.assertEqual(
            material.precio_venta_sugerido,
            Decimal('14285714285.70'),
        )

    def test_catalog_codes_use_category_name_initials_and_increment(self):
        from gestion_mantenimiento.Gestion_ot.forms import MaterialForm

        def crear_material():
            return self.client.post(
                reverse('crear_material_ajax', args=[self.ot.pk]),
                data='{"categoria":"repuestos","nombre":"Pulsador Verde","costo_base":"7.00"}',
                content_type='application/json',
            )

        primera_respuesta = crear_material()
        segunda_respuesta = crear_material()

        self.assertEqual(primera_respuesta.status_code, 201)
        self.assertEqual(primera_respuesta.json()['codigo'], 'RPV01')
        self.assertEqual(segunda_respuesta.status_code, 201)
        self.assertEqual(segunda_respuesta.json()['codigo'], 'RPV02')
        self.assertFalse(MaterialForm().fields.get('codigo'))

    def test_catalog_code_sequence_increments_globally_across_category_initials(self):
        Material.objects.create(
            codigo='RR01',
            categoria='repuestos',
            nombre='Rodamiento inicial',
            costo_base=Decimal('7.00'),
            precio_venta_sugerido=Decimal('10.00'),
        )
        material_iniciales_distintas = Material(
            categoria='repuestos',
            nombre='Kit Empaques',
            costo_base=Decimal('7.00'),
            precio_venta_sugerido=Decimal('10.00'),
        )
        material_iniciales_distintas.save()

        material_mismas_iniciales = Material(
            categoria='repuestos',
            nombre='Rodamiento Repuesto',
            costo_base=Decimal('7.00'),
            precio_venta_sugerido=Decimal('10.00'),
        )
        material_mismas_iniciales.save()

        material_mismas_iniciales_siguiente = Material(
            categoria='repuestos',
            nombre='Rodamiento Refrigerado',
            costo_base=Decimal('7.00'),
            precio_venta_sugerido=Decimal('10.00'),
        )
        material_mismas_iniciales_siguiente.save()

        self.assertEqual(material_iniciales_distintas.codigo, 'RKE02')
        self.assertEqual(material_mismas_iniciales.codigo, 'RRR03')
        self.assertEqual(material_mismas_iniciales_siguiente.codigo, 'RRR04')

    def test_catalog_codes_and_suggested_prices_follow_each_category(self):
        Material.objects.create(
            codigo='RPV01',
            categoria='repuestos',
            nombre='Código preexistente',
            costo_base=Decimal('1.00'),
            precio_venta_sugerido=Decimal('1.43'),
        )
        casos = [
            ('repuestos', 'Pulsador Verde', 'RPV02'),
            ('servicios', 'Rectificación de buje', 'SRB01'),
            ('frio', 'Cambio de compresor', 'FCC01'),
            ('maquinaria', 'Motor', 'MMOT01'),
            ('locativos', 'Pintura pared', 'LPP01'),
        ]

        for categoria, nombre, codigo_esperado in casos:
            with self.subTest(categoria=categoria, nombre=nombre):
                response = self.client.post(
                    reverse('crear_material_ajax', args=[self.ot.pk]),
                    data=json.dumps({
                        'categoria': categoria,
                        'nombre': nombre,
                        'costo_base': '7.00',
                    }),
                    content_type='application/json',
                )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()['codigo'], codigo_esperado)
                material = Material.objects.get(codigo=codigo_esperado)
                expected_price = Decimal('7.00')
                if categoria in {'repuestos', 'maquinaria', 'frio', 'locativos'}:
                    expected_price = Decimal('10.00')
                self.assertEqual(material.precio_venta_sugerido, expected_price)

    def test_closure_page_renders_material_catalog_and_table(self):
        Material.objects.create(
            codigo='MAQ-TECN-01',
            categoria='maquinaria',
            nombre='Maquinaria solo admin',
            costo_base=Decimal('20.00'),
            precio_venta_sugerido=Decimal('30.00'),
        )
        Material.objects.create(
            codigo='FRI-TECN-01',
            categoria='frio',
            nombre='Equipo frío solo admin',
            costo_base=Decimal('20.00'),
            precio_venta_sugerido=Decimal('30.00'),
        )
        response = self.client.get(reverse('cierre_ot', args=[self.ot.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Agregar Material / Repuesto')
        self.assertContains(response, 'Rodamiento')
        self.assertContains(response, 'materiales_ot.js')
        self.assertContains(response, 'id="buscar-material-unificado" class="form-control" list="materiales-catalogo"')
        self.assertContains(response, 'data-id="')
        self.assertContains(response, 'data-costo="')
        self.assertNotContains(response, 'Maquinaria solo admin')
        self.assertNotContains(response, 'Equipo frío solo admin')
        self.assertSetEqual(
            set(response.context['materiales_catalogo'].values_list('categoria', flat=True)),
            {'repuestos'},
        )
        self.assertNotContains(response, 'id="buscar-material"')
        self.assertNotContains(response, 'id="select-material"')
        self.assertNotContains(response, 'btn-abrir-modal-nuevo-material')
        self.assertNotContains(response, 'modal-nuevo-material')
        self.assertNotContains(response, 'Crear nuevo repuesto')
        self.assertContains(response, 'id="input-cantidad" class="form-control" value="1" min="0.01" step="0.01">')
        self.assertContains(response, 'id="input-costo-real" class="form-control" min="0" step="0.01">')
        self.assertNotContains(response, 'nuevo-codigo')

    def test_ot_list_shows_quick_material_button_only_for_assigned_in_process_orders(self):
        self.ot.estado = self.estado_en_proceso
        self.ot.save(update_fields=['estado'])
        self.ot_ajena.estado = self.estado_en_proceso
        self.ot_ajena.save(update_fields=['estado'])
        Material.objects.create(
            codigo='MAQ-LISTA-01',
            categoria='maquinaria',
            nombre='Maquinaria fuera de catálogo técnico',
            costo_base=Decimal('20.00'),
            precio_venta_sugerido=Decimal('30.00'),
        )

        response = self.client.get(reverse('listar_ot'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('agregar_material_rapido_ot', args=[self.ot.pk]),
        )
        self.assertNotContains(response, 'Maquinaria fuera de catálogo técnico')
        self.assertSetEqual(
            set(response.context['materiales_catalogo'].values_list('categoria', flat=True)),
            {'repuestos'},
        )
        self.assertNotContains(
            response,
            reverse('agregar_material_rapido_ot', args=[self.ot_ajena.pk]),
        )
        self.assertContains(response, 'Materiales (0)')

    def test_cannot_open_another_technicians_closure(self):
        response = self.client.get(reverse('cierre_ot', args=[self.ot_ajena.pk]))

        self.assertEqual(response.status_code, 404)

    def test_cannot_create_catalog_material_for_another_technicians_order(self):
        response = self.client.post(
            reverse('crear_material_ajax', args=[self.ot_ajena.pk]),
            data='{"categoria":"repuestos","nombre":"Correa","costo_base":"7.00"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Material.objects.filter(codigo='MAT-002').exists())


class GoogleDriveMediaStorageTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username='drive-storage-user',
            password='test-password',
        )
        self.ubicacion = Ubicacion.objects.create(
            nombre='Ubicación Drive',
            codigo='UBI-DRIVE',
        )
        self.equipo = Equipo.objects.create(
            nombre='Equipo Drive',
            codigo='EQ-DRIVE',
            ubicacion=self.ubicacion,
        )
        estado, _ = Estado.objects.get_or_create(nombre='en proceso')
        solicitud = Solicitud.objects.create(
            creado_por=self.user.username,
            descripcion_problema='Prueba almacenamiento Drive',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=estado,
        )
        self.ot = OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado=self.user.username,
            estado=estado,
        )
        self.storage = GoogleDriveMediaStorage()

    @override_settings(
        GOOGLE_DRIVE_MEDIA_ENABLED=True,
        GOOGLE_DRIVE_MEDIA_FOLDER_ID='drive-folder',
        RAILWAY_ENVIRONMENT='',
    )
    def test_drive_storage_upload_is_private_and_uses_short_field_name(self):
        upload = SimpleUploadedFile(
            'una-factura-con-un-nombre-muy-largo.png',
            b'image-bytes',
            content_type='image/png',
        )
        with patch(
            'gestion_mantenimiento.Gestion_ot.drive_utils.subir_archivo_privado_a_drive',
            return_value={'drive_file_id': 'drive-file-id'},
        ) as upload_to_drive:
            saved_name = self.storage.save(
                'materiales/facturas/una-factura-con-un-nombre-muy-largo.png',
                upload,
            )

        self.assertEqual(saved_name, 'drive/drive-file-id/file.png')
        self.assertLessEqual(len(saved_name), 100)
        upload_to_drive.assert_called_once()
        self.assertEqual(
            self.storage.url(saved_name),
            reverse('drive_media', args=['drive-file-id']),
        )

    @override_settings(
        GOOGLE_DRIVE_MEDIA_ENABLED=True,
        GOOGLE_DRIVE_MEDIA_FOLDER_ID='drive-folder',
        RAILWAY_ENVIRONMENT='',
    )
    def test_drive_storage_opens_private_file_through_drive_helper(self):
        with patch(
            'gestion_mantenimiento.Gestion_ot.drive_utils.descargar_archivo_privado_drive',
            return_value=BytesIO(b'private-image'),
        ) as download_from_drive:
            with self.storage.open('drive/drive-file-id/file.png') as image_file:
                self.assertEqual(image_file.read(), b'private-image')

        download_from_drive.assert_called_once_with('drive-file-id')

    @override_settings(
        GOOGLE_DRIVE_MEDIA_ENABLED=True,
        GOOGLE_DRIVE_MEDIA_FOLDER_ID='drive-folder',
        RAILWAY_ENVIRONMENT='',
    )
    def test_pdf_image_helper_reads_private_drive_file_without_local_path(self):
        material = Material.objects.create(
            codigo='DRIVE-PDF-001',
            nombre='Material PDF',
            costo_base='10.00',
            precio_venta_sugerido='14.29',
        )
        material_ot = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=material,
            cantidad='1',
            costo_real='10.00',
        )
        material_ot.foto_factura.name = 'drive/pdf-file-id/file.png'

        with patch(
            'gestion_mantenimiento.Gestion_ot.drive_utils.descargar_archivo_privado_drive',
            return_value=BytesIO(b'private-image-for-pdf'),
        ):
            image_path, is_temp = views.obtener_imagen_temporal_para_pdf(
                material_ot.foto_factura
            )

        self.assertTrue(is_temp)
        with open(image_path, 'rb') as image_file:
            self.assertEqual(image_file.read(), b'private-image-for-pdf')
        os.remove(image_path)

        template_file_field = MaterialOT(
            orden_trabajo=self.ot,
            material=material,
            cantidad='1',
            costo_real='10.00',
            foto_factura='drive/pdf-file-id/file.png',
        ).foto_factura
        with patch(
            'gestion_mantenimiento.Gestion_ot.drive_utils.descargar_archivo_privado_drive',
            return_value=BytesIO(b'private-image-for-template'),
        ):
            template_image_path, is_temp = _obtener_imagen_temporal(
                template_file_field
            )

        self.assertTrue(is_temp)
        with open(template_image_path, 'rb') as image_file:
            self.assertEqual(image_file.read(), b'private-image-for-template')
        os.remove(template_image_path)

    @override_settings(
        GOOGLE_DRIVE_MEDIA_ENABLED=False,
        RAILWAY_ENVIRONMENT='production',
    )
    def test_missing_drive_configuration_fails_in_railway(self):
        upload = SimpleUploadedFile('invoice.png', b'image-bytes')
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            'Google Drive media storage requiere credenciales',
        ):
            self.storage.save('materiales/facturas/invoice.png', upload)

    def test_private_drive_media_view_checks_ot_access(self):
        from django.contrib.auth import get_user_model

        material = Material.objects.create(
            codigo='DRIVE-001',
            nombre='Material con factura privada',
            costo_base='10.00',
            precio_venta_sugerido='14.29',
        )
        material_ot = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=material,
            cantidad='1',
            costo_real='10.00',
        )
        material_ot.foto_factura.name = 'drive/private-file-id/file.png'
        material_ot.save(update_fields=['foto_factura'])

        with patch.object(
            GoogleDriveMediaStorage,
            'open',
            return_value=File(BytesIO(b'private-image'), name='file.png'),
        ):
            self.client.force_login(self.user)
            response = self.client.get(
                reverse('drive_media', args=['private-file-id'])
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(b''.join(response.streaming_content), b'private-image')

            self.client.logout()
            response = self.client.get(
                reverse('drive_media', args=['private-file-id'])
            )
            self.assertEqual(response.status_code, 302)

            other_user = get_user_model().objects.create_user(
                username='other-drive-user',
                password='test-password',
            )
            self.client.force_login(other_user)
            response = self.client.get(
                reverse('drive_media', args=['private-file-id'])
            )
            self.assertEqual(response.status_code, 404)


class RentabilidadAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from gestion_mantenimiento.users.models import ConfiguracionPago

        self.user_model = get_user_model()
        self.tecnico = self.user_model.objects.create_user(
            username='tecnico-rentabilidad',
            password='test-password',
        )
        self.tecnico.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.admin = self.user_model.objects.create_user(
            username='supervisor-rentabilidad',
            password='test-password',
        )
        self.admin.groups.add(Group.objects.get_or_create(name='Supervisor')[0])
        self.ubicacion = Ubicacion.objects.create(
            nombre='Cliente rentabilidad',
            codigo='UBI-RENT',
        )
        self.equipo = Equipo.objects.create(
            nombre='Equipo rentabilidad',
            codigo='EQ-RENT',
            ubicacion=self.ubicacion,
        )
        self.estado, _ = Estado.objects.get_or_create(nombre='finalizada')
        self.estado_revision, _ = Estado.objects.get_or_create(nombre='en revision')
        solicitud = Solicitud.objects.create(
            creado_por=self.tecnico.username,
            descripcion_problema='Prueba rentabilidad',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
        )
        self.ot = OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado=self.tecnico.username,
            estado=self.estado,
        )
        hoy = timezone.localdate()
        fecha_cierre = timezone.make_aware(
            datetime.combine(hoy, datetime.min.time().replace(hour=11))
        )
        CierreOt.objects.create(
            orden_trabajo=self.ot,
            fecha_inicio_actividad=fecha_cierre,
            hora_inicio=datetime.min.time().replace(hour=9),
            hora_fin=datetime.min.time().replace(hour=11),
            valor_mano_obra=Decimal('60.00'),
        )
        self.material = Material.objects.create(
            codigo='MAT-RENT-001',
            nombre='Material rentabilidad',
            costo_base=Decimal('50.00'),
            precio_venta_sugerido=Decimal('100.00'),
        )
        MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=self.material,
            cantidad=Decimal('2.00'),
            costo_real=Decimal('50.00'),
            precio_venta_aplicado=Decimal('100.00'),
        )
        ConfiguracionPago.objects.create(
            usuario=self.tecnico,
            tipo_pago='por_dia',
            valor_dia=Decimal('700.00'),
        )

    def test_supervisor_can_access_and_sees_rentabilidad_link(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('rentabilidad_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Panel de rentabilidad')
        self.assertContains(response, 'profit-technician-chart')
        self.assertContains(response, 'profit-client-chart')
        self.assertContains(response, reverse('rentabilidad_admin'))

    def test_technician_is_redirected_without_access(self):
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse('rentabilidad_admin'))

        self.assertRedirects(response, reverse('dashboard'))

    def test_calculates_material_and_manual_labor_income_payroll_and_gain(self):
        self.client.force_login(self.admin)
        hoy = timezone.localdate().isoformat()
        response = self.client.get(
            reverse('rentabilidad_admin'),
            {'desde': hoy, 'hasta': hoy, 'tecnico': self.tecnico.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cantidad_calculable'], 1)
        fila = response.context['filas'][0]
        self.assertEqual(fila['estado_facturacion'], 'pendiente')
        self.assertFalse(fila['factura_dian_subida'])
        self.assertEqual(response.context['totales']['ingreso_materiales'], Decimal('200.00'))
        self.assertEqual(response.context['totales']['valor_mano_obra'], Decimal('60.00'))
        self.assertEqual(response.context['totales']['ingresos'], Decimal('260.00'))
        self.assertEqual(response.context['totales']['costo_materiales'], Decimal('100.00'))
        self.assertEqual(response.context['totales']['costo_nomina'], Decimal('200.00'))
        self.assertEqual(response.context['totales']['ganancia'], Decimal('-40.00'))
        self.assertEqual(response.context['por_tecnico'][0]['cantidad_ots'], 1)
        self.assertEqual(response.context['por_cliente'][0]['ganancia'], Decimal('-40.00'))
        self.assertEqual(response.context['costos_totales'], Decimal('300.00'))
        self.assertEqual(response.context['margen_total'], Decimal('-15.38'))
        self.assertEqual(
            response.context['datos_graficos']['tecnicos'],
            [{
                'nombre': self.ot.tecnico_display,
                'ingresos': Decimal('260.00'),
                'costos': Decimal('300.00'),
            }],
        )
        self.assertEqual(
            response.context['datos_graficos']['clientes'][0]['ingresos'],
            Decimal('260.00'),
        )
        self.assertContains(response, 'Ingreso total')
        self.assertContains(response, 'Mano de obra')

    def test_rentabilidad_groups_by_root_location_and_orders_newest_first(self):
        raiz_duplicada = Ubicacion.objects.create(
            nombre=self.ubicacion.nombre,
            codigo='UBI-RENT-DUP',
        )
        sububicaciones = [
            Ubicacion.objects.create(
                nombre='Sucursal principal',
                codigo='UBI-RENT-CHILD',
                parent=self.ubicacion,
            ),
            Ubicacion.objects.create(
                nombre='Sucursal duplicada',
                codigo='UBI-RENT-DUP-CHILD',
                parent=raiz_duplicada,
            ),
        ]
        fecha_cierre = self.ot.cierreot.fecha_inicio_actividad

        for indice, ubicacion in enumerate(sububicaciones, start=1):
            equipo = Equipo.objects.create(
                nombre=f'Equipo rentabilidad adicional {indice}',
                codigo=f'EQ-RENT-ADD-{indice}',
                ubicacion=ubicacion,
            )
            solicitud = Solicitud.objects.create(
                creado_por=self.tecnico.username,
                descripcion_problema='Prueba de agrupación por raíz',
                equipo=equipo,
                ubicacion=ubicacion,
                estado=self.estado,
            )
            ot = OrdenTrabajo.objects.create(
                solicitud=solicitud,
                tecnico_asignado=self.tecnico.username,
                estado=self.estado,
            )
            CierreOt.objects.create(
                orden_trabajo=ot,
                fecha_inicio_actividad=fecha_cierre,
                hora_inicio=datetime.min.time().replace(hour=9),
                hora_fin=datetime.min.time().replace(hour=11),
                valor_mano_obra=Decimal('60.00'),
            )

        self.client.force_login(self.admin)
        hoy = timezone.localdate().isoformat()
        response = self.client.get(
            reverse('rentabilidad_admin'),
            {'desde': hoy, 'hasta': hoy},
        )

        self.assertEqual(response.status_code, 200)
        consecutivos = [
            fila['ot'].solicitud.consecutivo
            for fila in response.context['filas']
        ]
        self.assertEqual(consecutivos, sorted(consecutivos, reverse=True))
        resumenes_cliente = response.context['por_cliente']
        self.assertEqual(len(resumenes_cliente), 2)
        self.assertEqual(
            [resumen['nombre'] for resumen in resumenes_cliente],
            [self.ubicacion.nombre, self.ubicacion.nombre],
        )
        self.assertEqual(
            sorted(resumen['cantidad_ots'] for resumen in resumenes_cliente),
            [1, 2],
        )

    def test_rentabilidad_context_reports_uploaded_dian_invoice(self):
        cierre = self.ot.cierreot
        cierre.factura_dian_drive_id = 'private-drive-file-id'
        cierre.estado_facturacion = 'facturada'
        cierre.save(update_fields=[
            'factura_dian_drive_id',
            'estado_facturacion',
        ])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('rentabilidad_admin'))

        self.assertEqual(response.status_code, 200)
        fila = response.context['filas'][0]
        self.assertEqual(fila['estado_facturacion'], 'facturada')
        self.assertTrue(fila['factura_dian_subida'])
        self.assertContains(response, 'Facturada')
        self.assertContains(response, 'Ver PDF')
        self.assertContains(
            response,
            reverse('descargar_factura_dian', args=[self.ot.pk]),
        )

    def test_rentabilidad_table_shows_invoice_status_and_actions(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('rentabilidad_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estado factura')
        self.assertContains(response, 'Prefactura')
        self.assertContains(response, 'Ver / Subir PDF DIAN')
        self.assertContains(
            response,
            reverse('subir_factura_dian', args=[self.ot.pk]),
        )

    def test_upload_dian_invoice_saves_drive_id_and_marks_billed(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from gestion_mantenimiento.Gestion_ot import views

        self.client.force_login(self.admin)
        pdf = SimpleUploadedFile(
            'factura.pdf',
            b'%PDF-1.7\ncontenido de prueba',
            content_type='application/pdf',
        )

        with patch.dict('os.environ', {'GOOGLE_DRIVE_FOLDER_ID': 'drive-folder-id'}):
            with patch.object(
                views,
                'subir_pdf_privado_a_drive',
                return_value={'drive_file_id': 'private-dian-file-id'},
            ) as upload:
                response = self.client.post(
                    reverse('subir_factura_dian', args=[self.ot.pk]),
                    {'factura_dian': pdf},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True})
        upload.assert_called_once_with(
            b'%PDF-1.7\ncontenido de prueba',
            f'factura-dian-ot-{self.ot.pk}.pdf',
            folder_id='drive-folder-id',
        )
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.factura_dian_drive_id, 'private-dian-file-id')
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'facturada')

    def test_upload_dian_invoice_rejects_non_pdf_content(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from gestion_mantenimiento.Gestion_ot import views

        self.client.force_login(self.admin)
        file_upload = SimpleUploadedFile(
            'factura.pdf',
            b'not a PDF',
            content_type='application/pdf',
        )

        with patch.object(views, 'subir_pdf_privado_a_drive') as upload:
            response = self.client.post(
                reverse('subir_factura_dian', args=[self.ot.pk]),
                {'factura_dian': file_upload},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn('no parece ser un PDF válido', response.json()['error'])
        upload.assert_not_called()
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'pendiente')

    def test_upload_dian_invoice_requires_configured_drive_folder(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from gestion_mantenimiento.Gestion_ot import views

        self.client.force_login(self.admin)
        file_upload = SimpleUploadedFile(
            'factura.pdf',
            b'%PDF-1.7\ncontenido de prueba',
            content_type='application/pdf',
        )

        with patch.dict('os.environ', {'GOOGLE_DRIVE_FOLDER_ID': ''}):
            response = self.client.post(
                reverse('subir_factura_dian', args=[self.ot.pk]),
                {'factura_dian': file_upload},
            )

        self.assertEqual(response.status_code, 503)
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'pendiente')

    def test_upload_dian_invoice_rejects_duplicate_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from gestion_mantenimiento.Gestion_ot import views

        cierre = self.ot.cierreot
        cierre.factura_dian_drive_id = 'existing-private-file-id'
        cierre.estado_facturacion = 'facturada'
        cierre.save(update_fields=['factura_dian_drive_id', 'estado_facturacion'])
        self.client.force_login(self.admin)
        file_upload = SimpleUploadedFile(
            'factura.pdf',
            b'%PDF-1.7\ncontenido de prueba',
            content_type='application/pdf',
        )

        with patch.object(views, 'subir_pdf_privado_a_drive') as upload:
            response = self.client.post(
                reverse('subir_factura_dian', args=[self.ot.pk]),
                {'factura_dian': file_upload},
            )

        self.assertEqual(response.status_code, 409)
        upload.assert_not_called()

    def test_invoice_dian_download_is_private_and_streamed(self):
        from gestion_mantenimiento.Gestion_ot import views

        cierre = self.ot.cierreot
        cierre.factura_dian_drive_id = 'private-dian-file-id'
        cierre.estado_facturacion = 'facturada'
        cierre.save(update_fields=['factura_dian_drive_id', 'estado_facturacion'])
        self.client.force_login(self.admin)

        with patch.object(
            views,
            'iterar_archivo_privado_drive',
            return_value=iter([b'%PDF-1.7\nprivate content']),
        ) as download:
            response = self.client.get(
                reverse('descargar_factura_dian', args=[self.ot.pk])
            )
            content = b''.join(response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(content, b'%PDF-1.7\nprivate content')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        download.assert_called_once_with('private-dian-file-id')

    def test_technician_cannot_upload_or_download_dian_invoice(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from gestion_mantenimiento.Gestion_ot import views

        cierre = self.ot.cierreot
        cierre.factura_dian_drive_id = 'private-dian-file-id'
        cierre.estado_facturacion = 'facturada'
        cierre.save(update_fields=['factura_dian_drive_id', 'estado_facturacion'])
        self.client.force_login(self.tecnico)
        file_upload = SimpleUploadedFile(
            'factura.pdf',
            b'%PDF-1.7\ncontenido de prueba',
            content_type='application/pdf',
        )

        with patch.object(views, 'subir_pdf_privado_a_drive') as upload:
            response = self.client.post(
                reverse('subir_factura_dian', args=[self.ot.pk]),
                {'factura_dian': file_upload},
            )

        self.assertEqual(response.status_code, 403)
        upload.assert_not_called()
        response = self.client.get(
            reverse('descargar_factura_dian', args=[self.ot.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_invoice_detail_includes_items_and_reconciles_to_rentabilidad_total(self):
        servicio_material = Material.objects.create(
            codigo='S001',
            categoria='servicios',
            nombre='Mano de obra - Diagnóstico',
            costo_base=Decimal('50.00'),
            precio_venta_sugerido=Decimal('50.00'),
        )
        ServicioOT.objects.create(
            orden_trabajo=self.ot,
            nombre=servicio_material.nombre,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('50.00'),
        )
        cierre = self.ot.cierreot
        cierre.valor_mano_obra = Decimal('60.00')
        cierre.descripcion_falla = 'Mantenimiento preventivo'
        cierre.save(update_fields=['valor_mano_obra', 'descripcion_falla'])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('detalle_factura_ot', args=[self.ot.pk])
        )

        self.assertEqual(response.status_code, 200)
        factura = response.json()['factura']
        self.assertEqual(factura['cliente'], self.ubicacion.nombre)
        self.assertEqual(factura['equipo'], self.equipo.nombre)
        self.assertEqual(factura['descripcion'], 'Mantenimiento preventivo')
        self.assertEqual(factura['materiales'][0]['codigo'], self.material.codigo)
        self.assertEqual(factura['materiales'][0]['total'], '200.00')
        self.assertEqual(factura['servicios'][0]['codigo'], 'S001')
        self.assertEqual(factura['servicios'][0]['total'], '50.00')
        self.assertEqual(factura['servicios'][1]['descripcion'], 'Mano de obra / ajuste registrado')
        self.assertEqual(factura['servicios'][1]['total'], '10.00')
        self.assertEqual(factura['subtotal'], '260.00')
        self.assertEqual(factura['total'], '260.00')
        self.assertEqual(factura['impuestos'], '0.00')

    def test_invoice_detail_is_forbidden_to_technician(self):
        self.client.force_login(self.tecnico)

        response = self.client.get(
            reverse('detalle_factura_ot', args=[self.ot.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_manual_labor_form_field_is_optional_and_defaults_to_zero(self):
        from gestion_mantenimiento.Gestion_ot.forms import CierreOtFacturacionForm

        cierre = self.ot.cierreot
        form = CierreOtFacturacionForm(data={}, instance=cierre)
        form.full_clean()

        self.assertFalse(form.fields['valor_mano_obra'].required)
        self.assertEqual(form.cleaned_data['valor_mano_obra'], Decimal('0.00'))
        self.assertEqual(set(form.fields), {'valor_mano_obra'})

    def test_model_rejects_facturada_without_dian_pdf(self):
        from django.core.exceptions import ValidationError

        cierre = self.ot.cierreot
        cierre.estado_facturacion = 'facturada'
        cierre.factura_dian_drive_id = ''

        with self.assertRaises(ValidationError) as error:
            cierre.clean()

        self.assertIn(
            'No se puede marcar como Facturada sin adjuntar el PDF de la DIAN.',
            error.exception.message_dict['estado_facturacion'],
        )

    def test_invalid_date_range_is_rejected(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('rentabilidad_admin'),
            {'desde': '2026-10-20', 'hasta': '2026-10-01'},
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_management_view_shows_materials_and_invoice_values(self):
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot)
        material_ot.foto_factura.name = 'materiales/facturas/factura-prueba.png'
        material_ot.save(update_fields=['foto_factura'])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('gestionar_ot_admin', args=[self.ot.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestión y facturación')
        self.assertContains(response, self.material.nombre)
        self.assertContains(response, 'Ver factura')
        self.assertContains(response, 'Total facturado')
        self.assertContains(response, 'Generar Prefactura')
        self.assertNotContains(response, 'Estado de facturación')
        self.assertNotContains(response, 'name="estado_facturacion"')
        self.assertNotContains(response, 'Estado operativo (solo lectura)')
        self.assertNotContains(response, 'OT Finalizada')
        self.assertNotContains(response, 'Estado de la OT</strong>')
        self.assertContains(response, 'Agregar material (Admin)')
        self.assertContains(response, 'id="admin-material-search" list="admin-materials-datalist"')
        self.assertContains(
            response,
            'id="aplicar-margen" name="aplicar_margen" value="1" checked',
        )
        self.assertContains(response, 'Aplicar margen (0.7)')
        self.assertNotContains(response, 'admin-open-create-material')
        self.assertNotContains(response, 'Servicios y mano de obra')
        self.assertEqual(response.content.count(b'Facturaci\xc3\xb3n del servicio'), 1)
        self.assertContains(response, 'for="admin-service-name">Servicio</label>')
        self.assertContains(response, '.admin-service-form > button { width: auto; padding: 8px 20px; justify-self: start; }')
        self.assertNotContains(response, 'Valor manual de mano de obra / servicio')
        self.assertNotContains(response, 'name="valor_mano_obra"')
        self.assertContains(response, 'id="admin-service-name" name="nombre"')
        self.assertContains(response, 'id="admin-service-quantity" name="cantidad"')
        self.assertContains(response, 'id="admin-service-price" name="precio_unitario"')

    def test_service_catalog_includes_machinery_cold_and_locative_categories(self):
        catalog_materials = [
            ('MAQ-OT-001', 'maquinaria', 'Maquinaria para tercerizar'),
            ('FRI-OT-001', 'frio', 'Equipo frío para tercerizar'),
            ('LOC-OT-001', 'locativos', 'Trabajo locativo para tercerizar'),
            ('SER-OT-001', 'servicios', 'Servicio catalogado'),
        ]
        for code, category, name in catalog_materials:
            Material.objects.create(
                codigo=code,
                categoria=category,
                nombre=name,
                costo_base=Decimal('100.00'),
                precio_venta_sugerido=Decimal('150.00'),
            )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('gestionar_ot_admin', args=[self.ot.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="filtro-categoria-material" name="categoria"')
        for prefix in ('R', 'M', 'F', 'L'):
            self.assertContains(response, f'<option value="{prefix}">')
        self.assertNotContains(response, 'filtro-categoria-servicio')
        services = response.context['servicios_catalogo']
        self.assertSetEqual(
            set(services.values_list('categoria', flat=True)),
            {'repuestos', 'maquinaria', 'frio', 'locativos', 'servicios'},
        )
        for _, _, name in catalog_materials:
            self.assertContains(response, name)
        self.assertContains(response, 'data-precio="100.00"')
        self.assertContains(response, 'data-categoria="maquinaria" data-precio="100.00"')
        self.assertContains(response, 'data-categoria="servicios" data-precio="150.00"')
        for category in ('repuestos', 'maquinaria', 'frio', 'locativos', 'servicios'):
            self.assertContains(response, f'data-categoria="{category}"')

    def test_admin_can_create_service_catalog_item_with_selected_category_and_code(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('agregar_servicio_ot_admin', args=[self.ot.pk]),
            {
                'categoria': 'maquinaria',
                'nombre': 'Motor de reemplazo',
                'cantidad': '1',
                'precio_unitario': '75000.00',
            },
        )

        self.assertRedirects(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        material = Material.objects.get(nombre='Motor de reemplazo')
        self.assertEqual(material.categoria, 'maquinaria')
        self.assertTrue(material.codigo.startswith('M'))
        self.assertEqual(material.precio_venta_sugerido, Decimal('75000.00'))
        service_line = ServicioOT.objects.get(orden_trabajo=self.ot)
        self.assertEqual(service_line.total, Decimal('75000.00'))
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('75060.00'))

    def test_non_service_material_uses_markup_when_added_by_admin(self):
        self.client.force_login(self.admin)
        categories = {
            'repuestos': 'R',
            'maquinaria': 'M',
            'frio': 'F',
            'locativos': 'L',
        }
        expected_income = Decimal('200.00')
        for category, prefix in categories.items():
            with self.subTest(category=category):
                material = Material.objects.create(
                    codigo=f'{prefix}-MARGIN-TEST',
                    categoria=category,
                    nombre=f'Material categoría {category}',
                    costo_base=Decimal('350000.00'),
                    precio_venta_sugerido=Decimal('350000.00'),
                )
                response = self.client.post(
                    reverse('agregar_material_ot_admin', args=[self.ot.pk]),
                    {
                        'categoria': prefix,
                        'material': material.pk,
                        'cantidad': '2.00',
                        'costo_real': '350000.00',
                    },
                )

                self.assertRedirects(
                    response,
                    reverse('gestionar_ot_admin', args=[self.ot.pk]),
                )
                material_ot = MaterialOT.objects.get(
                    orden_trabajo=self.ot,
                    material=material,
                )
                self.assertEqual(
                    material_ot.precio_venta_aplicado,
                    Decimal('500000.00'),
                )
                self.assertEqual(material_ot.cantidad, Decimal('2.00'))
                self.assertEqual(
                    material_ot.precio_venta_aplicado * material_ot.cantidad,
                    Decimal('1000000.00'),
                )
                expected_income += Decimal('1000000.00')
                response = self.client.get(
                    reverse('gestionar_ot_admin', args=[self.ot.pk]),
                )
                self.assertEqual(
                    response.context['resumen']['ingreso_materiales'],
                    expected_income,
                )

    def test_admin_can_create_material_using_selected_category_and_code_prefix(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('agregar_material_ot_admin', args=[self.ot.pk]),
            {
                'categoria': 'M',
                'material_name': 'Motor de reemplazo nuevo',
                'cantidad': '1.00',
                'costo_real': '70000.00',
                'aplicar_margen': '1',
            },
        )

        self.assertRedirects(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        material = Material.objects.get(nombre='Motor de reemplazo nuevo')
        self.assertEqual(material.categoria, 'maquinaria')
        self.assertTrue(material.codigo.startswith('M'))
        self.assertEqual(material.precio_venta_sugerido, Decimal('100000.00'))
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot, material=material)
        self.assertEqual(material_ot.precio_venta_aplicado, Decimal('100000.00'))

    def test_admin_can_add_new_material_without_applying_margin(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('agregar_material_ot_admin', args=[self.ot.pk]),
            {
                'categoria': 'R',
                'material_name': 'Material especial sin margen',
                'cantidad': '2.00',
                'costo_real': '70000.00',
                'aplicar_margen': '0',
            },
        )

        self.assertRedirects(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        material = Material.objects.get(nombre='Material especial sin margen')
        self.assertEqual(material.costo_base, Decimal('70000.00'))
        self.assertEqual(material.precio_venta_sugerido, Decimal('100000.00'))
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot, material=material)
        self.assertEqual(material_ot.costo_real, Decimal('70000.00'))
        self.assertEqual(material_ot.precio_venta_aplicado, Decimal('70000.00'))

    def test_admin_management_post_ignores_tampered_billed_state_without_pdf(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
            {'estado_facturacion': 'facturada'},
        )

        self.assertRedirects(response, reverse('facturacion_admin'))
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('60.00'))
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'pendiente')

    def test_admin_management_post_preserves_existing_dian_invoice(self):
        self.ot.cierreot.factura_dian_drive_id = 'private-drive-file-id'
        self.ot.cierreot.estado_facturacion = 'facturada'
        self.ot.cierreot.save(update_fields=[
            'factura_dian_drive_id',
            'estado_facturacion',
        ])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
            {'estado_facturacion': 'facturada'},
        )

        self.assertRedirects(response, reverse('facturacion_admin'))
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'facturada')

    def test_billing_ajax_ignores_tampered_invoice_status_and_returns_redirect(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('actualizar_mano_obra', args=[self.ot.pk]),
            {'estado_facturacion': 'facturada'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], reverse('facturacion_admin'))
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('60.00'))
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'pendiente')


    def test_technician_cannot_access_admin_management_or_update_materials(self):
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot)
        self.client.force_login(self.tecnico)

        response = self.client.get(
            reverse('gestionar_ot_admin', args=[self.ot.pk])
        )
        self.assertRedirects(response, reverse('dashboard'))

        response = self.client.post(
            reverse(
                'actualizar_material_ot_admin',
                args=[self.ot.pk, material_ot.pk],
            ),
            {'cantidad': '4', 'costo_real': '50', 'precio_venta_aplicado': '100'},
        )
        self.assertRedirects(response, reverse('dashboard'))

        response = self.client.post(
            reverse('agregar_material_ot_admin', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1',
                'costo_real': '30.00',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(
            MaterialOT.objects.filter(orden_trabajo=self.ot).count(),
            1,
        )

        response = self.client.post(
            reverse('actualizar_mano_obra', args=[self.ot.pk]),
            {'valor_mano_obra': '900000'},
        )
        self.assertEqual(response.status_code, 403)
        material_ot.refresh_from_db()
        self.assertEqual(material_ot.cantidad, Decimal('2.00'))
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('60.00'))

    def test_admin_updates_billing_without_changing_operational_state(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('actualizar_mano_obra', args=[self.ot.pk]),
            {
                'valor_mano_obra': '500000.00',
                # Legacy/tampered submissions must not mutate the operational state.
                'estado': self.estado_revision.pk,
                'estado_facturacion': 'facturada',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_materiales'], '200.00')
        self.assertEqual(response.json()['mano_obra'], '500000.00')
        self.assertEqual(response.json()['total_facturado'], '500200.00')
        self.assertEqual(response.json()['costo_nomina'], '200.00')
        self.assertEqual(response.json()['ganancia'], '499900.00')
        self.assertEqual(response.json()['margen'], '99.94')
        self.assertEqual(response.json()['estado_facturacion'], 'pendiente')
        self.ot.refresh_from_db()
        self.assertEqual(self.ot.estado, self.estado)
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('500000.00'))
        self.assertEqual(self.ot.cierreot.estado_facturacion, 'pendiente')

    def test_admin_can_add_material_to_finalized_order_and_financials_update(self):
        self.assertEqual(self.ot.estado.nombre, 'finalizada')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('agregar_material_ot_admin', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1.00',
                'costo_real': '30.00',
                'observaciones': 'Material omitido por el técnico',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        material_agregado = MaterialOT.objects.get(
            orden_trabajo=self.ot,
            observaciones='Material omitido por el técnico',
        )
        self.assertEqual(material_agregado.cantidad, Decimal('1.00'))
        self.assertEqual(material_agregado.costo_real, Decimal('30.00'))
        self.assertEqual(
            material_agregado.precio_venta_aplicado,
            Decimal('42.86'),
        )

        response = self.client.get(
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['resumen']['ingreso_materiales'],
            Decimal('242.86'),
        )
        self.assertEqual(
            response.context['resumen']['costo_materiales'],
            Decimal('130.00'),
        )

    def test_admin_can_create_catalog_material_for_finalized_order(self):
        self.assertEqual(self.ot.estado.nombre, 'finalizada')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('crear_material_ajax', args=[self.ot.pk]),
            data='{"categoria":"repuestos","nombre":"Repuesto admin nuevo","costo_base":"70.00"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['codigo'], 'RRA01')
        material = Material.objects.get(codigo='RRA01')
        self.assertEqual(
            material.precio_venta_sugerido,
            Decimal('100.00'),
        )
        response = self.client.get(
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        self.assertTrue(
            response.context['material_admin_form'].fields['material']
            .queryset.filter(pk=material.pk).exists()
        )
        self.assertContains(response, 'id="admin-material-search"')
        self.assertContains(response, 'data-material-id="')
        self.assertContains(response, 'id="servicios-datalist"')

    def test_admin_can_add_a_new_service_line_and_save_it_to_the_catalog(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('agregar_servicio_ot_admin', args=[self.ot.pk]),
            {
                'nombre': 'Servicio de mantenimiento especial',
                'cantidad': '2.00',
                'precio_unitario': '150000.00',
            },
        )

        self.assertRedirects(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        service_line = ServicioOT.objects.get(orden_trabajo=self.ot)
        self.assertEqual(service_line.nombre, 'Servicio de mantenimiento especial')
        self.assertEqual(service_line.total, Decimal('300000.00'))
        catalog_service = Material.objects.get(
            categoria='servicios',
            nombre='Servicio de mantenimiento especial',
        )
        self.assertEqual(catalog_service.costo_base, Decimal('0.00'))
        self.assertEqual(
            catalog_service.precio_venta_sugerido,
            Decimal('150000.00'),
        )
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('300060.00'))
        response = self.client.get(reverse('gestionar_ot_admin', args=[self.ot.pk]))
        self.assertContains(response, '$ 300.000,00')
        self.assertContains(response, '$ 300.060,00')

    def test_admin_can_delete_service_and_recalculate_labor_and_invoice(self):
        servicio = ServicioOT.objects.create(
            orden_trabajo=self.ot,
            nombre='Servicio para eliminar',
            cantidad=Decimal('2.00'),
            precio_unitario=Decimal('50.00'),
        )
        cierre = self.ot.cierreot
        cierre.valor_mano_obra = Decimal('160.00')
        cierre.save(update_fields=['valor_mano_obra'])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        self.assertContains(response, 'btn-eliminar-servicio')
        self.assertContains(response, reverse(
            'eliminar_servicio_ot_admin',
            args=[self.ot.pk, servicio.pk],
        ))

        response = self.client.post(
            reverse('eliminar_servicio_ot_admin', args=[self.ot.pk, servicio.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mano_obra'], '60.00')
        self.assertEqual(response.json()['total_facturado'], '260.00')
        self.assertFalse(ServicioOT.objects.filter(pk=servicio.pk).exists())
        cierre.refresh_from_db()
        self.assertEqual(cierre.valor_mano_obra, Decimal('60.00'))

    def test_technician_cannot_delete_admin_service_line(self):
        servicio = ServicioOT.objects.create(
            orden_trabajo=self.ot,
            nombre='Servicio protegido',
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('50.00'),
        )
        self.client.force_login(self.tecnico)

        response = self.client.post(
            reverse('eliminar_servicio_ot_admin', args=[self.ot.pk, servicio.pk]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ServicioOT.objects.filter(pk=servicio.pk).exists())

    def test_adding_catalog_machinery_as_service_does_not_create_duplicate_catalog_entry(self):
        machinery = Material.objects.create(
            codigo='MAQ-OT-002',
            categoria='maquinaria',
            nombre='Equipo tercerizado',
            costo_base=Decimal('116000.00'),
            precio_venta_sugerido=Decimal('165714.29'),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('gestionar_ot_admin', args=[self.ot.pk]))
        self.assertContains(
            response,
            'data-categoria="maquinaria" data-precio="116000.00"',
        )

        response = self.client.post(
            reverse('agregar_servicio_ot_admin', args=[self.ot.pk]),
            {
                'nombre': machinery.nombre,
                'cantidad': '2.00',
                'precio_unitario': '116000.00',
            },
        )

        self.assertRedirects(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        self.assertEqual(
            Material.objects.filter(nombre=machinery.nombre).count(),
            1,
        )
        service_line = ServicioOT.objects.get(orden_trabajo=self.ot)
        self.assertEqual(service_line.total, Decimal('232000.00'))
        self.ot.cierreot.refresh_from_db()
        self.assertEqual(self.ot.cierreot.valor_mano_obra, Decimal('232060.00'))

    def test_admin_can_add_free_text_material_with_real_cost_as_catalog_base_cost(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('agregar_material_ot_admin', args=[self.ot.pk]),
            {
                'material_name': 'Material de texto libre',
                'cantidad': '2.00',
                'costo_real': '70000.00',
            },
        )

        self.assertRedirects(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        material = Material.objects.get(nombre='Material de texto libre')
        self.assertEqual(material.costo_base, Decimal('70000.00'))
        self.assertEqual(material.precio_venta_sugerido, Decimal('100000.00'))
        material_ot = MaterialOT.objects.get(
            orden_trabajo=self.ot,
            material=material,
        )
        self.assertEqual(material_ot.costo_real, Decimal('70000.00'))
        self.assertEqual(material_ot.precio_venta_aplicado, Decimal('100000.00'))

    def test_admin_can_correct_or_delete_order_material(self):
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                'actualizar_material_ot_admin',
                args=[self.ot.pk, material_ot.pk],
            ),
            {
                'cantidad': '3.00',
                'costo_real': '40.00',
                'precio_venta_aplicado': '80.00',
            },
        )
        self.assertRedirects(
            response,
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        material_ot.refresh_from_db()
        self.assertEqual(material_ot.cantidad, Decimal('3.00'))
        self.assertEqual(material_ot.costo_real, Decimal('40.00'))
        self.assertEqual(material_ot.precio_venta_aplicado, Decimal('80.00'))

        response = self.client.post(
            reverse(
                'eliminar_material_ot_admin',
                args=[self.ot.pk, material_ot.pk],
            )
        )
        self.assertRedirects(
            response,
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        self.assertFalse(MaterialOT.objects.filter(pk=material_ot.pk).exists())

    def test_technician_closure_form_does_not_expose_manual_labor_price(self):
        from gestion_mantenimiento.Gestion_ot.forms import CierreOtForm

        self.assertNotIn('valor_mano_obra', CierreOtForm().fields)
        self.client.force_login(self.tecnico)
        response = self.client.get(reverse('cierre_ot', args=[self.ot.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Valor cobrado por mano de obra')

    def test_supervisor_list_keeps_the_original_closure_link(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('listar_ot'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('cierre_ot', args=[self.ot.pk]),
        )
        self.assertNotContains(response, reverse('gestionar_ot_admin', args=[self.ot.pk]))
        self.assertContains(response, reverse('facturacion_admin'))

    def test_invoice_queue_only_shows_closed_orders_not_yet_invoiced(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('facturacion_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Facturación pendiente')
        self.assertContains(
            response,
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )
        self.assertContains(response, 'Prefactura')

        self.ot.cierreot.factura_dian_drive_id = 'private-drive-file-id'
        self.ot.cierreot.estado_facturacion = 'facturada'
        self.ot.cierreot.save(update_fields=[
            'factura_dian_drive_id',
            'estado_facturacion',
        ])
        response = self.client.get(reverse('facturacion_admin'))
        self.assertNotContains(
            response,
            reverse('gestionar_ot_admin', args=[self.ot.pk]),
        )

    def test_invoice_queue_filters_orders_and_sorts_latest_closures_first(self):
        solicitud_reciente = Solicitud.objects.create(
            creado_por=self.tecnico.username,
            descripcion_problema='Cierre más reciente',
            equipo=self.equipo,
            ubicacion=Ubicacion.objects.create(
                nombre='ZZ Cliente',
                codigo='UBI-ZZ',
            ),
            estado=self.estado,
        )
        ot_reciente = OrdenTrabajo.objects.create(
            solicitud=solicitud_reciente,
            tecnico_asignado='zzz-tecnico',
            estado=self.estado,
        )
        CierreOt.objects.create(
            orden_trabajo=ot_reciente,
            fecha_inicio_actividad=(
                self.ot.cierreot.fecha_inicio_actividad + relativedelta(days=1)
            ),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('facturacion_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['ots'].values_list('pk', flat=True)),
            [ot_reciente.pk, self.ot.pk],
        )
        self.assertEqual(len(response.context['eventos_calendario']), 2)
        self.assertEqual(
            response.context['eventos_calendario'][0]['url'],
            reverse('gestionar_ot_admin', args=[ot_reciente.pk]),
        )

        orden_ascendente_esperado = [self.ot.pk, ot_reciente.pk]
        for columna in ('ot', 'tecnico', 'cliente', 'fecha'):
            response = self.client.get(
                reverse('facturacion_admin'),
                {'orden': columna, 'direccion': 'asc'},
            )
            self.assertEqual(
                list(response.context['ots'].values_list('pk', flat=True)),
                orden_ascendente_esperado,
                msg=f'Orden ascendente incorrecto para {columna}.',
            )

        fecha_cierre = self.ot.cierreot.fecha_inicio_actividad.date().isoformat()
        response = self.client.get(
            reverse('facturacion_admin'),
            {
                'tecnico': self.tecnico.username,
                'cliente': 'Cliente renta',
                'fecha_inicio': fecha_cierre,
                'fecha_fin': fecha_cierre,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['ots'].values_list('pk', flat=True)),
            [self.ot.pk],
        )
        self.assertEqual(len(response.context['eventos_calendario']), 1)
        self.assertContains(response, 'billing-calendar')
        sort_url = response.context['ordenamientos']['ot']['url']
        self.assertIn('tecnico=', sort_url)
        self.assertIn('cliente=Cliente+renta', sort_url)
        self.assertIn(f'fecha_inicio={fecha_cierre}', sort_url)
        self.assertIn(f'fecha_fin={fecha_cierre}', sort_url)

        response = self.client.get(
            reverse('facturacion_admin'),
            {'orden': 'fecha', 'direccion': 'asc'},
        )
        self.assertEqual(response.context['orden_actual'], 'fecha')
        self.assertEqual(response.context['direccion_actual'], 'asc')
        self.assertContains(response, 'aria-sort="ascending"')

    def test_technician_cannot_access_invoice_queue(self):
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse('facturacion_admin'))

        self.assertRedirects(response, reverse('dashboard'))
