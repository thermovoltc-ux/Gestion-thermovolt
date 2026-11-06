from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


EVENTOS_SOLICITUD = {
    'creacion': 'Solicitud creada',
    'asignacion': 'Técnico asignado',
    'informe': 'Informe de mantenimiento disponible',
    'finalizacion': 'Orden de trabajo finalizada',
}


def enviar_correo_solicitud(solicitud, tipo_evento, cuerpo_extra='', destinatarios=None):
    if tipo_evento not in EVENTOS_SOLICITUD:
        raise ValueError(f'Tipo de evento no válido: {tipo_evento}')

    ubicacion = solicitud.ubicacion_nombre or 'Sin ubicación'
    asunto = f'[Solicitud #{solicitud.consecutivo}] - {ubicacion} - CO {solicitud.co or "N/A"}'

    fecha_creacion = solicitud.fecha_creacion
    if fecha_creacion:
        if timezone.is_naive(fecha_creacion):
            fecha_creacion = timezone.make_aware(fecha_creacion)
        fecha_creacion = timezone.localtime(fecha_creacion).strftime('%d/%m/%Y %H:%M')
    else:
        fecha_creacion = 'N/A'

    estado = solicitud.estado.nombre if solicitud.estado else 'N/A'
    equipo = solicitud.equipo.nombre if solicitud.equipo else 'N/A'
    cuerpo = f"""Hola,

Este es un correo automático sobre la Solicitud #{solicitud.consecutivo}.
Evento: {EVENTOS_SOLICITUD[tipo_evento]}

Información de la solicitud:
- Ubicación: {ubicacion}
- Equipo: {equipo}
- CO: {solicitud.co or 'N/A'}
- Estado actual: {estado}
- Fecha de creación: {fecha_creacion}

{cuerpo_extra or ''}

Saludos,
Equipo de Thermovolt
"""

    if not destinatarios:
        destinatarios = [solicitud.email_solicitante] if solicitud.email_solicitante else []
    elif isinstance(destinatarios, str):
        destinatarios = [destinatarios]

    destinatarios = list(dict.fromkeys(
        destinatario.strip()
        for destinatario in destinatarios
        if destinatario and destinatario.strip()
    ))
    if not destinatarios:
        return False

    email = EmailMultiAlternatives(
        subject=asunto,
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )
    if tipo_evento != 'informe':
        contexto = {
            'consecutivo': solicitud.consecutivo,
            'evento': EVENTOS_SOLICITUD[tipo_evento],
            'ubicacion': ubicacion,
            'equipo': equipo,
            'co': solicitud.co or 'N/A',
            'estado': estado,
            'fecha_creacion': fecha_creacion,
            'cuerpo_extra': cuerpo_extra or '',
            'email_contacto': settings.DEFAULT_FROM_EMAIL,
            'telefono_contacto': getattr(settings, 'THERMOVOLT_PHONE', ''),
            'sitio_web': getattr(settings, 'THERMOVOLT_WEBSITE', ''),
        }
        html_content = render_to_string('emails/correo_solicitud.html', contexto)
        email.attach_alternative(html_content, 'text/html')

        logo_path = finders.find('images/thermovolt-logo.png')
        if not logo_path:
            raise FileNotFoundError('No se encontró el logo de Thermovolt en los archivos estáticos.')
        with open(logo_path, 'rb') as logo_file:
            logo = MIMEImage(logo_file.read(), _subtype='png')
        logo.add_header('Content-ID', '<thermovolt-logo>')
        logo.add_header('Content-Disposition', 'inline', filename='thermovolt-logo.png')
        email.attach(logo)

    return bool(email.send(fail_silently=False))
