from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, Q, Sum, When
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods

from .forms import MovimientoInventarioForm, ProductoForm
from .models import MovimientoInventario, Producto


def _puede_gestionar_catalogo(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=['Admin', 'Supervisor']).exists()
    )


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
    busqueda = request.GET.get('q', '').strip()
    productos = Producto.objects.select_related(
        'categoria',
        'material_asociado',
    )
    if busqueda:
        productos = productos.filter(
            Q(codigo__icontains=busqueda)
            | Q(nombre__icontains=busqueda)
            | Q(categoria__nombre__icontains=busqueda)
            | Q(material_asociado__codigo__icontains=busqueda)
            | Q(material_asociado__nombre__icontains=busqueda)
        )
    productos = productos.annotate(
        stock_actual=Coalesce(
            _stock_expression(),
            Decimal('0'),
            output_field=DecimalField(max_digits=15, decimal_places=3),
        ),
    )
    return render(request, 'almacen/lista_productos.html', {
        'productos': productos,
        'busqueda': busqueda,
        'puede_editar_catalogo': _puede_gestionar_catalogo(request.user),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def editar_producto(request, producto_id):
    if not _puede_gestionar_catalogo(request.user):
        raise PermissionDenied

    producto = get_object_or_404(Producto, pk=producto_id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                producto = get_object_or_404(
                    Producto.objects.select_for_update(),
                    pk=producto_id,
                )
                form = ProductoForm(request.POST, instance=producto)
                if form.is_valid():
                    producto = form.save(commit=False)
                    material = form.cleaned_data['material_asociado']
                    producto.material_asociado = material
                    producto.save()
                    if material:
                        material.nombre = form.cleaned_data['nombre_material']
                        material.costo_base = form.cleaned_data['costo_base']
                        material.precio_venta_sugerido = form.cleaned_data[
                            'precio_venta_sugerido'
                        ]
                        material.save(update_fields=[
                            'nombre',
                            'costo_base',
                            'precio_venta_sugerido',
                        ])
                    messages.success(request, 'Producto y material asociado actualizados.')
                    return redirect('almacen:lista_productos')
        except IntegrityError:
            messages.error(
                request,
                'No se pudo guardar: el código del producto o la asociación del material ya está en uso.',
            )
            return redirect('almacen:editar_producto', producto_id=producto_id)
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'almacen/editar_producto.html', {
        'form': form,
        'producto': producto,
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
