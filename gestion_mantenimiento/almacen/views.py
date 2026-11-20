from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, Prefetch, Q, Sum, When
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    HerramientaAsignacionForm,
    HerramientaCreacionForm,
    HerramientaDevolucionForm,
    MovimientoInventarioForm,
    ProductoForm,
    ProductoHerramientaRapidaForm,
    ProductoRapidoForm,
)
from .models import (
    HerramientaUnidad,
    HistorialHerramienta,
    MovimientoInventario,
    Producto,
)
from gestion_mantenimiento.notificaciones.models import Notificacion
from gestion_mantenimiento.notificaciones.utils import notificar_administradores


def _puede_gestionar_catalogo(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=['Admin', 'Supervisor']).exists()
    )


def _es_peticion_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _errores_formulario(form):
    return {
        'errors': form.errors.get_json_data(),
    }


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
def lista_herramientas(request):
    estado = request.GET.get('estado', '').strip()
    tecnico_id = request.GET.get('tecnico', '').strip()
    tipo_producto = request.GET.get('tipo_producto', '').strip()
    estados_permitidos = {choice[0] for choice in HerramientaUnidad.ESTADO_CHOICES}

    if estado and estado not in estados_permitidos:
        return HttpResponseBadRequest('El filtro de estado no es válido.')
    if tipo_producto not in {'', Producto.HERRAMIENTA}:
        return HttpResponseBadRequest('El filtro de tipo de producto no es válido.')

    herramientas = HerramientaUnidad.objects.select_related(
        'producto',
        'producto__categoria',
        'tecnico_asignado',
    ).prefetch_related(
        Prefetch(
            'historial',
            queryset=HistorialHerramienta.objects.select_related('tecnico'),
        ),
    )
    if estado:
        herramientas = herramientas.filter(estado=estado)
    if tipo_producto == Producto.HERRAMIENTA:
        herramientas = herramientas.filter(
            producto__tipo_producto=Producto.HERRAMIENTA,
        )
    if tecnico_id:
        try:
            tecnico_id = int(tecnico_id)
        except ValueError:
            return HttpResponseBadRequest('El filtro de técnico debe ser un ID numérico.')
        herramientas = herramientas.filter(tecnico_asignado_id=tecnico_id)

    for herramienta in herramientas:
        if herramienta.estado == HerramientaUnidad.DISPONIBLE:
            herramienta.asignacion_form = HerramientaAsignacionForm()
        elif herramienta.estado == HerramientaUnidad.ASIGNADA:
            herramienta.devolucion_form = HerramientaDevolucionForm()

    return render(request, 'almacen/lista_herramientas.html', {
        'herramientas': herramientas,
        'productos': Producto.objects.filter(
            Q(tipo_producto=Producto.HERRAMIENTA)
            | Q(herramientas_unidad__isnull=False),
        ).select_related('categoria').distinct().order_by('nombre', 'codigo'),
        'herramienta_form': HerramientaCreacionForm(),
        'estados': HerramientaUnidad.ESTADO_CHOICES,
        'estado_seleccionado': estado,
        'tipo_producto_seleccionado': tipo_producto,
        'tecnicos': get_user_model().objects.order_by(
            'first_name',
            'last_name',
            'username',
        ).filter(is_active=True),
        'tecnico_seleccionado': tecnico_id,
    })


@login_required
@require_POST
def crear_herramienta(request):
    form = HerramientaCreacionForm(request.POST)
    if not form.is_valid():
        if _es_peticion_ajax(request):
            return JsonResponse(_errores_formulario(form), status=400)
        messages.error(request, 'Revisa los datos de la herramienta.')
        return redirect('almacen:lista_herramientas')

    try:
        with transaction.atomic():
            herramienta = form.save()
    except IntegrityError:
        form.add_error(
            'identificador_unico',
            'Ya existe una herramienta con este identificador.',
        )
        if _es_peticion_ajax(request):
            return JsonResponse(_errores_formulario(form), status=400)
        messages.error(request, 'El identificador único ya está registrado.')
        return redirect('almacen:lista_herramientas')

    if _es_peticion_ajax(request):
        return JsonResponse({
            'id': herramienta.pk,
            'producto_id': herramienta.producto_id,
            'producto_label': (
                f'{herramienta.producto.codigo} — {herramienta.producto.nombre}'
            ),
            'identificador_unico': herramienta.identificador_unico,
            'estado': herramienta.get_estado_display(),
            'message': 'Herramienta creada correctamente.',
        }, status=201)

    messages.success(request, 'Herramienta creada correctamente.')
    return redirect('almacen:lista_herramientas')


