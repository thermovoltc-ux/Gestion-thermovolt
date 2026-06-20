"""
Generador de PDFs SIMPLE y DIRECTO desde plantilla DOCX
- Reemplaza tags simples
- Inserta firmas en el lugar correcto (debajo del documento)
- Inserta imágenes al final (ANTES y DESPUÉS)
- Convierte a PDF sin complicaciones
"""

import os
import io
import logging
import requests
import tempfile
import platform
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)


def _obtener_imagen_temporal(file_field_o_url):
    """
    Obtiene ruta temporal de una imagen desde FileField, URL o data URL
    Returns: (ruta_temporal, es_temporal) o (None, False) si falla
    """
    if not file_field_o_url:
        return None, False
    
    try:
        # URL remota (Cloudinary)
        if isinstance(file_field_o_url, str) and file_field_o_url.startswith('http'):
            response = requests.get(file_field_o_url, timeout=15)
            response.raise_for_status()
            suffix = '.png' if 'png' in file_field_o_url.lower() else '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                return tmp.name, True
        
        # FileField de Django
        elif hasattr(file_field_o_url, 'url'):
            url = file_field_o_url.url
            if url and url.startswith('http'):
                return _obtener_imagen_temporal(url)  # Recursivo
        
        # Path local
        if hasattr(file_field_o_url, 'path'):
            local_path = file_field_o_url.path
            if local_path and os.path.exists(local_path):
                return local_path, False
    
    except Exception as e:
        logger.warning(f"Error obteniendo imagen: {e}")
    
    return None, False


def reemplazar_tags_en_docx(doc, reemplazos):
    """
    Reemplaza tags {{clave}} en todo el documento DOCX
    
    Args:
        doc: Documento de python-docx
        reemplazos: Dict {tag: valor}
    """
    for para in doc.paragraphs:
        for tag, valor in reemplazos.items():
            if f"<<{tag}>>" in para.text:
                para.text = para.text.replace(f"<<{tag}>>", str(valor))
    
    # También en tablas
    for tabla in doc.tables:
        for row in tabla.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for tag, valor in reemplazos.items():
                        if f"<<{tag}>>" in para.text:
                            para.text = para.text.replace(f"<<{tag}>>", str(valor))


def _insertar_firma_en_docx(doc, cierre_ot):
    """
    Inserta las firmas DEBAJO de los documentos en la sección "Confirmación de trabajo recibido"
    Las imágenes de firma van directamente debajo del texto "Documento de identidad: XXX"
    """
    if not cierre_ot.firma_digital and not cierre_ot.firma_receptor:
        logger.info("⚠️ No hay firmas para agregar")
        return
    
    try:
        # Buscar el párrafo "Confirmación de trabajo recibido:"
        confirmacion_encontrada = False
        para_confirmacion_idx = None
        
        for idx, para in enumerate(doc.paragraphs):
            if "Confirmación de trabajo recibido" in para.text:
                confirmacion_encontrada = True
                para_confirmacion_idx = idx
                logger.info(f"✅ Encontrado 'Confirmación de trabajo recibido' en párrafo {idx}")
                break
        
        if not confirmacion_encontrada:
            logger.warning("⚠️ No se encontró 'Confirmación de trabajo recibido' en documento")
            return
        
        # Buscar la tabla de firmas (suele ser la última tabla o después de "Confirmación")
        tabla_encontrada = False
        tabla_idx = None
        
        for idx, tabla in enumerate(doc.tables):
            # Buscar tabla que contenga "Realiz" o "Recibido"
            for row in tabla.rows:
                for cell in row.cells:
                    texto_celda = '\n'.join([p.text for p in cell.paragraphs])
                    if ('Realiz' in texto_celda or 'Recibido' in texto_celda) and 'Documento' in texto_celda:
                        tabla_encontrada = True
                        tabla_idx = idx
                        logger.info(f"✅ Encontrada tabla de firmas (tabla {idx})")
                        break
                if tabla_encontrada:
                    break
        
        if not tabla_encontrada:
            logger.warning("⚠️ No se encontró tabla de firmas")
            return
        
        # Agregar firmas debajo de la tabla
        # Insertamos párrafos después de la tabla con las imágenes
        tabla = doc.tables[tabla_idx]
        
        # Agregar espacio
        p_espacio = doc.add_paragraph()
        p_espacio.text = ""
        
        # Agregar firma técnico si existe
        if cierre_ot.firma_digital:
            tmp_path, es_temp = _obtener_imagen_temporal(cierre_ot.firma_digital)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    p_firma_tec = doc.add_paragraph()
                    p_firma_tec.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    run = p_firma_tec.add_run()
                    run.add_picture(tmp_path, width=Inches(1.5))
                    logger.info("✅ Firma técnico agregada")
                except Exception as e:
                    logger.warning(f"Error agregando firma técnico: {e}")
        
        # Agregar firma receptor si existe
        if cierre_ot.firma_receptor:
            tmp_path, es_temp = _obtener_imagen_temporal(cierre_ot.firma_receptor)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    p_firma_rec = doc.add_paragraph()
                    p_firma_rec.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                    run = p_firma_rec.add_run()
                    run.add_picture(tmp_path, width=Inches(1.5))
                    logger.info("✅ Firma receptor agregada")
                except Exception as e:
                    logger.warning(f"Error agregando firma receptor: {e}")
    
    except Exception as e:
        logger.warning(f"Error en _insertar_firma_en_docx: {e}")


