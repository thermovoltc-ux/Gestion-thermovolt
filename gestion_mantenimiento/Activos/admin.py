from django.contrib import admin
from .models import Ubicacion, Equipo, CentroOperaciones


@admin.register(CentroOperaciones)
class CentroOperacionesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cliente', 'codigo', 'activo')
    list_filter = ('cliente', 'activo')
    search_fields = ('nombre', 'codigo', 'cliente__nombre')


# Register your models here.
admin.site.register(Equipo)
admin.site.register(Ubicacion)
