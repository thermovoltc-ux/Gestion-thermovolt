from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group
from gestion_mantenimiento.Gestion_ot.models import OrdenTrabajo, TareaMantenimiento
from solicitudes.models import Solicitud
from Activos.models import Equipo, Ubicacion

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

            # Validar que el usuario pertenece al grupo seleccionado
            if tipo_cuenta == 'jefe_de_area' and not user.groups.filter(name='Admin').exists():
                form.add_error('tipo_cuenta', 'No perteneces al grupo Jefe de Área.')
            elif tipo_cuenta == 'administrador' and not user.groups.filter(name='Cliente').exists():
                form.add_error('tipo_cuenta', 'No perteneces al grupo Administrador.')
            elif tipo_cuenta == 'tecnico' and not user.groups.filter(name='Tecnico').exists():
                form.add_error('tipo_cuenta', 'No perteneces al grupo Técnico.')
            else:
                auth_login(request, user)
                request.session['tipo_cuenta'] = tipo_cuenta
                request.session['co'] = co
                return redirect('dashboard')  # Redirige a la página de inicio después del inicio de sesión
    else:
        form = CustomAuthenticationForm()
    
    register_form = CustomUserCreationForm()
    return render(request, 'users/login.html', {
        'form': form,
        'register_form': register_form
    })

@login_required
def dashboard(request):
    today = timezone.now().date()
    equipo_id = request.GET.get('equipo_id')
    ubicacion_id = request.GET.get('ubicacion_id')

    equipos = Equipo.objects.all().order_by('nombre')
    ubicaciones = Ubicacion.objects.all().order_by('nombre')

    tipo_cuenta = request.session.get('tipo_cuenta', 'tecnico')

    ots_base = OrdenTrabajo.objects.all()
    if tipo_cuenta == 'tecnico':
        ots_base = ots_base.filter(tecnico_asignado=request.user.username)

    ot_en_proceso = ots_base.filter(estado__nombre='en proceso').count()
    ot_en_revision = ots_base.filter(estado__nombre='en revision').count()
    ot_finalizada = ots_base.filter(estado__nombre='finalizada').count()
    ot_pendientes = ots_base.exclude(estado__nombre='finalizada').count()

    solicitudes_totales = Solicitud.objects.count()
    solicitudes_solicitadas = Solicitud.objects.filter(estado__nombre='solicitado').count()

    tareas_planificadas_qs = TareaMantenimiento.objects.select_related('plan__equipo__ubicacion')
    tareas_no_planificadas_qs = Solicitud.objects.select_related('equipo__ubicacion', 'ubicacion')

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
    activos_detenidos = ots_base.filter(estado__nombre__in=['en proceso', 'en revision']).count()
    porcentaje_cumplimiento = 0
    total_ots = ot_en_proceso + ot_en_revision + ot_finalizada
    if total_ots > 0:
        porcentaje_cumplimiento = int((ot_finalizada / total_ots) * 100)

    total_tareas = tareas_planificadas + tareas_no_planificadas
    planificadas_pct = int((tareas_planificadas / total_tareas) * 100) if total_tareas else 0
    no_planificadas_pct = 100 - planificadas_pct if total_tareas else 0

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
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'tareas_planificadas': tareas_planificadas,
            'tareas_no_planificadas': tareas_no_planificadas,
            'total_tareas': total_tareas,
            'planificadas_pct': planificadas_pct,
            'no_planificadas_pct': no_planificadas_pct,
        })

    return render(request, 'users/dashboard.html', context)

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
