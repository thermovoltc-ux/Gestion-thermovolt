from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from .models import  GestionOt, OrdenTrabajo, CierreOt, ImagenCierreOt

# Formulario para GestionOt
class GestionOtForm(forms.ModelForm):
    class Meta:
        model = GestionOt
        fields = ['solicitud', 'tecnico']

# Formulario para OrdenTrabajo
class OrdenTrabajoForm(forms.ModelForm):
    tecnico_asignado = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Tecnico'),
        required=True,
        label="Nombre del Técnico"
    )

    class Meta:
        model = OrdenTrabajo
        fields = [
            'solicitud', 'tecnico_asignado', 'fecha_actividad', 'estado', 
            
        ]
        widgets = {
            'fecha_actividad': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean_fecha_actividad(self):
        fecha_actividad = self.cleaned_data.get('fecha_actividad')
        if fecha_actividad and timezone.is_naive(fecha_actividad):
            fecha_actividad = timezone.make_aware(fecha_actividad, timezone.get_current_timezone())
        return fecha_actividad

class CierreOtForm(forms.ModelForm):
    firma_digital = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Firma Digital"
    )
    se_soluciono = forms.BooleanField(
        required=False,
        label="¿Se solucionó la falla?"
    )

    class Meta:
        model = CierreOt
        fields = [
            'tipo_mantenimiento', 'materiales_utilizados', 'correo_tecnico', 
            'descripcion_falla', 'fecha_inicio_actividad', 'observaciones', 
            'nombre_tecnico', 'causa_falla', 'hora_inicio', 'documento_tecnico', 
            'tipo_intervencion', 'hora_fin', 'firma_digital', 'se_soluciono'
        ]

class ImagenCierreOtForm(forms.ModelForm):
    class Meta:
        model = ImagenCierreOt
        fields = ['imagen', 'tipo', 'descripcion']