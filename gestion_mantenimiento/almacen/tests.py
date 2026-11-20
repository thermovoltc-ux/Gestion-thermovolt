from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .models import CategoriaProducto, MovimientoInventario, Producto


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

    def test_product_list_shows_calculated_stock(self):
        self.crear_movimiento(MovimientoInventario.ENTRADA, '5')
        self.crear_movimiento(MovimientoInventario.SALIDA, '1')

        response = self.client.get(reverse('almacen:lista_productos'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['productos'][0].stock_actual, Decimal('4'))
        self.assertContains(response, '4,000')
        self.assertContains(response, 'warehouse-stock-low')
        self.assertContains(response, 'ds-table')

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
