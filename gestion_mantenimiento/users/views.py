from datetime import timedelta

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import (
    CalendarioTecnicoForm,
    ConfiguracionPagoForm,
    CustomAuthenticationForm,
    CustomUserCreationForm,
    DescuentoForm,
)
from django.contrib.auth.decorators import user_passes_test
from allauth.socialaccount.models import SocialApp
from gestion_mantenimiento.Gestion_ot.models import OrdenTrabajo, TareaMantenimiento
from gestion_mantenimiento.solicitudes.models import Solicitud
from gestion_mantenimiento.Activos.models import Equipo, Ubicacion
from gestion_mantenimiento.users.access import obtener_cliente_actual, obtener_scope_ubicacion_ids
from .models import CalendarioTecnico, ConfiguracionPago, Descuento, RegistroAsistencia

TIPO_CUENTA_A_GRUPO = {
    'jefe_de_area': 'Admin',
    'administrador': 'Cliente',
    'tecnico': 'Tecnico',
}


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            # Mostrar mensaje de éxito
            login_form = CustomAuthenticationForm()
            return render(request, 'users/login.html', {
                'form': login_form,
                'register_form': form,
                'success_message': '¡Registro exitoso! Por favor inicia sesión con tus credenciales.'
            })
    else:
        form = CustomUserCreationForm()
    
    login_form = CustomAuthenticationForm()
    return render(request, 'users/login.html', {
        'form': login_form,
        'register_form': form
    })

def custom_login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            tipo_cuenta = form.cleaned_data.get('tipo_cuenta')
            co = form.cleaned_data.get('co')

            # Permitir a superusuarios / staff iniciar sesión sin validar grupos
            if user.is_superuser or user.is_staff:
                auth_login(request, user)
                request.session['tipo_cuenta'] = tipo_cuenta
                request.session['co'] = co
                return redirect('dashboard')

            # Validar que el usuario pertenece al grupo seleccionado
            grupo_esperado = TIPO_CUENTA_A_GRUPO.get(tipo_cuenta)
            if not grupo_esperado:
                form.add_error('tipo_cuenta', 'Tipo de cuenta inválido.')
            elif not user.groups.filter(name=grupo_esperado).exists():
                form.add_error(
                    'tipo_cuenta',
                    f'No perteneces al grupo {grupo_esperado}.',
                )
            else:
                auth_login(request, user)
                request.session['tipo_cuenta'] = tipo_cuenta
                request.session['co'] = co
                return redirect('dashboard')  # Redirige a la página de inicio después del inicio de sesión
    else:
        form = CustomAuthenticationForm()
    
    register_form = CustomUserCreationForm()
    google_login_enabled = SocialApp.objects.filter(provider='google').exists()
    return render(request, 'users/login.html', {
        'form': form,
        'register_form': register_form,
        'google_login_enabled': google_login_enabled,
    })

