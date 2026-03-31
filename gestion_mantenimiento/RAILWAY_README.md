# Despliegue en Railway para Gestion Mantenimiento

Railway es una plataforma gratuita para pruebas (con $5 de crédito inicial) que despliega apps Django automáticamente desde GitHub.

## Pasos para Desplegar

### 1. Preparar el Proyecto
- Asegúrate de que `requirements.txt`, `Procfile` y `runtime.txt` estén en la raíz.
- Configura variables de entorno en Railway (ver abajo).
- Sube tu código a un repo GitHub público.

### 2. Crear Proyecto en Railway
- Ve a [railway.app](https://railway.app) y crea una cuenta gratuita.
- Crea un nuevo proyecto y conecta tu repo GitHub.
- Railway detectará Django y construirá automáticamente.

### 3. Variables de Entorno
En el dashboard de Railway, agrega estas variables:
- `DEBUG`: `False`
- `SECRET_KEY`: Genera una nueva clave segura (ej. `openssl rand -base64 32`)
- `ALLOWED_HOSTS`: `*` (o tu dominio si tienes)
- `DATABASE_URL`: Railway lo configura automáticamente si usas su base de datos Postgres (recomendado para persistencia).
- Otras: `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (para correos), etc.

### 4. Base de Datos
- Railway ofrece Postgres gratis. En el dashboard, agrega una base de datos y copia la `DATABASE_URL`.
- Si prefieres SQLite (no recomendado para producción), usa la config por defecto.

### 5. Desplegar
- Railway despliega automáticamente al push a GitHub.
- La URL será algo como `https://tu-proyecto.up.railway.app`.
- Ejecuta `python manage.py migrate` si es necesario (puedes hacerlo localmente o en Railway CLI).

### 6. Pruebas
- Accede a la URL desde móvil/web.
- Verifica logs en el dashboard de Railway.

## Notas
- Para gratis, usa el crédito inicial. Luego paga ~$5/mes por recursos.
- Si hay errores, revisa logs y ajusta settings.py.
- Para SSL, Railway lo maneja automáticamente.