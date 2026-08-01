import os
import json
from io import BytesIO
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


def subir_pdf_a_drive(pdf_bytes: bytes, filename: str, folder_id: Optional[str] = None) -> str:
    """Sube un PDF a Google Drive usando una cuenta de servicio y devuelve un enlace público."""
    service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    service_account_json_path = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON_PATH') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

    if service_account_json:
        try:
            credentials_info = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON no contiene JSON válido.') from exc
    elif service_account_json_path:
        if not os.path.exists(service_account_json_path):
            raise RuntimeError(f'El archivo de credenciales de Drive no existe: {service_account_json_path}')
        try:
            with open(service_account_json_path, 'r', encoding='utf-8') as credentials_file:
                credentials_info = json.load(credentials_file)
        except Exception as exc:
            raise RuntimeError('No se pudo leer el archivo de credenciales de Drive.') from exc
    else:
        raise RuntimeError('La variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_SERVICE_ACCOUNT_JSON_PATH no está configurada.')

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )

    drive_service = build('drive', 'v3', credentials=credentials)
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

    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'},
            supportsAllDrives=True,
            supportsTeamDrives=True,
        ).execute()
    except Exception:
        # Ignorar si el permiso ya existe o si la API no lo permite.
        pass

    info = drive_service.files().get(
        fileId=file_id,
        fields='webViewLink, webContentLink',
        supportsAllDrives=True,
        supportsTeamDrives=True,
    ).execute()
    return info.get('webViewLink') or info.get('webContentLink') or f'https://drive.google.com/file/d/{file_id}/view'
