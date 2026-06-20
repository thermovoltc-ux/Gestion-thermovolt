#!/usr/bin/env python
"""
Script para validar SendGrid API Key y configuración en Railway

Uso:
  python validate_sendgrid.py

Requiere variables de entorno:
  SENDGRID_API_KEY: Tu SendGrid API Key (comienza con SG.)
  SENDGRID_FROM_EMAIL: Email verificado en SendGrid (default: thermovoltc@gmail.com)
"""

import os
import sys
import json
import requests

# Configuración desde variables de entorno
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', 'thermovoltc@gmail.com')

print("=" * 70)
print("🧪 VALIDACIÓN DE SENDGRID")
print("=" * 70)

# 0. Verificar que la API Key está configurada
if not SENDGRID_API_KEY:
    print("\n❌ ERROR: SENDGRID_API_KEY no está configurada")
    print("\nPara usar este script, establece:")
    print("  Windows (PowerShell):")
    print("    $env:SENDGRID_API_KEY = 'SG.xxxxxx...'")
    print("    python validate_sendgrid.py")
    print("\n  Linux/Mac:")
    print("    export SENDGRID_API_KEY='SG.xxxxxx...'")
    print("    python validate_sendgrid.py")
    sys.exit(1)

print(f"\n✓ SENDGRID_API_KEY cargada desde variables de entorno")
print(f"  Email FROM: {SENDGRID_FROM_EMAIL}")

# 1. Verificar API Key
print("\n✓ Paso 1: Validar formato de API Key")
if SENDGRID_API_KEY.startswith("SG."):
    print(f"  ✓ API Key válida: {SENDGRID_API_KEY[:10]}...{SENDGRID_API_KEY[-5:]}")
    print(f"  ✓ Longitud: {len(SENDGRID_API_KEY)} caracteres")
else:
    print("  ❌ API Key no empieza con 'SG.'")
    sys.exit(1)

# 2. Hacer test a SendGrid
print("\n✓ Paso 2: Conectar a SendGrid API")

headers = {
    "Authorization": f"Bearer {SENDGRID_API_KEY}",
    "Content-Type": "application/json"
}

# Test 1: Obtener información de la cuenta
print("  - Obteniendo información de la cuenta...")
response = requests.get(
    "https://api.sendgrid.com/v3/user/profile",
    headers=headers,
    timeout=10
)

print(f"  Status Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("  ✅ Autenticación exitosa")
    print(f"    - Email: {data.get('email', 'N/A')}")
    print(f"    - Nombre: {data.get('first_name', '')} {data.get('last_name', '')}")
else:
    print(f"  ❌ Error: Status {response.status_code}")
    try:
        print(f"  Response: {response.text}")
    except Exception as e:
        print(f"  Error parsing response: {e}")
    sys.exit(1)

# 3. Verificar saldo de créditos
print("\n✓ Paso 3: Verificar créditos/límites")
response = requests.get(
    "https://api.sendgrid.com/v3/user/account",
    headers=headers,
    timeout=10
)

if response.status_code == 200:
    data = response.json()
    print("  ✅ Información de cuenta obtenida")
    print(f"    - Tipo de plan: {data.get('type', 'N/A')}")
    print(f"    - Estatus: {data.get('status', 'N/A')}")
    if 'credits' in data:
        print(f"    - Créditos: {data.get('credits', 'N/A')}")
    print(f"    - Email (account): {data.get('email', 'N/A')}")
else:
    print(f"  ⚠️  No se pudo obtener información de créditos (Status: {response.status_code})")
    if response.status_code == 401:
        print("    ERROR 401: Posible API Key inválida")

# 4. Verificar que el email "from" está verificado
print("\n✓ Paso 4: Verificar email 'from' en SendGrid")
response = requests.get(
    "https://api.sendgrid.com/v3/verified_senders",
    headers=headers,
    timeout=10
)

if response.status_code == 200:
    data = response.json()
    senders = data.get('results', [])
    verified_emails = [s.get('from_email', '').lower() for s in senders if s.get('verified')]
    
    if SENDGRID_FROM_EMAIL.lower() in verified_emails:
        print(f"  ✅ Email '{SENDGRID_FROM_EMAIL}' está verificado en SendGrid")
    else:
        print(f"  ❌ Email '{SENDGRID_FROM_EMAIL}' NO está verificado en SendGrid")
        print(f"     Emails verificados: {verified_emails}")
        print(f"     ACCIÓN: Verifica en https://app.sendgrid.com/settings/sender_auth")
else:
    print(f"  ⚠️  No se pudo obtener lista de senders (Status: {response.status_code})")

# 5. Hacer un test de envío (sin realmente enviar)
print("\n✓ Paso 5: Test de estructura de email")
test_payload = {
    "personalizations": [
        {
            "to": [{"email": "test@example.com"}],
            "subject": "Test Email"
        }
    ],
    "from": {"email": SENDGRID_FROM_EMAIL},
    "content": [{"type": "text/plain", "value": "This is a test email from validation script."}]
}

response = requests.post(
    "https://api.sendgrid.com/v3/mail/send",
    json=test_payload,
    headers=headers,
    timeout=10
)

if response.status_code in (200, 202):
    print("  ✅ Email enviado exitosamente (REAL)")
    print(f"     Status: {response.status_code}")
elif response.status_code == 400:
    error_data = response.json()
    print(f"  ⚠️  Error 400 (Validación): {error_data}")
    if 'errors' in error_data:
        for error in error_data['errors']:
            print(f"     - {error.get('message', 'Unknown error')}")
elif response.status_code == 401:
    print(f"  ❌ ERROR 401: Authentication failed")
    print(f"     Response: {response.text}")
else:
    print(f"  ⚠️  Status {response.status_code}: {response.text}")

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)
print("""
PRÓXIMOS PASOS:

1. Si ves ✅ en todos los tests:
   - Ya tienes la API Key correcta
   - Configura estas variables en Railway:
     SENDGRID_API_KEY: [Tu API Key - comienza con SG.]
     SENDGRID_FROM_EMAIL: thermovoltc@gmail.com
   - Redeploy tu aplicación en Railway
   - Prueba generando un nuevo informe OT

2. Si ves ❌ "Email no verificado":
   - Ve a https://app.sendgrid.com/settings/sender_auth
   - Crea un nuevo "Verified Sender" para thermovoltc@gmail.com
   - Verifica el email desde tu bandeja de entrada
   - Espera 5-10 minutos a que se propague

3. Si ves ❌ "ERROR 401":
   - La API Key podría estar inválida
   - Crea una NEW API Key en SendGrid
   - Reemplaza la antigua con la nueva en Railway

4. El código ahora detecta Railway y usa ReportLab directamente
   (sin intentar LibreOffice) para garantizar que los PDFs se generen.
""")
