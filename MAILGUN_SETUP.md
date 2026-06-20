# 🚀 Mailgun Setup para Railway

## ¿Por qué Mailgun?

- ✅ API REST (no requiere SMTP)
- ✅ Funciona perfectamente en Railway (sin restricciones de red)
- ✅ Plan free: 5000 emails/mes
- ✅ 30 días de prueba gratuita sin tarjeta de crédito
- ✅ Muy confiable y usado por empresas grandes

**Ventaja sobre SendGrid:** SendGrid free usa SMTP (bloqueado en Railway), mientras que Mailgun también ofrece API REST.

---

## 📋 PASO 1: Crear Cuenta en Mailgun

1. Ve a https://mailgun.com/
2. Haz clic en "Sign Up for Free"
3. Completa el formulario:
   - Email: Tu email
   - Password: Tu contraseña
4. Verifica tu email
5. Crea un cuenta (se abre dashboard)

---

## 🔑 PASO 2: Obtener API Key

1. En el dashboard, ve a **Settings** (rueda de engranaje abajo a la izquierda)
2. Haz clic en **API Security**
3. En la sección **Private API key**, verás tu API Key
4. Haz clic en el icono de copiar

Tu API Key se verá así (formato de ejemplo):
```
key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 🌐 PASO 3: Obtener Sender Domain

1. En el dashboard, ve a **Sending** → **Domain**
2. Si es la primera vez, verás un dominio sandbox (por defecto):
   ```
   sandbox1234567890.mailgun.org
   ```

Durante la prueba, todos los emails se envían desde un sandbox. Para usar tu propio dominio más adelante:
- Ve a **Domains** → **Add New Domain**
- Sigue los pasos de verificación DNS

---

## ⚙️ PASO 4: Configurar en Railway

En la interfaz de Railway, agrega estas variables de entorno (reemplaza los valores con los tuyos):

```
MAILGUN_API_KEY = key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MAILGUN_SENDER_DOMAIN = sandboxxxxxxxxxxxxxxxxxxxxxxxxx.mailgun.org
DEFAULT_FROM_EMAIL = noreply@sandboxxxxxxxxxxxxxxxxxxxxxxxxx.mailgun.org
```

**⚠️ IMPORTANTE:** El `DEFAULT_FROM_EMAIL` debe usar tu dominio sandbox (o personalizado si lo configuraste).

---

## 📦 PASO 5: Instalar Dependencia

La dependencia ya está agregada a `requirements.txt`:
```
django-anymail[mailgun]==10.2
```

En Railway se instalará automáticamente con el siguiente redeploy.

---

## 🚀 PASO 6: Redeploy en Railway

1. Haz push a GitHub:
```bash
git add -A
git commit -m "Configurar Mailgun como backend de email"
git push origin master
```

2. En Railway dashboard:
   - Agrega las variables de entorno (MAILGUN_API_KEY, MAILGUN_SENDER_DOMAIN, DEFAULT_FROM_EMAIL)
   - Presiona **Redeploy**

---

## ✅ PASO 7: Probar

1. En la aplicación, genera un nuevo informe OT
2. En Railway logs, busca:
   ```
   ✅ Email enviado EXITOSAMENTE via Mailgun
   ```

---

## 🐛 Troubleshooting

### Error: "MAILGUN_API_KEY not configured"
- Verifica que en Railway está configurada la variable `MAILGUN_API_KEY`
- Redeploy después de agregar variables

### Error: "Invalid sender domain"
- Verifica que `MAILGUN_SENDER_DOMAIN` es exactamente igual a tu sandbox o dominio personalizado
- Busca en Mailgun dashboard → Sending → Domain → el nombre exacto

### Error: "Unauthorized - Check your API key"
- Copia de nuevo la API Key de Mailgun
- Elimina espacios o caracteres extras
- Redeploy

---

## 📊 Monitoreo

En Mailgun dashboard puedes ver:
- Logs de emails enviados
- Bounces y errores
- Estadísticas de entrega

Ve a **Logs** para verificar que los emails fueron enviados correctamente.

---

## 💡 Notas

- **Sandbox limita destinatarios**: En el plan free con sandbox, solo puedes enviar a direcciones que hayas autorizado previamente en Mailgun
- **Producción**: Para enviar a cualquier dirección, usa tu propio dominio (requiere verificación DNS)
- **Sugerencia**: Agrega los emails de prueba en Mailgun dashboard → Settings → Authorized Recipients

