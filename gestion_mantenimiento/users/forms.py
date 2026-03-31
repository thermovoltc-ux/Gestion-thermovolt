from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

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