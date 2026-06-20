"""
Custom Django email backends - Legacy support (now using Mailgun)
Kept for reference and potential fallback use
"""

import os
import logging
from django.core.mail.backends.smtp import EmailBackend as BaseEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsoleBackend

logger = logging.getLogger(__name__)


class MultiPortEmailBackend(BaseEmailBackend):
    """
    Legacy SMTP backend with multi-port fallback - DEPRECATED
    
    Now using Mailgun via django-anymail.
    This backend is kept for reference only.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ports_to_try = [587, 465, 25]
        self.connection = None

    def open(self):
        """Attempt SMTP connection with port fallback (minimal logging)"""
        if self.connection is not None:
            return False

        for port in self.ports_to_try:
            try:
                self.port = port
                self.use_ssl = (port == 465)
                self.use_tls = (port != 465)
                
                super().open()
                logger.warning(f"SMTP connected on port {port}")
                return True
            except Exception as e:
                logger.debug(f"Port {port} failed: {str(e)}")
                continue

        logger.error(f"Failed SMTP connection on all ports: {self.ports_to_try}")
        return False

    def close(self):
        """Close SMTP connection"""
        try:
            super().close()
        except Exception:
            pass


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
        from django.conf import settings
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

                logger.info(f"Email guardado localmente: {filepath}")
                msg_count += 1
            except Exception as e:
                logger.error(f"Error guardando email: {e}")
                if not self.fail_silently:
                    raise

        return msg_count

