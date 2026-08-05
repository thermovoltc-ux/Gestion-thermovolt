import os
import json
import tempfile
from io import BytesIO
from typing import Optional

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
except ImportError:  # pragma: no cover - fallback seguro para entorno sin librerías de Drive
    service_account = None
    build = None
    MediaIoBaseUpload = None
    MediaIoBaseDownload = None


def _get_drive_credentials_info():
    service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    service_account_json_path = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON_PATH') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

    if service_account_json:
        try:
            return json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON no contiene JSON válido.') from exc

    if service_account_json_path:
        if not os.path.exists(service_account_json_path):
            raise RuntimeError(f'El archivo de credenciales de Drive no existe: {service_account_json_path}')
        try:
            with open(service_account_json_path, 'r', encoding='utf-8') as credentials_file:
                return json.load(credentials_file)
        except Exception as exc:
            raise RuntimeError('No se pudo leer el archivo de credenciales de Drive.') from exc

    raise RuntimeError('La variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_SERVICE_ACCOUNT_JSON_PATH no está configurada.')


def crear_drive_service():
    if service_account is None or build is None:
        raise RuntimeError('La librería de Google Drive no está instalada en este entorno. Instala google-api-python-client y google-auth para activar el flujo privado.')

    credentials_info = _get_drive_credentials_info()
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=credentials)


def subir_pdf_privado_a_drive(pdf_bytes: bytes, filename: str, folder_id: Optional[str] = None) -> dict:
    """Sube un PDF a Google Drive manteniendo el archivo privado y devuelve metadatos de almacenamiento."""
    if MediaIoBaseUpload is None or MediaIoBaseDownload is None:
        raise RuntimeError('La librería de Google Drive no está instalada en este entorno para subir o descargar archivos privados.')

    drive_service = crear_drive_service()
    folder_id = folder_id.strip() if folder_id else ''
    if not folder_id:
        raise RuntimeError('Para subir con cuenta de servicio se requiere GOOGLE_DRIVE_FOLDER_ID apuntando a una carpeta de Drive compartido (shared drive).')

    file_metadata = {'name': filename, 'parents': [folder_id]}
    file_stream = BytesIO(pdf_bytes)
    media = MediaIoBaseUpload(file_stream, mimetype='application/pdf', resumable=True)

    created_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,name,mimeType,size',
        supportsAllDrives=True,
        supportsTeamDrives=True,
    ).execute()

    file_id = created_file.get('id')
    if not file_id:
        raise RuntimeError('No se pudo obtener el ID del archivo subido a Drive.')

    return {
        'drive_file_id': file_id,
        'nombre_archivo': created_file.get('name') or filename,
        'mime_type': created_file.get('mimeType') or 'application/pdf',
        'file_size_bytes': int(created_file.get('size') or len(pdf_bytes)),
    }


def descargar_archivo_privado_drive(file_id: str):
    """Descarga un archivo de Drive en streaming seguro hacia un archivo temporal local."""
    if MediaIoBaseUpload is None or MediaIoBaseDownload is None:
        raise RuntimeError('La librería de Google Drive no está instalada en este entorno para descargar archivos privados.')

    drive_service = crear_drive_service()
    request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
    temp_file = tempfile.TemporaryFile()
    downloader = MediaIoBaseDownload(temp_file, request, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    temp_file.seek(0)
    return temp_file


def subir_pdf_a_drive(pdf_bytes: bytes, filename: str, folder_id: Optional[str] = None) -> str:
    """Sube un PDF a Google Drive usando una cuenta de servicio y devuelve un enlace público."""
    if MediaIoBaseUpload is None or MediaIoBaseDownload is None:
        raise RuntimeError('La librería de Google Drive no está instalada en este entorno para subir el archivo.')

    drive_service = crear_drive_service()
    folder_id = folder_id.strip() if folder_id else ''
    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    file_stream = BytesIO(pdf_bytes)
    media = MediaIoBaseUpload(file_stream, mimetype='application/pdf', resumable=True)

    if not folder_id:
        raise RuntimeError('Para subir con cuenta de servicio se requiere GOOGLE_DRIVE_FOLDER_ID apuntando a una carpeta de Drive compartido (shared drive).')

    created_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,webViewLink,webContentLink',
        supportsAllDrives=True,
        supportsTeamDrives=True,
    ).execute()

    file_id = created_file.get('id')
    if not file_id:
        raise RuntimeError('No se pudo obtener el ID del archivo subido a Drive.')

    info = drive_service.files().get(
        fileId=file_id,
        fields='webViewLink, webContentLink',
        supportsAllDrives=True,
        supportsTeamDrives=True,
    ).execute()

    # Preferir la URL de contenido directo porque webViewLink apunta a la página
    # HTML de visualización del archivo, no necesariamente al blob del archivo.
    direct_download_url = info.get('webContentLink')
    if direct_download_url:
        return direct_download_url

    view_url = info.get('webViewLink')
    if view_url:
        return view_url

    return f'https://drive.google.com/uc?export=download&id={file_id}'
