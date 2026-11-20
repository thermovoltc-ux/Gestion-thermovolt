from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, When
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods

from .forms import MovimientoInventarioForm
from .models import MovimientoInventario, Producto


def _stock_expression():
    return Sum(
        Case(
            When(
                movimientos__tipo=MovimientoInventario.ENTRADA,
                then=F('movimientos__cantidad'),
            ),
            When(
                movimientos__tipo=MovimientoInventario.SALIDA,
                then=-F('movimientos__cantidad'),
            ),
            When(
                movimientos__tipo=MovimientoInventario.AJUSTE,
                then=F('movimientos__cantidad'),
            ),
            output_field=DecimalField(max_digits=15, decimal_places=3),
        ),
        output_field=DecimalField(max_digits=15, decimal_places=3),
    )


@login_required
def lista_productos(request):
    productos = Producto.objects.select_related('categoria').annotate(
        stock_actual=Coalesce(
            _stock_expression(),
            Decimal('0'),
            output_field=DecimalField(max_digits=15, decimal_places=3),
        ),
    )
    return render(request, 'almacen/lista_productos.html', {
        'productos': productos,
    })


@login_required
def lista_movimientos(request):
    movimientos = MovimientoInventario.objects.select_related(
        'producto',
        'producto__categoria',
        'usuario',
    )
    producto_id = request.GET.get('producto', '').strip()
    producto = None

    if producto_id:
        try:
            producto_id = int(producto_id)
        except ValueError:
            return HttpResponseBadRequest('El filtro de producto debe ser un ID numérico.')
        producto = get_object_or_404(Producto, pk=producto_id)
        movimientos = movimientos.filter(producto=producto)

    return render(request, 'almacen/lista_movimientos.html', {
        'movimientos': movimientos,
        'producto_filtrado': producto,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def registrar_movimiento(request, tipo):
    tipos_permitidos = {
        'entrada': MovimientoInventario.ENTRADA,
        'salida': MovimientoInventario.SALIDA,
    }
    tipo_movimiento = tipos_permitidos.get(tipo)
    if tipo_movimiento is None:
        return HttpResponseBadRequest('Tipo de movimiento no válido.')

    if request.method == 'POST':
        form = MovimientoInventarioForm(request.POST, tipo=tipo_movimiento)
        if form.is_valid():
            with transaction.atomic():
                producto = get_object_or_404(
                    Producto.objects.select_for_update(),
                    pk=form.cleaned_data['producto'].pk,
                )
                cantidad = form.cleaned_data['cantidad']

                if (
                    tipo_movimiento == MovimientoInventario.SALIDA
                    and producto.stock < cantidad
                ):
                    form.add_error(
                        'cantidad',
                        f'Stock insuficiente. Disponible: {producto.stock} '
                        f'{producto.unidad_medida}.',
                    )
                else:
                    movimiento = form.save(commit=False)
                    movimiento.producto = producto
                    movimiento.tipo = tipo_movimiento
                    movimiento.usuario = request.user
                    if movimiento.costo_unitario is None:
                        movimiento.costo_unitario = Decimal('0')
                    movimiento.save()

            if not form.errors:
                messages.success(request, 'Movimiento de inventario registrado.')
                return redirect(
                    f"{reverse('almacen:lista_movimientos')}?"
                    f"{urlencode({'producto': movimiento.producto_id})}"
                )
    else:
        form = MovimientoInventarioForm(tipo=tipo_movimiento)

    return render(request, 'almacen/formulario_movimiento.html', {
        'form': form,
        'tipo_movimiento': tipo_movimiento,
        'es_entrada': tipo_movimiento == MovimientoInventario.ENTRADA,
    })
