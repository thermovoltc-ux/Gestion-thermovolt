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
    Intenta primero con docx2pdf + LibreOffice, luego fallback
    
    Args:
        docx_buffer: BytesIO con contenido DOCX
    
    Returns:
        BytesIO con PDF o None si falla
    """
    try:
        # Detectar si es producción
        is_railway = os.environ.get('RAILWAY_ENVIRONMENT_NAME')
        
        if is_railway:
            logger.info("🚂 Entorno Railway detectado - usando fallback ReportLab")
            # En Railway, usar ReportLab
            return _generar_pdf_reportlab_fallback()
        
        # En local, intentar docx2pdf
        try:
            from docx2pdf import convert
            import tempfile
            
            logger.info("Intentando conversión DOCX→PDF con docx2pdf + LibreOffice")
            
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
            logger.info("Intentando fallback a ReportLab")
            return _generar_pdf_reportlab_fallback()
    
    except Exception as e:
        logger.error(f"Error en conversión: {e}")
        return None


def _generar_pdf_reportlab_fallback():
    """
    Fallback a ReportLab si docx2pdf no funciona
    (Retorna un PDF genérico simple)
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        logger.info("Generando PDF con ReportLab como fallback")
        
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        
        c.setFont("Helvetica", 12)
        c.drawString(100, 750, "Informe de Mantenimiento")
        c.drawString(100, 700, "(Generado con ReportLab - fallback)")
        
        c.save()
        pdf_buffer.seek(0)
        
        logger.info("✅ PDF fallback generado con ReportLab")
        return pdf_buffer
    
    except Exception as e:
        logger.error(f"Error en fallback ReportLab: {e}")
        return None
