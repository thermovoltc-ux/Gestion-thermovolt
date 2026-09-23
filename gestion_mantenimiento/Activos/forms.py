from django import forms
from .models import Ubicacion, Equipo

class UbicacionForm(forms.ModelForm):
    parent = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), required=False, label="Ubicación padre (opcional)")
    co = forms.CharField(
        required=False,
        label="Centro de Operaciones",
        widget=forms.TextInput(attrs={'placeholder': 'Ej: 071'}),
    )

    class Meta:
        model = Ubicacion
        fields = ['nombre', 'codigo', 'co', 'descripcion', 'direccion', 'pais', 'ciudad', 'imagen', 'parent']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Ubicacion.objects.all()

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
        self.fields['ubicacion'].queryset = Ubicacion.objects.all()
        self.fields['parent'].queryset = Equipo.objects.all()