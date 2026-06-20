"""
Generador de PDFs CON REPORTLAB DIRECTO - Control 100% del layout
- Genera PDF completamente con ReportLab (sin DOCX)
- Logo, tablas, firmas, imágenes en el orden CORRECTO
- Funciona en Windows y Linux/Railway
"""

import os
import io
import logging
import requests
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image as PlatypusImage
)

logger = logging.getLogger(__name__)


def _obtener_imagen_temporal(file_field_o_url):
    """
    Obtiene ruta temporal de una imagen desde FileField, URL o data URL
    """
    if not file_field_o_url:
        return None, False
    
    try:
        if isinstance(file_field_o_url, str) and file_field_o_url.startswith('http'):
            response = requests.get(file_field_o_url, timeout=15)
            response.raise_for_status()
            suffix = '.png' if 'png' in file_field_o_url.lower() else '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                return tmp.name, True
        
        elif hasattr(file_field_o_url, 'url'):
            url = file_field_o_url.url
            if url and url.startswith('http'):
                return _obtener_imagen_temporal(url)
        
        if hasattr(file_field_o_url, 'path'):
            local_path = file_field_o_url.path
            if local_path and os.path.exists(local_path):
                return local_path, False
    
    except Exception as e:
        logger.warning(f"Error obteniendo imagen: {e}")
    
    return None, False


def _obtener_logo():
    """
    Obtiene la ruta del logo THERMOVOLT
    """
    rutas_posibles = [
        os.path.join(os.path.dirname(__file__), '../../static/images/Logoinforme.jpg'),
        os.path.join(os.path.dirname(__file__), '../static/images/Logoinforme.jpg'),
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../static/images/Logoinforme.jpg')),
    ]
    
    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            logger.info(f"✅ Logo encontrado: {ruta}")
            return ruta
    
    logger.warning("⚠️ Logo no encontrado")
    return None


