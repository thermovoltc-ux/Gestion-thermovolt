# Gestión de Mantenimiento

Aplicación web para la gestión de mantenimiento de activos y órdenes de trabajo.

## Requisitos

- Python 3.9+
- Node.js (para webpack)
- PostgreSQL (para producción) o SQLite (para desarrollo)

## Instalación

1. Clona el repositorio:
   ```bash
   git clone <url-del-repo>
   cd gestion_mantenimiento
   ```

2. Crea un entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   ```

3. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   npm install
   ```

4. Configura variables de entorno:
   ```bash
   cp .env.example .env
   # Edita .env con tus credenciales
   ```

5. Ejecuta migraciones:
   ```bash
   python manage.py migrate
   ```

6. Compila assets:
   ```bash
   npm run build
   python manage.py collectstatic
   ```

7. Crea un superusuario:
   ```bash
   python manage.py createsuperuser
   ```

8. Ejecuta el servidor:
   ```bash
   python manage.py runserver
   ```

## Despliegue en Railway

Esta aplicación está optimizada para desplegarse en Railway con SQLite.

### Pasos para desplegar:

1. **Crear proyecto en Railway:**
   - Ve a [Railway.app](https://railway.app) y crea una cuenta
   - Crea un nuevo proyecto
   - Conecta tu repositorio GitHub: `thermovoltc-ux/Gestion-thermovolt`

2. **Configurar variables de entorno:**
   Agrega estas variables en Railway (Variables → Add):

   ```
   SECRET_KEY=tu_clave_secreta_muy_segura_aqui
   DEBUG=False
   ALLOWED_HOSTS=tu-proyecto.up.railway.app
   SECURE_SSL_REDIRECT=True
   DATABASE_URL=sqlite:///db.sqlite3
   EMAIL_HOST_USER=tu_email@gmail.com
   EMAIL_HOST_PASSWORD=tu_app_password
   GOOGLE_CLIENT_ID=tu_google_client_id
   GOOGLE_CLIENT_SECRET=tu_google_client_secret
   ```

3. **Railway detectará automáticamente:**
   - `Procfile` para el comando de ejecución
   - `requirements.txt` para las dependencias
   - `runtime.txt` si necesitas una versión específica de Python

4. **Despliegue automático:**
   - Railway ejecutará automáticamente las migraciones y collectstatic
   - La aplicación estará disponible en `https://tu-proyecto.up.railway.app`

### Notas importantes:

- **SQLite en Railway:** Los archivos se persisten, pero considera PostgreSQL para producción real
- **Superusuario:** Crea el superusuario manualmente después del despliegue usando Railway CLI o conectándote a la base de datos
- **Dominio:** Railway asigna automáticamente un dominio `*.up.railway.app`

### Comandos útiles para Railway:

```bash
# Ver logs
railway logs

# Conectar a la base de datos
railway connect

# Ejecutar comandos Django
railway run python manage.py shell
```

## Configuración OAuth

Para Google OAuth:
1. Ve a Google Cloud Console
2. Crea credenciales OAuth 2.0
3. Agrega los URIs de redireccionamiento autorizados
4. Configura las variables en .env

## Licencia

[Tu licencia aquí]

## Envíos dinámicos de informes por PDV (CLIENT_EMAIL_MAP)

La aplicación puede enrutar automáticamente los correos de cierre de OT a direcciones de email específicas por PDV/cliente.

Cómo configurarlo:

- Opción 1: Añadir el mapeo directamente en `gestion_mantenimiento/settings.py` (ya incluye un ejemplo):

```
CLIENT_EMAIL_MAP = {
   "bostauros niquia": "calidadpuntos@bostauros.co",
   "tienda central": "calidad@ejemplo.com,ops@ejemplo.com",
}
```

- Opción 2 (recomendado para producción): definir la variable de entorno `CLIENT_EMAIL_MAP` con un JSON string (útil en Railway):

```
CLIENT_EMAIL_MAP='{"bostauros niquia": "calidadpuntos@bostauros.co"}'
```

Comportamiento:
- Al cerrar una OT, el sistema buscará el PDV asociado y, si existe una entrada en `CLIENT_EMAIL_MAP`, enviará el informe a esas direcciones además del técnico.
- Si no hay mapeo, el sistema intentará usar `solicitud.email_solicitante` como fallback.

Recuerda añadir los emails reales en `CLIENT_EMAIL_MAP` o por variable de entorno antes de desplegar.