from django.contrib import admin
from .models import  GestionOt, OrdenTrabajo, Estado, CierreOt


# Register your models here.
admin.site.register(GestionOt)
admin.site.register(OrdenTrabajo)
admin.site.register(Estado)
admin.site.register(CierreOt)