from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from mptt.models import MPTTModel, TreeForeignKey

# Modelo de Estado
class Estado(models.Model):
    ESTADO_CHOICES = [
        ('solicitado', 'Solicitado'),
        ('en proceso', 'OT en Proceso'),
        ('en revision', 'OT en Revisión'),
        ('finalizada', 'OT Finalizada')
    ]
    nombre = models.CharField(max_length=20, choices=ESTADO_CHOICES, unique=True)

    def __str__(self):
        return self.nombre


# Modelo de GestionOt
class GestionOt(models.Model):
    solicitud = models.ForeignKey('solicitudes.Solicitud', on_delete=models.CASCADE)
    tecnico = models.CharField(max_length=100)
    fecha_asignacion = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"GestionOt {self.solicitud}"
    

# Modelo de OrdenTrabajo
class OrdenTrabajo(models.Model):
    solicitud = models.ForeignKey('solicitudes.Solicitud', on_delete=models.CASCADE, related_name='ordenes_trabajo', default=1)
    tecnico_asignado = models.CharField(max_length=100)
    fecha_actividad = models.DateTimeField(blank=True, null=True)
    estado = models.ForeignKey(Estado, on_delete=models.SET_NULL, null=True, default=1)  # Referencia al modelo Estado


    def __str__(self):
        return f"OT-{self.solicitud.consecutivo} - {self.tecnico_asignado}"

class CierreOt(models.Model):
    orden_trabajo = models.OneToOneField(OrdenTrabajo, on_delete=models.CASCADE)
    estado = models.ForeignKey(Estado, on_delete=models.SET_NULL, null=True, default=1)
    tipo_mantenimiento = models.CharField(max_length=255, null=True, blank=True)
    materiales_utilizados = models.TextField(null=True, blank=True)
    correo_tecnico = models.EmailField(null=True, blank=True)
    descripcion_falla = models.TextField(null=True, blank=True)
    fecha_inicio_actividad = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    nombre_tecnico = models.CharField(max_length=255, null=True, blank=True)
    causa_falla = models.TextField(null=True, blank=True)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    documento_tecnico = models.FileField(max_length=100, null=True, blank=True)
    tipo_intervencion = models.CharField(max_length=100, null=True, blank=True)
    firma_digital = models.TextField(null=True, blank=True)  # Firma como data URL (base64)
    se_soluciono = models.BooleanField(default=False)  # Si se solucionó la falla

    def __str__(self):
        return f"OT-{self.orden_trabajo.solicitud.consecutivo} - {self.nombre_tecnico} "


# Modelo para imágenes asociadas a CierreOt
class ImagenCierreOt(models.Model):
    TIPO_CHOICES = (
        ("antes", "Antes"),
        ("despues", "Después"),
    )
    cierre_ot = models.ForeignKey(CierreOt, on_delete=models.CASCADE, related_name="imagenes")
    imagen = models.ImageField(upload_to="cierre_ot/imagenes/")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Imagen {self.tipo} de {self.cierre_ot}"