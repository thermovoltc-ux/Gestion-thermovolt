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

    def __init__(self, *args, user=None, scope_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        parent_queryset = Ubicacion.objects.all()
        if scope_ids is not None:
            parent_queryset = parent_queryset.filter(id__in=scope_ids)
        self.fields['parent'].queryset = parent_queryset

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

    def __init__(self, *args, user=None, scope_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        ubicaciones = Ubicacion.objects.all()
        equipos = Equipo.objects.all()
        if scope_ids is not None:
            ubicaciones = ubicaciones.filter(id__in=scope_ids)
            equipos = equipos.filter(ubicacion_id__in=scope_ids)
        self.fields['ubicacion'].queryset = ubicaciones
        self.fields['parent'].queryset = equipos