@login_required
@require_POST
def asignar_herramienta(request, herramienta_id):
    form = HerramientaAsignacionForm(request.POST)
    if not form.is_valid():
        errores = '; '.join(
            error
            for errores_campo in form.errors.values()
            for error in errores_campo
        )
        messages.error(request, f'No se pudo asignar la herramienta: {errores}')
        return redirect('almacen:lista_herramientas')

    try:
        with transaction.atomic():
            herramienta = get_object_or_404(
                HerramientaUnidad.objects.select_for_update(),
                pk=herramienta_id,
            )
            if herramienta.estado != HerramientaUnidad.DISPONIBLE:
                messages.error(
                    request,
                    'La herramienta ya no está disponible para asignación.',
                )
                return redirect('almacen:lista_herramientas')

            tecnico = form.cleaned_data['tecnico']
            fecha_asignacion = timezone.now()
            observaciones = form.cleaned_data['observaciones']
            HistorialHerramienta.objects.create(
                herramienta=herramienta,
                tecnico=tecnico,
                observaciones=observaciones,
            )
            herramienta.estado = HerramientaUnidad.ASIGNADA
            herramienta.tecnico_asignado = tecnico
            herramienta.fecha_asignacion = fecha_asignacion
            herramienta.observaciones = observaciones
            herramienta.save(update_fields=[
                'estado',
                'tecnico_asignado',
                'fecha_asignacion',
                'observaciones',
            ])
    except IntegrityError:
        messages.error(
            request,
            'No se pudo asignar la herramienta porque ya tiene una asignación activa.',
        )
        return redirect('almacen:lista_herramientas')

    messages.success(request, 'Herramienta asignada correctamente.')
    return redirect('almacen:lista_herramientas')


