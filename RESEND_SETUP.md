# Configuración de Resend para Email en Railway

## 📧 ¿Qué es Resend?

Resend es un servicio moderno de envío de emails diseñado para desarrolladores. Es más simple que SendGrid y funciona perfectamente con Railway.

**Ventajas:**
- ✅ Funciona en Railway (sin bloqueos de red)
- ✅ Simple de configurar (solo 1 API key)
- ✅ Gratuito hasta 100 emails/día
- ✅ Mejor deliverability que Gmail SMTP
- ✅ Soporte para dominio personalizado

---

## 🚀 Pasos para Configurar

### 1. Crear Cuenta en Resend

1. Ir a https://resend.com
2. Click en **"Get Started"** (es gratuito)
3. Registrarse con email
4. Verificar email en bandeja de entrada
5. Ingresar al dashboard

### 2. Generar API Key

1. En el dashboard, ir a **Settings** → **API Keys**
2. Click en **Create API Key**
3. Copiar la key (comienza con `re_...`)
4. Guardar en un lugar seguro

Ejemplo:
```
re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Agregar Variable de Entorno en Railway

1. Ir a Railway: https://railway.app
2. Seleccionar proyecto **Gestion Thermovolt**
3. Ir a pestaña **Variables**
4. Click en **New Variable**
5. Nombre: `RESEND_API_KEY`
6. Valor: Pegar la API key de Resend (re_...)
7. Click en **Save**

**Resultado esperado:**
```
RESEND_API_KEY = re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. Redeploy en Railway

1. En Railway, ir a pestaña **Deployments**
2. Click en **Redeploy** en el deployment actual
3. Esperar a que se complete (verás "STARTUP: launching gunicorn")

### 5. Probar Cierre de OT

1. Acceder a la aplicación
2. Crear u seleccionar una Orden de Trabajo (OT)
3. Click en **Cerrar OT**
4. Llenar el formulario y enviar
5. Revisar logs en Railway - deberías ver:
   ```
   Intentando enviar email a: ['tecnico@email.com']
   Email enviado exitosamente
   ```

6. Revisar email en bandeja de entrada del técnico

---

## 🔧 Configuración en settings.py

El código ya está configurado. La aplicación hace esto automáticamente:

```python
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
if RESEND_API_KEY:
    EMAIL_BACKEND = 'django_resend.backends.ResendBackend'
else:
    # Fallback a Gmail
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
```

**Significa:**
- Si `RESEND_API_KEY` está configurado → Usa Resend ✅
- Si no está configurado → Usa Gmail (fallback)

---

## 📊 Monitoreo

### Ver logs de email en Railway

1. Ir a Railway → Proyecto
2. Click en **Logs**
3. Buscar por:
   - `"Email enviado exitosamente"` = Email enviado ✅
   - `"Error enviando email"` = Email falló ❌

### Verificar en Dashboard de Resend

1. Ir a https://resend.com/emails
2. Ver lista de emails enviados
3. Click en cualquiera para ver detalles

---

## ❓ Troubleshooting

### Problema: "Email enviado pero no llega"

**Solución:**
1. Revisar carpeta Spam
2. Agregar `noreply@resend.dev` a contactos
3. En Resend dashboard, ir a **Domains** y configurar dominio personalizado (opcional)

### Problema: "Error enviando email"

**Soluciones:**
1. Verificar que API key está correcta en Railway
2. Verificar que el email del técnico es válido
3. Revisar logs en Railway para ver error específico

### Problema: "Network is unreachable" (después de actualizar)

**Solución:**
- ✅ Eso significa que el fallback a Gmail se activó
- Si RESEND_API_KEY no está configurado, usará Gmail (que puede fallar en Railway)
- Verificar que RESEND_API_KEY está en Railway Variables

---

## 💡 Mejores Prácticas

1. **Mantener API Key segura**
   - Nunca comitear la key en Git
   - Solo en Railway Variables o archivo `.env` local (no comiteado)

2. **Usar dominio personalizado** (opcional)
   - Para mayor profesionalismo
   - En Resend: Settings → Domains → Add Domain
   - Configurar MX records en tu dominio

3. **Monitorear entrega**
   - Revisar logs regularmente
   - Usar dashboard de Resend para estadísticas

---

## 📝 Resumen

| Paso | Estado | Detalles |
|------|--------|---------|
| django-resend instalado | ✅ | requirements.txt actualizado |
| settings.py configurado | ✅ | EMAIL_BACKEND condicional |
| Crear Resend account | ⏳ | https://resend.com |
| Generar API key | ⏳ | En Resend dashboard |
| Railway variable | ⏳ | RESEND_API_KEY = re_... |
| Redeploy en Railway | ⏳ | Click en Redeploy |
| Probar OT closure | ⏳ | Revisar logs y email |

---

## 📞 Soporte

**Si algo no funciona:**

1. Revisar logs en Railway (pestaña Logs)
2. Verificar RESEND_API_KEY en Railway Variables
3. Probar en local primero con Gmail
4. Revisar documentación: https://resend.com/docs

---

**¡Listo! Sigue los pasos y tu aplicación enviará emails correctamente desde Railway.** 🎉
