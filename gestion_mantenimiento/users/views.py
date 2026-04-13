from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group
from Gestion_ot.models import OrdenTrabajo, TareaMantenimiento
from solicitudes.models import Solicitud

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

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
    return render(request, 'users/login.html', {'form': form})

@login_required
def dashboard(request):
    today = timezone.now().date()

    ot_en_proceso = OrdenTrabajo.objects.filter(estado__nombre='en proceso').count()
    ot_en_revision = OrdenTrabajo.objects.filter(estado__nombre='en revision').count()
    ot_finalizada = OrdenTrabajo.objects.filter(estado__nombre='finalizada').count()
    ot_pendientes = OrdenTrabajo.objects.exclude(estado__nombre='finalizada').count()

    solicitudes_totales = Solicitud.objects.count()
    solicitudes_solicitadas = Solicitud.objects.filter(estado__nombre='solicitado').count()
    tareas_planificadas = TareaMantenimiento.objects.count()
    tareas_no_planificadas = solicitudes_totales
    tareas_atrasadas = TareaMantenimiento.objects.filter(estado='pendiente', fecha_programada__lt=today).count()
    activos_detenidos = OrdenTrabajo.objects.filter(estado__nombre__in=['en proceso', 'en revision']).count()
    porcentaje_cumplimiento = 0
    total_ots = ot_en_proceso + ot_en_revision + ot_finalizada
    if total_ots > 0:
        porcentaje_cumplimiento = int((ot_finalizada / total_ots) * 100)

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
    }
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
