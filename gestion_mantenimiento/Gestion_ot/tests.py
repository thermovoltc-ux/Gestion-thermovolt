from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from io import BytesIO
from io import StringIO
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import IntegrityError
from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files import File
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from gestion_mantenimiento.almacen.models import (
    CategoriaProducto,
    MovimientoInventario,
    Producto,
)
from gestion_mantenimiento.Activos.models import CentroOperaciones, Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import (
    CierreOt,
    Estado,
    InformeDriveArchivo,
    Material,
    MaterialOT,
    OrdenTrabajo,
    PlanMantenimiento,
    ProcesoInforme,
    ServicioOT,
    TareaMantenimiento,
)
from gestion_mantenimiento.notificaciones.models import Notificacion
from gestion_mantenimiento.users.models import Cliente, PerfilUsuario
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


class CentroOperacionesGestionOtIsolationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cliente-ot-scope',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.client.force_login(self.user)
        self.allowed_center = CentroOperaciones.objects.create(
            nombre='CO OT permitido',
            codigo='CO-OT-PERMITIDO',
        )
        self.other_center = CentroOperaciones.objects.create(
            nombre='CO OT ajeno',
            codigo='CO-OT-AJENO',
        )
        self.allowed_location = Ubicacion.objects.create(
            nombre='Ubicación OT permitida',
            codigo='UBI-OT-PERMITIDA',
            centro_operaciones=self.allowed_center,
        )
        self.foreign_location = Ubicacion.objects.create(
            nombre='Ubicación OT privada',
            codigo='UBI-OT-AJENA',
            centro_operaciones=self.other_center,
        )
        self.allowed_equipment = Equipo.objects.create(
            nombre='Equipo OT permitido',
            codigo='EQ-OT-PERMITIDO',
            ubicacion=self.allowed_location,
        )
        self.foreign_equipment = Equipo.objects.create(
            nombre='Equipo OT privado',
            codigo='EQ-OT-AJENO',
            ubicacion=self.foreign_location,
        )
        self.requested = Estado.objects.get_or_create(nombre='solicitado')[0]
        self.finalized = Estado.objects.get_or_create(nombre='finalizada')[0]
        self.allowed_request = Solicitud.objects.create(
            creado_por=self.user.username,
            descripcion_problema='Solicitud OT permitida',
            equipo=self.allowed_equipment,
            ubicacion=self.allowed_location,
            estado=self.finalized,
        )
        self.foreign_request = Solicitud.objects.create(
            creado_por='cliente-externo',
            descripcion_problema='Solicitud OT privada',
            equipo=self.foreign_equipment,
            ubicacion=self.foreign_location,
            estado=self.finalized,
        )
        self.allowed_ot = OrdenTrabajo.objects.create(
            solicitud=self.allowed_request,
            tecnico_asignado='Tecnico scope',
            estado=self.finalized,
            fecha_actividad=timezone.now(),
        )
        self.foreign_ot = OrdenTrabajo.objects.create(
            solicitud=self.foreign_request,
            tecnico_asignado='Tecnico externo',
            estado=self.finalized,
        )
        self.allowed_closure = CierreOt.objects.create(
            orden_trabajo=self.allowed_ot,
            fecha_inicio_actividad=timezone.now(),
            hora_inicio=datetime.min.time().replace(hour=9),
            hora_fin=datetime.min.time().replace(hour=10),
            estado_facturacion='pendiente',
        )
        self.foreign_closure = CierreOt.objects.create(
            orden_trabajo=self.foreign_ot,
            fecha_inicio_actividad=timezone.now(),
            hora_inicio=datetime.min.time().replace(hour=9),
            hora_fin=datetime.min.time().replace(hour=10),
            estado_facturacion='pendiente',
        )
        self.allowed_plan = PlanMantenimiento.objects.create(
            equipo=self.allowed_equipment,
            nombre='Plan CO permitido',
            fecha_inicio=timezone.localdate(),
        )
        self.foreign_plan = PlanMantenimiento.objects.create(
            equipo=self.foreign_equipment,
            nombre='Plan CO privado',
            fecha_inicio=timezone.localdate(),
        )
        self.allowed_task = TareaMantenimiento.objects.create(
            plan=self.allowed_plan,
            fecha_programada=timezone.localdate(),
        )
        self.foreign_task = TareaMantenimiento.objects.create(
            plan=self.foreign_plan,
            fecha_programada=timezone.localdate(),
        )
        session = self.client.session
        session['centro_operaciones_id'] = self.allowed_center.pk
        session['tipo_cuenta'] = 'jefe_de_area'
        session.save()

    @staticmethod
    def _ids(queryset):
        return set(queryset.values_list('pk', flat=True))

    def test_dashboard_ot_boards_and_preventive_list_are_scoped(self):
        dashboard = self.client.get(reverse('dashboard'))
        board = self.client.get(reverse('gestion_ot'))
        ot_list = self.client.get(reverse('listar_ot'))
        plans = self.client.get(reverse('lista_planes'))

        self.assertEqual(dashboard.context['solicitudes_totales'], 1)
        self.assertEqual(
            self._ids(board.context['ordenes_trabajo']),
            {self.allowed_ot.pk},
        )
        self.assertEqual(self._ids(ot_list.context['ots']), {self.allowed_ot.pk})
        self.assertEqual(self._ids(plans.context['planes']), {self.allowed_plan.pk})
        self.assertNotContains(board, self.foreign_request.descripcion_problema)
        self.assertNotContains(plans, self.foreign_plan.nombre)

    def test_client_can_see_ot_status_but_not_manage_link_or_closure(self):
        response = self.client.get(reverse('listar_ot'))
        calendar_events = json.loads(response.context['calendar_events_json'])
        closure_response = self.client.get(
            reverse('cierre_ot', args=[self.allowed_ot.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._ids(response.context['ots']),
            {self.allowed_ot.pk},
        )
        self.assertNotContains(response, 'Gestionar')
        self.assertEqual(calendar_events[0]['url'], '')
        self.assertEqual(closure_response.status_code, 404)
        self.assertNotContains(
            closure_response,
            'Costo unitario real',
            status_code=404,
        )

    def test_client_cannot_download_material_invoice_from_private_media_route(self):
        material = Material.objects.create(
            codigo='CO-PRIVATE-INVOICE',
            nombre='Material con factura privada',
            costo_base='170000.00',
            precio_venta_sugerido='242857.14',
        )
        material_ot = MaterialOT.objects.create(
            orden_trabajo=self.allowed_ot,
            material=material,
            cantidad='1',
            costo_real='170000.00',
        )
        material_ot.foto_factura.name = 'drive/private-invoice-file/file.pdf'
        material_ot.save(update_fields=['foto_factura'])

        with patch.object(GoogleDriveMediaStorage, 'open') as open_private_file:
            response = self.client.get(
                reverse('drive_media', args=['private-invoice-file']),
            )

        self.assertEqual(response.status_code, 404)
        open_private_file.assert_not_called()

    def test_client_group_takes_precedence_over_admin_for_financial_routes(self):
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])

        rentabilidad = self.client.get(reverse('rentabilidad_admin'))
        facturacion = self.client.get(reverse('facturacion_admin'))
        invoice_detail = self.client.get(
            reverse('detalle_factura_ot', args=[self.allowed_ot.pk]),
        )
        invoice_download = self.client.get(
            reverse('descargar_factura_dian', args=[self.allowed_ot.pk]),
        )

        self.assertEqual(rentabilidad.status_code, 302)
        self.assertEqual(facturacion.status_code, 302)
        self.assertEqual(invoice_detail.status_code, 403)
        self.assertEqual(invoice_download.status_code, 404)

    def test_direct_ot_request_plan_and_report_details_reject_foreign_co(self):
        responses = [
            self.client.get(reverse('cierre_ot', args=[self.foreign_ot.pk])),
            self.client.get(
                reverse('detalles_solicitud', args=[self.foreign_request.consecutivo]),
            ),
            self.client.get(reverse('detalle_plan', args=[self.foreign_plan.pk])),
            self.client.get(
                reverse(
                    'estado_proceso_informe',
                    args=[self.foreign_ot.pk, 'foreign-operation'],
                ),
            ),
        ]

        self.assertTrue(all(response.status_code == 404 for response in responses))
        self.assertEqual(
            self.client.get(reverse('cierre_ot', args=[self.allowed_ot.pk])).status_code,
            404,
        )

    def test_foreign_report_downloads_and_client_financial_routes_do_not_expose_data(self):
        report = InformeDriveArchivo.objects.create(
            cierre_ot=self.foreign_closure,
            drive_file_id='foreign-drive-report',
            nombre_archivo='informe-privado.pdf',
            download_token='foreign-download-token',
        )
        token_response = self.client.get(
            reverse('descargar_informe_token', args=[report.download_token]),
        )
        local_response = self.client.get(
            reverse(
                'descargar_informe_pdf',
                args=[f'informe_ot_{self.foreign_request.consecutivo}_privado.pdf'],
            ),
        )
        rentabilidad_response = self.client.get(reverse('rentabilidad_admin'))
        facturacion_response = self.client.get(reverse('facturacion_admin'))
        invoice_response = self.client.get(
            reverse('detalle_factura_ot', args=[self.foreign_ot.pk]),
        )

        self.assertEqual(token_response.status_code, 404)
        self.assertEqual(local_response.status_code, 404)
        self.assertEqual(rentabilidad_response.status_code, 302)
        self.assertEqual(facturacion_response.status_code, 302)
        self.assertNotIn(
            self.foreign_location.nombre.encode(),
            rentabilidad_response.content,
        )
        self.assertNotIn(
            self.foreign_location.nombre.encode(),
            facturacion_response.content,
        )
        self.assertIn(invoice_response.status_code, {403, 404})

    def test_internal_user_with_center_sees_only_that_centers_billing_and_profitability(self):
        self.user.groups.clear()
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        self.client.force_login(self.user)
        today = timezone.localdate().isoformat()

        billing = self.client.get(reverse('facturacion_admin'))
        profitability = self.client.get(
            reverse('rentabilidad_admin'),
            {'desde': today, 'hasta': today},
        )

        self.assertEqual(billing.status_code, 200)
        self.assertEqual(profitability.status_code, 200)
        self.assertEqual(
            self._ids(billing.context['ots']),
            {self.allowed_ot.pk},
        )
        self.assertEqual(
            {row['ot'].pk for row in profitability.context['filas']},
            {self.allowed_ot.pk},
        )

    def test_client_without_center_gets_empty_dashboard_ot_and_preventive_lists(self):
        session = self.client.session
        session.pop('centro_operaciones_id', None)
        session['tipo_cuenta'] = 'jefe_de_area'
        session.save()

        dashboard = self.client.get(reverse('dashboard'))
        board = self.client.get(reverse('gestion_ot'))
        ot_list = self.client.get(reverse('listar_ot'))
        plans = self.client.get(reverse('lista_planes'))
        closure = self.client.get(reverse('cierre_ot', args=[self.allowed_ot.pk]))
        request_detail = self.client.get(
            reverse('detalles_solicitud', args=[self.allowed_request.consecutivo]),
        )
        report_status = self.client.get(
            reverse(
                'estado_proceso_informe',
                args=[self.allowed_ot.pk, 'no-co-operation'],
            ),
        )
        local_report = self.client.get(
            reverse(
                'descargar_informe_pdf',
                args=[f'informe_ot_{self.allowed_request.consecutivo}_sin-co.pdf'],
            ),
        )
        report = InformeDriveArchivo.objects.create(
            cierre_ot=self.allowed_closure,
            drive_file_id='allowed-drive-report',
            nombre_archivo='informe-permitido.pdf',
            download_token='allowed-download-token',
        )
        token_report = self.client.get(
            reverse('descargar_informe_token', args=[report.download_token]),
        )
        billing = self.client.get(reverse('facturacion_admin'))
        profitability = self.client.get(reverse('rentabilidad_admin'))

        self.assertEqual(dashboard.context['solicitudes_totales'], 0)
        self.assertEqual(list(board.context['ordenes_trabajo']), [])
        self.assertEqual(list(ot_list.context['ots']), [])
        self.assertEqual(list(plans.context['planes']), [])
        self.assertEqual(closure.status_code, 404)
        self.assertEqual(request_detail.status_code, 404)
        self.assertEqual(report_status.status_code, 404)
        self.assertEqual(local_report.status_code, 404)
        self.assertEqual(token_report.status_code, 404)
        self.assertEqual(billing.status_code, 302)
        self.assertEqual(profitability.status_code, 302)


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
            email_solicitante='cliente@example.com',
            co='CO-42',
            estado=SimpleNamespace(nombre='en proceso'),
            fecha_creacion=datetime(2026, 9, 30, tzinfo=datetime_timezone.utc),
            enviar_email=False,
            save=Mock(),
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

    def test_sends_link_with_shared_subject_and_without_attachment(self):
        self.assertTrue(self._send_with_link('https://reports.example/informe.pdf'))

        message = mail.outbox[0]
        self.assertIn('https://reports.example/informe.pdf', message.body)
        self.assertEqual(message.subject, '[Solicitud #42] - PDV prueba - CO CO-42')
        self.assertEqual(message.to, ['tecnico@example.com', 'cliente@example.com'])
        self.assertEqual(message.bcc, [])
        self.assertEqual(message.attachments, [])
        self.assertEqual(len(message.alternatives), 1)
        html, content_type = message.alternatives[0]
        self.assertEqual(content_type, 'text/html')
        self.assertIn('href="https://reports.example/informe.pdf"', html)
        self.assertIn('>Descargar informe (PDF)</a>', html)
        self.assertNotIn('https://reports.example/informe.pdf', html.split('href=')[0])
        self.assertEqual(self.cierre_ot.orden_trabajo.solicitud.estado.nombre, 'en revision')
        self.cierre_ot.orden_trabajo.solicitud.save.assert_called_once_with(update_fields=['estado'])

    def test_reports_unavailable_without_fallback_attachment(self):
        self.assertTrue(self._send_with_link(None))

        message = mail.outbox[0]
        self.assertIn('El informe no está disponible por el momento', message.body)
        self.assertEqual(message.subject, '[Solicitud #42] - PDV prueba - CO CO-42')
        self.assertEqual(message.bcc, [])
        self.assertEqual(message.attachments, [])
        self.assertEqual(len(message.alternatives), 1)
        self.assertIn('El informe no está disponible por el momento', message.alternatives[0][0])
        self.assertNotIn('Descargar informe (PDF)', message.alternatives[0][0])


class GestionOtFilterRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = self._create_user('tester', 'contraseña123')
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
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

    def test_kanban_shows_unassigned_requested_ot_with_its_solicitud(self):
        solicitud_sin_tecnico = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Solicitud con OT sin técnico',
            equipo=self.equipo_a,
            ubicacion=self.ubicacion_a,
            estado=self.estado_solicitado,
            fecha_creacion=timezone.now(),
        )
        OrdenTrabajo.objects.create(
            solicitud=solicitud_sin_tecnico,
            tecnico_asignado='',
            estado=self.estado_solicitado,
        )

        estado_en_proceso, _ = Estado.objects.get_or_create(nombre='en proceso')
        solicitud_ot_en_proceso = Solicitud.objects.create(
            creado_por='tester',
            descripcion_problema='Solicitud con OT en proceso',
            equipo=self.equipo_a,
            ubicacion=self.ubicacion_a,
            estado=self.estado_solicitado,
            fecha_creacion=timezone.now(),
        )
        OrdenTrabajo.objects.create(
            solicitud=solicitud_ot_en_proceso,
            tecnico_asignado='',
            estado=estado_en_proceso,
        )

        response = self.client.get(reverse('gestion_ot'))

        self.assertEqual(response.status_code, 200)
        consecutivos = {
            solicitud.consecutivo
            for solicitud in response.context['solicitudes']
        }
        self.assertIn(solicitud_sin_tecnico.consecutivo, consecutivos)
        self.assertNotIn(solicitud_ot_en_proceso.consecutivo, consecutivos)
        self.assertNotIn(self.ot_actual.solicitud.consecutivo, consecutivos)

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


class SolicitudEmailEventTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='tecnico-email-eventos',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        self.client.force_login(self.user)
        self.ubicacion = Ubicacion.objects.create(
            nombre='Ubicación correo eventos',
            codigo='UBI-CORREO',
            co='CO-CORREO',
        )
        self.equipo = Equipo.objects.create(
            nombre='Equipo correo eventos',
            codigo='EQ-CORREO',
            ubicacion=self.ubicacion,
        )
        self.estado_solicitado = Estado.objects.get_or_create(nombre='solicitado')[0]
        self.solicitud = Solicitud.objects.create(
            creado_por=self.user.username,
            descripcion_problema='Solicitud con eventos de correo',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado_solicitado,
            email_solicitante='solicitante@example.com',
            enviar_email=True,
        )

    def _actualizar_solicitud(self, estado, tecnico=None, fecha=None):
        return self.client.post(
            reverse('actualizar_estado_solicitud'),
            data=json.dumps({
                'numero': self.solicitud.consecutivo,
                'estado': estado,
                'tecnico': tecnico,
                'fecha': (fecha or timezone.now()).isoformat(),
            }),
            content_type='application/json',
        )

    @patch('gestion_mantenimiento.Gestion_ot.views.enviar_correo_solicitud')
    def test_assignment_sends_notification_once_when_technician_changes(self, send_email):
        fecha_actividad = datetime(2026, 11, 10, 14, 30, tzinfo=datetime_timezone.utc)
        response = self._actualizar_solicitud(
            'en proceso',
            'tecnico-asignado',
            fecha=fecha_actividad,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email_warning'], None)
        send_email.assert_called_once_with(
            self.solicitud,
            'asignacion',
            cuerpo_extra=(
                'Técnico asignado: tecnico-asignado\n'
                f'Fecha programada: {timezone.localtime(fecha_actividad).strftime("%d/%m/%Y %H:%M")}'
            ),
        )
        self.assertEqual(
            self.solicitud.orden_trabajo.fecha_actividad,
            fecha_actividad,
        )

        response = self._actualizar_solicitud('en proceso', 'tecnico-asignado')

        self.assertEqual(response.status_code, 200)
        send_email.assert_called_once()

    @patch('gestion_mantenimiento.Gestion_ot.views.enviar_correo_solicitud')
    def test_assignment_does_not_send_without_requester_email(self, send_email):
        self.solicitud.email_solicitante = ''
        self.solicitud.save(update_fields=['email_solicitante'])

        response = self._actualizar_solicitud('en proceso', 'tecnico-asignado')

        self.assertEqual(response.status_code, 200)
        send_email.assert_not_called()

    @patch('gestion_mantenimiento.Gestion_ot.views.enviar_correo_solicitud')
    def test_assignment_does_not_send_when_email_checkbox_was_unselected(self, send_email):
        self.solicitud.enviar_email = False
        self.solicitud.save(update_fields=['enviar_email'])

        response = self._actualizar_solicitud('en proceso', 'tecnico-asignado')

        self.assertEqual(response.status_code, 200)
        send_email.assert_not_called()

    @patch(
        'gestion_mantenimiento.Gestion_ot.views.enviar_correo_solicitud',
        side_effect=RuntimeError('provider unavailable'),
    )
    def test_assignment_email_failure_is_reported_without_undoing_assignment(self, send_email):
        response = self._actualizar_solicitud('en proceso', 'tecnico-asignado')

        self.assertEqual(response.status_code, 200)
        self.assertIn('no se pudo enviar el correo de asignación', response.json()['email_warning'])
        self.solicitud.refresh_from_db()
        self.assertEqual(
            self.solicitud.orden_trabajo.tecnico_asignado,
            'tecnico-asignado',
        )
        send_email.assert_called_once()

    @patch('gestion_mantenimiento.Gestion_ot.views.enviar_correo_solicitud')
    def test_finalization_sends_notification_only_on_transition(self, send_email):
        estado_revision = Estado.objects.get_or_create(nombre='en revision')[0]
        self.solicitud.estado = estado_revision
        self.solicitud.save(update_fields=['estado'])
        OrdenTrabajo.objects.create(
            solicitud=self.solicitud,
            tecnico_asignado='tecnico-asignado',
            estado=estado_revision,
        )

        response = self._actualizar_solicitud('finalizada')

        self.assertEqual(response.status_code, 200)
        send_email.assert_called_once_with(
            self.solicitud,
            'finalizacion',
            cuerpo_extra=f'La orden de trabajo OT-{self.solicitud.consecutivo} ha sido finalizada.',
        )

        response = self._actualizar_solicitud('finalizada')

        self.assertEqual(response.status_code, 200)
        send_email.assert_called_once()

    @patch('gestion_mantenimiento.Gestion_ot.views.enviar_correo_solicitud')
    def test_finalization_does_not_send_when_email_checkbox_was_unselected(self, send_email):
        self.solicitud.enviar_email = False
        self.solicitud.save(update_fields=['enviar_email'])
        estado_revision = Estado.objects.get_or_create(nombre='en revision')[0]
        self.solicitud.estado = estado_revision
        self.solicitud.save(update_fields=['estado'])
        OrdenTrabajo.objects.create(
            solicitud=self.solicitud,
            tecnico_asignado='tecnico-asignado',
            estado=estado_revision,
        )

        response = self._actualizar_solicitud('finalizada')

        self.assertEqual(response.status_code, 200)
        send_email.assert_not_called()


class PreventiveRequestCoTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='tecnico-preventivo-co',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(self.user)
        self.ubicacion = Ubicacion.objects.create(
            nombre='Ubicación preventivo CO',
            codigo='UBI-PREV-CO',
            co='CO-PREV',
        )
        self.equipo = Equipo.objects.create(
            nombre='Equipo preventivo CO',
            codigo='EQ-PREV-CO',
            ubicacion=self.ubicacion,
        )
        self.plan = PlanMantenimiento.objects.create(
            equipo=self.equipo,
            nombre='Plan preventivo CO',
            fecha_inicio=timezone.localdate(),
        )
        self.tarea = TareaMantenimiento.objects.create(
            plan=self.plan,
            fecha_programada=timezone.localdate(),
        )

    def _asignar_tarea(self):
        return self.client.post(
            reverse('asignar_tarea_preventiva', args=[self.tarea.pk]),
            data=json.dumps({
                'tecnico': 'tecnico-asignado',
                'fecha': timezone.localdate().isoformat(),
            }),
            content_type='application/json',
        )

    def test_preventive_request_saves_co_from_equipment_location(self):
        response = self._asignar_tarea()

        self.assertEqual(response.status_code, 200)
        solicitud = Solicitud.objects.get(consecutivo=response.json()['consecutivo'])
        self.assertEqual(solicitud.co, 'CO-PREV')

    def test_preventive_request_is_created_without_location_or_session_co(self):
        self.equipo.ubicacion = None
        self.equipo.save()

        response = self._asignar_tarea()

        self.assertEqual(response.status_code, 200)
        solicitud = Solicitud.objects.get(consecutivo=response.json()['consecutivo'])
        self.assertEqual(solicitud.co, '')

    def test_preventive_request_notifies_center_client_and_admin(self):
        centro = CentroOperaciones.objects.create(
            nombre='Centro preventivo notificaciones',
            codigo='CO-PREV',
        )
        self.ubicacion.centro_operaciones = centro
        self.ubicacion.save(update_fields=['centro_operaciones'])

        cliente_usuario = get_user_model().objects.create_user(
            username='cliente-preventivo',
            password='test-password',
        )
        cliente = Cliente.objects.create(
            nombre='Cliente preventivo',
            codigo='CLI-PREV',
        )
        cliente.centros_operaciones.add(centro)
        PerfilUsuario.objects.create(
            user=cliente_usuario,
            cliente=cliente,
        )

        admin = get_user_model().objects.create_user(
            username='admin-preventivo',
            password='test-password',
        )
        admin.groups.add(Group.objects.get_or_create(name='Admin')[0])

        response = self._asignar_tarea()

        self.assertEqual(response.status_code, 200)
        customer_notification = Notificacion.objects.get(
            usuario=cliente_usuario,
            tipo=Notificacion.MANTENIMIENTO_PREVENTIVO,
        )
        admin_notification = Notificacion.objects.get(
            usuario=admin,
            tipo=Notificacion.MANTENIMIENTO_PREVENTIVO,
        )
        self.assertIn('Equipo preventivo CO', customer_notification.mensaje)
        self.assertIn(
            timezone.localdate().strftime('%d/%m/%Y'),
            customer_notification.mensaje,
        )
        self.assertIn('Plan preventivo CO', admin_notification.mensaje)
        self.assertIn('CO', admin_notification.mensaje)


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

    def test_admin_can_manually_retry_failed_process(self):
        admin = get_user_model().objects.create_user(
            username='retry-admin',
            password='test-password',
        )
        admin.groups.add(Group.objects.get_or_create(name='Admin')[0])
        self.client.force_login(admin)
        proceso = self.crear_proceso('manual-retry', 4)
        proceso.last_error = 'Falta una firma'
        proceso.save(update_fields=['last_error'])

        with patch.object(views.threading, 'Thread') as thread_class:
            response = self.client.post(
                reverse(
                    'reintentar_proceso_informe',
                    args=[self.cierre_ot.orden_trabajo_id, proceso.operation_id],
                ),
            )

        proceso.refresh_from_db()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(proceso.estado, ProcesoInforme.PENDIENTE)
        self.assertEqual(proceso.intentos, 0)
        self.assertEqual(proceso.last_error, '')
        thread_class.assert_called_once()
        thread_class.return_value.start.assert_called_once()

    def test_manual_retry_requires_admin_and_client_group_takes_precedence(self):
        user = get_user_model().objects.create_user(
            username='retry-client',
            password='test-password',
            is_superuser=True,
        )
        user.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.client.force_login(user)
        proceso = self.crear_proceso('client-retry', 4)
        proceso.last_error = 'Error interno'
        proceso.save(update_fields=['last_error'])

        state_response = self.client.get(
            reverse(
                'estado_proceso_informe',
                args=[self.cierre_ot.orden_trabajo_id, proceso.operation_id],
            ),
        )

        response = self.client.post(
            reverse(
                'reintentar_proceso_informe',
                args=[self.cierre_ot.orden_trabajo_id, proceso.operation_id],
            ),
        )

        proceso.refresh_from_db()
        self.assertIsNone(state_response.json()['last_error'])
        self.assertFalse(state_response.json()['puede_reintentar'])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(proceso.estado, ProcesoInforme.ERROR)
        self.assertEqual(proceso.intentos, 4)

    def test_technician_cannot_manually_retry_failed_process(self):
        technician = get_user_model().objects.create_user(
            username='retry-technician',
            password='test-password',
        )
        technician.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(technician)
        proceso = self.crear_proceso('technician-retry', 4)

        response = self.client.post(
            reverse(
                'reintentar_proceso_informe',
                args=[self.cierre_ot.orden_trabajo_id, proceso.operation_id],
            ),
        )

        proceso.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(proceso.estado, ProcesoInforme.ERROR)
        self.assertEqual(proceso.intentos, 4)

    def test_state_api_exposes_error_only_to_admin_and_offers_retry_url(self):
        proceso = self.crear_proceso('state-error', 4)
        proceso.last_error = 'Falta una firma'
        proceso.save(update_fields=['last_error'])
        admin = get_user_model().objects.create_user(
            username='retry-state-admin',
            password='test-password',
        )
        admin.groups.add(Group.objects.get_or_create(name='Admin')[0])
        self.client.force_login(admin)

        response = self.client.get(
            reverse(
                'estado_proceso_informe',
                args=[self.cierre_ot.orden_trabajo_id, proceso.operation_id],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['last_error'], 'Falta una firma')
        self.assertTrue(response.json()['puede_reintentar'])
        self.assertEqual(
            response.json()['url_reintentar'],
            reverse(
                'reintentar_proceso_informe',
                args=[self.cierre_ot.orden_trabajo_id, proceso.operation_id],
            ),
        )


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

    def _crear_producto_almacen(self, entradas):
        categoria = CategoriaProducto.objects.create(
            nombre=f'Repuestos OT {self.ot.pk}',
        )
        producto = Producto.objects.create(
            codigo=f'ALM-{self.ot.pk}',
            nombre='Rodamiento de almacén',
            categoria=categoria,
            unidad_medida='Unidad',
        )
        for cantidad, costo_unitario in entradas:
            MovimientoInventario.objects.create(
                producto=producto,
                tipo=MovimientoInventario.ENTRADA,
                cantidad=Decimal(cantidad),
                costo_unitario=Decimal(costo_unitario),
                usuario=self.user,
            )
        return producto

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

    def test_material_name_and_code_snapshots_do_not_change_with_catalog(self):
        material_ot = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=self.material,
            cantidad=Decimal('1.00'),
            costo_real=Decimal('10.00'),
            precio_venta_aplicado=Decimal('14.29'),
        )

        self.material.nombre = 'Rodamiento actualizado'
        self.material.codigo = 'MAT-RENAMED'
        self.material.save(update_fields=['nombre', 'codigo'])
        material_ot.refresh_from_db()

        self.assertEqual(material_ot.nombre_snapshot, 'Rodamiento')
        self.assertEqual(material_ot.codigo_snapshot, 'MAT-001')
        self.assertEqual(material_ot.nombre_historico, 'Rodamiento')
        self.assertEqual(material_ot.codigo_historico, 'MAT-001')

    def test_inventory_material_uses_weighted_average_and_creates_ot_exit(self):
        producto = self._crear_producto_almacen([
            ('10.000', '10.00'),
            ('10.000', '20.00'),
        ])

        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'producto_almacen': producto.pk,
                'cantidad': '2.00',
                'costo_real': '999.99',
            },
        )

        self.assertEqual(response.status_code, 201)
        material_ot = MaterialOT.objects.get(orden_trabajo=self.ot)
        self.assertEqual(material_ot.producto_almacen, producto)
        self.assertEqual(material_ot.costo_real, Decimal('15.00'))
        self.assertEqual(material_ot.precio_venta_aplicado, Decimal('21.43'))
        self.assertEqual(producto.stock, Decimal('18.000'))

        salida = MovimientoInventario.objects.get(
            producto=producto,
            tipo=MovimientoInventario.SALIDA,
        )
        self.assertEqual(salida.cantidad, Decimal('2.00'))
        self.assertEqual(salida.costo_unitario, Decimal('15.00'))
        self.assertEqual(salida.documento_referencia, f'OT-{self.ot.pk}')
        self.assertEqual(salida.usuario, self.user)

    def test_insufficient_inventory_does_not_save_ot_material_or_exit(self):
        producto = self._crear_producto_almacen([('2.000', '7.50')])

        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'producto_almacen': producto.pk,
                'cantidad': '3.00',
                'costo_real': '999.99',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Stock insuficiente', response.json()['error'])
        self.assertFalse(MaterialOT.objects.filter(orden_trabajo=self.ot).exists())
        self.assertEqual(
            MovimientoInventario.objects.filter(
                producto=producto,
                tipo=MovimientoInventario.SALIDA,
            ).count(),
            0,
        )
        self.assertEqual(producto.stock, Decimal('2.000'))

    def test_inventory_product_rejects_a_different_linked_material(self):
        producto = self._crear_producto_almacen([('2.000', '7.50')])
        producto.material_asociado = self.material
        producto.save(update_fields=['material_asociado'])
        other_material = Material.objects.create(
            codigo='MAT-002',
            nombre='Otro repuesto',
            costo_base='4.00',
            precio_venta_sugerido='5.71',
        )

        response = self.client.post(
            reverse('agregar_material_ot', args=[self.ot.pk]),
            {
                'material': other_material.pk,
                'producto_almacen': producto.pk,
                'cantidad': '1.00',
                'costo_real': '7.50',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('asociado a otro material', str(response.json()['errors']))
        self.assertFalse(MaterialOT.objects.filter(orden_trabajo=self.ot).exists())
        self.assertFalse(
            MovimientoInventario.objects.filter(
                producto=producto,
                tipo=MovimientoInventario.SALIDA,
            ).exists()
        )

    def test_repeated_inventory_add_request_does_not_debit_twice(self):
        producto = self._crear_producto_almacen([('5.000', '8.00')])
        url = reverse('agregar_material_ot', args=[self.ot.pk])
        payload = {
            'material': self.material.pk,
            'producto_almacen': producto.pk,
            'cantidad': '2.00',
            'costo_real': '999.99',
        }

        first_response = self.client.post(url, payload)
        retry_response = self.client.post(url, payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertTrue(retry_response.json()['duplicate'])
        self.assertEqual(MaterialOT.objects.filter(orden_trabajo=self.ot).count(), 1)
        self.assertEqual(
            MovimientoInventario.objects.filter(
                producto=producto,
                tipo=MovimientoInventario.SALIDA,
            ).count(),
            1,
        )
        self.assertEqual(producto.stock, Decimal('3.000'))

    def test_standard_and_quick_add_accept_pdf_invoices(self):
        from tempfile import TemporaryDirectory

        self.ot_ajena.tecnico_asignado = self.user.username
        self.ot_ajena.estado = self.estado_en_proceso
        self.ot_ajena.save(update_fields=['tecnico_asignado', 'estado'])
        pdf_content = b'%PDF-1.7\ninvoice'

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                for order, route_name, filename in (
                    (self.ot, 'agregar_material_ot', 'factura-cierre.pdf'),
                    (self.ot_ajena, 'agregar_material_rapido_ot', 'factura-rapida.pdf'),
                ):
                    with self.subTest(route=route_name):
                        response = self.client.post(
                            reverse(route_name, args=[order.pk]),
                            {
                                'material': self.material.pk,
                                'cantidad': '1',
                                'costo_real': '10.00',
                                'foto_factura': SimpleUploadedFile(
                                    filename,
                                    pdf_content,
                                    content_type='application/pdf',
                                ),
                            },
                        )

                        self.assertEqual(response.status_code, 201)
                        material_ot = MaterialOT.objects.get(orden_trabajo=order)
                        self.assertTrue(material_ot.foto_factura.name.endswith('.pdf'))
                        with material_ot.foto_factura.open('rb') as uploaded_file:
                            self.assertEqual(uploaded_file.read(), pdf_content)

    def test_quick_add_rejects_invoice_with_unsupported_extension(self):
        self.ot.estado = self.estado_en_proceso
        self.ot.save(update_fields=['estado'])

        response = self.client.post(
            reverse('agregar_material_rapido_ot', args=[self.ot.pk]),
            {
                'material': self.material.pk,
                'cantidad': '1',
                'costo_real': '10.00',
                'foto_factura': SimpleUploadedFile(
                    'factura.exe',
                    b'not an invoice',
                    content_type='application/octet-stream',
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Extensiones permitidas', str(response.json()['errors']))

    def test_repeated_identical_add_request_reuses_existing_ot_material(self):
        url = reverse('agregar_material_ot', args=[self.ot.pk])
        payload = {
            'material': self.material.pk,
            'cantidad': '2.00',
            'costo_real': '10.00',
        }

        first_response = self.client.post(url, payload)
        retry_response = self.client.post(url, payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertTrue(retry_response.json()['duplicate'])
        self.assertEqual(retry_response.json()['id'], first_response.json()['id'])
        self.assertEqual(MaterialOT.objects.filter(orden_trabajo=self.ot).count(), 1)

    def test_quick_add_repeated_identical_request_does_not_create_second_row(self):
        self.ot.estado = self.estado_en_proceso
        self.ot.save(update_fields=['estado'])
        url = reverse('agregar_material_rapido_ot', args=[self.ot.pk])
        payload = {
            'material': self.material.pk,
            'cantidad': '1.00',
            'costo_real': '10.00',
        }

        first_response = self.client.post(url, payload)
        retry_response = self.client.post(url, payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertTrue(retry_response.json()['duplicate'])
        self.assertEqual(MaterialOT.objects.filter(orden_trabajo=self.ot).count(), 1)

    def test_same_material_with_different_cost_or_observations_remains_a_separate_line(self):
        url = reverse('agregar_material_ot', args=[self.ot.pk])
        responses = [
            self.client.post(url, {
                'material': self.material.pk,
                'cantidad': '1.00',
                'costo_real': '10.00',
            }),
            self.client.post(url, {
                'material': self.material.pk,
                'cantidad': '1.00',
                'costo_real': '11.00',
            }),
            self.client.post(url, {
                'material': self.material.pk,
                'cantidad': '1.00',
                'costo_real': '10.00',
                'observaciones': 'Uso independiente del mismo repuesto.',
            }),
        ]

        self.assertTrue(all(response.status_code == 201 for response in responses))
        self.assertEqual(MaterialOT.objects.filter(orden_trabajo=self.ot).count(), 3)

    def test_duplicate_cleanup_command_only_deletes_exact_blank_lines_after_apply(self):
        original = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=self.material,
            cantidad=Decimal('2.00'),
            costo_real=Decimal('10.00'),
            precio_venta_aplicado=Decimal('14.29'),
        )
        exact_duplicate = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=self.material,
            cantidad=Decimal('2.00'),
            costo_real=Decimal('10.00'),
            precio_venta_aplicado=Decimal('14.29'),
        )
        different_cost = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=self.material,
            cantidad=Decimal('2.00'),
            costo_real=Decimal('11.00'),
            precio_venta_aplicado=Decimal('15.72'),
        )
        with_observations = MaterialOT.objects.create(
            orden_trabajo=self.ot,
            material=self.material,
            cantidad=Decimal('2.00'),
            costo_real=Decimal('10.00'),
            precio_venta_aplicado=Decimal('14.29'),
            observaciones='Línea legítima con detalle propio.',
        )

        dry_run_output = StringIO()
        call_command('limpiar_materiales_ot_duplicados', stdout=dry_run_output)
        self.assertIn('No se modificó ningún registro', dry_run_output.getvalue())
        self.assertTrue(MaterialOT.objects.filter(pk=exact_duplicate.pk).exists())

        apply_output = StringIO()
        call_command('limpiar_materiales_ot_duplicados', '--apply', stdout=apply_output)

        self.assertFalse(MaterialOT.objects.filter(pk=exact_duplicate.pk).exists())
        self.assertTrue(MaterialOT.objects.filter(pk=original.pk).exists())
        self.assertTrue(MaterialOT.objects.filter(pk=different_cost.pk).exists())
        self.assertTrue(MaterialOT.objects.filter(pk=with_observations.pk).exists())
        self.assertIn('Filas duplicadas eliminadas: 1', apply_output.getvalue())

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
        self.assertContains(response, 'accept="image/*,application/pdf"')
        self.assertNotContains(response, 'capture="environment"')
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
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
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
        self.admin.groups.add(Group.objects.get_or_create(name='Admin')[0])
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
            estado_facturacion='pendiente',
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
        self.assertEqual(response.context['filas'][0]['costos_totales'], Decimal('300.00'))
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

    def test_rentabilidad_excludes_orders_until_prefactura_is_generated(self):
        solicitud = Solicitud.objects.create(
            creado_por=self.tecnico.username,
            descripcion_problema='OT aún sin prefactura',
            equipo=self.equipo,
            ubicacion=self.ubicacion,
            estado=self.estado,
        )
        ot_sin_prefactura = OrdenTrabajo.objects.create(
            solicitud=solicitud,
            tecnico_asignado=self.tecnico.username,
            estado=self.estado,
        )
        CierreOt.objects.create(
            orden_trabajo=ot_sin_prefactura,
            fecha_inicio_actividad=self.ot.cierreot.fecha_inicio_actividad,
            hora_inicio=datetime.min.time().replace(hour=9),
            hora_fin=datetime.min.time().replace(hour=11),
        )
        self.client.force_login(self.admin)
        url_rentabilidad = reverse('rentabilidad_admin')

        response = self.client.get(url_rentabilidad)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [fila['ot'].pk for fila in response.context['filas']],
            [self.ot.pk],
        )
        self.assertEqual(
            ot_sin_prefactura.cierreot.estado_facturacion,
            'sin_prefactura',
        )

        response = self.client.post(
            reverse('actualizar_mano_obra', args=[ot_sin_prefactura.pk]),
            {'valor_mano_obra': '0.00'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['estado_facturacion'], 'pendiente')
        response = self.client.get(url_rentabilidad)
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            {fila['ot'].pk for fila in response.context['filas']},
            {self.ot.pk, ot_sin_prefactura.pk},
        )

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
                estado_facturacion='pendiente',
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
        self.assertContains(response, 'Facturada - Ver PDF')
        self.assertContains(response, 'profit-action-done')
        self.assertContains(
            response,
            reverse('descargar_factura_dian', args=[self.ot.pk]),
        )

    def test_rentabilidad_table_shows_compact_financial_columns_and_pending_action(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('rentabilidad_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Estado factura')
        self.assertContains(response, 'Costos totales')
        self.assertContains(response, 'Ingreso total')
        self.assertContains(response, 'Ganancia estimada')
        self.assertContains(response, 'Prefactura')
        self.assertContains(response, 'Prefactura - Subir PDF')
        self.assertContains(response, 'profit-action-pending')
        self.assertContains(
            response,
            reverse('subir_factura_dian', args=[self.ot.pk]),
        )

    def test_invoice_modal_has_conditional_upload_and_compact_metadata(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('rentabilidad_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Factura de Venta')
        self.assertContains(response, 'invoice-metadata')
        self.assertContains(response, 'id="factura-cliente"')
        self.assertContains(response, 'id="factura-tecnico"')
        self.assertContains(response, 'id="factura-equipo"')
        self.assertContains(response, 'invoice-dian-success')
        self.assertContains(response, '.invoice-dian-success[hidden] { display: none; }')
        self.assertContains(response, 'const facturaYaSubida = button.dataset.facturaDianSubida === \'true\';')
        self.assertContains(response, '✓ Esta OT ya ha sido facturada')
        self.assertContains(response, 'Descargar PDF DIAN')
        self.assertContains(response, 'Subir PDF y Marcar como Facturada')
        self.assertNotContains(response, 'Factura electrónica DIAN')
        self.assertNotContains(response, 'Guardar Factura DIAN')

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
        self.assertContains(response, 'accept="image/*,application/pdf"')
        self.assertNotContains(response, 'capture="environment"')
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

    def test_admin_can_add_pdf_invoice_to_material(self):
        from tempfile import TemporaryDirectory

        self.client.force_login(self.admin)
        material = Material.objects.create(
            codigo='MAT-RENT-PDF',
            nombre='Material con factura PDF',
            costo_base=Decimal('50.00'),
            precio_venta_sugerido=Decimal('100.00'),
        )
        pdf_content = b'%PDF-1.7\ninvoice'

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('agregar_material_ot_admin', args=[self.ot.pk]),
                    {
                        'categoria': 'R',
                        'material': material.pk,
                        'cantidad': '1.00',
                        'costo_real': '50.00',
                        'aplicar_margen': '0',
                        'foto_factura': SimpleUploadedFile(
                            'factura-supervisor.pdf',
                            pdf_content,
                            content_type='application/pdf',
                        ),
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
                self.assertTrue(material_ot.foto_factura.name.endswith('.pdf'))
                with material_ot.foto_factura.open('rb') as uploaded_file:
                    self.assertEqual(uploaded_file.read(), pdf_content)

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
            estado_facturacion='pendiente',
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
