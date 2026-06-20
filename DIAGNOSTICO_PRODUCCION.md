# 🔧 Diagnóstico de Problemas de Producción

## Problemas Reportados

1. **PDF vacío (0 bytes)** - El PDF se genera pero está vacío
2. **SendGrid 401 "Maximum credits exceeded"** - Error de autenticación/créditos

---

## 🚨 PROBLEMA 1: PDF VACÍO (0 BYTES)

### Causa Raíz
LibreOffice en Railway está generando un PDF vacío cuando convierte el DOCX. Esto generalmente ocurre cuando:
- LibreOffice no está instalado correctamente en Railway
- Hay permisos insuficientes
- Faltan dependencias (LibreOffice requiere varias librerías)
- LibreOffice se bloquea en headless mode sin interfaz gráfica

### Solución Inmediata (Fallback Automático)
✅ **YA IMPLEMENTADO** - El código ahora detecta PDFs vacíos y usa ReportLab automáticamente.

Si ves en logs: `❌ PDF generado pero está vacío (0 bytes) - libreroffice falló silenciosamente. Usando ReportLab como fallback`

Esto significa que está funcionando el fallback.

### Solución Permanente: Instalar LibreOffice en Railway

**Opción A: Usar Procfile y buildpacks**

1. En el archivo `Procfile`, agrega una línea antes del comando de ejecución:
```bash
#!/bin/bash
apt-get update && apt-get install -y libreoffice
exec python manage.py runserver
```

2. O usa `start.sh` que ya existe. Abre [start.sh](start.sh) y verifica que incluya:
```bash
#!/bin/bash
# Instalar LibreOffice si no está disponible
if ! command -v soffice &> /dev/null; then
    echo "Instalando LibreOffice..."
    apt-get update
    apt-get install -y libreoffice
fi
# Iniciar Django
exec python manage.py runserver
```

**Opción B: Verificar que LibreOffice está en PATH**

En Railway, ejecuta en SSH o logs:
```bash
which soffice
# o
command -v libreoffice
```

Si no devuelve nada, LibreOffice no está instalado.

### Verificar Logs de PDF

Busca en los logs de Railway estas líneas para verificar estado:

✅ **Éxito**:
```
✓ PDF DESDE PLANTILLA COMPLETADO EXITOSAMENTE
```

⚠️ **Fallback activo** (OK, usando ReportLab):
```
❌ PDF generado pero está vacío (0 bytes) - libreroffice falló silenciosamente. Usando ReportLab como fallback
```

---

## 🔐 PROBLEMA 2: SendGrid 401 "Maximum credits exceeded"

### Causas Posibles

1. **❌ API Key inválida o expirada**
   - La SENDGRID_API_KEY en Railway podría estar mal copiada
   - SendGrid puede generar una nueva API key si rotó las credenciales

2. **❌ Email "from" no verificado**
   - El email `thermovoltc@gmail.com` podría no estar verificado en SendGrid
   - SendGrid requiere verificar el dominio o email antes de enviar

3. **❌ Cuenta Sin Créditos**
   - Si usas SendGrid Free, podrías haber alcanzado el límite de envíos
   - El error "Maximum credits exceeded" es poco común a menos que uses un plan con límite

4. **❌ Problema con el servidor de SendGrid**
   - A veces SendGrid devuelve 401 cuando hay error de servidor

### Soluciones

#### Paso 1: Verificar API Key en Railway

