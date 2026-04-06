from django.contrib import admin
from .models import GestionOt, OrdenTrabajo, Estado, CierreOt, PlanMantenimiento, ActividadMantenimiento, TareaMantenimiento


# Register your models here.
admin.site.register(GestionOt)
admin.site.register(OrdenTrabajo)
admin.site.register(Estado)
admin.site.register(CierreOt)


# ============================================================================
# ADMIN PARA MANTENIMIENTO PREVENTIVO
# ============================================================================

class ActividadMantenimientoInline(admin.TabularInline):
    model = ActividadMantenimiento
    extra = 1
    fields = ['nombre', 'descripcion', 'orden']


@admin.register(PlanMantenimiento)
class PlanMantenimientoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'equipo', 'cantidad', 'unidad', 'fecha_inicio', 'proxima_fecha', 'activo']
    list_filter = ['activo', 'unidad', 'fecha_creacion']
    search_fields = ['nombre', 'equipo__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    inlines = [ActividadMantenimientoInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('equipo', 'nombre', 'descripcion')
        }),
        ('Periodicidad', {
            'fields': ('cantidad', 'unidad', 'fecha_inicio', 'proxima_fecha')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ActividadMantenimiento)
class ActividadMantenimientoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'plan', 'orden']
    list_filter = ['plan__equipo']
    search_fields = ['nombre', 'plan__nombre']
    ordering = ['plan', 'orden']


@admin.register(TareaMantenimiento)
class TareaMantenimientoAdmin(admin.ModelAdmin):
    list_display = ['plan', 'actividad', 'fecha_programada', 'tecnico', 'estado']
    list_filter = ['estado', 'fecha_programada', 'plan__equipo']
    search_fields = ['plan__nombre', 'tecnico__username']
    readonly_fields = ['fecha_creacion']
    
    fieldsets = (
        ('Plan', {
            'fields': ('plan', 'actividad')
        }),
        ('Fechas', {
            'fields': ('fecha_programada', 'fecha_ejecutada')
        }),
        ('Asignación', {
            'fields': ('tecnico', 'estado')
        }),
        ('Notas', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion',),
            'classes': ('collapse',)
        }),
    )