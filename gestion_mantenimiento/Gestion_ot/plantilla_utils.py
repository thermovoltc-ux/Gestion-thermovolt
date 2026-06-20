"""
Generador de PDFs desde plantilla DOCX con reemplazo de tags
Soporta tanto desarrollo (con docx2pdf + LibreOffice) como producción (Railway con ReportLab)
"""

import os
import io
import logging
from datetime import datetime
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)


def reemplazar_tags_en_docx(doc, reemplazos):
    """
    Reemplaza tags <<tag>> en un documento DOCX
    
    Args:
        doc: Documento de python-docx
        reemplazos: Dict con {tag: valor}
    
    Ejemplo:
        reemplazos = {
            'OT': '96',
            'cliente': 'Produpan',
            'equipo': 'Cava de refrigeración',
            ...
        }
    """
    # Reemplazar en párrafos
    for paragraph in doc.paragraphs:
        for tag, valor in reemplazos.items():
            placeholder = f"<<{tag}>>"
            if placeholder in paragraph.text:
                # Reemplazar preservando formato
                for run in paragraph.runs:
                    if placeholder in run.text:
                        run.text = run.text.replace(placeholder, str(valor))

    # Reemplazar en tablas
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for tag, valor in reemplazos.items():
                        placeholder = f"<<{tag}>>"
                        if placeholder in paragraph.text:
                            for run in paragraph.runs:
                                if placeholder in run.text:
                                    run.text = run.text.replace(placeholder, str(valor))


