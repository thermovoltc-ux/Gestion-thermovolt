from django import forms
from .models import Ubicacion, Equipo

class CombinedChoiceField(forms.ChoiceField):
    pass  # Ya no hace consultas en el constructor

class UbicacionForm(forms.ModelForm):
    parent = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), required=False, label="Ubicaciones Existentes")

    class Meta:
        model = Ubicacion
        fields = ['nombre', 'codigo', 'descripcion', 'direccion', 'pais', 'ciudad', 'parent']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Ubicacion.objects.all()

class EquipoForm(forms.ModelForm):
    combined_field = CombinedChoiceField(label="Ubicaciones y Equipos Existentes", required=False)

    class Meta:
        model = Equipo
        fields = [
            'nombre', 'codigo', 'fabricante', 'modelo', 'serie', 'prioridad',
            'descripcion', 'fecha_adquisicion', 'horas_uso', 'valor_compra',
            'valor_actual', 'combined_field'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empty_choice = [('', '---------')]
        ubicaciones = [(f'ubicacion_{u.id}', f'Ubicación: {u.nombre}') for u in Ubicacion.objects.all()]
        equipos = [(f'equipo_{e.id}', f'Equipo: {e.nombre}') for e in Equipo.objects.all()]
        self.fields['combined_field'].choices = empty_choice + ubicaciones + equipos