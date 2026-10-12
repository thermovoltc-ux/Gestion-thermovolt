# Contexto Maestro - Gestión de Mantenimiento

**Actualizado:** 12 de octubre de 2026

**Rama observada:** `master`
**Último commit de implementación observado:** `c6a758b` (`chore(activos): mover JS inline a archivo estatico arbol_activos.js`)

> Documento de continuidad basado en el código y el historial disponibles en este repositorio. Los detalles de Railway que dependen de la configuración activa deben confirmarse en el proyecto antes de ejecutar cambios de producción. No incluir secretos, tokens, URLs con credenciales ni copias de bases de datos en este documento o en Git.

> Al revisar la documentación histórica, `RAILWAY_README.md` parece contener valores de credenciales Cloudinary. Tratar esos valores como potencialmente expuestos: rotarlos con el proveedor y revisar su retiro en una tarea de seguridad separada. No copiarlos aquí.

## 1. Proyecto

Aplicación web Django para la gestión de mantenimiento industrial: ubicaciones y equipos, solicitudes, órdenes de trabajo, cierres e informes; incluye asistencia y nómina de técnicos.

El flujo principal es:

```text
Ubicación -> Equipo -> Solicitud -> Orden de Trabajo -> Cierre -> Informe PDF/Drive/email
                                              |
                                              +-> Planes y tareas de mantenimiento

Asistencia + configuración de pago + descuentos -> cálculo de nómina -> recibo/PDF/email
```

El repositorio remoto observado es `thermovoltc-ux/Gestion-thermovolt`, rama `master`. El dominio `web-production-f2af9.up.railway.app` fue proporcionado en contexto del proyecto; confirmar que siga siendo el dominio activo en Railway. La aplicación usa Railway según sus archivos de despliegue, pero los planes, recursos y configuración activa deben verificarse en el panel de Railway.

## 2. Stack y configuración

- Python del despliegue fijado en `runtime.txt`: 3.11.9. El README indica soporte desde Python 3.9+.
- Django 4.2.7 (`requirements.txt`). No describir este proyecto como Django 5.
- Base de datos: `settings.py` usa `DATABASE_URL` cuando existe. Sin esa variable, en Railway intenta `/data/db.sqlite3` y luego usa un archivo SQLite de respaldo; en desarrollo usa SQLite local. **El motor real del entorno de producción no se confirmó al redactar este documento.**
- PostgreSQL es una opción compatible mediante `DATABASE_URL`; no asumir que la base activa es PostgreSQL sin comprobar el entorno.
- Frontend: templates Django, HTML/CSS, JavaScript, jQuery, jsTree, FullCalendar y assets compilados con Webpack.
- PDFs: ReportLab; el flujo de informes también puede depender de LibreOffice según el entorno.
- Email: Anymail con backend Brevo, configurado por `BREVO_API_KEY`.
- Static: `STATIC_URL=/static/`, directorio de proyecto `static/`, `STATIC_ROOT=staticfiles`; WhiteNoise se añade al middleware fuera de DEBUG.
- Media: storage local por defecto. Cloudinary solo se activa explícitamente con `USE_CLOUDINARY_STORAGE=true` y configuración correspondiente.
- Zona horaria: `America/Bogota`, `USE_TZ=True`.
- Railway inicia mediante `Procfile` -> `start.sh`. El script ejecuta migraciones, crea estados, opcionalmente crea superusuario, hace `collectstatic`, inicia el worker de informes y lanza Gunicorn.
- `nixpacks.toml` configura Python 3.11 y Node, instala dependencias, ejecuta Webpack y arranca `start.sh`.

### Aplicaciones propias

| App | Responsabilidad y modelos representativos |
|---|---|
| `solicitudes` | Solicitudes de mantenimiento (`Solicitud`) y estados relacionados con el flujo. |
| `Activos` | Estructura de ubicaciones, equipos y activos (`Ubicacion`, `Equipo`, `Activo`, `Item`, áreas y centros de costo). |
| `Gestion_ot` | Órdenes y cierres (`OrdenTrabajo`, `CierreOt`), proceso de informe, planes, actividades y tareas preventivas. |
| `users` | Usuarios/perfiles/clientes, asistencia y nómina (`Cliente`, `PerfilUsuario`, `RegistroAsistencia`, `ConfiguracionPago`, `CalendarioTecnico`, `Descuento`, `ReciboPago`). |

Relaciones importantes: `OrdenTrabajo.solicitud` es OneToOne; `CierreOt.orden_trabajo` también es OneToOne. `Solicitud` conserva campos PDV/CO legacy; sus propiedades y el código de aplicación usan `Ubicacion` como fuente preferente cuando está relacionada.

## 3. Roles y acceso

El mapeo de tipo de cuenta a grupo definido en `users/views.py` es `jefe_de_area` -> `Admin`, `administrador` -> `Cliente`, `tecnico` -> `Tecnico`. El helper de acceso de nómina también reconoce usuarios `is_staff` y grupos `Admin`/`Supervisor`. No asumir que los nombres “Admin”, “Cliente” y “administrador” son intercambiables: respetar el helper de autorización de cada vista.

El acceso de administradores de cliente a ubicaciones se filtra por CO y sus ubicaciones descendientes en `users/access.py`. Los técnicos ven principalmente sus propias órdenes y registran asistencia.

## 4. Hitos completados

Los hashes siguientes se comprobaron en el historial local el 12/10/2026.

### Fase A - Seguridad

Commits: `3ff0305`, `b7564bf`, `9386cdd`.

- Se agregó `login_required` a nueve vistas de Activos.
- Se quitó `csrf_exempt` de dos vistas de OT.
- El middleware de Site limita su reescritura a DEBUG.

### Fase B - Integridad de datos

