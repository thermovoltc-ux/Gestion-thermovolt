from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group

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
    return render(request, 'users/dashboard.html')

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
