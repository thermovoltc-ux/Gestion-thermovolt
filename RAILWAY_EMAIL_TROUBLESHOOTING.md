# 🚂 Railway: Restricciones de Red y Soluciones

## Problema Identificado

Railway **no permite conexiones SMTP salientes directas** al puerto 587. Esto es una restricción común en muchos contenedores cloud por razones de seguridad.

**Error observado:**
```
OSError: [Errno 101] Network is unreachable
```

---

## ✅ SOLUCIONES IMPLEMENTADAS

### 1. **Backend Personalizado con Múltiples Puertos** ✓

Creé `custom_email_backends.py` que intenta en orden:
- Puerto 587 (TLS) - el estándar
- Puerto 465 (SSL) - alternativa común
- Puerto 25 (sin encriptación) - último recurso

Si todos fallan, crea logs locales para auditoría.

**Ventaja**: Automático - no requiere cambios en Railway

### 2. **Logging Mejorado** ✓

Ahora verás exactamente qué puerto se intentó y por qué falló.

---

## 🚀 PASOS PARA IMPLEMENTAR

### 1. Redeploy en Railway

El código nuevo ya está en GitHub. Railway lo descargará automáticamente al hacer redeploy.

### 2. Genera un nuevo informe OT

Deberías ver en los logs:

**Si funciona con puerto 465:**
```
📡 Intentando conexión SMTP en puerto 587...
⚠️  Puerto 587 falló: OSError: Network is unreachable
📡 Intentando conexión SMTP en puerto 465...
   - Usando SSL para puerto 465
✅ Conexión SMTP establecida en puerto 465
📬 ENVIANDO VIA SMTP:
✅ Email enviado EXITOSAMENTE via SMTP
```

**Si todos fallan:**
```
❌ No se pudo conectar a SMTP en ningún puerto (587, 465, 25)
   Railway podría tener restricciones de red saliente
💾 Intentando guardar emails localmente como fallback...
⚠️  1 emails guardados en logs como fallback
```

---

## 🆘 SI AÚN NO FUNCIONA

Si Railway sigue bloqueando todos los puertos SMTP, las opciones son:

### A) **Usar Mailgun** (Recomendado para Railway)

Mailgun es muy usado en Railway y funciona confiablemente:

1. Crea cuenta en https://mailgun.com (Plan free: 5000 emails/mes)
2. Obtén tu API Key
3. Instala: `pip install django-anymail[mailgun]`
4. Configura en settings.py

### B) **Usar SendGrid Pago**

Tu plan free está agotado, pero el plan inicial ($20/mes) daría créditos.

### C) **Guardar en Cola Local**

Agregar Celery/Redis para encolar emails y enviarlos periódicamente cuando haya conexión.

---

## 📊 RESUMEN DE LO QUE HICIMOS

✅ **Archivo nuevo**: `custom_email_backends.py`
- Backend que soporta múltiples puertos
- Fallback a logs locales si SMTP falla
- Logging detallado de cada intento

✅ **settings.py actualizado**
- Usa el nuevo backend: `MultiPortEmailBackend`
- Intenta puertos: 587 → 465 → 25

✅ **views.py mejorado**
- Mejor logging para diagnosticar fallos

---

## 🔍 PRÓXIMO PASO

**Haz Redeploy en Railway y genera un informe OT**

Comparte los logs exactos que ves - así sabemos si:
1. Puerto 465 funcionó ✓
2. Todos los puertos fallaron ❌ (necesitamos Mailgun/SendGrid pago)