Commits: `0df692c`, `0fe30ec`, `ac59a50`, `9bcd831`, `fe18449`, `219d31d`.

- Relación única de OrdenTrabajo por Solicitud.
- Consolidación del flujo de órdenes sobre `OrdenTrabajo`.
- Integridad de códigos únicos de ubicaciones y equipos, con resolución de duplicados.
- Ajustes a lista, calendario, Kanban, filtros y modal de equipos.
- La ubicación queda como fuente preferida para información de PDV/CO; existen campos legacy en Solicitud por compatibilidad.

### Fase C - Informe confiable

Commits: `99062ae`, `5ee63fb`, `8378a71`.

- Ajustes de envío del informe sin BCC ni adjunto, usando enlace.
- Persistencia de ruta/tamaño de PDF.
- Worker con reintentos de procesamiento de errores.

### Fase D - Limpieza

Commits: `49a68f4`, `5ba642c`, `3008268`, `36899ba`, `23ce055`.

- Eliminación de árbol HTML legacy, archivos JS/CSS vacíos, templates antiguos, código sin uso e imports.

### Fase E - Assets

- **E.1**, `c85d56b`: CSS del árbol trasladado a `static/css/arbol_activos.css`.
- **E.2**, `c6a758b`: los dos bloques JS del árbol trasladados a `static/js/arbol_activos.js`; template reducido a 307 líneas. URLs Django en datos HTML, ubicaciones leídas del select y funciones globales exportadas para handlers existentes. Validaciones realizadas: Django check, `node --check`, `findstatic` y render HTTP 200 con cero JS inline.
- **E.3** está pendiente. Los templates candidatos mencionados en notas anteriores deben volver a medirse antes de planificar cambios.

### Nómina

- **N.1**, `71f7e11`: modelos base.
- **N.2**, `716bb85`: motor de cálculo en `users/nomina.py`.
- **N.3**, `7920a12`: configuración por técnico.
- **N.4**, `7aaff51`: vista de supervisor y generación inicial.
- **N.5**, `5fb477b`: detalle y estados del recibo.
- **N.6**, `9d63424`: PDF de recibo y envío por email.
- **N.7**, `9acd575`: reportes y exportación Excel.
- **N.4b**, `4b1ba42`: regeneración masiva de borradores y recálculo individual; aprobados y pagados protegidos.
- Panel Hub de nómina, `ff9524e`: `/users/nomina/`, KPIs, accesos y últimos recibos.
- Limpieza del acceso duplicado de reportes en sidebar, `827a85a`.

El motor de cálculo está separado en `users/nomina.py`; mantenerlo sin cambios salvo solicitud expresa y pruebas específicas. El proceso del recibo usa estados borrador, aprobado, pagado y anulado.

## 5. Pendientes conocidos

### Fase E.3 - Organización de assets

Se propusieron templates de OT, planes y login con CSS/JS inline. Los conteos anotados en prompts previos no están verificados contra el estado actual; volver a inventariar antes de mover código.

### Fase F - Rendimiento/despliegue

Ideas pendientes, no cambios confirmados: revisar `select_related`/`prefetch_related`, evaluar índices con consultas reales, revisar el build Nixpacks y confirmar recompilación del bundle Webpack. Medir antes de optimizar.

### Almacén, facturación y rentabilidad

Es una propuesta de alcance futuro: materiales asociados a OTs, facturación y análisis de rentabilidad. No confundirla con el panel Hub ya implementado en `ff9524e`; acordar alcance y numeración antes de iniciar.

## 6. Desarrollo y validación

Desde la raíz del repo, en Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py check
python manage.py test
```

Para un cambio frontend, validar además el asset específico (`node --check` si aplica), `manage.py findstatic`, el render de la vista y el orden de carga. Ejecutar pruebas acotadas primero y luego las requeridas por el alcance.

Build del bundle según `package.json`:

```powershell
cd gestion_mantenimiento
npm ci
npm run build
```

El README menciona `.env.example`, pero su presencia debe verificarse antes de depender de él. No imprimir ni pegar secretos de `.env`, Railway o URLs de base de datos en tickets o conversaciones.

## 7. Despliegue y operación

- El `Procfile` delega a `start.sh`; revisar ese script antes de cambiar comandos de arranque.
- `start.sh` migra, corre `crear_estados`, opcionalmente crea superusuario a partir de variables, recolecta static, ejecuta el worker `procesar_informes_pendientes` y arranca Gunicorn con un worker y dos threads.
- En producción, confirmar variables, motor real de DB, volumen persistente, dominio y estado del deploy desde Railway. El README antiguo y comentarios de setup pueden no reflejar la configuración actual.
- Variables observadas en código/configuración incluyen `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `BREVO_API_KEY`, `DEFAULT_FROM_EMAIL`, `USE_CLOUDINARY_STORAGE` y las variables opcionales de superusuario. Los nombres no implican que estén definidas en cada entorno.

## 8. Backup y protección de datos

Railway puede usar PostgreSQL o SQLite según la configuración efectiva; `settings.py` admite ambos casos. Verificar el motor antes de respaldar. Seguir `docs/BACKUP.md`.

**Nunca** copiar una base de producción a `static/`, `staticfiles/` o una URL pública. Los backups contienen datos sensibles, no se suben a Git y deben almacenarse en ubicaciones privadas. La fecha/tamaño/ubicación de un backup solo se considera verificada tras revisar el archivo y su checksum; probar restauración en entorno aislado.

## 9. Cómo retomar

Al iniciar una sesión nueva, compartir este documento y especificar objetivo, alcance, restricciones, entorno y criterios de verificación. Al cerrar cada trabajo, actualizar estado, commits y tareas; confirmar los hechos nuevos contra repo/producción. No registrar credenciales ni datos personales en este documento.
