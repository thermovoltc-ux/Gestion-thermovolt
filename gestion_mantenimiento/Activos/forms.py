from django import forms
from .models import Ubicacion, Equipo, CentroOperaciones

class UbicacionForm(forms.ModelForm):
    parent = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), required=False, label="Ubicación padre (opcional)")
    centro_operaciones_codigo = forms.CharField(
        required=False,
        label="Centro de Operaciones",
        widget=forms.TextInput(attrs={'placeholder': 'Ej: 071'}),
    )

    class Meta:
        model = Ubicacion
        fields = ['nombre', 'codigo', 'descripcion', 'direccion', 'pais', 'ciudad', 'imagen', 'parent']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        cliente = None
        centro = None
        if user is not None:
            perfil = getattr(user, 'perfil_usuario', None)
            if perfil is not None:
                cliente = perfil.cliente
                centro = perfil.centro_operaciones

        if cliente is not None:
            self.fields['parent'].queryset = Ubicacion.objects.filter(centro_operaciones__cliente=cliente)
        else:
            self.fields['parent'].queryset = Ubicacion.objects.all()

        if self.instance and getattr(self.instance, 'centro_operaciones_id', None):
            self.fields['centro_operaciones_codigo'].initial = self.instance.centro_operaciones.codigo

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
        centro = None
        if user is not None:
            perfil = getattr(user, 'perfil_usuario', None)
            if perfil is not None:
                cliente = perfil.cliente
                centro = perfil.centro_operaciones

        if cliente is not None:
            ubicaciones = Ubicacion.objects.filter(centro_operaciones__cliente=cliente)
            if centro is not None:
                ubicaciones = ubicaciones.filter(centro_operaciones=centro)
            self.fields['ubicacion'].queryset = ubicaciones.order_by('centro_operaciones__nombre', 'nombre')
            self.fields['parent'].queryset = Equipo.objects.filter(ubicacion__centro_operaciones__cliente=cliente)
            if centro is not None:
                self.fields['parent'].queryset = self.fields['parent'].queryset.filter(ubicacion__centro_operaciones=centro)
        else:
            self.fields['ubicacion'].queryset = Ubicacion.objects.all()
            self.fields['parent'].queryset = Equipo.objects.all()