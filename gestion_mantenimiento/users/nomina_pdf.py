"""Generación de PDF de recibos de nómina con ReportLab."""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generar_pdf_recibo(recibo):
    """Genera un PDF profesional del recibo de pago en memoria."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    titulo_style = ParagraphStyle(
        'TituloRecibo',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=6,
    )
    subtitulo_style = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
    )

    story.append(Paragraph('Recibo de Pago', titulo_style))
    story.append(Paragraph(
        f"Período: {recibo.get_tipo_periodo_display()} | "
        f"{recibo.fecha_inicio.strftime('%d/%m/%Y')} - "
        f"{recibo.fecha_fin.strftime('%d/%m/%Y')}",
        subtitulo_style,
    ))
    story.append(Spacer(1, 20))

    info_data = [
        ['Técnico:', recibo.usuario.get_full_name() or recibo.usuario.username],
        ['Usuario:', recibo.usuario.username],
        ['Estado:', recibo.get_estado_display()],
        ['Fecha de emisión:', datetime.now().strftime('%d/%m/%Y %H:%M')],
    ]
    info_table = Table(info_data, colWidths=[1.5 * inch, 4.5 * inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 24))

    horas_data = [
        ['Concepto', 'Valor'],
        ['Días trabajados', str(recibo.dias_trabajados)],
        ['Horas normales', str(recibo.horas_normales)],
        ['Horas extras', str(recibo.horas_extras)],
        ['Horas nocturnas', str(recibo.horas_nocturnas)],
        ['Horas festivas', str(recibo.horas_festivas)],
    ]
    horas_table = Table(horas_data, colWidths=[4 * inch, 2 * inch])
    horas_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(horas_table)
    story.append(Spacer(1, 24))

    montos_data = [
        ['Concepto', 'Monto'],
        ['Bruto', f'${recibo.bruto}'],
        ['Descuentos', f'-${recibo.total_descuentos}'],
        ['NETO A PAGAR', f'${recibo.neto}'],
    ]
    montos_table = Table(montos_data, colWidths=[4 * inch, 2 * inch])
    montos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d1fae5')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 13),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#065f46')),
    ]))
    story.append(montos_table)
    story.append(Spacer(1, 30))

    story.append(Paragraph(
        'Este recibo es un documento informativo generado automáticamente. '
        'Para consultas, contactar al área administrativa.',
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#94a3b8'),
        ),
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generar_nombre_pdf(recibo):
    """Genera un nombre seguro y estable para el archivo adjunto."""
    return (
        f"recibo_{recibo.usuario.username}_"
        f"{recibo.fecha_inicio.strftime('%Y%m%d')}_"
        f"{recibo.fecha_fin.strftime('%Y%m%d')}.pdf"
    )
