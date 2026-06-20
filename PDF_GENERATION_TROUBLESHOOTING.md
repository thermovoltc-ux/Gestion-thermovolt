# Troubleshooting: Generación de PDFs

## Situación Actual (2026-06-20)

### El Problema
- PDFs se generan pero con formato genérico (sin logo, diseño minimalista)
- Las imágenes y firmas SÍ aparecen
- Los datos se rellenan correctamente
- No se parece al diseño original de la plantilla

### Causa Raíz
El sistema de conversión cae al **ReportLab fallback** que recrea el documento desde cero:

```
1. Intenta docx2pdf + LibreOffice
   ↓ (FALLA en Railway)
2. ReportLab fallback (recrea desde cero)
   ↓ Resultado: PDF básico sin diseño original
```

## Stack de Conversión

### Opción 1: LibreOffice + docx2pdf (PREFERIDA)
- **Funciona en**: Local (Windows) ✅
- **Funciona en Railway**: ❌ (No se instala correctamente)
- **Resultado**: PDF 100% igual a plantilla original

### Opción 2: ReportLab Fallback (ACTUAL en Railway)
- **Funciona en**: Railway cuando LibreOffice falla ✅
- **Resultado**: PDF básico, reconstruido desde cero
- **Problemas**:
  - Pierde todo el diseño CSS/estilos
  - Pierde formato visual
  - No reproduce tablas complejas perfectamente
  - Sin logo ni elementos visuales personalizados

## Soluciones Posibles

### ✅ Solución Recomendada (EN PROGRESO)
1. **Mejorar instalación de LibreOffice en Railway**
   - Instalar todas las dependencias gráficas
   - Configurar variables de entorno
   - Verificar que responda
   - **Estado**: Implementado en commit a2cca0b

2. **Si LibreOffice funciona**:
   - docx2pdf + LibreOffice preserva 100% del diseño
   - Las firmas e imágenes se agregan sin problemas
   - PDF se ve exactamente como la plantilla

### 🔄 Alternativa: HTML + CSS + WeasyPrint
Si LibreOffice no funciona en Railway:

1. Convertir DOCX → HTML
2. Agregar CSS con diseño (logo, tablas, etc.)
3. Usar WeasyPrint para generar PDF
4. **Ventaja**: Mejor control visual
5. **Desventaja**: Requiere reescribir plantilla en HTML

### ⚙️ Mejora: ReportLab Mejorado
Si ambas opciones anteriores fallan:
1. Extraer TODAS las imágenes del DOCX
2. Usar mejor la estructura de tablas
3. Aplicar estilos más cercanos al original
4. **Ventaja**: Funciona sin dependencias
5. **Desventaja**: Aún será básico

## Próximos Pasos

### Corto Plazo (Hoy)
1. Railway redeploy con mejor LibreOffice
2. Probar crear nuevo cierre de OT
3. Si PDF se ve bien → ✅ Listo
4. Si PDF sigue siendo genérico → continuar

### Mediano Plazo
- Si LibreOffice no funciona → implementar HTML+WeasyPrint
- Reescribir plantilla en HTML/CSS
- Testing en Railway

## Referencias de Código

**Archivo Principal**: `/gestion_mantenimiento/Gestion_ot/plantilla_utils.py`

**Funciones Clave**:
- `generar_pdf_desde_plantilla(cierre_ot)` → Punto de entrada
- `_convertir_docx_a_pdf(docx_buffer, cierre_ot)` → Pipeline de conversión
- `_docx_a_pdf_reportlab(docx_buffer, cierre_ot)` → Fallback ReportLab

**Scripts de Instalación**:
- `start.sh` → Instalación de LibreOffice en Railway

## Monitoreo

Para diagnosticar qué está pasando:
1. Revisar logs de Railway
2. Buscar: "Conversión docx2pdf exitosa" o "Usando ReportLab"
3. Si ve "Usando ReportLab" → LibreOffice no funciona
4. Si ve "docx2pdf exitosa" → LibreOffice está working
