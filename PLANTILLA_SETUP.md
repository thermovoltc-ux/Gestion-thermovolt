# 📋 Configuración de Plantilla DOCX

## ¿Qué debes hacer?

### 1️⃣ Copiar la plantilla

**Ubica el archivo `plantilla_ot.docx`** que ya creaste y cópialo a la **raíz del proyecto**:

```
gestion_mantenimiento/
├── plantilla_ot.docx          ← COPIAR AQUI
├── manage.py
├── requirements.txt
└── ...
```

**Ubicación final:** `c:\Users\Juan Esteban\Downloads\gestion_mantenimiento (1)\plantilla_ot.docx`

---

### 2️⃣ Verificar tags en la plantilla

Tu plantilla debe tener estos tags para que se reemplacen automáticamente:

```docx
Servicio N°: <<OT>>
Equipo: <<equipo>>
Cliente: <<cliente>>
FECHA: <<fecha>>
TIPO DE MANTENIMIENTO: <<tipomtto>>
TIPO DE INTERVENCIÓN: <<tipointervencion>>
CAUSA DE LA FALLA: <<causafalla>>
SE SOLUCIONO LA FALLA: <<sesoluciono>>
DESCRIPCIÓN DEL TRABAJO REALIZADO: <<descripcion>>
OBSERVACIONES: <<observacion>>
Realizador por: <<nombret>>
Documento de identidad: <<cct>>
Recibido por: <<recibido>>
Documento de identidad: <<cc>>
```

---

### 3️⃣ Tags disponibles

| Tag | Valor |
|-----|-------|
| `<<OT>>` | Número de OT (ej: 96) |
| `<<equipo>>` | Nombre del equipo |
| `<<cliente>>` | Nombre del cliente/ubicación |
| `<<fecha>>` | Fecha de la intervención (dd/mm/yyyy) |
| `<<tipomtto>>` | Tipo de mantenimiento (Correctivo/Preventivo) |
| `<<tipointervencion>>` | Tipo de intervención (Eléctrico/Mecánico) |
| `<<causafalla>>` | Causa de la falla |
| `<<sesoluciono>>` | Sí o No |
| `<<descripcion>>` | Descripción del trabajo realizado |
| `<<observacion>>` | Observaciones |
| `<<nombret>>` | Nombre del técnico |
| `<<cct>>` | Cédula del técnico |
| `<<recibido>>` | Nombre de quien recibe |
| `<<cc>>` | Cédula de quien recibe |

---

### 4️⃣ Cómo el sistema genera el PDF

**Localmente (desarrollo):**
1. Carga `plantilla_ot.docx`
2. Reemplaza todos los tags con datos reales
3. Convierte DOCX → PDF usando docx2pdf + LibreOffice
4. **Nombre:** `OT_20260620_96.pdf` (fecha + número OT)

**En Railway (producción):**
1. Carga `plantilla_ot.docx`
2. Reemplaza todos los tags con datos reales
3. Guarda PDF temporal
4. Si docx2pdf falla, usa fallback con ReportLab
5. **Nombre:** `OT_20260620_96.pdf`

---

### 5️⃣ Email mejorado

El email ahora se envía en **HTML presentable** con:
- Saludo cordial
- Información del servicio en un box destacado
- Logo de Thermovolt
- Firma profesional

---

## ✅ Checklist

- [ ] Copié `plantilla_ot.docx` a la carpeta raíz del proyecto
- [ ] La plantilla tiene todos los tags `<<>>` necesarios
- [ ] Hice push a GitHub con la plantilla
- [ ] Redeploy en Railway
- [ ] Generé un nuevo informe OT de prueba
- [ ] Verificué que el PDF se generó con nombre correcto (OT_YYYYMMDD_numero.pdf)
- [ ] Revisé que el email sea HTML presentable

---

## 🔧 Localización de la Plantilla

En `plantilla_utils.py` línea ~85, la plantilla se busca en:

```python
plantilla_path = os.path.join(
    os.path.dirname(__file__),
    '..',
    'plantilla_ot.docx'
)
```

Esto significa: `gestion_mantenimiento/plantilla_ot.docx`

Si quieres cambiar la ubicación, edita esa línea.

---

## 🐛 Troubleshooting

**Error: "Plantilla no encontrada en..."**
- Verifica que `plantilla_ot.docx` está en la carpeta raíz
- Asegúrate de que el nombre es exacto: `plantilla_ot.docx`
- Redeploy en Railway

**El PDF no se genera correctamente**
- Verificar en logs de Railway si ves "Cargando plantilla desde:"
- Si LibreOffice no está disponible, fallback a ReportLab es automático
- Revisar que los tags están correctamente formateados `<<tag>>`

---

**¿Listo? Copia la plantilla, haz push, redeploy en Railway y genera un informe OT** 👍

