# 🚂 Guía: Configurar SendGrid en Railway

## Paso 1: Copiar API Key de SendGrid

1. Ve a [SendGrid Dashboard](https://app.sendgrid.com)
2. Haz clic en **Settings** en la esquina inferior izquierda
3. Selecciona **API Keys**
4. Busca tu API key o crea una nueva:
   - Si creas una nueva: **Create API Key** → Nombre: "Railway" → **Create & View**
   - Debería empezar con `SG.` y tener aproximadamente 69 caracteres

5. **Copia la API Key completa** (solo se muestra una vez)

## Paso 2: Agregar Variables de Entorno en Railway

1. Ve a [https://railway.app](https://railway.app)
2. Abre tu proyecto → **Variables** 
3. Agregaa o actualiza estas variables:

```
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=thermovoltc@gmail.com
```

## Paso 3: Verificar que Email Está Verificado en SendGrid

**IMPORTANTE**: El email "from" debe estar verificado en SendGrid o tendrás error 401.

1. Ve a [SendGrid Dashboard → Email API](https://app.sendgrid.com/settings/sender_auth)
2. Busca "Verified Senders" 
3. Si `thermovoltc@gmail.com` **NO aparece**, crea uno:
   - **+ Create Sender**
   - **Email Address**: thermovoltc@gmail.com
   - **Display Name**: Mantenimiento
   - **Haz clic en tu dominio** → SendGrid enviará verificación
   - Verifica el email desde tu bandeja de entrada
   - Espera 5-10 minutos hasta que aparezca como "Verified"

## Paso 4: Probar Configuración (Opcional)

En Railway, en SSH o logs, ejecuta:

```bash
python manage.py shell
```

Luego:

```python
from django.conf import settings
import requests
import json

# 1. Verificar que la API Key está presente
api_key = getattr(settings, 'SENDGRID_API_KEY', None)
if not api_key:
    print("❌ SENDGRID_API_KEY no configurada")
else:
    print(f"✓ API Key presente: {api_key[:10]}...{api_key[-5:]}")

# 2. Verificar email FROM
from_email = getattr(settings, 'SENDGRID_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)
print(f"✓ Email FROM: {from_email}")

# 3. Probar envío a SendGrid (sin realmente enviar)
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "personalizations": [{"to": [{"email": "tu@email.com"}], "subject": "Test"}],
    "from": {"email": from_email},
    "content": [{"type": "text/plain", "value": "Test"}]
}

response = requests.post(
    "https://api.sendgrid.com/v3/mail/send",
    json=payload,
    headers=headers,
    timeout=30
)

print(f"Status Code: {response.status_code}")
if response.status_code == 202:
    print("✅ SendGrid está funcionando correctamente")
elif response.status_code == 401:
    print("❌ ERROR 401: Verifica que la API Key es correcta y el email está verificado")
else:
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
```

## Paso 5: Alternativa - Gmail SMTP Fallback

Si SendGrid sigue teniendo problemas, configura Gmail como fallback:

En Railway → Variables:
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=thermovoltc@gmail.com
EMAIL_HOST_PASSWORD=[app-password-16-caracteres]
```

Para obtener `app-password`:
1. Ve a [Google Account Security](https://myaccount.google.com/security)
2. Busca "App Passwords" (requiere 2FA activado)
3. Selecciona "Mail" y "Windows Computer"
4. Google te dará una contraseña de 16 caracteres
5. Cópiala en `EMAIL_HOST_PASSWORD`

## Checklist de Diagnóstico

- [ ] ¿La API Key de SendGrid está en Railway como `SENDGRID_API_KEY`?
- [ ] ¿Empieza la API Key con `SG.`?
- [ ] ¿El email `thermovoltc@gmail.com` aparece como "Verified" en SendGrid?
- [ ] ¿Ejecutaste `python manage.py migrate` en Railway después de cambiar variables?
- [ ] ¿Reiniciaste el deployment en Railway después de cambiar variables?

## Logs a Buscar en Railway

✅ **Cuando funciona**:
```
✓ SendGrid API Key configurada: SG.xxxxxx...xxxxx (longitud: 69)
📧 ENVIANDO VIA SENDGRID API:
   - From: thermovoltc@gmail.com
   - To: ['email@example.com']
✅ Email enviado exitosamente via SendGrid API
```

❌ **Cuando falla**:
```
❌ SendGrid API error 401: {"errors":[{"message":"Maximum credits exceeded",...}]}
🔐 ERROR DE AUTENTICACIÓN (401):
   - Probable causa 1: API Key inválida o expirada
   - Probable causa 2: Email 'from' no verificado en SendGrid
```

---

## ¿Aún No Funciona?

Si después de estos pasos aún ves error 401:

1. **Crea una NEW API Key en SendGrid** (podría haber expirado)
2. **Verifica el email from** en SendGrid Verified Senders
3. **Contacta SendGrid Support** si la API Key es válida pero sigue rechazando

O usa el **fallback Gmail SMTP** que está configurado como alternativa.

