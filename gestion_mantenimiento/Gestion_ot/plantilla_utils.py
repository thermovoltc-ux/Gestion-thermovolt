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
import base64
from datetime import datetime
from PIL import Image as PILImage

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


def _limpiar_texto(texto):
    """
    Limpia caracteres especiales no deseados del texto
    - Elimina caracteres como ■ (cuadrados negros)
    - Preserva saltos de línea naturales
    """
    if not texto:
        return texto
    
    # Caracteres especiales a eliminar
    caracteres_especiales = ['■', '●', '◆', '▪', '✓', '✗']
    
    for char in caracteres_especiales:
        texto = texto.replace(char, '').replace(char.encode('utf-8').decode('utf-8'), '')
    
    # Limpiar espacios múltiples manteniendo saltos de línea
    lineas = texto.split('\n')
    lineas_limpias = [linea.strip() for linea in lineas if linea.strip()]
    
    return '\n'.join(lineas_limpias)


def _obtener_imagen_temporal(file_field_o_url):
    """
    Obtiene ruta temporal de una imagen desde FileField, URL, data URL o base64
    """
    if not file_field_o_url:
        return None, False
    
    try:
        # Manejar data URLs (data:image/png;base64,...)
        if isinstance(file_field_o_url, str) and file_field_o_url.startswith('data:image'):
            try:
                # Extraer la parte base64
                if ',' in file_field_o_url:
                    header, encoded = file_field_o_url.split(',', 1)
                else:
                    encoded = file_field_o_url
                
                # Decodificar
                image_data = base64.b64decode(encoded)
                
                # Crear imagen temporal
                img = PILImage.open(io.BytesIO(image_data))
                logger.info(f"✅ Imagen decodificada - Modo: {img.mode}, Tamaño: {img.size}")
                
                # Manejar transparencia si es RGBA
                if img.mode == 'RGBA':
                    logger.info("Detectado RGBA - Reemplazando transparencia con fondo blanco")
                    white_bg = PILImage.new('RGB', img.size, (255, 255, 255))
                    white_bg.paste(img, mask=img.split()[3])  # split()[3] es el canal alpha
                    img = white_bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                    logger.info(f"Convertido a RGB desde {img.mode}")

                # Reducir resolución solo si es muy grande y guardar en JPEG con calidad alta
                max_width = 2400
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = max(1, int(img.height * ratio))
                    try:
                        img = img.resize((max_width, new_height), PILImage.LANCZOS)
                        logger.info(f"Imagen redimensionada a: {img.size}")
                    except Exception:
                        logger.warning("No se pudo redimensionar la imagen, se guardará tal cual")

                # Guardar como JPEG de alta calidad
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    try:
                        img.save(tmp.name, format='JPEG', quality=90, optimize=True)
                        try:
                            new_size = os.path.getsize(tmp.name)
                            logger.info(f"✅ Data URL procesada y guardada en: {tmp.name} ({new_size} bytes)")
                        except Exception:
                            logger.info(f"✅ Data URL procesada y guardada en: {tmp.name}")
                        return tmp.name, True
                    except Exception as e:
                        logger.warning(f"Fallo al guardar como JPEG: {e}, intentando PNG")
                        img.save(tmp.name, format='PNG', optimize=True)
                        return tmp.name, True
            except Exception as e:
                logger.error(f"❌ Error procesando data URL: {e}", exc_info=True)
                return None, False
        
        # Manejar URLs HTTP
        if isinstance(file_field_o_url, str) and file_field_o_url.startswith('http'):
            response = requests.get(file_field_o_url, timeout=15)
            response.raise_for_status()
            suffix = '.png' if 'png' in file_field_o_url.lower() else '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                return tmp.name, True
        
        # Manejar FileField con atributo url
        elif hasattr(file_field_o_url, 'url'):
            url = file_field_o_url.url
            if url and url.startswith('http'):
                return _obtener_imagen_temporal(url)
        
        # Manejar FileField con atributo path
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
            leading=11,
            alignment=TA_LEFT
        )
        
        # ==================== ENCABEZADO ====================
        
        # Logo + Servicio Nº en la misma línea (logo izq, servicio der)
        logo_cell = None
        logo_path = _obtener_logo()
        if logo_path:
            try:
                logo_cell = PlatypusImage(logo_path, width=2.2*inch, height=0.8*inch)
                logger.info("✅ Logo agregado al PDF")
            except Exception as e:
                logger.warning(f"Error agregando logo: {e}")
        
        servicio_style = ParagraphStyle(
            name='ServicioStyle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#1F2937'),
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold'
        )
        p_servicio = Paragraph(f"<b>Servicio Nº {numero_ot}</b>", servicio_style)
        
        encabezado_data = [[logo_cell or Paragraph('', body_style), p_servicio]]
        tabla_encabezado = Table(encabezado_data, colWidths=[3.5*inch, 3.5*inch])
        tabla_encabezado.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BORDERS', (0, 0), (-1, -1), 0, colors.white),
        ]))
        story.append(tabla_encabezado)
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
        
        desc_texto = _limpiar_texto(cierre_ot.descripcion_falla) or 'N/A'
        tabla_desc_data = [
            ['DESCRIPCIÓN DEL TRABAJO REALIZADO'],
            [desc_texto]
        ]
        tabla_desc = Table(tabla_desc_data, colWidths=[7.5*inch])
        tabla_desc.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWHEIGHTS', (0, 1), (-1, 1), None),
        ]))
        story.append(tabla_desc)
        story.append(Spacer(1, 0.1*inch))
        
        # ==================== OBSERVACIONES ====================
        
        obs_texto = _limpiar_texto(cierre_ot.observaciones) or 'N/A'
        tabla_obs_data = [
            ['OBSERVACIONES'],
            [obs_texto]
        ]
        tabla_obs = Table(tabla_obs_data, colWidths=[7.5*inch])
        tabla_obs.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWHEIGHTS', (0, 1), (-1, 1), None),
        ]))
        story.append(tabla_obs)
        story.append(Spacer(1, 0.15*inch))
        
        # ==================== CONFIRMACIÓN DE TRABAJO ====================
        
        story.append(Paragraph("Confirmación de trabajo recibido:", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Tabla 1: Nombres y documentos
        firma_data = [
            ['Realizador por:', 'Recibido por:'],
            [cierre_ot.nombre_tecnico or 'N/A', cierre_ot.nombre_receptor or 'N/A'],
            [f"CC: {cierre_ot.documento_tecnico or 'N/A'}", f"CC: {cierre_ot.documento_receptor or 'N/A'}"]
        ]
        
        tabla_firmas = Table(firma_data, colWidths=[3.75*inch, 3.75*inch])
        tabla_firmas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Encabezado centrado
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),   # Nombres y documentos a la izquierda
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.white),  # Líneas BLANCAS
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tabla_firmas)
        
        # Tabla 2: Imágenes de firmas (separada)
        story.append(Spacer(1, 0.05*inch))
        
        firma_tech_img = None
        firma_recep_img = None
        
        # Obtener imágenes de firmas
        try:
            if cierre_ot.firma_digital:
                firma_tech_path, _ = _obtener_imagen_temporal(cierre_ot.firma_digital)
                if firma_tech_path and os.path.exists(firma_tech_path):
                    try:
                        firma_tech_img = PlatypusImage(firma_tech_path, width=3.2*inch, height=1.4*inch)
                        logger.info("✅ Firma técnico cargada (3.2\" x 1.4\")")
                    except Exception as e:
                        logger.error(f"❌ Error creando imagen firma técnico: {e}")
        except Exception as e:
            logger.error(f"❌ Error procesando firma técnico: {e}")
        
        try:
            if cierre_ot.firma_receptor:
                firma_recep_path, _ = _obtener_imagen_temporal(cierre_ot.firma_receptor)
                if firma_recep_path and os.path.exists(firma_recep_path):
                    try:
                        firma_recep_img = PlatypusImage(firma_recep_path, width=3.2*inch, height=1.4*inch)
                        logger.info("✅ Firma receptor cargada (3.2\" x 1.4\")")
                    except Exception as e:
                        logger.error(f"❌ Error creando imagen firma receptor: {e}")
        except Exception as e:
            logger.error(f"❌ Error procesando firma receptor: {e}")
        
        # Construir tabla de imágenes solo si hay al menos una
        if firma_tech_img or firma_recep_img:
            img_cells = [
                firma_tech_img if firma_tech_img else Paragraph('', body_style),
                firma_recep_img if firma_recep_img else Paragraph('', body_style)
            ]
            tabla_imgs = Table([img_cells], colWidths=[3.75*inch, 3.75*inch])
            tabla_imgs.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centrado horizontal
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrado vertical
                ('GRID', (0, 0), (-1, -1), 0.5, colors.white),  # Líneas BLANCAS para efecto flotante
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('ROWHEIGHTS', (0, 0), (-1, 0), 1.5*inch),
            ]))
            story.append(tabla_imgs)
        
        # ==================== IMÁGENES ANTES/DESPUÉS ====================
        
        imagenes_antes = list(cierre_ot.imagenes.filter(tipo='antes'))
        imagenes_despues = list(cierre_ot.imagenes.filter(tipo='despues'))
        
        if imagenes_antes or imagenes_despues:
            story.append(PageBreak())
            
            heading_antes_style = ParagraphStyle(
                name='HeadingAntes',
                parent=styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#1F2937'),
                spaceAfter=6,
                spaceBefore=6,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )

            # Limitar a las primeras 4 imágenes para evitar PDFs enormes en email.
            max_fotos_por_tipo = 4
            
            # ANTES
            if imagenes_antes:
                story.append(Paragraph("FOTOS ANTES DEL TRABAJO", heading_antes_style))
                story.append(Spacer(1, 0.15*inch))
                
                # Agrupar imágenes de a 2 por fila
                fotos_antes = imagenes_antes[:max_fotos_por_tipo]
                for i in range(0, len(fotos_antes), 2):
                    fila_imgs = []
                    for j in range(2):
                        if i + j < len(fotos_antes):
                            try:
                                img_path, _ = _obtener_imagen_temporal(fotos_antes[i + j].imagen)
                                if img_path and os.path.exists(img_path):
                                    img_obj = PlatypusImage(img_path, width=2.7*inch, height=2.0*inch)
                                    fila_imgs.append(img_obj)
                                    logger.info("✅ Imagen ANTES agregada")
                                else:
                                    fila_imgs.append(Paragraph('[Imagen no disponible]', body_style))
                            except Exception as e:
                                logger.warning(f"Error imagen ANTES: {e}")
                                fila_imgs.append(Paragraph('[Error imagen]', body_style))
                        else:
                            fila_imgs.append(Paragraph('', body_style))
                    
                    if fila_imgs:
                        tabla_imgs_antes = Table([fila_imgs], colWidths=[3.2*inch, 3.2*inch])
                        tabla_imgs_antes.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('BORDERS', (0, 0), (-1, -1), 0, colors.white),
                        ]))
                        story.append(tabla_imgs_antes)
                        story.append(Spacer(1, 0.2*inch))
            
            # DESPUÉS
            if imagenes_despues:
                story.append(Paragraph("FOTOS DESPUÉS DEL TRABAJO", heading_antes_style))
                story.append(Spacer(1, 0.15*inch))
                
                # Agrupar imágenes de a 2 por fila
                fotos_despues = imagenes_despues[:max_fotos_por_tipo]
                for i in range(0, len(fotos_despues), 2):
                    fila_imgs = []
                    for j in range(2):
                        if i + j < len(fotos_despues):
                            try:
                                img_path, _ = _obtener_imagen_temporal(fotos_despues[i + j].imagen)
                                if img_path and os.path.exists(img_path):
                                    img_obj = PlatypusImage(img_path, width=2.7*inch, height=2.0*inch)
                                    fila_imgs.append(img_obj)
                                    logger.info("✅ Imagen DESPUÉS agregada")
                                else:
                                    fila_imgs.append(Paragraph('[Imagen no disponible]', body_style))
                            except Exception as e:
                                logger.warning(f"Error imagen DESPUÉS: {e}")
                                fila_imgs.append(Paragraph('[Error imagen]', body_style))
                        else:
                            fila_imgs.append(Paragraph('', body_style))
                    
                    if fila_imgs:
                        tabla_imgs_despues = Table([fila_imgs], colWidths=[3.2*inch, 3.2*inch])
                        tabla_imgs_despues.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('BORDERS', (0, 0), (-1, -1), 0, colors.white),
                        ]))
                        story.append(tabla_imgs_despues)
                        story.append(Spacer(1, 0.2*inch))
        
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
