from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from mptt.models import MPTTModel, TreeForeignKey

# Modelo de Solicitud
class Solicitud(models.Model):
    consecutivo = models.AutoField(primary_key=True)
    creado_por = models.CharField(max_length=100)
    descripcion_problema = models.TextField()
    equipo = models.ForeignKey('Activos.Equipo', on_delete=models.CASCADE, null=False, blank=False)
    email_solicitante = models.EmailField(max_length=254, null=True)
    enviar_email = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    PDV = models.CharField(max_length=100, null=True, blank=True)  # Campo PDV para almacenar el nombre de la ubicación
    estado = models.ForeignKey('Gestion_ot.Estado', on_delete=models.SET_NULL, null=True, default=1)  # Referencia al modelo Estado
    co = models.CharField(max_length=100, null=True, blank=True)  # Campo CO para almacenar el código de la ubicación
    solicitado_por = models.CharField(max_length=100, default='')  # Campo Solicitado por
    
    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta')
    ]
    prioridad = models.CharField(max_length=5, choices=PRIORIDAD_CHOICES, default='media')  # Nuevo campo

    ubicacion = models.ForeignKey('Activos.Ubicacion', on_delete=models.CASCADE, null=True, blank=True)  # Referencia al modelo Ubicacion

    def save(self, *args, **kwargs):
        if self.fecha_creacion and timezone.is_naive(self.fecha_creacion):
            self.fecha_creacion = timezone.make_aware(self.fecha_creacion, timezone.get_current_timezone())
        
        # Asignar el nombre y el código de la ubicación a los campos PDV y co
        if self.ubicacion:
            self.PDV = self.ubicacion.nombre
            self.co = self.ubicacion.codigo
        
        super(Solicitud, self).save(*args, **kwargs)

    def __str__(self):
        return f"Solicitud {self.consecutivo}"