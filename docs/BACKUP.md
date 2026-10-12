# Guía de backup de base de datos

**Actualizada:** 12 de octubre de 2026

## Principios

- Determinar primero qué motor usa el entorno que se va a respaldar. `settings.py` admite PostgreSQL mediante `DATABASE_URL` y SQLite; la configuración de Railway debe comprobarse antes de elegir el procedimiento.
- No imprimir, copiar a tickets ni compartir `DATABASE_URL`, contraseñas, tokens o archivos `.env`.
- **Nunca** guardar dumps en `static/`, `staticfiles/`, media pública ni servirlos por una URL pública. `collectstatic` y WhiteNoise no son mecanismos de transferencia privada.
- No añadir backups a Git. Guardar copias cifradas o en un destino privado con acceso restringido; conservar dos copias independientes.
- Verificar tamaño y checksum después de cada copia. Programar una prueba de restauración en un entorno aislado.

## Frecuencia sugerida

- Semanal, por ejemplo al cierre de la semana.
- Antes de un despliegue, migración o cambio importante de datos.
- Después de una carga masiva que no sea fácil de repetir.

## 1. Preparar y confirmar el entorno

1. Instalar Railway CLI y autenticarse.
2. Enlazar el proyecto correcto y seleccionar explícitamente el entorno/servicio de producción. Confirmar el nombre del proyecto y servicio en Railway.
3. En Railway UI, en el entorno y servicio correctos, verificar si `DATABASE_URL` está definida y si su esquema es `postgresql` o `sqlite`. No copiar ni compartir el valor completo. Si no está definida, contrastar `settings.py` y los logs de arranque (`DATABASE PATH`) y confirmar si hay un volumen persistente montado.

No usar `railway run python manage.py shell` para determinar la ruta de un SQLite remoto: `railway run` ejecuta el proceso local con variables del proyecto, pero no garantiza que el volumen `/data` del servicio esté montado en la máquina local. Si no se puede confirmar el motor y la ruta sin exponer secretos, detenerse y consultar al responsable del entorno.

## 2. PostgreSQL

Este procedimiento requiere que el `DATABASE_URL` del entorno seleccionado sea PostgreSQL y que el cliente `pg_dump` local sea compatible con la versión mayor del servidor. En Windows, instalar PostgreSQL client tools desde una fuente oficial y comprobar `pg_dump --version`.

En PowerShell, desde una terminal local autenticada con Railway CLI:

```powershell
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $env:USERPROFILE 'Documents\Backups Gestion Mantenimiento'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$env:BACKUP_FILE = Join-Path $backupDir "backup_$timestamp.dump"

railway run python -c "import os,subprocess,urllib.parse; u=urllib.parse.urlparse(os.environ['DATABASE_URL']); q=urllib.parse.parse_qs(u.query); env=os.environ.copy(); env.pop('DATABASE_URL',None); env['PGPASSWORD']=urllib.parse.unquote(u.password or ''); ssl=q.get('sslmode'); env['PGSSLMODE']=ssl[0] if ssl else env.get('PGSSLMODE','prefer'); args=['pg_dump','--format=custom','--no-owner','--no-acl','--host',u.hostname,'--port',str(u.port or 5432),'--username',urllib.parse.unquote(u.username or ''),'--dbname',u.path.lstrip('/'),'--file',os.environ['BACKUP_FILE']]; subprocess.run(args,env=env,check=True)"
```

`railway run` debe ejecutar el comando con las variables del proyecto/entorno seleccionado; el script no imprime ni pasa la URL completa como argumento a `pg_dump`. El password se entrega mediante el entorno del proceso. El host de `DATABASE_URL` puede ser privado y no aceptar conexiones desde la PC. Si `pg_dump` no conecta, no publiques el dump ni copies credenciales a un comando compartido: usa un snapshot/exportación privada aprobada o ejecuta el cliente desde un entorno autorizado que sí alcance la base. Si el cliente no encuentra `pg_dump`, instala uno compatible. Nunca copies el dump a static.

Verificar el archivo:

```powershell
Get-Item $env:BACKUP_FILE | Select-Object Name,Length,LastWriteTime
Get-FileHash $env:BACKUP_FILE -Algorithm SHA256
pg_restore --list $env:BACKUP_FILE | Select-Object -First 10
```

Guardar el archivo y el checksum en la carpeta privada de backups y en almacenamiento privado aprobado (por ejemplo, Drive con acceso restringido). No subirlos a Git ni enviarlos como adjunto de un issue.

## 3. SQLite local

Desde la raíz del repositorio, para la base local usar el API de backup de SQLite, que produce una copia consistente sin copiar un archivo mientras está siendo escrito:

