from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Solicitud

# Formulario para Solicitud
class SolicitudForm(forms.ModelForm):
    def __init__(self, *args, scope_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.scope_ids = scope_ids
        if scope_ids is not None:
            self.fields['equipo'].queryset = self.fields['equipo'].queryset.filter(
                ubicacion_id__in=scope_ids,
            )

    class Meta:
        model = Solicitud
        fields = [
            'consecutivo', 'creado_por', 'descripcion_problema', 'email_solicitante', 
            'fecha_creacion', 'equipo', 'solicitado_por', 'enviar_email', 'prioridad'
        ]
        widgets = {
            'fecha_creacion': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'prioridad': forms.Select(choices=Solicitud.PRIORIDAD_CHOICES),
            'equipo': forms.HiddenInput(attrs={'id': 'equipo'}),
        }

    def clean_fecha_creacion(self):
        fecha_creacion = self.cleaned_data.get('fecha_creacion')
        if fecha_creacion and timezone.is_naive(fecha_creacion):
            fecha_creacion = timezone.make_aware(fecha_creacion, timezone.get_current_timezone())
        return fecha_creacion

    def clean(self):
        cleaned_data = super().clean()
        equipo = cleaned_data.get('equipo')

        if not equipo:
            raise ValidationError({'equipo': 'Debes seleccionar un equipo.'})

        duplicada = Solicitud.objects.filter(equipo=equipo).exclude(estado__nombre='finalizada')
        if self.scope_ids is not None:
            duplicada = duplicada.filter(
                Q(ubicacion_id__in=self.scope_ids)
                | Q(equipo__ubicacion_id__in=self.scope_ids)
            )
        if self.instance.pk:
            duplicada = duplicada.exclude(pk=self.instance.pk)

        if duplicada.exists():
            raise ValidationError('Ya existe una solicitud activa para este equipo. Finaliza la solicitud anterior antes de crear una nueva.')

        return cleaned_data
