from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from gestion_mantenimiento.Gestion_ot.models import Material

from .models import (
    CategoriaProducto,
    HerramientaUnidad,
    HistorialHerramienta,
    MovimientoInventario,
    Producto,
)


class ProductoStockTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='almacen-test',
            password='test-password',
        )
        self.categoria = CategoriaProducto.objects.create(nombre='Repuestos')
        self.producto = Producto.objects.create(
            codigo='REP-001',
            nombre='Rodamiento',
            categoria=self.categoria,
            unidad_medida='Unidad',
        )

    def crear_movimiento(self, tipo, cantidad):
        return MovimientoInventario.objects.create(
            producto=self.producto,
            tipo=tipo,
            cantidad=Decimal(cantidad),
            costo_unitario=Decimal('1250.00'),
            usuario=self.usuario,
        )

    def test_stock_sum_entries_subtracts_exits_and_applies_signed_adjustments(self):
        self.crear_movimiento(MovimientoInventario.ENTRADA, '10.000')
        self.crear_movimiento(MovimientoInventario.SALIDA, '4.000')
        self.crear_movimiento(MovimientoInventario.AJUSTE, '-1.000')

        self.assertEqual(self.producto.stock, Decimal('5'))

    def test_weighted_average_reflects_remaining_inventory_after_exits(self):
        for tipo, cantidad, costo in (
            (MovimientoInventario.ENTRADA, '10.000', '10.00'),
            (MovimientoInventario.SALIDA, '4.000', '0.00'),
            (MovimientoInventario.ENTRADA, '10.000', '20.00'),
        ):
            MovimientoInventario.objects.create(
                producto=self.producto,
                tipo=tipo,
                cantidad=Decimal(cantidad),
                costo_unitario=Decimal(costo),
                usuario=self.usuario,
            )

        self.assertEqual(self.producto.stock, Decimal('16'))
        self.assertEqual(self.producto.costo_promedio_actual, Decimal('16.25'))

    def test_new_product_has_zero_stock(self):
        self.assertEqual(self.producto.stock, Decimal('0'))

    def test_movements_cannot_be_changed_or_deleted(self):
        movimiento = self.crear_movimiento(MovimientoInventario.ENTRADA, '2.000')

        with self.assertRaises(ValidationError):
            movimiento.save()
        with self.assertRaises(ValidationError):
            MovimientoInventario.objects.filter(pk=movimiento.pk).update(cantidad=Decimal('3'))
        with self.assertRaises(ValidationError):
            movimiento.delete()
        with self.assertRaises(ValidationError):
            MovimientoInventario.objects.filter(pk=movimiento.pk).delete()

    def test_entry_quantity_must_be_positive_and_adjustment_nonzero(self):
        for tipo, cantidad in (
            (MovimientoInventario.ENTRADA, '0'),
            (MovimientoInventario.SALIDA, '-1'),
            (MovimientoInventario.AJUSTE, '0'),
        ):
            with self.subTest(tipo=tipo, cantidad=cantidad):
                with self.assertRaises(ValidationError):
                    self.crear_movimiento(tipo, cantidad)

    def test_products_with_movements_cannot_be_deleted(self):
        self.crear_movimiento(MovimientoInventario.ENTRADA, '1.000')

        with self.assertRaises(ProtectedError):
            self.producto.delete()


class AlmacenViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='almacen-view-test',
            password='test-password',
        )
        self.client.force_login(self.usuario)
        self.categoria = CategoriaProducto.objects.create(nombre='Eléctricos')
        self.producto = Producto.objects.create(
            codigo='ELEC-001',
            nombre='Automático',
            categoria=self.categoria,
            unidad_medida='Unidad',
            stock_minimo=Decimal('4'),
        )

    def crear_movimiento(self, tipo, cantidad):
        return MovimientoInventario.objects.create(
            producto=self.producto,
            tipo=tipo,
            cantidad=Decimal(cantidad),
            costo_unitario=Decimal('2500.00'),
            usuario=self.usuario,
        )

    def crear_herramienta(self, identificador='SERIE-001'):
        return HerramientaUnidad.objects.create(
            producto=self.producto,
            identificador_unico=identificador,
        )

    def test_product_list_shows_calculated_stock(self):
        session = self.client.session
        session['tipo_cuenta'] = 'administrador'
        session.save()
        material = Material.objects.create(
            codigo='REP-LIST-01',
            categoria='repuestos',
            nombre='Contactor de búsqueda',
            costo_base=Decimal('100.00'),
            precio_venta_sugerido=Decimal('142.86'),
        )
        self.producto.material_asociado = material
        self.producto.save(update_fields=['material_asociado'])
        self.crear_movimiento(MovimientoInventario.ENTRADA, '5')
        self.crear_movimiento(MovimientoInventario.SALIDA, '1')

        response = self.client.get(
            reverse('almacen:lista_productos'),
            {'q': 'Contactor de búsqueda'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['productos'][0].stock_actual, Decimal('4'))
        self.assertContains(response, '4,000')
        self.assertContains(response, 'warehouse-stock-low')
        self.assertContains(response, 'ds-table')
        self.assertContains(
            response,
            f'href="{reverse("almacen:lista_productos")}"',
        )
        self.assertContains(response, 'Almacén')
        self.assertContains(response, 'REP-LIST-01')
        self.assertContains(response, 'Contactor de búsqueda')

    def test_staff_can_update_associated_material_prices_from_product_editor(self):
        material = Material.objects.create(
            codigo='REP-EDIT-01',
            categoria='repuestos',
            nombre='Contactor',
            costo_base=Decimal('100.00'),
            precio_venta_sugerido=Decimal('142.86'),
        )
        self.usuario.is_staff = True
        self.usuario.save(update_fields=['is_staff'])

        response = self.client.post(
            reverse('almacen:editar_producto', args=[self.producto.pk]),
            {
                'codigo': self.producto.codigo,
                'nombre': 'Automático actualizado',
                'categoria': self.categoria.pk,
                'unidad_medida': self.producto.unidad_medida,
                'stock_minimo': '5.000',
                'material_asociado': material.pk,
                'nombre_material': 'Contactor ajustado',
                'costo_base': '125.50',
                'precio_venta_sugerido': '179.29',
            },
        )

        self.assertRedirects(response, reverse('almacen:lista_productos'))
        self.producto.refresh_from_db()
        material.refresh_from_db()
        self.assertEqual(self.producto.nombre, 'Automático actualizado')
        self.assertEqual(self.producto.material_asociado, material)
        self.assertEqual(material.nombre, 'Contactor ajustado')
        self.assertEqual(material.costo_base, Decimal('125.50'))
        self.assertEqual(material.precio_venta_sugerido, Decimal('179.29'))

    def test_non_admin_cannot_edit_product_catalog(self):
        response = self.client.get(
            reverse('almacen:editar_producto', args=[self.producto.pk]),
        )

        self.assertEqual(response.status_code, 403)

    def test_insufficient_stock_exit_is_not_saved(self):
        self.crear_movimiento(MovimientoInventario.ENTRADA, '2')

        response = self.client.post(
            reverse('almacen:registrar_salida'),
            {
                'producto': self.producto.pk,
                'cantidad': '3',
                'costo_unitario': '',
                'documento_referencia': 'REQ-001',
                'observaciones': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stock insuficiente')
        self.assertEqual(
            MovimientoInventario.objects.filter(
                producto=self.producto,
                tipo=MovimientoInventario.SALIDA,
            ).count(),
            0,
        )
        self.assertEqual(self.producto.stock, Decimal('2'))

    def test_exit_with_sufficient_stock_is_saved_and_reduces_stock(self):
        self.crear_movimiento(MovimientoInventario.ENTRADA, '5')

        response = self.client.post(
            reverse('almacen:registrar_salida'),
            {
                'producto': self.producto.pk,
                'cantidad': '2',
                'costo_unitario': '',
                'documento_referencia': 'REQ-002',
                'observaciones': 'Uso en mantenimiento',
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('almacen:lista_movimientos')}?producto={self.producto.pk}",
        )
        salida = MovimientoInventario.objects.get(tipo=MovimientoInventario.SALIDA)
        self.assertEqual(salida.usuario, self.usuario)
        self.assertEqual(salida.costo_unitario, Decimal('0'))
        self.assertEqual(self.producto.stock, Decimal('3'))

    def test_quick_product_creation_returns_json_and_can_be_used_for_entry(self):
        response = self.client.post(
            reverse('almacen:crear_producto_rapido'),
            {
                'codigo': 'QUICK-001',
                'nombre': 'Producto rápido',
                'categoria': self.categoria.pk,
                'unidad_medida': 'Unidad',
                'stock_minimo': '0',
                'material_asociado': '',
                'nombre_material': '',
                'costo_base': '',
                'precio_venta_sugerido': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        producto = Producto.objects.get(pk=payload['id'])
        self.assertEqual(payload['label'], 'QUICK-001 — Producto rápido')
        self.assertEqual(producto.stock, Decimal('0'))

        entrada_response = self.client.post(
            reverse('almacen:registrar_entrada'),
            {
                'producto': producto.pk,
                'cantidad': '4',
                'costo_unitario': '8500.00',
                'documento_referencia': 'COMPRA-QUICK',
                'observaciones': '',
            },
        )

        self.assertRedirects(
            entrada_response,
            f"{reverse('almacen:lista_movimientos')}?producto={producto.pk}",
        )
        self.assertEqual(producto.stock, Decimal('4'))
        self.assertEqual(
            MovimientoInventario.objects.get(producto=producto).tipo,
            MovimientoInventario.ENTRADA,
        )

    def test_movement_form_renders_product_search_and_quick_create_dialog(self):
        response = self.client.get(reverse('almacen:registrar_entrada'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'movement-product-search')
        self.assertContains(response, 'warehouse-products')
        self.assertContains(response, 'quick-product-dialog')
        self.assertContains(response, 'almacen_rapido.js')

    def test_invalid_product_id_renders_movement_form_without_crashing(self):
        response = self.client.post(
            reverse('almacen:registrar_entrada'),
            {
                'producto': 'not-an-id',
                'cantidad': '1',
                'costo_unitario': '100',
                'documento_referencia': '',
                'observaciones': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors['producto'])

    def test_quick_tool_creation_returns_json_and_tool_appears_in_list(self):
        response = self.client.post(
            reverse('almacen:crear_herramienta'),
            {
                'producto': self.producto.pk,
                'identificador_unico': 'PATRIMONIAL-123',
                'observaciones': 'Taladro asignable',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        herramienta = HerramientaUnidad.objects.get(pk=payload['id'])
        self.assertEqual(herramienta.producto, self.producto)
        self.assertEqual(herramienta.estado, HerramientaUnidad.DISPONIBLE)
        self.assertEqual(payload['identificador_unico'], 'PATRIMONIAL-123')

        list_response = self.client.get(reverse('almacen:lista_herramientas'))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'PATRIMONIAL-123')
        self.assertContains(list_response, 'Agregar herramienta')
        self.assertContains(list_response, 'new-tool-dialog')

    def test_quick_tool_creation_rejects_duplicate_identifier(self):
        self.crear_herramienta('SERIE-DUPLICADA')

        response = self.client.post(
            reverse('almacen:crear_herramienta'),
            {
                'producto': self.producto.pk,
                'identificador_unico': 'SERIE-DUPLICADA',
                'observaciones': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('identificador_unico', response.json()['errors'])

    def test_movements_can_be_filtered_by_product(self):
        another_product = Producto.objects.create(
            codigo='ELEC-002',
            nombre='Contactor',
            categoria=self.categoria,
            unidad_medida='Unidad',
        )
        self.crear_movimiento(MovimientoInventario.ENTRADA, '1')
        MovimientoInventario.objects.create(
            producto=another_product,
            tipo=MovimientoInventario.ENTRADA,
            cantidad=Decimal('7'),
            costo_unitario=Decimal('1000'),
            usuario=self.usuario,
        )

        response = self.client.get(
            reverse('almacen:lista_movimientos'),
            {'producto': self.producto.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['movimientos']), 1)
        self.assertEqual(
            response.context['movimientos'][0].producto_id,
            self.producto.pk,
        )

    def test_inventory_pages_require_login(self):
        self.client.logout()

        for route in (
            'almacen:lista_productos',
            'almacen:lista_movimientos',
            'almacen:registrar_entrada',
            'almacen:registrar_salida',
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 302)

    def test_available_tool_can_be_assigned_and_creates_history(self):
        herramienta = self.crear_herramienta()
        tecnico = get_user_model().objects.create_user(
            username='tecnico-herramienta',
            first_name='Técnico',
            last_name='Prueba',
        )

        response = self.client.post(
            reverse('almacen:asignar_herramienta', args=[herramienta.pk]),
            {'tecnico': tecnico.pk, 'observaciones': 'Entrega inicial'},
        )

        self.assertRedirects(response, reverse('almacen:lista_herramientas'))
        herramienta.refresh_from_db()
        historial = HistorialHerramienta.objects.get(herramienta=herramienta)
        self.assertEqual(herramienta.estado, HerramientaUnidad.ASIGNADA)
        self.assertEqual(herramienta.tecnico_asignado, tecnico)
        self.assertIsNotNone(herramienta.fecha_asignacion)
        self.assertEqual(historial.tecnico, tecnico)
        self.assertIsNone(historial.fecha_devolucion)
        self.assertEqual(historial.observaciones, 'Entrega inicial')

    def test_return_makes_tool_available_and_closes_history(self):
        herramienta = self.crear_herramienta()
        tecnico = get_user_model().objects.create_user(username='tecnico-devolucion')
        self.client.post(
            reverse('almacen:asignar_herramienta', args=[herramienta.pk]),
            {'tecnico': tecnico.pk, 'observaciones': 'Asignada'},
        )

        response = self.client.post(
            reverse('almacen:devolver_herramienta', args=[herramienta.pk]),
            {'observaciones': 'Devuelta sin daños'},
        )

        self.assertRedirects(response, reverse('almacen:lista_herramientas'))
        herramienta.refresh_from_db()
        historial = HistorialHerramienta.objects.get(herramienta=herramienta)
        self.assertEqual(herramienta.estado, HerramientaUnidad.DISPONIBLE)
        self.assertIsNone(herramienta.tecnico_asignado)
        self.assertIsNone(herramienta.fecha_asignacion)
        self.assertIsNotNone(historial.fecha_devolucion)
        self.assertIn('Devuelta sin daños', historial.observaciones)

    def test_assigned_tool_cannot_be_assigned_to_another_technician(self):
        herramienta = self.crear_herramienta()
        primer_tecnico = get_user_model().objects.create_user(username='primer-tecnico')
        segundo_tecnico = get_user_model().objects.create_user(username='segundo-tecnico')
        self.client.post(
            reverse('almacen:asignar_herramienta', args=[herramienta.pk]),
            {'tecnico': primer_tecnico.pk, 'observaciones': ''},
        )

        response = self.client.post(
            reverse('almacen:asignar_herramienta', args=[herramienta.pk]),
            {'tecnico': segundo_tecnico.pk, 'observaciones': ''},
        )

        self.assertRedirects(response, reverse('almacen:lista_herramientas'))
        herramienta.refresh_from_db()
        self.assertEqual(herramienta.estado, HerramientaUnidad.ASIGNADA)
        self.assertEqual(herramienta.tecnico_asignado, primer_tecnico)
        self.assertEqual(HistorialHerramienta.objects.filter(
            herramienta=herramienta,
        ).count(), 1)

    def test_tool_list_filters_by_state_and_assigned_technician(self):
        herramienta = self.crear_herramienta()
        tecnico = get_user_model().objects.create_user(username='tecnico-filtro')
        self.client.post(
            reverse('almacen:asignar_herramienta', args=[herramienta.pk]),
            {'tecnico': tecnico.pk, 'observaciones': ''},
        )

        response = self.client.get(
            reverse('almacen:lista_herramientas'),
            {'estado': HerramientaUnidad.ASIGNADA, 'tecnico': tecnico.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['herramientas']), [herramienta])
        self.assertContains(response, 'Historial')
