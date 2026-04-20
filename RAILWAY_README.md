# Configuración de Railway para Gestión de Mantenimiento

## Variables de Entorno Requeridas

### Base de Datos PostgreSQL
```
DATABASE_URL=postgresql://usuario:password@host:puerto/database
```

### Django Settings
```
SECRET_KEY=tu_clave_secreta_muy_segura
DEBUG=False
DJANGO_SETTINGS_MODULE=gestion_mantenimiento.settings
```

### Superusuario (Opcional)
```
CREATE_SUPERUSER=true
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=tu_password_seguro
```

## Configuración de Cloudinary para Almacenamiento de Imágenes

Para resolver el problema de persistencia de imágenes en Railway (filesystem efímero), hemos implementado Cloudinary como almacenamiento de archivos.

### 1. Credenciales de Cloudinary Configuradas
```
CLOUDINARY_CLOUD_NAME=dn7uvpedg
CLOUDINARY_API_KEY=765566426138583
CLOUDINARY_API_SECRET=qxvDbC3NrWM57EQ_jyUTgdVGfOg
```

O usando la URL completa:
```
CLOUDINARY_URL=cloudinary://765566426138583:qxvDbC3NrWM57EQ_jyUTgdVGfOg@dn7uvpedg
```

### 2. Verificación
Una vez configurado, las imágenes subidas se almacenarán en Cloudinary y serán accesibles permanentemente.

## Despliegue

### Comando de Inicio
```
python manage.py runserver 0.0.0.0:$PORT
```

### Comando de Build (si es necesario)
```bash
pip install -r requirements.txt
```

## Comandos de Inicialización
El script `scripts/setup_railway.sh` ejecuta automáticamente:
1. Migraciones de base de datos
2. Creación de estados iniciales
3. Creación de superusuario (si está configurado)
4. Recolección de archivos estáticos

## Solución de Problemas

### Imágenes no se muestran
- Verifica que las variables de Cloudinary estén configuradas correctamente
- Revisa los logs de Railway para errores de conexión a Cloudinary

### Error de base de datos
- Asegúrate de que `DATABASE_URL` esté configurada correctamente
- Verifica que la base de datos PostgreSQL esté activa

### Archivos estáticos no cargan
- Los archivos estáticos se sirven desde WhiteNoise
- Verifica que `collectstatic` se ejecutó correctamente durante el build