from django import forms

from .models import MovimientoInventario


class MovimientoInventarioForm(forms.ModelForm):
    class Meta:
        model = MovimientoInventario
        fields = [
            'producto',
            'cantidad',
            'costo_unitario',
            'documento_referencia',
            'observaciones',
        ]
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.001',
                'step': '0.001',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
            }),
            'documento_referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '150',
                'placeholder': 'Factura, remisión u otro soporte',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
        }

    def __init__(self, *args, tipo, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo = tipo
        self.fields['producto'].queryset = self.fields['producto'].queryset.order_by(
            'nombre',
            'codigo',
        )
        self.fields['producto'].empty_label = 'Selecciona un producto'
        self.fields['costo_unitario'].required = tipo == MovimientoInventario.ENTRADA

