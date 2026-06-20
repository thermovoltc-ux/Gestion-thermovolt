# ✅ CONFIGURACIÓN CORRECTA DE GMAIL EN RAILWAY

## Problema: Contraseña con espacios

La contraseña de app de Gmail que Google proporciona tiene espacios:
```
cobu sxzm ypxy yzoo
```

**IMPORTANTE: En Railway DEBES quitar los espacios**

---

## ✅ VARIABLES CORRECTAS EN RAILWAY

Ve a **Railway Dashboard → Tu Proyecto → Variables** y verifica/agrega exactamente estas variables:

### Variables de Email

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=thermovoltc@gmail.com
EMAIL_HOST_PASSWORD=cobusxzmypxyyzoo
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=thermovoltc@gmail.com
```

**⚠️ CRÍTICO**: La contraseña **SIN espacios**: `cobusxzmypxyyzoo`

### Variables de SendGrid (opcional, pero aún están)

```
SENDGRID_API_KEY=[Tu API Key de SendGrid]
SENDGRID_FROM_EMAIL=thermovoltc@gmail.com
```

---

## ✅ ARCHIVO NUEVO: mise.toml

Ya creé este archivo en el proyecto - resuelve el error de mise:

```toml
[settings]
# Disable GitHub attestation verification for Python
python.github_attestations = false

[env]
# Python version to use
python = "3.9"
```

Este archivo se commitió automáticamente.

---

## 🚂 PASOS PARA COMPLETAR

### 1. ✅ Actualizar variables en Railway

```
EMAIL_HOST_PASSWORD=cobusxzmypxyyzoo   (SIN espacios)
```

Verifica en Railway que la variable se vea exactamente así (sin espacios).

### 2. ✅ Hacer Redeploy

En Railway Dashboard:
- Tu proyecto
- Build & Deploy
- Click en **Redeploy** (o espera redeploy automático)

---

## ✅ VERIFICAR QUE FUNCIONA

Después del redeploy, en los logs deberías ver:

```
STARTUP: checking and installing dependencies...
✓ Python instalado correctamente
✓ STARTUP: dependencias instaladas
```

Y cuando generes un OT:

```
📝 Generando PDF para OT XXX
   - Entorno: Railway
   - DEBUG: False
🚂 Detectado Railway/Producción - usando ReportLab
📬 ENVIANDO VIA SMTP:
   - Backend: django.core.mail.backends.smtp.EmailBackend
   - From: thermovoltc@gmail.com
   - To: ['email@example.com']
✅ Email enviado EXITOSAMENTE via SMTP
```

---

## 🆘 TROUBLESHOOTING

### Si ves error de autenticación SMTP:

```
Error enviando email: (535, b'5.7.8 Username and password not accepted')
```

**Causas y soluciones:**

1. **Contraseña tiene espacios** → Quita los espacios en Railway
2. **Contraseña incorrecta** → Copia exactamente los 16 caracteres de Google
3. **Gmail 2FA no activado** → Activa 2FA en tu cuenta Google
4. **Credenciales mal copiadas** → Prueba obtener nueva app password

### Si ves error de mise:

```
mise ERROR Failed to install core:python@3.9.18
```

✅ **Resuelto** - mise.toml ya está en el proyecto

---

## 📋 CHECKLIST FINAL

- [ ] ¿Verificaste que `EMAIL_HOST_PASSWORD` está **SIN espacios** en Railway?
- [ ] ¿Hiciste Redeploy después de actualizar variables?
- [ ] ¿Generaste un nuevo informe OT para probar?
- [ ] ¿Recibiste el PDF por email?
- [ ] ¿Ves en los logs "✅ Email enviado EXITOSAMENTE"?

---

## ✅ PRÓXIMO PASO

**Genera un nuevo informe OT y verifica que todo funciona.**

Si ves el email con PDF en tu bandeja → **¡TODO ESTÁ CONFIGURADO CORRECTAMENTE!**