def generar_pdf_desde_plantilla(cierre_ot, plantilla_path=None):
    """
    Genera PDF COMPLETAMENTE con ReportLab
    Orden correcto: Logo, Servicio N°, Tablas, Descripción, Firmas, Imágenes
    """
    try:
        # Preparar datos
        try:
            solicitud = cierre_ot.orden_trabajo.solicitud
            numero_ot = str(solicitud.consecutivo) if solicitud else 'N/A'
            equipo_nombre = solicitud.equipo.nombre if solicitud.equipo else "N/A"
            cliente_nombre = solicitud.ubicacion.nombre if solicitud.ubicacion else solicitud.PDV or "N/A"
            fecha_formato = cierre_ot.fecha_inicio_actividad.strftime('%d/%m/%Y') if cierre_ot.fecha_inicio_actividad else datetime.now().strftime('%d/%m/%Y')
        except Exception as e:
            logger.error(f"Error extrayendo datos: {e}")
            numero_ot = 'N/A'
            equipo_nombre = "N/A"
            cliente_nombre = "N/A"
            fecha_formato = datetime.now().strftime('%d/%m/%Y')
        
        # Crear PDF
        logger.info("📋 Generando PDF con ReportLab")
        pdf_buffer = io.BytesIO()
        pdf_doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.3*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Estilos personalizados
        title_style = ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            name='CustomHeading',
            parent=styles['Heading2'],
            fontSize=10,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=4,
            spaceBefore=4,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            name='CustomBody',
            parent=styles['BodyText'],
            fontSize=9,
            leading=11
        )
        
        # ==================== ENCABEZADO ====================
        
        # Logo
        logo_path = _obtener_logo()
        if logo_path:
            try:
                logo = PlatypusImage(logo_path, width=2.2*inch, height=0.8*inch)
                story.append(logo)
                logger.info("✅ Logo agregado al PDF")
            except Exception as e:
                logger.warning(f"Error agregando logo: {e}")
        
        # Servicio N°
        p_servicio = Paragraph(f"<b>Servicio Nº {numero_ot}</b>", title_style)
        story.append(p_servicio)
        story.append(Spacer(1, 0.2*inch))
        
        # ==================== TABLA 1: EQUIPO, CLIENTE, FECHA ====================
        
        tabla1_data = [
            ['Equipo', 'Cliente', 'FECHA'],
            [equipo_nombre, cliente_nombre, fecha_formato]
        ]
        
        tabla1 = Table(tabla1_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
        tabla1.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tabla1)
        story.append(Spacer(1, 0.15*inch))
        
        # ==================== TABLA 2: TIPO DE MANTENIMIENTO ====================
        
        tabla2_data = [
            ['TIPO DE\nMANTENIMIENTO', 'TIPO DE\nINTERVENCIÓN', 'CAUSA DE\nLA FALLA', 'SE SOLUCIONO\nLA FALLA'],
            [
                cierre_ot.tipo_mantenimiento or 'N/A',
                cierre_ot.tipo_intervencion or 'N/A',
                cierre_ot.causa_falla or 'N/A',
                'Sí' if cierre_ot.se_soluciono else 'No'
            ]
        ]
        
        tabla2 = Table(tabla2_data, colWidths=[1.875*inch]*4)
        tabla2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tabla2)
        story.append(Spacer(1, 0.15*inch))
        
        # ==================== DESCRIPCIÓN ====================
        
        story.append(Paragraph("DESCRIPCIÓN DEL TRABAJO REALIZADO", heading_style))
        desc_texto = cierre_ot.descripcion_falla or 'N/A'
        story.append(Paragraph(desc_texto, body_style))
        story.append(Spacer(1, 0.1*inch))
        
        # ==================== OBSERVACIONES ====================
        
        story.append(Paragraph("OBSERVACIONES", heading_style))
        obs_texto = cierre_ot.observaciones or 'N/A'
        story.append(Paragraph(obs_texto, body_style))
        story.append(Spacer(1, 0.15*inch))
        
        # ==================== CONFIRMACIÓN DE TRABAJO ====================
        
        story.append(Paragraph("Confirmación de trabajo recibido:", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Tabla de firmas
        firma_data = [
            ['Realizador por:', 'Recibido por:'],
            [cierre_ot.nombre_tecnico or 'N/A', cierre_ot.nombre_receptor or 'N/A'],
            [f"Doc: {cierre_ot.documento_tecnico or 'N/A'}", f"Doc: {cierre_ot.documento_receptor or 'N/A'}"],
            ['[FIRMA]', '[FIRMA]']
        ]
        
        tabla_firmas = Table(firma_data, colWidths=[3.75*inch, 3.75*inch])
        tabla_firmas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tabla_firmas)
        
        # Insertar firmas como imágenes
        story.append(Spacer(1, 0.1*inch))
        
        # Fila para imágenes de firmas
        firma_imgs = []
        
        if cierre_ot.firma_digital:
            tmp_path, _ = _obtener_imagen_temporal(cierre_ot.firma_digital)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    firma_imgs.append(PlatypusImage(tmp_path, width=1.5*inch, height=0.8*inch))
                    logger.info("✅ Firma técnico agregada")
                except:
                    firma_imgs.append(Paragraph('[Firma]', body_style))
        else:
            firma_imgs.append(Paragraph('[Firma]', body_style))
        
        if cierre_ot.firma_receptor:
            tmp_path, _ = _obtener_imagen_temporal(cierre_ot.firma_receptor)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    firma_imgs.append(PlatypusImage(tmp_path, width=1.5*inch, height=0.8*inch))
                    logger.info("✅ Firma receptor agregada")
                except:
                    firma_imgs.append(Paragraph('[Firma]', body_style))
        else:
            firma_imgs.append(Paragraph('[Firma]', body_style))
        
        if len(firma_imgs) == 2:
            tabla_imgs_firmas = Table([firma_imgs], colWidths=[3.75*inch, 3.75*inch])
            tabla_imgs_firmas.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(tabla_imgs_firmas)
        
        # ==================== IMÁGENES ANTES/DESPUÉS ====================
        
        imagenes_antes = cierre_ot.imagenes.filter(tipo='antes')
        imagenes_despues = cierre_ot.imagenes.filter(tipo='despues')
        
        if imagenes_antes.exists() or imagenes_despues.exists():
            story.append(PageBreak())
            
            # ANTES
            if imagenes_antes.exists():
                story.append(Paragraph("─ ANTES ─", heading_style))
                story.append(Spacer(1, 0.1*inch))
                
                for img in imagenes_antes:
                    try:
                        img_path, _ = _obtener_imagen_temporal(img.imagen)
                        if img_path and os.path.exists(img_path):
                            img_platypus = PlatypusImage(img_path, width=5*inch, height=3.75*inch)
                            story.append(img_platypus)
                            story.append(Spacer(1, 0.1*inch))
                            logger.info("✅ Imagen ANTES agregada")
                    except Exception as e:
                        logger.warning(f"Error imagen ANTES: {e}")
            
            # Espacio
            if imagenes_antes.exists() and imagenes_despues.exists():
                story.append(Spacer(1, 0.2*inch))
            
            # DESPUÉS
            if imagenes_despues.exists():
                story.append(Paragraph("─ DESPUÉS ─", heading_style))
                story.append(Spacer(1, 0.1*inch))
                
                for img in imagenes_despues:
                    try:
                        img_path, _ = _obtener_imagen_temporal(img.imagen)
                        if img_path and os.path.exists(img_path):
                            img_platypus = PlatypusImage(img_path, width=5*inch, height=3.75*inch)
                            story.append(img_platypus)
                            story.append(Spacer(1, 0.1*inch))
                            logger.info("✅ Imagen DESPUÉS agregada")
                    except Exception as e:
                        logger.warning(f"Error imagen DESPUÉS: {e}")
        
        # Generar PDF
        pdf_doc.build(story)
        pdf_buffer.seek(0)
        
        logger.info("✅ PDF generado completamente con ReportLab")
        return pdf_buffer
    
    except Exception as e:
        logger.error(f"❌ Error generando PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


# Funciones legacy (mantenidas por compatibilidad)
def reemplazar_tags_en_docx(doc, reemplazos):
    """Legacy - no se usa"""
    pass


def _insertar_firma_en_docx(doc, cierre_ot):
    """Legacy - no se usa"""
    pass


def _agregar_imagenes_al_final(doc, cierre_ot):
    """Legacy - no se usa"""
    pass


def _insertar_logo_dinamico(doc):
    """Legacy - no se usa"""
    pass


def _convertir_docx_a_pdf(docx_buffer):
    """Legacy - no se usa"""
    pass


def _docx_a_pdf_reportlab(docx_buffer):
    """Legacy - no se usa"""
    pass


def _generar_pdf_simple_minimo():
    """Legacy - no se usa"""
    pass