@login_required
def dashboard(request):
    today = timezone.localdate()
    equipo_id = request.GET.get('equipo_id')
    ubicacion_id = request.GET.get('ubicacion_id')

    tipo_cuenta = request.session.get('tipo_cuenta', 'tecnico')
    scope_ids = set()
    cliente = obtener_cliente_actual(request.user)
    if tipo_cuenta == 'administrador':
        scope_ids = obtener_scope_ubicacion_ids(request)
        cliente = obtener_cliente_actual(request.user)
        if cliente is None or not scope_ids:
            scope_ids = set()

    equipos = Equipo.objects.none()
    ubicaciones = Ubicacion.objects.none()
    if tipo_cuenta == 'administrador' and scope_ids:
        equipos = Equipo.objects.filter(ubicacion_id__in=scope_ids).order_by('nombre')
        ubicaciones = Ubicacion.objects.filter(id__in=scope_ids).order_by('nombre')
    elif tipo_cuenta != 'administrador':
        equipos = Equipo.objects.all().order_by('nombre')
        ubicaciones = Ubicacion.objects.all().order_by('nombre')

    ots_base = OrdenTrabajo.objects.all()
    if tipo_cuenta == 'tecnico':
        ots_base = ots_base.filter(tecnico_asignado=request.user.username)
    elif tipo_cuenta == 'administrador' and scope_ids:
        ots_base = ots_base.filter(
            Q(solicitud__ubicacion_id__in=scope_ids) | Q(solicitud__equipo__ubicacion_id__in=scope_ids)
        )
    elif tipo_cuenta == 'administrador':
        ots_base = OrdenTrabajo.objects.none()

    ot_en_proceso = ots_base.filter(estado__nombre='en proceso').count()
    ot_en_revision = ots_base.filter(estado__nombre='en revision').count()
    ot_finalizada = ots_base.filter(estado__nombre='finalizada').count()
    ot_pendientes = ots_base.exclude(estado__nombre='finalizada').count()

    solicitudes_qs = Solicitud.objects.all()
    if tipo_cuenta == 'tecnico':
        solicitudes_qs = solicitudes_qs.filter(creado_por=request.user.username)
    elif tipo_cuenta == 'administrador' and scope_ids:
        solicitudes_qs = solicitudes_qs.filter(
            Q(ubicacion_id__in=scope_ids) | Q(equipo__ubicacion_id__in=scope_ids)
        )
    elif tipo_cuenta == 'administrador':
        solicitudes_qs = Solicitud.objects.none()

    solicitudes_totales = solicitudes_qs.count()
    solicitudes_solicitadas = solicitudes_qs.filter(estado__nombre='solicitado').count()

    tareas_planificadas_qs = TareaMantenimiento.objects.select_related('plan__equipo__ubicacion')
    tareas_no_planificadas_qs = Solicitud.objects.select_related('equipo__ubicacion', 'ubicacion')

    if tipo_cuenta == 'administrador' and scope_ids:
        tareas_planificadas_qs = tareas_planificadas_qs.filter(plan__equipo__ubicacion_id__in=scope_ids)
        tareas_no_planificadas_qs = tareas_no_planificadas_qs.filter(
            Q(ubicacion_id__in=scope_ids) | Q(equipo__ubicacion_id__in=scope_ids)
        )
    elif tipo_cuenta == 'administrador':
        tareas_planificadas_qs = TareaMantenimiento.objects.none()
        tareas_no_planificadas_qs = Solicitud.objects.none()

    if equipo_id:
        tareas_planificadas_qs = tareas_planificadas_qs.filter(plan__equipo_id=equipo_id)
        tareas_no_planificadas_qs = tareas_no_planificadas_qs.filter(equipo_id=equipo_id)

    if ubicacion_id:
        ubicacion = Ubicacion.objects.filter(id=ubicacion_id).first()
        ubicacion_ids = [int(ubicacion_id)]
        if ubicacion:
            def get_descendant_ids(ubicacion_obj):
                ids = [ubicacion_obj.id]
                for child in ubicacion_obj.children.all():
                    ids.extend(get_descendant_ids(child))
                return ids
            ubicacion_ids = get_descendant_ids(ubicacion)
        tareas_planificadas_qs = tareas_planificadas_qs.filter(plan__equipo__ubicacion_id__in=ubicacion_ids)
        tareas_no_planificadas_qs = tareas_no_planificadas_qs.filter(
            Q(ubicacion_id__in=ubicacion_ids) | Q(equipo__ubicacion_id__in=ubicacion_ids)
        )

    tareas_planificadas = tareas_planificadas_qs.count()
    tareas_no_planificadas = tareas_no_planificadas_qs.count()
    tareas_atrasadas = TareaMantenimiento.objects.filter(estado='pendiente', fecha_programada__lt=today).count()
    if tipo_cuenta == 'administrador' and scope_ids:
        tareas_atrasadas = TareaMantenimiento.objects.filter(
            estado='pendiente',
            fecha_programada__lt=today,
            plan__equipo__ubicacion_id__in=scope_ids,
        ).count()
    elif tipo_cuenta == 'administrador':
        tareas_atrasadas = 0
    activos_detenidos = ots_base.filter(estado__nombre__in=['en proceso', 'en revision']).count()
    porcentaje_cumplimiento = 0
    total_ots = ot_en_proceso + ot_en_revision + ot_finalizada
    if total_ots > 0:
        porcentaje_cumplimiento = int((ot_finalizada / total_ots) * 100)

    total_tareas = tareas_planificadas + tareas_no_planificadas
    planificadas_pct = int((tareas_planificadas / total_tareas) * 100) if total_tareas else 0
    no_planificadas_pct = 100 - planificadas_pct if total_tareas else 0

    week_start = today - timedelta(days=6)
    ots_hoy = ots_base.filter(
        fecha_actividad__date=today,
    ).select_related('solicitud').order_by('fecha_actividad', 'solicitud__consecutivo')
    registros_semana = RegistroAsistencia.objects.filter(
        usuario=request.user,
        fecha__gte=week_start,
        fecha__lte=today,
    ).order_by('fecha', '-hora_entrada')
    horas_semana = sum(
        registro.horas_trabajadas or 0
        for registro in registros_semana
    )
    historial_asistencia = list(registros_semana[:7])

    context = {
        'solicitudes_solicitadas': solicitudes_solicitadas,
        'ot_en_proceso': ot_en_proceso,
        'ot_en_revision': ot_en_revision,
        'ot_finalizada': ot_finalizada,
        'ot_pendientes': ot_pendientes,
        'solicitudes_totales': solicitudes_totales,
        'tareas_planificadas': tareas_planificadas,
        'tareas_no_planificadas': tareas_no_planificadas,
        'tareas_atrasadas': tareas_atrasadas,
        'activos_detenidos': activos_detenidos,
        'porcentaje_cumplimiento': porcentaje_cumplimiento,
        'equipos': equipos,
        'ubicaciones': ubicaciones,
        'equipo_id_selected': int(equipo_id) if equipo_id else None,
        'ubicacion_id_selected': int(ubicacion_id) if ubicacion_id else None,
        'total_tareas': total_tareas,
        'planificadas_pct': planificadas_pct,
        'no_planificadas_pct': no_planificadas_pct,
        'tipo_cuenta': tipo_cuenta,
        'ots_hoy': list(ots_hoy),
        'horas_semana': horas_semana,
        'historial_asistencia': historial_asistencia,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'tareas_planificadas': tareas_planificadas,
            'tareas_no_planificadas': tareas_no_planificadas,
            'total_tareas': total_tareas,
            'planificadas_pct': planificadas_pct,
            'no_planificadas_pct': no_planificadas_pct,
        })

    registro_asistencia = RegistroAsistencia.objects.filter(
        usuario=request.user,
        fecha=today,
    ).first()
    if registro_asistencia:
        if registro_asistencia.hora_entrada and registro_asistencia.hora_salida:
            asistencia_estado = 'completa'
        elif registro_asistencia.hora_entrada:
            asistencia_estado = 'entrada'
        else:
            asistencia_estado = 'sin_entrada'
    else:
        asistencia_estado = 'sin_registro'

    context.update({
        'registro_asistencia': registro_asistencia,
        'asistencia_estado': asistencia_estado,
        'estado_asistencia': asistencia_estado,
    })

    return render(request, 'users/dashboard.html', context)


