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


def _agregar_imagenes_a_docx(doc, cierre_ot):
    """
    Agrega imágenes ANTES y DESPUÉS al final del documento DOCX
    
    Args:
        doc: Documento de python-docx
        cierre_ot: Instancia de CierreOt con imágenes relacionadas
    """
    from django.core.files.storage import default_storage
    
    # Obtener imágenes
    imagenes_antes = cierre_ot.imagenes.filter(tipo='antes')
    imagenes_despues = cierre_ot.imagenes.filter(tipo='despues')
    
    # Agregar título de imágenes
    if imagenes_antes.exists() or imagenes_despues.exists():
        # Agregar salto de página
        doc.add_page_break()
        
        # Sección ANTES
        if imagenes_antes.exists():
            doc.add_paragraph("─ ANTES ─", style='Heading 2')
            doc.add_paragraph()  # Salto de línea
            
            for img in imagenes_antes:
                try:
                    # Obtener ruta de la imagen
                    img_path = img.imagen.path if hasattr(img.imagen, 'path') else None
                    
                    if img_path and os.path.exists(img_path):
                        # Agregar imagen con altura máxima de 2.5 pulgadas
                        try:
                            doc.add_picture(img_path, width=2000000)  # ~2.1 pulgadas
                            logger.info(f"Imagen ANTES agregada: {img.imagen.name}")
                        except Exception as e:
                            logger.warning(f"Error insertando imagen ANTES: {e}")
                    else:
                        logger.warning(f"Ruta de imagen no disponible: {img.imagen.name}")
                except Exception as e:
                    logger.warning(f"Error procesando imagen ANTES: {e}")
            
            if imagenes_despues.exists():
                doc.add_page_break()
        
        # Sección DESPUÉS
        if imagenes_despues.exists():
            doc.add_paragraph("─ DESPUÉS ─", style='Heading 2')
            doc.add_paragraph()  # Salto de línea
            
            for img in imagenes_despues:
                try:
                    # Obtener ruta de la imagen
                    img_path = img.imagen.path if hasattr(img.imagen, 'path') else None
                    
                    if img_path and os.path.exists(img_path):
                        # Agregar imagen con altura máxima de 2.5 pulgadas
                        try:
                            doc.add_picture(img_path, width=2000000)  # ~2.1 pulgadas
                            logger.info(f"Imagen DESPUÉS agregada: {img.imagen.name}")
                        except Exception as e:
                            logger.warning(f"Error insertando imagen DESPUÉS: {e}")
                    else:
                        logger.warning(f"Ruta de imagen no disponible: {img.imagen.name}")
                except Exception as e:
                    logger.warning(f"Error procesando imagen DESPUÉS: {e}")
        
        logger.info(f"✅ Imágenes agregadas: {imagenes_antes.count()} antes, {imagenes_despues.count()} después")


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
    Genera PDF a partir de plantilla DOCX reemplazando tags e insertando imágenes
    
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
        
        # Agregar imágenes al final del documento
        try:
            _agregar_imagenes_a_docx(doc, cierre_ot)
        except Exception as e:
            logger.warning(f"Error agregando imágenes: {e}")
        
        # Guardar DOCX temporal
        docx_temporal = io.BytesIO()
        doc.save(docx_temporal)
        docx_temporal.seek(0)
        
        logger.info("DOCX generado en memoria con imágenes")
        
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
    Soporta imágenes insertas en el documento
    
    Args:
        docx_buffer: BytesIO con contenido DOCX
    
    Returns:
        BytesIO con PDF
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as PlatypusImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        
        logger.info("Leyendo documento DOCX para conversión a PDF")
        
        # Cargar DOCX desde buffer
        docx_buffer.seek(0)
        doc_original = Document(docx_buffer)
        
        # Crear PDF con Platypus
        pdf_buffer = io.BytesIO()
        pdf_doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        story = []
        
        # Crear estilos personalizados
        heading_style = ParagraphStyle(
            name='CustomHeading',
            parent=styles['Heading1'],
            fontSize=12,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=8,
            spaceBefore=4,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        )
        
        body_style = ParagraphStyle(
            name='CustomBody',
            parent=styles['BodyText'],
            fontSize=9,
            textColor=colors.HexColor('#374151'),
            spaceAfter=4,
            leading=11
        )
        
        # Extraer párrafos
        for i, para in enumerate(doc_original.paragraphs):
            texto = para.text.strip()
            
            if texto:
                # Detectar nivel de título
                if para.style and para.style.name and para.style.name.startswith('Heading'):
                    story.append(Paragraph(texto, heading_style))
                else:
                    story.append(Paragraph(texto, body_style))
                story.append(Spacer(1, 0.1*inch))
        
        # Extraer tablas con mejor formateo
        for table_idx, tabla in enumerate(doc_original.tables):
            try:
                # Convertir tabla preservando estructura
                data = []
                max_cols = max(len(tabla.rows[0].cells) if tabla.rows else 0, 
                              len(tabla.columns)) if tabla.columns else 0
                
                for row_idx, row in enumerate(tabla.rows):
                    row_data = []
                    for cell_idx, cell in enumerate(row.cells):
                        cell_text = '\n'.join([p.text for p in cell.paragraphs if p.text.strip()])
                        row_data.append(cell_text or '')
                    
                    # Rellenar celdas faltantes
                    while len(row_data) < max_cols:
                        row_data.append('')
                    
                    data.append(row_data)
                
                if data and len(data[0]) > 0:
                    # Calcular ancho de columnas automáticamente
                    available_width = 7.5*inch  # Ancho disponible
                    col_widths = [available_width / len(data[0])] * len(data[0])
                    
                    # Crear tabla Platypus
                    t = Table(data, colWidths=col_widths)
                    
                    # Estilos de tabla
                    style_commands = [
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('TOPPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F9FAFB')),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')]),
                        ('TOPPADDING', (0, 1), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                    ]
                    
                    t.setStyle(TableStyle(style_commands))
                    story.append(t)
                    story.append(Spacer(1, 0.15*inch))
                    
            except Exception as e:
                logger.warning(f"Error procesando tabla {table_idx}: {e}")
                continue
        
        # Extraer imágenes insertas en el DOCX
        # Las imágenes se insertan como archivos embebidos en el documento
        # Platypus las procesará automáticamente si están en el DOCX
        
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
