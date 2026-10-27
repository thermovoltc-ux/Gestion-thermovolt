from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gestion_mantenimiento.Activos.models import CentroOperaciones, Equipo, Ubicacion
from gestion_mantenimiento.Gestion_ot.models import Estado, OrdenTrabajo
from gestion_mantenimiento.solicitudes.models import Solicitud

from .models import (
    CalendarioTecnico,
    Cliente,
    ConfiguracionPago,
    Descuento,
    PerfilUsuario,
    ReciboPago,
    RegistroAsistencia,
)


class CustomLoginCentroOperacionesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin-centro-login',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.cliente = Cliente.objects.create(
            nombre='Cliente login',
            codigo='CLIENTE-LOGIN-CO',
        )
        PerfilUsuario.objects.create(user=self.user, cliente=self.cliente)
        self.centro = CentroOperaciones.objects.create(
            nombre='Centro permitido',
            codigo='CO-LOGIN-100',
        )
        self.cliente.centros_operaciones.add(self.centro)
        self.url = reverse('custom_login')

    def _login(self, co, tipo_cuenta='administrador'):
        return self.client.post(
            self.url,
            {
                'username': self.user.username,
                'password': 'test-password',
                'tipo_cuenta': tipo_cuenta,
                'co': co,
            },
        )

    def test_admin_login_stores_assigned_center_id(self):
        response = self._login(self.centro.codigo)

        self.assertRedirects(response, reverse('dashboard'))
        session = self.client.session
        self.assertEqual(session['centro_operaciones_id'], self.centro.pk)
        self.assertNotIn('co', session)

    def test_admin_with_registered_center_sees_assets_navigation(self):
        self._login(self.centro.codigo)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, reverse('lista_activos'))

    def test_area_manager_without_co_sees_assets_navigation(self):
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        response = self._login('', tipo_cuenta='jefe_de_area')

        self.assertRedirects(response, reverse('dashboard'))
        session = self.client.session
        self.assertNotIn('co', session)
        self.assertNotIn('centro_operaciones_id', session)

        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, reverse('lista_activos'))

    def test_client_account_cannot_login_without_co(self):
        response = self._login('')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertIn('co', response.context['form'].errors)

    def test_admin_login_rejects_center_assigned_to_another_client(self):
        otro_cliente = Cliente.objects.create(
            nombre='Otro cliente login',
            codigo='OTRO-CLIENTE-LOGIN-CO',
        )
        centro_ajeno = CentroOperaciones.objects.create(
            nombre='Centro ajeno',
            codigo='CO-LOGIN-900',
        )
        otro_cliente.centros_operaciones.add(centro_ajeno)

        response = self._login(centro_ajeno.codigo)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertIn(
            'El Centro de Operaciones no está habilitado para tu cliente.',
            response.context['form'].errors['co'],
        )

    def test_admin_login_uses_legacy_text_for_active_center_without_clients(self):
        centro_huerfano = CentroOperaciones.objects.create(
            nombre='Centro sin clientes',
            codigo='CO-LOGIN-ORPHAN',
        )

        response = self._login(centro_huerfano.codigo)

        self.assertRedirects(response, reverse('dashboard'))
        session = self.client.session
        self.assertNotIn('centro_operaciones_id', session)
        self.assertEqual(session['co'], centro_huerfano.codigo)

    def test_admin_login_rejects_inactive_center_without_clients(self):
        centro_inactivo = CentroOperaciones.objects.create(
            nombre='Centro inactivo sin clientes',
            codigo='CO-LOGIN-INACTIVE',
            activo=False,
        )

        response = self._login(centro_inactivo.codigo)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertIn('co', response.context['form'].errors)

    def test_admin_login_uses_legacy_text_for_unregistered_center(self):
        response = self._login('LEGACY-CO-77')

        self.assertRedirects(response, reverse('dashboard'))
        session = self.client.session
        self.assertNotIn('centro_operaciones_id', session)
        self.assertEqual(session['co'], 'LEGACY-CO-77')

    def test_technician_login_does_not_set_center_scope(self):
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])

        response = self._login('', tipo_cuenta='tecnico')

        self.assertRedirects(response, reverse('dashboard'))
        session = self.client.session
        self.assertNotIn('centro_operaciones_id', session)
        self.assertNotIn('co', session)


