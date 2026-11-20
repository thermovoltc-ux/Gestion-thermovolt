from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase

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
