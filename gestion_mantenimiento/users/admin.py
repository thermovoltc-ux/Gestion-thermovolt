from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    CalendarioTecnico,
    Cliente,
    ConfiguracionPago,
    Descuento,
    PerfilUsuario,
    ReciboPago,
    RegistroAsistencia,
)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Cliente)
admin.site.register(PerfilUsuario)
admin.site.register(CalendarioTecnico)
admin.site.register(ConfiguracionPago)
admin.site.register(Descuento)
admin.site.register(ReciboPago)


@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = (
        'usuario',
        'fecha',
        'hora_entrada',
        'hora_salida',
        'horas_trabajadas',
    )
    list_filter = ('fecha', 'usuario')
    search_fields = (
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
    )
    date_hierarchy = 'fecha'
    readonly_fields = ('horas_trabajadas', 'creado', 'actualizado')