@require_POST
@login_required
def marcar_asistencia(request):
    if not request.user.groups.filter(name='Tecnico').exists():
        messages.error(request, 'Solo los usuarios del equipo Técnico pueden marcar asistencia.')
        return redirect('dashboard')

    accion = request.POST.get('accion')
    if accion not in {'entrada', 'salida'}:
        messages.error(request, 'La acción de asistencia no es válida.')
        return redirect('dashboard')

    fecha_actual = timezone.localdate()
    registro, _ = RegistroAsistencia.objects.get_or_create(
        usuario=request.user,
        fecha=fecha_actual,
    )

    calendar_url = (
        f"{reverse('listar_ot')}?tecnico={request.user.username}&vista=calendario"
    )

    if registro.hora_entrada and registro.hora_salida:
        messages.success(request, 'Ya completaste el día.')
        return redirect(calendar_url)

    if accion == 'entrada':
        if registro.hora_entrada is None:
            registro.hora_entrada = timezone.now()
            registro.save()
            messages.success(request, 'Entrada registrada correctamente.')
        else:
            messages.info(request, 'La entrada de hoy ya fue registrada.')
    elif registro.hora_entrada is None:
        messages.error(request, 'Primero debes registrar la entrada del día.')
        return redirect(calendar_url)
    else:
        registro.hora_salida = timezone.now()
        registro.save()
        messages.success(request, 'Salida registrada correctamente.')

    return redirect(calendar_url)


