from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from mptt.models import MPTTModel, TreeForeignKey

from django.db import models



# Modelo Regional
class Regional(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre



# Modelo UnidadNegocio
class UnidadNegocio(models.Model):
    nombre = models.CharField(max_length=100)
    regional = models.ForeignKey(Regional, related_name='unidades_negocio', on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

# Modelo Ubicacion
class Ubicacion(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, null=False, blank=False)
    codigo = models.CharField(max_length=20, null=False, blank=False)
    descripcion = models.TextField(null=True, blank=True)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    pais = models.CharField(max_length=100, null=True, blank=True)
    ciudad = models.CharField(max_length=100, null=True, blank=True)
    imagen = models.ImageField(upload_to='ubicaciones/', null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.nombre
    
# Modelo Area
class Area(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.ForeignKey(Ubicacion, related_name='areas', on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

# Modelo CentroCostos
class CentroCostos(models.Model):
    nombre = models.CharField(max_length=100)
    area = models.ForeignKey(Area, related_name='centros_costos', on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

# Modelo Activo
class Activo(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True, related_name='activos')
    regional = models.ForeignKey(Regional, on_delete=models.SET_NULL, null=True)
    numero_serie = models.CharField(max_length=100, unique=True, blank=True, null=True)
    centro_costos = models.ForeignKey(CentroCostos, related_name='activos', on_delete=models.CASCADE, null=True, blank=True)
    fecha_adquisicion = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=50, choices=[
        ('operativo', 'Operativo'),
        ('mantenimiento', 'En Mantenimiento'),
        ('fuera_servicio', 'Fuera de Servicio')
    ], default='operativo')

    def __str__(self):
        return self.nombre

# Modelo Item
class Item(MPTTModel):
    nombre = models.CharField(max_length=100)
    activo = models.ForeignKey(Activo, related_name='items', on_delete=models.CASCADE)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['nombre']

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, null=False, blank=False)
    codigo = models.CharField(max_length=20, null=False, blank=False)
    fabricante = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    prioridad = models.CharField(max_length=5, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    fecha_adquisicion = models.DateField(null=True, blank=True)
    horas_uso = models.IntegerField(null=True, blank=True)
    valor_compra = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    imagen = models.ImageField(upload_to='equipos/', null=True, blank=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE , null=True, blank=True, related_name='equipos')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    @property
    def display_label(self):
        label_parts = [self.codigo]
        if self.ubicacion and self.ubicacion.nombre:
            label_parts.append(self.ubicacion.nombre)
        label_parts.append(self.nombre)
        return "/".join([part for part in label_parts if part])

    def __str__(self):
        return self.nombre
