import mimetypes
import re
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.core.files.storage import Storage, default_storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from googleapiclient.errors import HttpError


@deconstructible
class GoogleDriveMediaStorage(Storage):
    drive_prefix = 'drive/'

    def _drive_enabled(self):
        if settings.GOOGLE_DRIVE_MEDIA_ENABLED:
            return True
        if getattr(settings, 'RAILWAY_ENVIRONMENT', ''):
            raise ImproperlyConfigured(
                'Google Drive media storage requiere credenciales de servicio y '
                'GOOGLE_DRIVE_MEDIA_FOLDER_ID en Railway.'
            )
        return False

    def _drive_id(self, name):
        normalized = str(name).replace('\\', '/')
        if not normalized.startswith(self.drive_prefix):
            return None
        parts = normalized.split('/', 2)
        if len(parts) < 3 or not parts[1]:
            return None
        return parts[1]

    def _save(self, name, content):
        if not self._drive_enabled():
            return default_storage.save(name, content)

        from .drive_utils import subir_archivo_privado_a_drive

        filename = PurePosixPath(str(name).replace('\\', '/')).name
        mime_type = (
            getattr(content, 'content_type', None)
            or mimetypes.guess_type(filename)[0]
            or 'application/octet-stream'
        )
        metadata = subir_archivo_privado_a_drive(
            content,
            filename,
            mime_type,
            folder_id=settings.GOOGLE_DRIVE_MEDIA_FOLDER_ID,
        )
        suffix = PurePosixPath(filename).suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,10}', suffix):
            suffix = ''
        storage_filename = f'file{suffix}'
        return f'{self.drive_prefix}{metadata["drive_file_id"]}/{storage_filename}'

    def _open(self, name, mode='rb'):
        drive_id = self._drive_id(name)
        if not drive_id:
            return default_storage.open(name, mode)
        if mode not in ('rb', 'r'):
            raise ValueError('Google Drive media storage solo permite abrir archivos en lectura.')

        from .drive_utils import descargar_archivo_privado_drive

        file_handle = descargar_archivo_privado_drive(drive_id)
        return File(file_handle, name=PurePosixPath(str(name).replace('\\', '/')).name)

    def delete(self, name):
        drive_id = self._drive_id(name)
        if not drive_id:
            return default_storage.delete(name)

        from .drive_utils import crear_drive_service

        crear_drive_service().files().delete(
            fileId=drive_id,
            supportsAllDrives=True,
        ).execute()

    def exists(self, name):
        drive_id = self._drive_id(name)
        if not drive_id:
            return default_storage.exists(name)

        from .drive_utils import crear_drive_service

        try:
            crear_drive_service().files().get(
                fileId=drive_id,
                fields='id',
                supportsAllDrives=True,
            ).execute()
            return True
        except HttpError as exc:
            if exc.resp.status == 404:
                return False
            raise

    def size(self, name):
        drive_id = self._drive_id(name)
        if not drive_id:
            return default_storage.size(name)

        from .drive_utils import crear_drive_service

        metadata = crear_drive_service().files().get(
            fileId=drive_id,
            fields='size',
            supportsAllDrives=True,
        ).execute()
        return int(metadata['size'])

    def url(self, name):
        drive_id = self._drive_id(name)
        if not drive_id:
            return default_storage.url(name)
        return reverse('drive_media', kwargs={'file_id': drive_id})

    def path(self, name):
        if self._drive_id(name):
            raise NotImplementedError('Los archivos de Google Drive no tienen ruta local.')
        return default_storage.path(name)