def _agregar_imagenes_al_final(doc, cierre_ot):
    """
    Agrega imágenes ANTES y DESPUÉS al final del documento
    """
    if not cierre_ot:
        return
    
    try:
        imagenes_antes = cierre_ot.imagenes.filter(tipo='antes')
        imagenes_despues = cierre_ot.imagenes.filter(tipo='despues')
        
        if not imagenes_antes.exists() and not imagenes_despues.exists():
            logger.info("ℹ️ No hay imágenes ANTES/DESPUÉS")
            return
        
        # Agregar salto de página
        doc.add_page_break()
        
        # Sección ANTES
        if imagenes_antes.exists():
            p_antes = doc.add_paragraph()
            p_antes.text = "─ ANTES ─"
            p_antes.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            p_antes.runs[0].bold = True
            
            doc.add_paragraph()  # Espacio
            
            for img in imagenes_antes:
                try:
                    img_path, es_temp = _obtener_imagen_temporal(img.imagen)
                    if img_path and os.path.exists(img_path):
                        p_img = doc.add_paragraph()
                        run = p_img.add_run()
                        run.add_picture(img_path, width=Inches(5))
                        logger.info("✅ Imagen ANTES agregada")
                except Exception as e:
                    logger.warning(f"Error imagen ANTES: {e}")
        
        # Espacio entre secciones
        if imagenes_antes.exists() and imagenes_despues.exists():
            doc.add_paragraph()
        
        # Sección DESPUÉS
        if imagenes_despues.exists():
            p_despues = doc.add_paragraph()
            p_despues.text = "─ DESPUÉS ─"
            p_despues.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            p_despues.runs[0].bold = True
            
            doc.add_paragraph()  # Espacio
            
            for img in imagenes_despues:
                try:
                    img_path, es_temp = _obtener_imagen_temporal(img.imagen)
                    if img_path and os.path.exists(img_path):
                        p_img = doc.add_paragraph()
                        run = p_img.add_run()
                        run.add_picture(img_path, width=Inches(5))
                        logger.info("✅ Imagen DESPUÉS agregada")
                except Exception as e:
                    logger.warning(f"Error imagen DESPUÉS: {e}")
        
        logger.info("✅ Imágenes agregadas al final")
    
    except Exception as e:
        logger.warning(f"Error agregando imágenes: {e}")


