from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import GestionOt, OrdenTrabajo, CierreOt, ImagenCierreOt, PlanMantenimiento, ActividadMantenimiento, TareaMantenimiento, CierreOtActividad

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
    causa_falla = forms.CharField(
        required=False,
        widget=forms.TextInput(),
        label="Causa de la falla"
    )
    firma_digital = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'hidden': 'hidden'}),
        label="Firma Digital"
    )
    firma_receptor = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Firma Receptor"
    )
    se_soluciono = forms.BooleanField(
        required=False,
        widget=forms.RadioSelect(choices=[(True, 'Sí'), (False, 'No')]),
        label="¿Se solucionó la falla?"
    )

    class Meta:
        model = CierreOt
        fields = [
            'tipo_mantenimiento', 'materiales_utilizados', 'correo_tecnico',
            'descripcion_falla', 'fecha_inicio_actividad', 'observaciones',
            'nombre_tecnico', 'causa_falla', 'hora_inicio', 'documento_tecnico',
            'tipo_intervencion', 'hora_fin', 'firma_digital', 'firma_receptor', 'se_soluciono',
            'nombre_receptor', 'documento_receptor'
        ]
        widgets = {
            'fecha_inicio_actividad': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
        }

class CierreOtActividadForm(forms.ModelForm):
    actividad = forms.ModelChoiceField(
        queryset=ActividadMantenimiento.objects.all(),
        widget=forms.HiddenInput()
    )
    realizada = forms.BooleanField(required=False, label="Realizada")
    comentario = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Comentario adicional'
        }),
        label="Comentario"
    )

    class Meta:
        model = CierreOtActividad
        fields = ['actividad', 'realizada', 'comentario']

CierreOtActividadFormSet = inlineformset_factory(
    CierreOt,
    CierreOtActividad,
    form=CierreOtActividadForm,
    extra=0,
    can_delete=False
)

class ImagenCierreOtForm(forms.ModelForm):
    class Meta:
        model = ImagenCierreOt
        fields = ['imagen', 'tipo', 'descripcion']

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


# ============================================================================
# FORMULARIOS PARA MANTENIMIENTO PREVENTIVO
# ============================================================================

class PlanMantenimientoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from gestion_mantenimiento.Activos.models import Equipo
        self.fields['equipo'].queryset = Equipo.objects.all()
        self.fields['equipo'].label_from_instance = lambda obj: obj.display_label
    class Meta:
        model = PlanMantenimiento
        fields = ['equipo', 'nombre', 'descripcion', 'cantidad', 'unidad', 'fecha_inicio', 'activo']
        widgets = {
            'equipo': forms.Select(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Lubricación mensual, Inspección trimestral'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe el propósito y detalles del plan'
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'unidad': forms.Select(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ActividadMantenimientoForm(forms.ModelForm):
    class Meta:
        model = ActividadMantenimiento
        fields = ['nombre', 'descripcion', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la actividad'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Instrucciones o detalles'
            }),
            'orden': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
        }


class ActividadMantenimientoFormSet(forms.BaseInlineFormSet):
    """FormSet para manejar múltiples actividades en un plan"""
    pass


class TareaMantenimientoForm(forms.ModelForm):
    class Meta:
        model = TareaMantenimiento
        fields = ['actividad', 'fecha_programada', 'fecha_ejecutada', 'tecnico', 'estado', 'observaciones']
        widgets = {
            'fecha_programada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'fecha_ejecutada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tecnico': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }

class ImagenAntesForm(forms.Form):
    imagenes_antes = forms.ImageField(widget=MultipleFileInput(attrs={'multiple': True}), required=False, label="Imágenes Antes")

class ImagenDespuesForm(forms.Form):
    imagenes_despues = forms.ImageField(widget=MultipleFileInput(attrs={'multiple': True}), required=False, label="Imágenes Después")