# 🚀 Brevo (Sendinblue) Setup para Railway

## ¿Por qué Brevo?

- ✅ **100% GRATIS PARA SIEMPRE** - 300 emails/día
- ✅ No requiere tarjeta de crédito para el plan free
- ✅ API REST (funciona perfectamente en Railway)
- ✅ Muy confiable - usado por millones de usuarios
- ✅ Tu caso: 1-2 emails/semana = 8 emails/mes (¡dentro del free!)

---

## 📋 PASO 1: Crear Cuenta en Brevo

1. Ve a https://www.brevo.com/
2. Haz clic en **"Sign Up Free"**
3. Completa el formulario:
   - Email: Tu email
   - Password: Tu contraseña
   - Empresa: Thermovolt
4. Verifica tu email
5. Confirma tu cuenta

---

## 🔑 PASO 2: Obtener API Key

1. En el dashboard, ve a **Settings** (rueda de engranaje abajo a la izquierda)
2. Haz clic en **SMTP & API**
3. En la sección **API Keys**, verás la opción para generar una clave
4. Haz clic en **"Create a new API key"**
5. Asigna un nombre (ej: "Thermovolt Railway")
6. Haz clic en **"Generate"**
7. Copia la API Key (aparece una sola vez)

Tu API Key se verá así (formato):
```
xkexxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## ⚙️ PASO 3: Configurar en Railway

En la interfaz de Railway, agrega esta variable de entorno:

```
BREVO_API_KEY = xkexxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL = thermovoltc@gmail.com
EMAIL_ADICIONAL = thermovoltc@gmail.com
```

**⚠️ IMPORTANTE:** 
- Reemplaza `xke...` con tu API Key real de Brevo
- `DEFAULT_FROM_EMAIL` debe ser un email verificado (ej: tu gmail)
- `EMAIL_ADICIONAL` es para copias (opcional)

---

## 🔐 PASO 4: Verificar Email (Sender)

Brevo requiere que verifiques el email desde el cual enviarás:

1. En Brevo dashboard, ve a **Senders**
2. Verifica que tu email (ej: thermovoltc@gmail.com) está listado
3. Si NO está, haz clic en **"Add a Sender"** y sigue el proceso de verificación

---

## 📦 PASO 5: Instalar Dependencia

La dependencia ya está agregada a `requirements.txt`:
```
django-anymail[brevo]==10.2
```

En Railway se instalará automáticamente con el siguiente redeploy.

---

## 🚀 PASO 6: Redeploy en Railway

1. Asegúrate de haber hecho push a GitHub
   (El código ya está actualizado)

2. En Railway dashboard:
   - Agrega las variables de entorno:
     - `BREVO_API_KEY` = (tu API key de Brevo)
     - `DEFAULT_FROM_EMAIL` = (tu email verificado)
     - `EMAIL_ADICIONAL` = (opcional)
   - Presiona **Redeploy**

---

## ✅ PASO 7: Probar

1. En la aplicación, genera un nuevo informe OT
2. En Railway logs, busca:
   ```
   ✅ Email enviado EXITOSAMENTE via Brevo
   ```

Si ves ese mensaje, ¡está funcionando! 🎉

---

## 📊 Monitoreo

En Brevo dashboard puedes ver:
- Ve a **Statistics** o **Analytics**
- Verifica emails enviados, abiertos, clics
- Dashboard muestra uso (emails/día vs límite free)

---

## 💡 Límites del Plan Free

- **300 emails/día** (2100 emails/semana)
- **Tu caso**: 1-2 emails/semana ✅ Muy dentro del límite
- **Contactos**: Ilimitados
- **Validez**: Indefinida (no expira)

---

## 🆘 Troubleshooting

### Error: "BREVO_API_KEY not configured"
- Verifica que en Railway está configurada la variable `BREVO_API_KEY`
- Redeploy después de agregar variables

### Error: "Invalid API Key"
- Copia nuevamente la API Key de Brevo
- Elimina espacios o caracteres extras
- Verifica que es una clave v3 (no v2)
- Redeploy

### Error: "Sender email not verified"
- Ve a Brevo → Senders
- Verifica que tu email de `DEFAULT_FROM_EMAIL` está listado y verificado
- Si no, agrégalo siguiendo el proceso de verificación

---

## 📖 Diferencia vs Mailgun

| Aspecto | Brevo | Mailgun |
|--------|-------|---------|
| **Costo** | 100% gratis siempre | $35/mes después de 30 días |
| **API Key** | Una sola clave | Múltiples opciones |
| **Facilidad** | ⭐⭐⭐⭐⭐ Muy fácil | ⭐⭐⭐⭐ Fácil |
| **Plan Free** | 300/día ilimitado | Trial 30 días |

---

**¿Listo para empezar? Crea la cuenta en Brevo y comparte tu API Key cuando la tengas** 👍