def generar_pdf_desde_plantilla(cierre_ot, plantilla_path=None):
    """
    Genera PDF SIMPLE desde plantilla DOCX
    
    1. Carga plantilla
    2. Reemplaza tags
    3. Inserta firmas
    4. Inserta imágenes
    5. Convierte a PDF
    """
    if plantilla_path is None:
        plantilla_path = os.path.join(
            os.path.dirname(__file__),
            '../..',
            'plantilla_ot.docx'
        )
    
    try:
        if not os.path.exists(plantilla_path):
            logger.warning(f"⚠️ Plantilla no encontrada en {plantilla_path}")
            return None
        
        logger.info(f"📄 Cargando plantilla: {plantilla_path}")
        doc = Document(plantilla_path)
        
        # Preparar datos para reemplazo
        try:
            solicitud = cierre_ot.orden_trabajo.solicitud
            equipo_nombre = solicitud.equipo.nombre if solicitud.equipo else "N/A"
            cliente_nombre = solicitud.ubicacion.nombre if solicitud.ubicacion else solicitud.PDV or "N/A"
            fecha_formato = cierre_ot.fecha_inicio_actividad.strftime('%d/%m/%Y') if cierre_ot.fecha_inicio_actividad else datetime.now().strftime('%d/%m/%Y')
        except Exception as e:
            logger.error(f"Error extrayendo datos: {e}")
            equipo_nombre = "N/A"
            cliente_nombre = "N/A"
            fecha_formato = datetime.now().strftime('%d/%m/%Y')
        
        # Reemplazos simples
        reemplazos = {
            'OT': str(solicitud.consecutivo) if solicitud else '',
            'equipo': equipo_nombre,
            'cliente': cliente_nombre,
            'fecha': fecha_formato,
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
        
        logger.info(f"🔍 Reemplazando {len(reemplazos)} tags")
        reemplazar_tags_en_docx(doc, reemplazos)
        
        # Insertar firmas
        try:
            _insertar_firma_en_docx(doc, cierre_ot)
        except Exception as e:
            logger.warning(f"⚠️ Error con firmas: {e}")
        
        # Agregar imágenes
        try:
            _agregar_imagenes_al_final(doc, cierre_ot)
        except Exception as e:
            logger.warning(f"⚠️ Error con imágenes: {e}")
        
        # Guardar DOCX temporal en memoria
        docx_temporal = io.BytesIO()
        doc.save(docx_temporal)
        docx_temporal.seek(0)
        
        logger.info("📝 DOCX generado exitosamente")
        
        # Convertir a PDF
        pdf_buffer = _convertir_docx_a_pdf(docx_temporal)
        
        if pdf_buffer:
            logger.info("✅ PDF generado exitosamente")
            return pdf_buffer
        else:
            logger.warning("⚠️ No se pudo convertir a PDF")
            return None
    
    except Exception as e:
        logger.error(f"❌ Error generando PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def _convertir_docx_a_pdf(docx_buffer):
    """
    Convierte DOCX a PDF
    - En Windows: docx2pdf (mejor calidad)
    - En Linux/Railway: ReportLab (funciona sin Microsoft Word)
    """
    try:
        sistema = platform.system()
        logger.info(f"🖥️ Sistema detectado: {sistema}")
        
        # En Windows, intentar docx2pdf primero
        if sistema == 'Windows':
            try:
                from docx2pdf import convert
                
                with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
                    tmp_docx.write(docx_buffer.getvalue())
                    tmp_docx_path = tmp_docx.name
                
                tmp_pdf_path = tmp_docx_path.replace('.docx', '.pdf')
                convert(tmp_docx_path, tmp_pdf_path)
                
                with open(tmp_pdf_path, 'rb') as f:
                    pdf_buffer = io.BytesIO(f.read())
                
                os.unlink(tmp_docx_path)
                if os.path.exists(tmp_pdf_path):
                    os.unlink(tmp_pdf_path)
                
                logger.info("✅ Conversión docx2pdf exitosa (Windows)")
                return pdf_buffer
            
            except Exception as e:
                logger.warning(f"docx2pdf falló, usando ReportLab: {e}")
        
        # En Linux o si docx2pdf falla: ReportLab
        logger.info("🚂 Usando ReportLab (compatible con Railway/Linux)")
        return _docx_a_pdf_reportlab(docx_buffer)
    
    except Exception as e:
        logger.error(f"Error en conversión: {e}")
        return None


def _docx_a_pdf_reportlab(docx_buffer):
    """
    Convierte DOCX a PDF usando ReportLab
    Funciona en Railway sin Microsoft Word
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib import colors
        
        logger.info("📋 Convirtiendo DOCX a PDF con ReportLab")
        
        docx_buffer.seek(0)
        doc_original = Document(docx_buffer)
        
        # PDF con Platypus
        pdf_buffer = io.BytesIO()
        pdf_doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        # Estilos
        body_style = ParagraphStyle(
            name='CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            leading=12
        )
        
        # Agregar contenido del DOCX
        for para in doc_original.paragraphs:
            texto = para.text.strip()
            if texto:
                story.append(Paragraph(texto, body_style))
                story.append(Spacer(1, 0.1*inch))
        
        # Agregar tablas
        from reportlab.platypus import Table, TableStyle
        for tabla in doc_original.tables:
            try:
                data = []
                for row in tabla.rows:
                    row_data = []
                    for cell in row.cells:
                        cell_text = '\n'.join([p.text for p in cell.paragraphs if p.text.strip()])
                        row_data.append(cell_text or '')
                    data.append(row_data)
                
                if data:
                    col_count = max(len(row) for row in data)
                    col_widths = [7.5*inch / col_count] * col_count
                    
                    t = Table(data, colWidths=col_widths)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 0.15*inch))
            except Exception as e:
                logger.warning(f"Error procesando tabla: {e}")
        
        # Generar PDF
        pdf_doc.build(story)
        pdf_buffer.seek(0)
        
        logger.info("✅ PDF generado con ReportLab")
        return pdf_buffer
    
    except Exception as e:
        logger.error(f"Error ReportLab: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
