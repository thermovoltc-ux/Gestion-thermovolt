"""Generación de PDF de recibos de nómina con ReportLab."""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ETIQUETAS_DESCUENTO = {
    'prestamo': 'Préstamo',
    'adelanto': 'Adelanto',
    'fiscal': 'Retención fiscal',
    'seguridad_social': 'Seguridad social',
    'otro': 'Otro',
}


def _decimal(valor):
    return Decimal(str(valor or 0))


def _formatear_pesos(valor):
    monto_entero = _decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return f"$ {format(monto_entero, ',.0f').replace(',', '.')}"


def _formatear_cantidad(valor):
    return f'{_decimal(valor):.2f}'


def _filas_detalle_pago(recibo):
    detalles = recibo.detalles or {}
    config = detalles.get('config') or {}
    tipo_pago = config.get('tipo_pago')
    monto_base = _decimal(detalles.get('monto_base'))
    filas = [['Concepto', 'Cantidad', 'Valor unitario', 'Subtotal']]

    if tipo_pago == 'por_dia':
        valor_dia = _decimal(config.get('valor_dia'))
        filas.append([
            'Pago por días trabajados',
            str(recibo.dias_trabajados),
            _formatear_pesos(valor_dia),
            _formatear_pesos(monto_base),
        ])
    elif tipo_pago == 'salario_fijo':
        dias_periodo = Decimal((recibo.fecha_fin - recibo.fecha_inicio).days + 1)
        valor_dia = monto_base / dias_periodo if dias_periodo else Decimal('0')
        filas.append([
            'Salario base prorrateado',
            str(int(dias_periodo)),
            _formatear_pesos(valor_dia),
            _formatear_pesos(monto_base),
        ])
    else:
        filas.append([
            'Horas normales',
            _formatear_cantidad(recibo.horas_normales),
            _formatear_pesos(config.get('valor_hora_normal')),
            _formatear_pesos(monto_base),
        ])

    monto_extras = _decimal(detalles.get('monto_extras'))
    if recibo.horas_extras or monto_extras:
        filas.append([
            'Horas extras',
            _formatear_cantidad(recibo.horas_extras),
            _formatear_pesos(config.get('valor_hora_extra')),
            _formatear_pesos(monto_extras),
        ])

    for concepto, clave_monto, horas in (
        ('Recargo nocturno', 'monto_recargo_nocturno', recibo.horas_nocturnas),
        ('Recargo festivo', 'monto_recargo_festivo', recibo.horas_festivas),
    ):
        monto = _decimal(detalles.get(clave_monto))
        if monto:
            valor_unitario = monto / _decimal(horas) if horas else Decimal('0')
            filas.append([
                concepto,
                _formatear_cantidad(horas),
                _formatear_pesos(valor_unitario),
                _formatear_pesos(monto),
            ])

    filas.append(['TOTAL BRUTO', '', '', _formatear_pesos(recibo.bruto)])
    return filas


def _filas_descuento(recibo):
    detalles = recibo.detalles or {}
    descuentos = detalles.get('descuentos') or []
    filas = []
    for descuento in descuentos:
        tipo = ETIQUETAS_DESCUENTO.get(
            descuento.get('tipo'),
            (descuento.get('tipo') or 'Descuento').replace('_', ' ').capitalize(),
        )
        descripcion = descuento.get('descripcion', '').strip()
        concepto = tipo
        if descripcion:
            concepto = f'{tipo}: {descripcion}'
        filas.append((concepto, f"-{_formatear_pesos(descuento.get('monto'))}"))

    if not filas and _decimal(recibo.total_descuentos):
        filas.append(('Descuentos aplicados', f"-{_formatear_pesos(recibo.total_descuentos)}"))
    return filas


def generar_pdf_recibo(recibo):
    """Genera un PDF profesional del recibo de pago en memoria."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
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
    story.append(Spacer(1, 12))

    info_data = [
        ['Técnico:', recibo.usuario.get_full_name() or recibo.usuario.username],
        ['Usuario:', recibo.usuario.username],
        ['Estado:', recibo.get_estado_display()],
        ['Fecha de emisión:', datetime.now().strftime('%d/%m/%Y %H:%M')],
    ]
    info_table = Table(info_data, colWidths=[1.5 * inch, 5.5 * inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    horas_data = [
        ['Días trabajados', str(recibo.dias_trabajados),
         'Horas normales', _formatear_cantidad(recibo.horas_normales)],
        ['Horas extras', _formatear_cantidad(recibo.horas_extras),
         'Horas nocturnas', _formatear_cantidad(recibo.horas_nocturnas)],
        ['Horas festivas', _formatear_cantidad(recibo.horas_festivas), '', ''],
    ]
    horas_table = Table(
        horas_data,
        colWidths=[1.5 * inch, 1 * inch, 1.5 * inch, 1 * inch],
    )
    horas_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#334155')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(horas_table)
    story.append(Spacer(1, 12))

    detalle_data = _filas_detalle_pago(recibo)
    detalle_table = Table(
        detalle_data,
        colWidths=[2.5 * inch, 1 * inch, 1.5 * inch, 2 * inch],
        repeatRows=1,
    )
    detalle_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
    ]))
    story.append(detalle_table)
    story.append(Spacer(1, 8))

    descuentos = _filas_descuento(recibo)
    if descuentos:
        story.append(Paragraph(
            'Descuentos aplicados',
            ParagraphStyle(
                'TituloDescuentos',
                parent=styles['Heading3'],
                fontSize=10,
                textColor=colors.HexColor('#1e293b'),
                spaceAfter=4,
            ),
        ))
        descuento_style = ParagraphStyle(
            'DetalleDescuento',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
        )
        descuentos_data = [
            [Paragraph(escape(concepto), descuento_style), monto]
            for concepto, monto in descuentos
        ]
        descuentos_table = Table(
            descuentos_data,
            colWidths=[5.5 * inch, 1.5 * inch],
        )
        descuentos_table.setStyle(TableStyle([
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#dc3545')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(descuentos_table)
        story.append(Spacer(1, 6))

    resumen_data = [
        ['Total descuentos', f"-{_formatear_pesos(recibo.total_descuentos)}"],
        ['NETO A PAGAR', _formatear_pesos(recibo.neto)],
    ]
    resumen_table = Table(resumen_data, colWidths=[5 * inch, 2 * inch])
    resumen_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d1fae5')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#065f46')),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
    ]))
    story.append(resumen_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        'Este recibo es un documento informativo generado automáticamente. '
        'Para consultas, contactar al área administrativa.',
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
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