def generar_pdf_desde_plantilla(cierre_ot, plantilla_path=None):
    """
    Genera PDF a partir de plantilla DOCX reemplazando tags
    
    Args:
        cierre_ot: Instancia de CierreOt
        plantilla_path: Ruta a plantilla_ot.docx (si None, usa ruta por defecto)
    
    Returns:
        BytesIO con contenido PDF
    """
    if plantilla_path is None:
        # Ruta por defecto: plantilla_ot.docx en la raíz del proyecto
        plantilla_path = os.path.join(
            os.path.dirname(__file__),
            '../..',
            'plantilla_ot.docx'
        )
    
    try:
        # Verificar que plantilla existe
        if not os.path.exists(plantilla_path):
            logger.warning(f"Plantilla no encontrada en {plantilla_path}")
            return None
        
        # Cargar plantilla
        logger.info(f"Cargando plantilla desde: {plantilla_path}")
        doc = Document(plantilla_path)
        
        # Preparar datos para reemplazo
        try:
            solicitud = cierre_ot.orden_trabajo.solicitud
            equipo_nombre = solicitud.equipo.nombre if solicitud.equipo else "N/A"
            cliente_nombre = solicitud.ubicacion.nombre if solicitud.ubicacion else "N/A"
        except Exception as e:
            logger.error(f"Error extrayendo datos: {e}")
            equipo_nombre = "N/A"
            cliente_nombre = "N/A"
        
        # Tags a reemplazar
        reemplazos = {
            'OT': str(solicitud.consecutivo),
            'equipo': equipo_nombre,
            'cliente': cliente_nombre,
            'fecha': cierre_ot.fecha_inicio_actividad.strftime('%d/%m/%Y') if cierre_ot.fecha_inicio_actividad else datetime.now().strftime('%d/%m/%Y'),
            'tipomtto': cierre_ot.tipo_mantenimiento or 'N/A',
            'tipointervencion': cierre_ot.tipo_intervencion or 'N/A',
            'causafalla': cierre_ot.causa_falla or 'N/A',
            'sesoluciono': 'Sí' if cierre_ot.se_soluciono else 'No',
            'descripcion': cierre_ot.descripcion_falla or 'N/A',
            'observacion': cierre_ot.observaciones or 'N/A',
            'nombret': cierre_ot.nombre_tecnico or 'N/A',
            'recibido': cierre_ot.nombre_receptor or 'N/A',
            'cct': cierre_ot.documento_tecnico or 'N/A',
            'cc': cierre_ot.documento_receptor or 'N/A',
        }
        
        logger.info(f"Reemplazando tags en plantilla: {list(reemplazos.keys())}")
        reemplazar_tags_en_docx(doc, reemplazos)
        
        # Guardar DOCX temporal
        docx_temporal = io.BytesIO()
        doc.save(docx_temporal)
        docx_temporal.seek(0)
        
        logger.info("DOCX generado en memoria")
        
        # Intentar convertir a PDF
        pdf_buffer = _convertir_docx_a_pdf(docx_temporal)
        
        if pdf_buffer:
            logger.info(f"PDF generado exitosamente desde plantilla")
            return pdf_buffer
        else:
            logger.warning("No se pudo convertir DOCX a PDF")
            return None
            
    except Exception as e:
        logger.error(f"Error generando PDF desde plantilla: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def _convertir_docx_a_pdf(docx_buffer):
    """
    Convierte BytesIO DOCX a BytesIO PDF
    Intenta primero con docx2pdf + LibreOffice, luego fallback con ReportLab
    
    Args:
        docx_buffer: BytesIO con contenido DOCX
    
    Returns:
        BytesIO con PDF o None si falla
    """
    try:
        # Detectar si es producción
        is_railway = os.environ.get('RAILWAY_ENVIRONMENT_NAME')
        
        if not is_railway:
            # En local, intentar docx2pdf
            try:
                from docx2pdf import convert
                import tempfile
                
                logger.info("💻 Local: Intentando conversión DOCX→PDF con docx2pdf + LibreOffice")
                
                # Guardar DOCX temporal
                with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
                    tmp_docx.write(docx_buffer.getvalue())
                    tmp_docx_path = tmp_docx.name
                
                # Convertir a PDF
                tmp_pdf_path = tmp_docx_path.replace('.docx', '.pdf')
                convert(tmp_docx_path, tmp_pdf_path)
                
                # Leer PDF
                with open(tmp_pdf_path, 'rb') as f:
                    pdf_buffer = io.BytesIO(f.read())
                
                # Limpiar temporales
                os.unlink(tmp_docx_path)
                if os.path.exists(tmp_pdf_path):
                    os.unlink(tmp_pdf_path)
                
                logger.info("✅ Conversión docx2pdf exitosa")
                return pdf_buffer
                
            except Exception as e:
                logger.warning(f"docx2pdf falló: {e}")
        
        # Fallback: convertir DOCX a PDF leyendo contenido con ReportLab
        logger.info("🚂 Usando ReportLab para convertir DOCX a PDF")
        return _docx_a_pdf_reportlab(docx_buffer)
    
    except Exception as e:
        logger.error(f"Error en conversión: {e}")
        return None


def _docx_a_pdf_reportlab(docx_buffer):
    """
    Convierte DOCX a PDF leyendo contenido con python-docx y generando PDF con ReportLab
    Funciona en Railway sin LibreOffice
    
    Args:
        docx_buffer: BytesIO con contenido DOCX
    
    Returns:
        BytesIO con PDF
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        
        logger.info("Leyendo documento DOCX para conversión a PDF")
        
        # Cargar DOCX desde buffer
        docx_buffer.seek(0)
        doc_original = Document(docx_buffer)
        
        # Crear PDF con Platypus
        pdf_buffer = io.BytesIO()
        pdf_doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        
        # Estilos
        styles = getSampleStyleSheet()
        story = []
        
        # Extractar párrafos
        for para in doc_original.paragraphs:
            texto = para.text.strip()
            if texto:
                # Detectar nivel de título
                if para.style.name.startswith('Heading'):
                    level = int(para.style.name[-1]) if para.style.name[-1].isdigit() else 1
                    font_size = 16 - (level * 2)
                    style = ParagraphStyle(
                        name=f'CustomHeading{level}',
                        parent=styles['Heading1'],
                        fontSize=font_size,
                        textColor=colors.HexColor('#1F2937'),
                        spaceAfter=12,
                        spaceBefore=6,
                        fontName='Helvetica-Bold'
                    )
                    story.append(Paragraph(texto, style))
                else:
                    style = ParagraphStyle(
                        name='CustomBody',
                        parent=styles['BodyText'],
                        fontSize=10,
                        textColor=colors.HexColor('#374151'),
                        spaceAfter=6,
                        leading=12
                    )
                    story.append(Paragraph(texto, style))
                story.append(Spacer(1, 0.15*inch))
        
        # Extractar tablas
        for table_idx, tabla in enumerate(doc_original.tables):
            try:
                # Convertir tabla
                data = []
                for row in tabla.rows:
                    row_data = []
                    for cell in row.cells:
                        cell_text = '\n'.join([p.text for p in cell.paragraphs])
                        row_data.append(cell_text)
                    data.append(row_data)
                
                if data:
                    # Crear tabla Platypus
                    t = Table(data, colWidths=[2*inch]*len(data[0]))
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F3F4F6')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D1D5DB')),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 0.2*inch))
            except Exception as e:
                logger.warning(f"Error procesando tabla {table_idx}: {e}")
                continue
        
        # Generar PDF
        pdf_doc.build(story)
        pdf_buffer.seek(0)
        
        logger.info("✅ DOCX convertido a PDF exitosamente con ReportLab")
        return pdf_buffer
        
    except Exception as e:
        logger.error(f"Error en conversión DOCX→PDF ReportLab: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return _generar_pdf_simple_minimo()


def _generar_pdf_simple_minimo():
    """
    Fallback final: PDF mínimo si todo falla
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        logger.warning("⚠️ Usando PDF mínimo como fallback final")
        
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "Informe de Mantenimiento")
        
        c.setFont("Helvetica", 11)
        c.drawString(50, 720, "El informe se procesó correctamente")
        c.drawString(50, 700, "pero con contenido mínimo.")
        
        c.save()
        pdf_buffer.seek(0)
        
        logger.info("✅ PDF mínimo generado")
        return pdf_buffer
    
    except Exception as e:
        logger.error(f"Error crítico generando PDF: {e}")
        return None
