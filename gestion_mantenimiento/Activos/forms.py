from django import forms
from .models import Ubicacion, Equipo, CentroOperaciones

class UbicacionForm(forms.ModelForm):
    parent = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), required=False, label="Ubicación padre (opcional)")
    centro_operaciones = forms.ModelChoiceField(
        queryset=CentroOperaciones.objects.none(),
        required=False,
        label="Centro de Operaciones",
    )

    class Meta:
        model = Ubicacion
        fields = ['nombre', 'codigo', 'descripcion', 'direccion', 'pais', 'ciudad', 'imagen', 'parent', 'centro_operaciones']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        cliente = None
        if user is not None:
            perfil = getattr(user, 'perfil_usuario', None)
            if perfil is not None:
                cliente = perfil.cliente

        if cliente is not None:
            self.fields['parent'].queryset = Ubicacion.objects.filter(centro_operaciones__cliente=cliente)
            self.fields['centro_operaciones'].queryset = CentroOperaciones.objects.filter(cliente=cliente).order_by('nombre')
        else:
            self.fields['parent'].queryset = Ubicacion.objects.all()
            self.fields['centro_operaciones'].queryset = CentroOperaciones.objects.all().order_by('cliente__nombre', 'nombre')

class EquipoForm(forms.ModelForm):
    ubicacion = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), required=False, label="Ubicación")
    parent = forms.ModelChoiceField(queryset=Equipo.objects.none(), required=False, label="Equipo padre (opcional)")

    class Meta:
        model = Equipo
        fields = [
            'nombre', 'codigo', 'fabricante', 'modelo', 'serie', 'prioridad',
            'descripcion', 'fecha_adquisicion', 'horas_uso', 'valor_compra',
            'valor_actual', 'imagen', 'ubicacion', 'parent'
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        cliente = None
        if user is not None:
            perfil = getattr(user, 'perfil_usuario', None)
            if perfil is not None:
                cliente = perfil.cliente

        if cliente is not None:
            self.fields['ubicacion'].queryset = Ubicacion.objects.filter(centro_operaciones__cliente=cliente).order_by('centro_operaciones__nombre', 'nombre')
            self.fields['parent'].queryset = Equipo.objects.filter(ubicacion__centro_operaciones__cliente=cliente)
        else:
            self.fields['ubicacion'].queryset = Ubicacion.objects.all()
            self.fields['parent'].queryset = Equipo.objects.all()