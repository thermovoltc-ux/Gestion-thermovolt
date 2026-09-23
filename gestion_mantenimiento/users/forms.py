from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

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

        perfil = getattr(self.user_cache, 'perfil_usuario', None) if getattr(self, 'user_cache', None) else None
        perfil_co = None
        if perfil is not None and getattr(perfil, 'centro_operaciones', None) is not None:
            perfil_co = perfil.centro_operaciones.codigo

        if not co and perfil_co:
            cleaned_data['co'] = perfil_co
            co = perfil_co

        if tipo_cuenta == 'administrador' and not co:
            self.add_error('co', 'El CO del PDV es requerido para administradores.')

        return cleaned_data