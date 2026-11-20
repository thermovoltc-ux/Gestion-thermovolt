from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from gestion_mantenimiento.Gestion_ot.models import Material

from .models import (
    CategoriaProducto,
    HerramientaUnidad,
    MovimientoInventario,
    Producto,
)


class HerramientaAsignacionForm(forms.Form):
    tecnico = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Técnico',
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label='Observaciones',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tecnico'].queryset = get_user_model().objects.filter(
            is_active=True,
        ).order_by('first_name', 'last_name', 'username')
        self.fields['tecnico'].empty_label = 'Selecciona un técnico'


class HerramientaDevolucionForm(forms.Form):
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label='Observaciones de devolución',
    )


class HerramientaCreacionForm(forms.ModelForm):
    class Meta:
        model = HerramientaUnidad
        fields = ['producto', 'identificador_unico', 'observaciones']
        widgets = {
            'producto': forms.HiddenInput(),
            'identificador_unico': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '100',
                'autocomplete': 'off',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
        }
        labels = {
            'producto': 'Producto',
            'identificador_unico': 'Identificador único',
            'observaciones': 'Observaciones',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.select_related(
            'categoria',
        ).order_by('nombre', 'codigo')
        self.fields['producto'].empty_label = 'Selecciona un producto'


class ProductoForm(forms.ModelForm):
    nombre_material = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Nombre del material asociado',
    )
    costo_base = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '0.01',
        }),
    )
    precio_venta_sugerido = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '0.01',
        }),
    )

    class Meta:
        model = Producto
        fields = [
            'codigo',
            'nombre',
            'categoria',
            'unidad_medida',
            'stock_minimo',
            'material_asociado',
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control'}),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.001',
            }),
            'material_asociado': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material_asociado'].queryset = Material.objects.order_by(
            'nombre',
            'codigo',
        )
        self.fields['material_asociado'].required = False
        material = self.instance.material_asociado if self.instance.pk else None
        if material:
            self.initial.setdefault('nombre_material', material.nombre)
            self.initial.setdefault('costo_base', material.costo_base)
            self.initial.setdefault(
                'precio_venta_sugerido',
                material.precio_venta_sugerido,
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('material_asociado'):
            for field_name in (
                'nombre_material',
                'costo_base',
                'precio_venta_sugerido',
            ):
                field_value = cleaned_data.get(field_name)
                if (
                    field_value is None
                    or (field_name == 'nombre_material' and not field_value.strip())
                ):
                    self.add_error(
                        field_name,
                        'Este campo es obligatorio para el material asociado.',
                    )
        return cleaned_data


class ProductoRapidoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre',
            'tipo_producto',
            'unidad_medida',
            'stock_minimo',
            'material_asociado',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_producto': forms.Select(attrs={'class': 'form-control'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control'}),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.001',
            }),
            'material_asociado': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material_asociado'].queryset = Material.objects.order_by(
            'nombre',
            'codigo',
        )
        self.fields['material_asociado'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('material_asociado') or not cleaned_data.get('nombre'):
            return cleaned_data

        coincidencias = Material.objects.filter(
            nombre__iexact=cleaned_data['nombre'].strip(),
            producto_almacen__isnull=True,
        )
        if coincidencias.count() == 1:
            cleaned_data['material_asociado'] = coincidencias.first()
        return cleaned_data

    def save(self, commit=True):
        producto = super().save(commit=False)
        nombre_categoria = (
            'Herramientas'
            if producto.tipo_producto == Producto.HERRAMIENTA
            else 'Repuestos'
        )
        producto.categoria, _ = CategoriaProducto.objects.get_or_create(
            nombre=nombre_categoria,
        )
        if commit:
            producto.save()
            self.save_m2m()
        return producto


class ProductoHerramientaRapidaForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'tipo_producto', 'unidad_medida']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_producto': forms.Select(attrs={'class': 'form-control'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_producto'].choices = [
            (Producto.HERRAMIENTA, 'Herramienta'),
        ]
        self.initial.setdefault('tipo_producto', Producto.HERRAMIENTA)

    def save(self, commit=True):
        producto = super().save(commit=False)
        producto.categoria, _ = CategoriaProducto.objects.get_or_create(
            nombre='Herramientas',
        )
        if commit:
            producto.save()
            self.save_m2m()
        return producto


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
            'producto': forms.HiddenInput(),
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