```powershell
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$source = 'db.sqlite3'
$backupDir = Join-Path $env:USERPROFILE 'Documents\Backups Gestion Mantenimiento'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$destination = Join-Path $backupDir "backup_$timestamp.sqlite3"
$env:SOURCE_SQLITE = (Resolve-Path $source).Path
$env:DESTINATION_SQLITE = $destination

@'
import os
import sqlite3
source = sqlite3.connect(os.environ['SOURCE_SQLITE'])
destination = sqlite3.connect(os.environ['DESTINATION_SQLITE'])
source.backup(destination)
destination.close()
source.close()
'@ | .\.venv\Scripts\python.exe -

Get-Item $destination | Select-Object Name,Length,LastWriteTime
Get-FileHash $destination -Algorithm SHA256
Remove-Item Env:SOURCE_SQLITE,Env:DESTINATION_SQLITE
```

Reemplazar `db.sqlite3` por la ruta local que muestra la configuración si no coincide.

## 4. SQLite en Railway

La aplicación puede usar `/data/db.sqlite3` en Railway cuando no recibe `DATABASE_URL` y el volumen `/data` está disponible. Un comando ejecutado localmente con `railway run` **no convierte por sí solo** una ruta SQLite remota en un archivo local.

Antes de respaldar SQLite en Railway:

1. Confirmar el path y el volumen persistente activos en el servicio.
2. Usar una función oficial de snapshot/exportación del proveedor o un canal privado de transferencia aprobado para leer el archivo desde el servicio/volumen.
3. Generar una copia SQLite consistente con el backup API de SQLite; coordinarlo para evitar escrituras concurrentes si el mecanismo no soporta snapshot.
4. Transferirla directamente a un destino privado, verificar checksum e integridad y guardar una copia independiente.

Si no existe un procedimiento seguro de descarga para el volumen, detenerse y acordarlo con el administrador de Railway. No copiar el archivo a una carpeta estática o pública ni dejarlo en `/tmp` como única copia.

## 5. Verificar y registrar

Para cada backup, anotar en un registro privado:

- Fecha/hora y entorno respaldado.
- Motor y versión del servidor/cliente.
- Nombre, tamaño y SHA-256 del archivo.
- Ubicaciones privadas donde se guardaron las copias.
- Resultado de la última prueba de restauración.

El checksum confirma que las copias coinciden; no demuestra por sí solo que la base se pueda restaurar. Probar periódicamente una restauración aislada.

## 6. Restauración

La restauración puede sobrescribir datos actuales. Confirmar el entorno y tener una copia reciente de la base destino antes de continuar. Probar primero en staging o una base desechable.

### PostgreSQL

Con `DATABASE_URL` ya configurado de forma segura para la base destino y `pg_restore` compatible:

```powershell
pg_restore --list $env:BACKUP_FILE
```

Solo después de revisar destino, dump y plan de recuperación, restaurar. `--clean` elimina objetos existentes y puede causar pérdida de datos; no ejecutar contra producción sin aprobación y ventana de mantenimiento. Seguir el procedimiento DBA/Railway aprobado para la base del proyecto.

### SQLite

Detener escrituras de la aplicación o usar un snapshot consistente; preservar primero el archivo actual y restaurar el backup al path exacto configurado para ese entorno. Reiniciar el servicio y validar con Django check y pruebas funcionales básicas. No reemplazar la DB de producción sin respaldo del estado previo y aprobación.

## 7. Limpieza y seguridad

- No hay que hacer `collectstatic` ni restart para “publicar” un backup; no publicar backups.
- Eliminar con seguridad las copias temporales locales cuando la copia privada haya sido verificada y la política de retención lo permita.
- Revisar `.gitignore` y `git status`; confirmar que ningún `.sql`, `.dump`, `.sqlite3` o `.gz` con datos reales vaya a staging.
- Mantener la retención definida por la empresa. No asumir que el plan Railway tiene snapshots automáticos ni que no los tiene: verificar las capacidades actuales del plan.

## Errores frecuentes

### `pg_dump: server version mismatch`

Instalar un cliente compatible con la versión mayor del servidor y repetir el dump.

### `DATABASE_URL` no existe o apunta a SQLite

No ejecutar `pg_dump`. Confirmar el motor efectivo y seguir la guía SQLite correspondiente.

### Dump vacío, demasiado pequeño o con checksum diferente

No considerarlo válido ni borrar fuentes temporales. Repetirlo y revisar el log local sin exponer secretos.

### No se puede obtener de forma privada la DB SQLite de Railway

No usar `static/` ni endpoints públicos como atajo. Acordar un snapshot/transferencia privada con el responsable del servicio antes de dar el backup por realizado.
