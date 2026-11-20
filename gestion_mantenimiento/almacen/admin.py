from django.contrib import admin

from .models import (
    CategoriaProducto,
    HerramientaUnidad,
    HistorialHerramienta,
    MovimientoInventario,
    Producto,
)


@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre', 'descripcion']


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'categoria', 'unidad_medida', 'stock_minimo', 'stock']
    list_filter = ['categoria', 'unidad_medida']
    search_fields = ['codigo', 'nombre']
    readonly_fields = ['stock']
    ordering = ['nombre', 'codigo']


@admin.register(HerramientaUnidad)
class HerramientaUnidadAdmin(admin.ModelAdmin):
    list_display = [
        'identificador_unico',
        'producto',
        'estado',
        'tecnico_asignado',
        'fecha_asignacion',
    ]
    list_filter = ['estado', 'producto__categoria']
    search_fields = [
        'identificador_unico',
        'producto__codigo',
        'producto__nombre',
        'tecnico_asignado__username',
    ]


@admin.register(HistorialHerramienta)
class HistorialHerramientaAdmin(admin.ModelAdmin):
    list_display = [
        'herramienta',
        'tecnico',
        'fecha_asignacion',
        'fecha_devolucion',
    ]
    list_filter = ['fecha_asignacion', 'fecha_devolucion']
    search_fields = [
        'herramienta__identificador_unico',
        'herramienta__producto__nombre',
        'tecnico__username',
    ]
    readonly_fields = [
        'herramienta',
        'tecnico',
        'fecha_asignacion',
        'fecha_devolucion',
        'observaciones',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = [
        'fecha',
        'producto',
        'tipo',
        'cantidad',
        'costo_unitario',
        'usuario',
        'documento_referencia',
    ]
    list_filter = ['tipo', 'fecha', 'producto__categoria']
    search_fields = ['producto__codigo', 'producto__nombre', 'documento_referencia', 'usuario__username']
    date_hierarchy = 'fecha'
    ordering = ['-fecha', '-pk']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
