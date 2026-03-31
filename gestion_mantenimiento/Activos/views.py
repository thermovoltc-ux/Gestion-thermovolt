from django.shortcuts import render, redirect
from .forms import UbicacionForm, EquipoForm
from .models import Ubicacion, Equipo

def crear_ubicacion(request):
    if request.method == 'POST':
        form = UbicacionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_activos')
    else:
        form = UbicacionForm()
    return render(request, 'Activos/crear_ubicacion.html', {'form': form})

def crear_equipo(request):
    if request.method == 'POST':
        form = EquipoForm(request.POST)
        if form.is_valid():
            equipo = form.save(commit=False)
            combined_value = form.cleaned_data['combined_field']
            if combined_value.startswith('ubicacion_'):
                ubicacion_id = int(combined_value.split('_')[1])
                equipo.ubicacion = Ubicacion.objects.get(id=ubicacion_id)
            elif combined_value.startswith('equipo_'):
                equipo_id = int(combined_value.split('_')[1])
                equipo.parent = Equipo.objects.get(id=equipo_id)
            equipo.save()
            return redirect('lista_activos')
    else:
        form = EquipoForm()
    return render(request, 'Activos/crear_equipo.html', {'form': form})

def lista_activos(request):
    ubicaciones = Ubicacion.objects.filter(parent__isnull=True)
    context = {
        'ubicaciones': ubicaciones,
    }
    return render(request, 'Activos/lista_activos.html', context)
