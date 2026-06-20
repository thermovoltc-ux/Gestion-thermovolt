"""
Custom Django email backend with fallbacks for production environments
"""

import os
import logging
from django.core.mail.backends.smtp import EmailBackend as BaseEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsoleBackend
from django.conf import settings

logger = logging.getLogger(__name__)


class MultiPortEmailBackend(BaseEmailBackend):
    """
    SMTP backend que intenta múltiples puertos y hosts como fallback
    Útil para entornos con restricciones de red como Railway
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ports_to_try = [587, 465, 25]  # Intentar estos puertos en orden
        self.connection = None

    def open(self):
        """
        Intenta abrir conexión SMTP con múltiples puertos como fallback
        """
        if self.connection is not None:
            return False

        for port in self.ports_to_try:
            try:
                logger.info(f"📡 Intentando conexión SMTP en puerto {port}...")
                self.port = port
                
                # Para puerto 465, usar SSL en lugar de TLS
                if port == 465:
                    self.use_ssl = True
                    self.use_tls = False
                    logger.info(f"   - Usando SSL para puerto {port}")
                else:
                    self.use_ssl = False
                    self.use_tls = True
                    logger.info(f"   - Usando TLS para puerto {port}")
                
                super().open()
                logger.info(f"✅ Conexión SMTP establecida en puerto {port}")
                return True
            except Exception as e:
                logger.warning(f"⚠️  Puerto {port} falló: {type(e).__name__}: {str(e)}")
                self.connection = None
                continue

        # Si todos los puertos fallan, registrar error
        logger.error("❌ No se pudo conectar a SMTP en ningún puerto (587, 465, 25)")
        logger.error("   Railway podría tener restricciones de red saliente")
        return False

    def send_messages(self, email_messages):
        """
        Envía mensajes, con fallback a Console si SMTP falla
        """
        if not email_messages:
            return 0

        msg_count = 0
        try:
            if not self.open():
                logger.error("❌ No se pudo abrir conexión SMTP")
                logger.info("💾 Intentando guardar emails localmente como fallback...")
                # Fallback: Usar ConsoleBackend para guardar en stdout/logs
                console_backend = ConsoleBackend()
                msg_count = console_backend.send_messages(email_messages)
                logger.warning(f"⚠️  {msg_count} emails guardados en logs como fallback")
                return msg_count

            for message in email_messages:
                sent = self._send(message)
                if sent:
                    msg_count += 1
        except Exception as e:
            logger.error(f"❌ Error enviando emails: {e}")
            if not self.fail_silently:
                raise
        finally:
            if self.connection is not None:
                self.close()

        return msg_count


class LocalFileEmailBackend:
    """
    Backend de email que guarda emails en archivos locales
    Útil cuando las conexiones de red están bloqueadas
    """

    def __init__(self, *args, fail_silently=False, **kwargs):
        self.fail_silently = fail_silently

    def open(self):
        return True

    def close(self):
        return True

    def send_messages(self, email_messages):
        msg_count = 0
        email_dir = os.path.join(settings.MEDIA_ROOT, 'email_queue')
        os.makedirs(email_dir, exist_ok=True)

        for message in email_messages:
            try:
                import datetime
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                filename = f"email_{timestamp}_{msg_count}.txt"
                filepath = os.path.join(email_dir, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"To: {', '.join(message.to)}\n")
                    f.write(f"From: {message.from_email}\n")
                    f.write(f"Subject: {message.subject}\n")
                    f.write(f"Date: {datetime.datetime.now()}\n\n")
                    f.write(message.body)

                logger.info(f"📄 Email guardado localmente: {filepath}")
                msg_count += 1
            except Exception as e:
                logger.error(f"Error guardando email: {e}")
                if not self.fail_silently:
                    raise

        return msg_count
