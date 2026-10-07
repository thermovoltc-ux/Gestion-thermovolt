from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

from .models import CalendarioTecnico, ConfiguracionPago, Descuento


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electrónico")
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'password1' and field_name != 'password2':
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': field.label
                })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email

class CustomAuthenticationForm(AuthenticationForm):
    TIPO_CUENTA_CHOICES = [
        ('jefe_de_area', 'Jefe de Área'),
        ('administrador', 'Administrador'),
        ('tecnico', 'Técnico'),
    ]

    tipo_cuenta = forms.ChoiceField(choices=TIPO_CUENTA_CHOICES, required=True)
    co = forms.CharField(max_length=100, required=False, label="CO del PDV")

    class Meta:
        model = User
        fields = ('username', 'password')

    def clean(self):
        cleaned_data = super().clean()
        tipo_cuenta = cleaned_data.get('tipo_cuenta')
        co = cleaned_data.get('co')

        if tipo_cuenta == 'administrador' and not co:
            self.add_error('co', 'El CO del PDV es requerido para administradores.')

        return cleaned_data


class ConfiguracionPagoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionPago
        fields = [
            'tipo_pago',
            'valor_dia',
            'salario_mensual',
            'valor_hora_normal',
            'valor_hora_extra',
            'recargo_nocturno_porcentaje',
            'recargo_festivo_porcentaje',
            'horas_semana_estandar',
            'dia_pico_placa',
            'activo',
        ]
        widgets = {
            'tipo_pago': forms.Select(attrs={'class': 'form-control'}),
            'valor_dia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'salario_mensual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_hora_normal': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_hora_extra': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'recargo_nocturno_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'recargo_festivo_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'horas_semana_estandar': forms.NumberInput(attrs={'class': 'form-control'}),
            'dia_pico_placa': forms.Select(attrs={'class': 'form-control'}),
        }


class DescuentoForm(forms.ModelForm):
    class Meta:
        model = Descuento
        fields = [
            'usuario',
            'tipo',
            'monto',
            'fecha_aplicacion',
            'descripcion',
            'cuotas_totales',
            'cuota_actual',
            'activo',
        ]


class CalendarioTecnicoForm(forms.ModelForm):
    class Meta:
        model = CalendarioTecnico
        fields = [
            'usuario',
            'fecha',
            'tipo',
            'horas_esperadas',
            'remunerado',
            'descripcion',
        ]