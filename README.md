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

## Despliegue

Esta aplicación está configurada para desplegarse en Railway.

Asegúrate de configurar las variables de entorno en tu plataforma de despliegue.

## Configuración OAuth

Para Google OAuth:
1. Ve a Google Cloud Console
2. Crea credenciales OAuth 2.0
3. Agrega los URIs de redireccionamiento autorizados
4. Configura las variables en .env

## Licencia

[Tu licencia aquí]