class RegistroAsistenciaTests(TestCase):
    def test_calcula_horas_trabajadas_automaticamente(self):
        user = get_user_model().objects.create_user(
            username='tecnico-prueba',
            password='test-password',
        )
        now = timezone.now()
        registro = RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=now - timedelta(hours=8),
            hora_salida=now,
        )

        self.assertEqual(registro.horas_trabajadas, 8.0)

    def test_no_calcula_horas_sin_entrada_y_salida(self):
        user = get_user_model().objects.create_user(
            username='tecnico-sin-horas',
            password='test-password',
        )
        registro = RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
        )

        self.assertIsNone(registro.horas_trabajadas)

    def test_dashboard_muestra_botones_de_asistencia_para_tecnico(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-dashboard',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'asistencia-card')
        self.assertContains(response, 'Marcar entrada')
        self.assertNotContains(response, 'Marcar salida')
        self.assertContains(response, 'Registro de Asistencia')

    def test_dashboard_muestra_solo_la_accion_correspondiente_al_estado(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-estados',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Marcar salida')
        self.assertNotContains(response, 'Marcar entrada')

        RegistroAsistencia.objects.filter(usuario=user).update(
            hora_salida=timezone.now(),
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Jornada completa')
        self.assertNotContains(response, 'Marcar entrada')
        self.assertNotContains(response, 'Marcar salida')

    def test_marcar_entrada_crea_registro_y_redirige_al_calendario(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.post(
            reverse('marcar_asistencia'),
            {'accion': 'entrada'},
        )

        registro = RegistroAsistencia.objects.get(usuario=user)
        self.assertIsNotNone(registro.hora_entrada)
        self.assertIsNone(registro.hora_salida)
        self.assertRedirects(
            response,
            f"{reverse('listar_ot')}?vista=calendario&tecnico={user.username}",
        )

    def test_marcar_salida_completa_el_dia(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-salida',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=8),
        )
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.post(
            reverse('marcar_asistencia'),
            {'accion': 'salida'},
        )

        registro = RegistroAsistencia.objects.get(
            usuario=user,
            fecha=timezone.localdate(),
        )
        self.assertIsNotNone(registro.hora_salida)
        self.assertEqual(registro.horas_trabajadas, 8.0)
        self.assertRedirects(
            response,
            f"{reverse('listar_ot')}?vista=calendario&tecnico={user.username}",
        )

    def test_calendario_filtra_ots_por_tecnico(self):
        user = get_user_model().objects.create_user(
            username='Hiller01',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        ubicacion = Ubicacion.objects.create(
            nombre='Ubicación prueba',
            codigo='UBI-01',
        )
        equipo = Equipo.objects.create(
            nombre='Equipo prueba',
            codigo='EQ-01',
            ubicacion=ubicacion,
        )
        estado = Estado.objects.get_or_create(nombre='solicitado')[0]
        solicitud_hiller = Solicitud.objects.create(
            creado_por=user.username,
            descripcion_problema='OT de Hiller01',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        solicitud_otero = Solicitud.objects.create(
            creado_por=user.username,
            descripcion_problema='OT de otro técnico',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        OrdenTrabajo.objects.create(
            solicitud= solicitud_hiller,
            tecnico_asignado='Hiller01',
            fecha_actividad=timezone.now(),
            estado=estado,
        )
        OrdenTrabajo.objects.create(
            solicitud= solicitud_otero,
            tecnico_asignado='Otro Tecnico',
            fecha_actividad=timezone.now(),
            estado=estado,
        )

        response = self.client.get(
            reverse('listar_ot'),
            {'vista': 'calendario', 'tecnico': 'Hiller01'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ots'].count(), 1)
        self.assertEqual(response.context['ots'].first().tecnico_asignado, 'Hiller01')

    def test_dia_completado_muestra_mensaje(self):
        user = get_user_model().objects.create_user(
            username='tecnico-h2-completo',
            password='test-password',
        )
        user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        RegistroAsistencia.objects.create(
            usuario=user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=8),
            hora_salida=timezone.now(),
        )
        self.client.force_login(user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

        response = self.client.post(
            reverse('marcar_asistencia'),
            {'accion': 'entrada'},
            follow=True,
        )

        self.assertRedirects(
            response,
            f"{reverse('listar_ot')}?vista=calendario&tecnico={user.username}",
        )
        self.assertEqual(
            str(list(response.wsgi_request._messages)[0]),
            'Ya completaste el día.',
        )


class ModelosNominaTests(TestCase):
    """Tests básicos de los modelos de nómina."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tecnico_test',
            password='test',
            email='tecnico@example.com',
        )

    def test_configuracion_pago_se_crea(self):
        config = ConfiguracionPago.objects.create(
            usuario=self.user,
            tipo_pago='por_dia',
            valor_dia=Decimal('122000.00'),
        )

        self.assertEqual(config.usuario.username, 'tecnico_test')
        self.assertEqual(config.tipo_pago, 'por_dia')

    def test_calendario_tecnico_crea_dia(self):
        dia = CalendarioTecnico.objects.create(
            usuario=self.user,
            fecha=timezone.localdate(),
            tipo='pico_placa',
            horas_esperadas=Decimal('4.00'),
        )

        self.assertEqual(dia.tipo, 'pico_placa')

    def test_descuento_se_crea(self):
        desc = Descuento.objects.create(
            usuario=self.user,
            tipo='prestamo',
            monto=Decimal('50000.00'),
            fecha_aplicacion=timezone.localdate(),
        )

        self.assertEqual(desc.tipo, 'prestamo')

    def test_recibo_pago_se_crea(self):
        recibo = ReciboPago.objects.create(
            usuario=self.user,
            tipo_periodo='quincenal',
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate(),
            bruto=Decimal('732000.00'),
            neto=Decimal('732000.00'),
        )

        self.assertEqual(recibo.estado, 'borrador')


class MotorNominaTests(TestCase):
    """Tests del motor de cálculo de nómina."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tecnico_nomina',
            password='test',
        )
        self.config = ConfiguracionPago.objects.create(
            usuario=self.user,
            tipo_pago='por_dia',
            valor_dia=Decimal('122000.00'),
            valor_hora_normal=Decimal('15000.00'),
            valor_hora_extra=Decimal('18750.00'),
            horas_semana_estandar=42,
        )

    def test_calculo_periodo_vacio(self):
        from gestion_mantenimiento.users.nomina import calcular_periodo

        resultado = calcular_periodo(
            self.user,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        self.assertEqual(resultado['horas_normales'], Decimal('0.00'))
        self.assertEqual(resultado['bruto'], Decimal('0.00'))

    def test_calculo_con_registros(self):
        from gestion_mantenimiento.users.nomina import calcular_periodo

        inicio = date(2026, 10, 1)
        for i in range(5):
            fecha = inicio + timedelta(days=i)
            RegistroAsistencia.objects.create(
                usuario=self.user,
                fecha=fecha,
                hora_entrada=timezone.make_aware(
                    datetime.combine(fecha, datetime.min.time().replace(hour=8))
                ),
                hora_salida=timezone.make_aware(
                    datetime.combine(fecha, datetime.min.time().replace(hour=16))
                ),
            )

        resultado = calcular_periodo(
            self.user,
            inicio,
            date(2026, 10, 15),
        )

        self.assertEqual(resultado['dias_trabajados'], 5)
        self.assertEqual(resultado['bruto'], Decimal('610000.00'))

    def test_calculo_con_descuento(self):
        from gestion_mantenimiento.users.nomina import calcular_periodo

        inicio = date(2026, 10, 1)
        RegistroAsistencia.objects.create(
            usuario=self.user,
            fecha=inicio,
            hora_entrada=timezone.make_aware(
                datetime.combine(inicio, datetime.min.time().replace(hour=8))
            ),
            hora_salida=timezone.make_aware(
                datetime.combine(inicio, datetime.min.time().replace(hour=16))
            ),
        )
        Descuento.objects.create(
            usuario=self.user,
            tipo='prestamo',
            monto=Decimal('50000.00'),
            fecha_aplicacion=inicio,
        )

        resultado = calcular_periodo(
            self.user,
            inicio,
            date(2026, 10, 15),
        )

        self.assertEqual(resultado['total_descuentos'], Decimal('50000.00'))
        self.assertEqual(resultado['neto'], Decimal('72000.00'))


class DashboardTecnicoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tecnico-dashboard-h3',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        self.client.force_login(self.user)
        self.client.session['tipo_cuenta'] = 'tecnico'
        self.client.session.save()

    def test_dashboard_muestra_resumen_semanal(self):
        RegistroAsistencia.objects.create(
            usuario=self.user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=4),
            hora_salida=timezone.now(),
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('horas_semana', response.context)
        self.assertGreaterEqual(response.context['horas_semana'], 4)
        self.assertContains(response, 'Esta semana')

    def test_dashboard_muestra_historial_asistencia(self):
        RegistroAsistencia.objects.create(
            usuario=self.user,
            fecha=timezone.localdate(),
            hora_entrada=timezone.now() - timedelta(hours=4),
            hora_salida=timezone.now(),
        )

        response = self.client.get(reverse('dashboard'))

        self.assertIn('historial_asistencia', response.context)
        self.assertGreaterEqual(len(response.context['historial_asistencia']), 1)
        self.assertContains(response, 'Últimos 7 días')

    def test_dashboard_muestra_agenda_de_hoy(self):
        ubicacion = Ubicacion.objects.create(
            nombre='Ubicación prueba',
            codigo='UBI-H3',
        )
        equipo = Equipo.objects.create(
            nombre='Equipo prueba',
            codigo='EQ-H3',
            ubicacion=ubicacion,
        )
        estado = Estado.objects.get_or_create(nombre='en proceso')[0]
        solicitud = Solicitud.objects.create(
            creado_por=self.user.username,
            descripcion_problema='Agenda del técnico',
            equipo=equipo,
            ubicacion=ubicacion,
            estado=estado,
        )
        OrdenTrabajo.objects.create(
            solicitud= solicitud,
            tecnico_asignado=self.user.username,
            fecha_actividad=timezone.now(),
            estado=estado,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertIn('ots_hoy', response.context)
        self.assertGreaterEqual(len(response.context['ots_hoy']), 1)
        self.assertContains(response, 'Mi agenda de hoy')
        self.assertContains(response, 'OT-')


class ReportesNominaTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin-reportes',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(self.admin)

    def test_reportes_renderizan_resumen_y_filtros(self):
        response = self.client.get(
            reverse('nomina_reportes'),
            {'periodo': 'mensual', 'desde': '2026-10-01', 'hasta': '2026-10-31'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reportes de Nómina')
        self.assertContains(response, 'Exportar a Excel')
        self.assertEqual(response.context['fecha_inicio'], date(2026, 10, 1))
        self.assertEqual(response.context['fecha_fin'], date(2026, 10, 31))

    def test_export_excel_devuelve_workbook_valido(self):
        response = self.client.get(
            reverse('nomina_reporte_export_excel'),
            {'desde': '2026-10-01', 'hasta': '2026-10-31'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertTrue(response.content.startswith(b'PK\x03\x04'))
        self.assertIn('Content-Disposition', response)


class RegenerarRecibosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tecnico_regenerar',
            password='test-password',
        )
        self.grupo_tecnico = Group.objects.get_or_create(name='Tecnico')[0]
        self.user.groups.add(self.grupo_tecnico)
        ConfiguracionPago.objects.create(
            usuario=self.user,
            tipo_pago='por_dia',
            valor_dia=Decimal('100000.00'),
        )
        self.admin = get_user_model().objects.create_user(
            username='admin_regenerar',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(self.admin)
        self.fecha_inicio = date(2026, 10, 1)
        self.fecha_fin = date(2026, 10, 15)

    def _crear_asistencia(self, fecha):
        hora_inicio = datetime.combine(fecha, datetime.min.time().replace(hour=8))
        hora_fin = datetime.combine(fecha, datetime.min.time().replace(hour=16))
        RegistroAsistencia.objects.create(
            usuario=self.user,
            fecha=fecha,
            hora_entrada=timezone.make_aware(hora_inicio),
            hora_salida=timezone.make_aware(hora_fin),
        )

    def _post_generar(self):
        return self.client.post(
            reverse('nomina_generar_recibos'),
            {
                'fecha_inicio': self.fecha_inicio.isoformat(),
                'fecha_fin': self.fecha_fin.isoformat(),
                'tipo_periodo': 'quincenal',
            },
        )

    def _crear_recibo(self, estado='borrador', usuario=None):
        return ReciboPago.objects.create(
            usuario=usuario or self.user,
            tipo_periodo='quincenal',
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
            dias_trabajados=1,
            bruto=Decimal('100000.00'),
            neto=Decimal('100000.00'),
            estado=estado,
        )

    def test_regenerar_borrador_actualiza_datos(self):
        recibo_viejo = self._crear_recibo()
        self._crear_asistencia(self.fecha_inicio)
        self._crear_asistencia(self.fecha_inicio + timedelta(days=1))

        response = self._post_generar()

        self.assertEqual(response.status_code, 302)
        recibos = ReciboPago.objects.filter(
            usuario=self.user,
            tipo_periodo='quincenal',
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        self.assertEqual(recibos.count(), 1)
        recibo_nuevo = recibos.get()
        self.assertNotEqual(recibo_nuevo.id, recibo_viejo.id)
        self.assertEqual(recibo_nuevo.dias_trabajados, 2)
        self.assertEqual(recibo_nuevo.bruto, Decimal('200000.00'))

    def test_regeneracion_masiva_no_modifica_aprobado_ni_pagado(self):
        aprobado = self._crear_recibo(estado='aprobado')
        otro_tecnico = get_user_model().objects.create_user(username='tecnico_pagado')
        otro_tecnico.groups.add(self.grupo_tecnico)
        ConfiguracionPago.objects.create(
            usuario=otro_tecnico,
            tipo_pago='por_dia',
            valor_dia=Decimal('100000.00'),
        )
        pagado = self._crear_recibo(estado='pagado', usuario=otro_tecnico)

        self._post_generar()

        aprobado.refresh_from_db()
        pagado.refresh_from_db()
        self.assertEqual(aprobado.estado, 'aprobado')
        self.assertEqual(aprobado.bruto, Decimal('100000.00'))
        self.assertEqual(pagado.estado, 'pagado')
        self.assertEqual(pagado.bruto, Decimal('100000.00'))

    def test_recalcular_recibo_borrador_conserva_id_actualiza_datos(self):
        recibo = self._crear_recibo()
        recibo_id = recibo.id
        recibo.pdf_path = 'recibo-anterior.pdf'
        recibo.enviado_por_email = True
        recibo.fecha_envio = timezone.now()
        recibo.save()
        self._crear_asistencia(self.fecha_inicio)
        self._crear_asistencia(self.fecha_inicio + timedelta(days=1))

        detalle = self.client.get(reverse('nomina_recibo_detalle', args=[recibo_id]))
        self.assertContains(detalle, 'Recalcular')

        response = self.client.post(
            reverse('nomina_recibo_recalcular', args=[recibo_id]),
        )

        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()
        self.assertEqual(recibo.id, recibo_id)
        self.assertEqual(recibo.dias_trabajados, 2)
        self.assertEqual(recibo.bruto, Decimal('200000.00'))
        self.assertEqual(recibo.pdf_path, '')
        self.assertFalse(recibo.enviado_por_email)
        self.assertIsNone(recibo.fecha_envio)

    def test_recalcular_no_modifica_recibo_aprobado(self):
        recibo = self._crear_recibo(estado='aprobado')
        detalle = self.client.get(
            reverse('nomina_recibo_detalle', args=[recibo.id]),
        )
        self.assertNotContains(detalle, 'Recalcular')
        response = self.client.post(
            reverse('nomina_recibo_recalcular', args=[recibo.id]),
        )

        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()
        self.assertEqual(recibo.estado, 'aprobado')
        self.assertEqual(recibo.bruto, Decimal('100000.00'))
