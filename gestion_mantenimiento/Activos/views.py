from django.shortcuts import render, redirect
from .forms import UbicacionForm, EquipoForm
from .models import Ubicacion, Equipo

def crear_ubicacion(request):
    if request.method == 'POST':
        form = UbicacionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('lista_activos')
    else:
        form = UbicacionForm()
    return render(request, 'Activos/crear_ubicacion.html', {'form': form})

def crear_equipo(request):
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('lista_activos')
    else:
        form = EquipoForm()
    return render(request, 'Activos/crear_equipo.html', {'form': form})

def crear_equipo_dinamico(request):
    """Crea un equipo hijo dinámicamente desde el árbol"""
    if request.method == 'POST':
        parent_id = request.POST.get('parent_id')
        parent_type = request.POST.get('parent_type')
        form = EquipoForm(request.POST, request.FILES)

        if form.is_valid():
            equipo = form.save(commit=False)

            if parent_type == 'ubicacion' and parent_id:
                try:
                    ubicacion = Ubicacion.objects.get(id=parent_id)
                    equipo.ubicacion = ubicacion
                except Ubicacion.DoesNotExist:
                    pass

            if parent_type == 'equipo' and parent_id:
                try:
                    parent_equipo = Equipo.objects.get(id=parent_id)
                    equipo.parent = parent_equipo
                    if not equipo.ubicacion and parent_equipo.ubicacion:
                        equipo.ubicacion = parent_equipo.ubicacion
                except Equipo.DoesNotExist:
                    pass

            equipo.save()
            return redirect('lista_activos')

        # Si el formulario no es válido, se redirige igual para evitar bloquear la vista de árbol
        return redirect('lista_activos')

    return redirect('lista_activos')

def lista_activos(request):
    ubicaciones = Ubicacion.objects.filter(parent__isnull=True)
    ubicaciones_all = Ubicacion.objects.all()
    context = {
        'ubicaciones': ubicaciones,
        'ubicaciones_all': ubicaciones_all,
    }
    return render(request, 'Activos/lista_activos.html', context)