@login_required
@require_POST
def devolver_herramienta(request, herramienta_id):
    form = HerramientaDevolucionForm(request.POST)
    if not form.is_valid():
        errores = '; '.join(
            error
            for errores_campo in form.errors.values()
            for error in errores_campo
        )
        messages.error(request, f'No se pudo devolver la herramienta: {errores}')
        return redirect('almacen:lista_herramientas')

    with transaction.atomic():
        herramienta = get_object_or_404(
            HerramientaUnidad.objects.select_for_update(),
            pk=herramienta_id,
        )
        if herramienta.estado != HerramientaUnidad.ASIGNADA:
            messages.error(request, 'La herramienta no tiene una asignación activa.')
            return redirect('almacen:lista_herramientas')

        historial = HistorialHerramienta.objects.select_for_update().filter(
            herramienta=herramienta,
            fecha_devolucion__isnull=True,
        ).order_by('-fecha_asignacion', '-pk').first()
        if historial is None:
            messages.error(
                request,
                'No se encontró el historial activo de esta herramienta; no se cambió su estado.',
            )
            return redirect('almacen:lista_herramientas')

        observaciones = form.cleaned_data['observaciones']
        historial.fecha_devolucion = timezone.now()
        if observaciones:
            historial.observaciones = '\n'.join(filter(
                None,
                [historial.observaciones, f'Devolución: {observaciones}'],
            ))
        historial.save(update_fields=['fecha_devolucion', 'observaciones'])

        herramienta.estado = HerramientaUnidad.DISPONIBLE
        herramienta.tecnico_asignado = None
        herramienta.fecha_asignacion = None
        herramienta.observaciones = observaciones
        herramienta.save(update_fields=[
            'estado',
            'tecnico_asignado',
            'fecha_asignacion',
            'observaciones',
        ])

    messages.success(request, 'Herramienta devuelta al almacén.')
    return redirect('almacen:lista_herramientas')


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
                    stock_anterior = producto.stock
                    movimiento = form.save(commit=False)
                    movimiento.producto = producto
                    movimiento.tipo = tipo_movimiento
                    movimiento.usuario = request.user
                    if movimiento.costo_unitario is None:
                        movimiento.costo_unitario = Decimal('0')
                    movimiento.save()
                    stock_actual = producto.stock
                    if (
                        tipo_movimiento == MovimientoInventario.SALIDA
                        and producto.stock_minimo > 0
                        and stock_anterior >= producto.stock_minimo
                        and stock_actual < producto.stock_minimo
                    ):
                        notificar_administradores(
                            Notificacion.STOCK_BAJO,
                            'Stock bajo',
                            (
                                f'El producto {producto.nombre} tiene stock bajo. '
                                f'Actual: {stock_actual}, '
                                f'mínimo: {producto.stock_minimo}.'
                            ),
                            reverse('almacen:lista_productos'),
                        )

            if not form.errors:
                messages.success(request, 'Movimiento de inventario registrado.')
                return redirect(
                    f"{reverse('almacen:lista_movimientos')}?"
                    f"{urlencode({'producto': movimiento.producto_id})}"
                )
    else:
        form = MovimientoInventarioForm(tipo=tipo_movimiento)

    selected_product = form.cleaned_data.get('producto') if form.is_bound else None
    return render(request, 'almacen/formulario_movimiento.html', {
        'form': form,
        'productos': Producto.objects.select_related('categoria').order_by(
            'nombre',
            'codigo',
        ),
        'selected_product': selected_product,
        'producto_form': ProductoRapidoForm(),
        'tipo_movimiento': tipo_movimiento,
        'es_entrada': tipo_movimiento == MovimientoInventario.ENTRADA,
    })


@login_required
@require_POST
def crear_producto_rapido(request):
    form = ProductoRapidoForm(request.POST)
    if not form.is_valid():
        if _es_peticion_ajax(request):
            return JsonResponse(_errores_formulario(form), status=400)
        messages.error(request, 'Revisa los datos del producto.')
        return redirect('almacen:registrar_entrada')

    try:
        with transaction.atomic():
            producto = form.save()
    except IntegrityError:
        form.add_error(
            None,
            'No fue posible generar un código único para el producto. Intenta de nuevo.',
        )
        if _es_peticion_ajax(request):
            return JsonResponse(_errores_formulario(form), status=400)
        messages.error(request, 'No fue posible generar un código único para el producto.')
        return redirect('almacen:registrar_entrada')

    if _es_peticion_ajax(request):
        return JsonResponse({
            'id': producto.pk,
            'codigo': producto.codigo,
            'nombre': producto.nombre,
            'label': f'{producto.codigo} — {producto.nombre}',
            'message': 'Producto creado correctamente.',
        }, status=201)

    messages.success(request, 'Producto creado correctamente.')
    destino = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destino = reverse('almacen:registrar_entrada')
    return redirect(destino)


@login_required
@require_POST
def crear_producto_herramienta_rapido(request):
    form = ProductoHerramientaRapidaForm(request.POST)
    if not form.is_valid():
        return JsonResponse(_errores_formulario(form), status=400)

    try:
        with transaction.atomic():
            producto = form.save()
    except IntegrityError:
        form.add_error(
            None,
            'No se pudo generar un código único para el producto. Intenta de nuevo.',
        )
        return JsonResponse(_errores_formulario(form), status=400)

    return JsonResponse({
        'id': producto.pk,
        'codigo': producto.codigo,
        'nombre': producto.nombre,
        'label': f'{producto.codigo} — {producto.nombre}',
        'message': 'Producto creado y seleccionado correctamente.',
    }, status=201)