def logout_view(request):
    logout(request)
    return redirect('custom_login')

def group_required(*group_names):
    def in_groups(u):
        if u.is_authenticated:
            if bool(u.groups.filter(name__in=group_names)) | u.is_superuser:
                return True
        return False
    return user_passes_test(in_groups)

@group_required('Admin')
def admin_view(request):
    return render(request, 'users/admin_view.html')


def _es_admin(user):
    return user.is_staff or user.groups.filter(name__in=['Admin', 'Supervisor']).exists()


def _requiere_admin(view_func):
    from functools import wraps

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not _es_admin(request.user):
            messages.error(request, 'No tenés permiso para acceder a esta sección.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper


@_requiere_admin
def nomina_configuracion(request):
    try:
        grupo_tecnico = Group.objects.get(name='Tecnico')
        tecnicos = User.objects.filter(groups=grupo_tecnico).order_by('username')
    except Group.DoesNotExist:
        tecnicos = User.objects.none()

    tecnicos_data = []
    for tecnico in tecnicos:
        try:
            config = tecnico.configuracion_pago
        except ConfiguracionPago.DoesNotExist:
            config = None
        tecnicos_data.append({'usuario': tecnico, 'config': config})

    return render(
        request,
        'users/nomina/configuracion.html',
        {'tecnicos_data': tecnicos_data},
    )


@_requiere_admin
def nomina_configurar_tecnico(request, user_id):
    tecnico = get_object_or_404(User, id=user_id)
    try:
        config = tecnico.configuracion_pago
    except ConfiguracionPago.DoesNotExist:
        config = ConfiguracionPago(usuario=tecnico)

    if request.method == 'POST':
        form = ConfiguracionPagoForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, f'Configuración actualizada para {tecnico.username}.')
            return redirect('nomina_configuracion')
    else:
        form = ConfiguracionPagoForm(instance=config)

    return render(
        request,
        'users/nomina/configurar_tecnico.html',
        {'tecnico': tecnico, 'form': form},
    )


@_requiere_admin
def nomina_descuentos(request):
    descuentos = Descuento.objects.order_by('-fecha_aplicacion')
    return render(
        request,
        'users/nomina/descuentos.html',
        {'descuentos': descuentos},
    )


@_requiere_admin
def nomina_descuento_form(request, descuento_id=None):
    descuento = (
        get_object_or_404(Descuento, id=descuento_id)
        if descuento_id is not None
        else None
    )
    if request.method == 'POST':
        form = DescuentoForm(request.POST, instance=descuento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Descuento guardado correctamente.')
            return redirect('nomina_descuentos')
    else:
        form = DescuentoForm(instance=descuento)

    return render(
        request,
        'users/nomina/descuento_form.html',
        {'form': form, 'descuento': descuento},
    )


@_requiere_admin
def nomina_calendario(request):
    dias = CalendarioTecnico.objects.order_by('-fecha')
    return render(
        request,
        'users/nomina/calendario.html',
        {'dias': dias},
    )


@_requiere_admin
def nomina_calendario_form(request, dia_id=None):
    dia = get_object_or_404(CalendarioTecnico, id=dia_id) if dia_id is not None else None
    if request.method == 'POST':
        form = CalendarioTecnicoForm(request.POST, instance=dia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Día especial guardado correctamente.')
            return redirect('nomina_calendario')
    else:
        form = CalendarioTecnicoForm(instance=dia)

    return render(
        request,
        'users/nomina/calendario_form.html',
        {'form': form, 'dia': dia},
    )