1. Ve a [https://railway.app/project/[project-id]/variables](https://railway.app)
2. Busca la variable `SENDGRID_API_KEY`
3. Copia el valor completo y verifica en [SendGrid Dashboard](https://app.sendgrid.com/settings/api_keys):
   - ¿Existe esta API key?
   - ¿Está ACTIVA (no deshabilitada)?
   - ¿La fecha de expiración es futura?

#### Paso 2: Verificar que el Email "From" está Verificado

1. Ve a [SendGrid Dashboard → Email API Settings](https://app.sendgrid.com/settings/sender_auth)
2. Busca `thermovoltc@gmail.com` en:
   - **Sender Authentication** (si usas SPF/DKIM)
   - **Verified Senders** (antigua forma)
3. Si no está, crea un nuevo "Verified Sender":
   - SendGrid Dashboard → Email API → Verified Senders
   - Click "+ Create Sender"
   - Email: `thermovoltc@gmail.com`
   - Nombre: "Mantenimiento"
   - Verifica el email (SendGrid enviará confirmación)

#### Paso 3: Aumentar Logging de SendGrid

Ya está implementado. Busca en logs:
```
✓ SendGrid API Key configurada: SG.xxxxxx...xxxxx (longitud: 69)
📧 ENVIANDO VIA SENDGRID API:
   - From: thermovoltc@gmail.com
   - To: ['email@example.com']
   - Tamaño PDF: 2.50 MB
❌ SendGrid API error 401: {"errors":[{"message":"Maximum credits exceeded",...}]}
```

#### Paso 4: Fallback a Gmail/SMTP (Solución Rápida)

Si SendGrid sigue fallando, usa Gmail SMTP:

1. Verifica que `EMAIL_BACKEND` en [settings.py](gestion_mantenimiento/settings.py) es:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
```

2. Verifica variables en Railway:
```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=thermovoltc@gmail.com
EMAIL_HOST_PASSWORD=[tu app password]
```

3. Para Gmail, necesitas **App Password** (no contraseña normal):
   - Ve a https://myaccount.google.com/apppasswords
   - Selecciona "Mail" y "Windows Computer"
   - Copia la contraseña de 16 caracteres
   - Pégala en `EMAIL_HOST_PASSWORD` en Railway

### Verificar que Fallback SMTP Funciona

El código intenta así:
1. **Primero**: SendGrid (si SENDGRID_API_KEY existe)
2. **Si falla**: Django SMTP (EmailBackend)

En logs verás:
```
✅ Email enviado exitosamente via SMTP local
```

Si solo ves "Error enviando email" sin intentar SMTP, significa que no está configurado.

---

## 🧪 PRUEBAS MANUALES

### Test 1: Verificar SendGrid está Configurado

En Django Shell (en Railway via SSH):
```bash
python manage.py shell
```

Luego:
```python
from django.conf import settings
print("SENDGRID_API_KEY:", getattr(settings, 'SENDGRID_API_KEY', 'NO CONFIGURADA')[:10] + "...")
print("SENDGRID_FROM_EMAIL:", getattr(settings, 'SENDGRID_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL))
```

### Test 2: Enviar Email de Prueba

```python
from django.core.mail import EmailMessage
email = EmailMessage(
    subject="Test",
    body="Prueba de email",
    from_email="thermovoltc@gmail.com",
    to=["tu@email.com"]
)
email.send()
```

Si devuelve `1`, fue exitoso.

### Test 3: Validar Que LibreOffice Está en PATH

```bash
which soffice
# Debería devolver algo como: /usr/bin/soffice
# Si no devuelve nada, LibreOffice no está instalado
```

---

## ✅ PRÓXIMOS PASOS

1. **Verifica la API Key de SendGrid en Railway** - Probablemente el problema
2. **Verifica que `thermovoltc@gmail.com` está verificado en SendGrid** 
3. **Si SendGrid sigue fallando, configura Gmail SMTP como fallback**
4. **Verifica que LibreOffice está instalado en Railway** (si ves PDFs vacíos)

---

## 📊 Estado Actual del Código

✅ **Mejoras implementadas:**
- Mejor detección de PDF vacío (0 bytes)
- Fallback automático a ReportLab si PDF está vacío
- Logging mejorado de SendGrid con diagnosis automática
- Manejo de error 401 con sugerencias

🔄 **Esperando acción:**
- Verificar y corregir SENDGRID_API_KEY en Railway
- Verificar que email "from" está verificado en SendGrid
- Instalar LibreOffice en Railway si es necesario

