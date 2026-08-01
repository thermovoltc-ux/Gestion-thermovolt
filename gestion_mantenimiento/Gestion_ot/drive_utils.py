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
    if not service_account_json:
        raise RuntimeError('La variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON no está configurada.')

    try:
        credentials_info = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON no contiene JSON válido.') from exc

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )

    drive_service = build('drive', 'v3', credentials=credentials)
    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    file_stream = BytesIO(pdf_bytes)
    media = MediaIoBaseUpload(file_stream, mimetype='application/pdf', resumable=True)

    created_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,webViewLink,webContentLink'
    ).execute()

    file_id = created_file.get('id')
    if not file_id:
        raise RuntimeError('No se pudo obtener el ID del archivo subido a Drive.')

    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
    except Exception:
        # Ignorar si el permiso ya existe o si la API no lo permite.
        pass

    info = drive_service.files().get(fileId=file_id, fields='webViewLink, webContentLink').execute()
    return info.get('webViewLink') or info.get('webContentLink') or f'https://drive.google.com/file/d/{file_id}/view'
