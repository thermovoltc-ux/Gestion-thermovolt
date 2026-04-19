from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from mptt.models import MPTTModel, TreeForeignKey
from datetime import timedelta
from dateutil.relativedelta import relativedelta

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
    firma_tecnico = models.TextField(null=True, blank=True)  # Firma del técnico en base64
    firma_receptor = models.TextField(null=True, blank=True)  # Firma de la persona que recibe
    nombre_receptor = models.CharField(max_length=255, null=True, blank=True)  # Nombre de la persona que recibe
    documento_receptor = models.CharField(max_length=20, null=True, blank=True)  # Número de documento de la persona que recibe
    causa_falla = models.TextField(null=True, blank=True)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    documento_tecnico = models.CharField(max_length=20, null=True, blank=True)  # Número de documento del técnico
    tipo_intervencion = models.CharField(max_length=100, null=True, blank=True)
    firma_digital = models.TextField(null=True, blank=True)  # Firma como data URL (base64)
    se_soluciono = models.BooleanField(default=False)  # Si se solucionó la falla

    def __str__(self):
        return f"OT-{self.orden_trabajo.solicitud.consecutivo} - {self.nombre_tecnico} "


class CierreOtActividad(models.Model):
    cierre_ot = models.ForeignKey(CierreOt, on_delete=models.CASCADE, related_name='actividades_cierre')
    actividad = models.ForeignKey('ActividadMantenimiento', on_delete=models.CASCADE)
    realizada = models.BooleanField(default=False)
    comentario = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['actividad__orden']

    def __str__(self):
        estado = 'Realizada' if self.realizada else 'Pendiente'
        return f"{self.actividad.nombre} - {estado}"


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


# ============================================================================
# MODELOS DE MANTENIMIENTO PREVENTIVO (NUEVOS)
# ============================================================================

class PlanMantenimiento(models.Model):
    """Plan de mantenimiento preventivo asociado a un equipo"""
    UNIDAD_CHOICES = [
        ('dias', 'Días'),
        ('semanas', 'Semanas'),
        ('meses', 'Meses'),
        ('anios', 'Años'),
    ]
    
    equipo = models.ForeignKey('Activos.Equipo', on_delete=models.CASCADE, related_name='planes_mantenimiento')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    
    # Periodicidad dinámica: cantidad + unidad
    cantidad = models.PositiveIntegerField(default=1, help_text="Cada cuántos períodos se repite")
    unidad = models.CharField(max_length=10, choices=UNIDAD_CHOICES, default='meses')
    
    fecha_inicio = models.DateField()
    proxima_fecha = models.DateField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.equipo.nombre} — {self.nombre} (Cada {self.cantidad} {self.get_unidad_display()})"
    
    def get_periodo_display(self):
        return f"Cada {self.cantidad} {self.get_unidad_display()}"
    
    def calcular_siguiente_fecha(self, fecha_base=None):
        """Calcula la siguiente fecha de mantenimiento basada en la periodicidad"""
        if fecha_base is None:
            fecha_base = self.proxima_fecha or self.fecha_inicio
        
        if self.unidad == 'dias':
            return fecha_base + timedelta(days=self.cantidad)
        elif self.unidad == 'semanas':
            return fecha_base + timedelta(weeks=self.cantidad)
        elif self.unidad == 'meses':
            return fecha_base + relativedelta(months=self.cantidad)
        elif self.unidad == 'anios':
            return fecha_base + relativedelta(years=self.cantidad)
        return fecha_base
    
    def generar_tareas_automaticas(self, num_tareas=12):
        """
        Genera automáticamente tareas de mantenimiento para los próximos meses
        num_tareas: cantidad de tareas a generar (default 12 = 1 año)
        """
        fecha_actual = self.proxima_fecha or self.fecha_inicio
        
        for i in range(num_tareas):
            # Obtener o crear tarea
            fecha_programada = self.calcular_siguiente_fecha(fecha_actual)
            
            tarea, created = TareaMantenimiento.objects.get_or_create(
                plan=self,
                fecha_programada=fecha_programada,
                defaults={
                    'actividad': self.actividades.first() if self.actividades.exists() else None,
                    'estado': 'pendiente'
                }
            )
            
            if created:
                fecha_actual = fecha_programada
        
        self.proxima_fecha = self.calcular_siguiente_fecha(fecha_actual)
        self.save()


class ActividadMantenimiento(models.Model):
    """Actividades/tareas que componen un plan de mantenimiento"""
    plan = models.ForeignKey(PlanMantenimiento, on_delete=models.CASCADE, related_name='actividades')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=1, help_text="Orden de ejecución")

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.plan.nombre} — {self.nombre}"


class TareaMantenimiento(models.Model):
    """Registro de ejecución de una tarea de mantenimiento"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
        ('convertido', 'Convertido a OT'),
    ]
    
    plan = models.ForeignKey(PlanMantenimiento, on_delete=models.CASCADE, related_name='tareas')
    actividad = models.ForeignKey(ActividadMantenimiento, on_delete=models.SET_NULL, null=True, blank=True)
    
    fecha_programada = models.DateField()
    fecha_ejecutada = models.DateField(blank=True, null=True)
    
    tecnico = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='tareas_mantenimiento')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_programada']

    def __str__(self):
        return f"Tarea {self.plan.equipo.nombre} — {self.get_estado_display()}"


# ============================================================================
# SIGNALS PARA GENERACIÓN AUTOMÁTICA
# ============================================================================

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=PlanMantenimiento)
def generar_tareas_plan(sender, instance, created, **kwargs):
    """
    Cuando se crea o actualiza un plan, genera automáticamente las tareas
    """
    if created:
        # Generar 12 tareas iniciales (1 año aproximadamente)
        instance.generar_tareas_automaticas(num_tareas=12)