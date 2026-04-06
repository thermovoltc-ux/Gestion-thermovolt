# RESUMEN EJECUTIVO - Exploración Codebase

## 🎯 RESPUESTAS DIRECTAS A TUS PREGUNTAS

### 1️⃣ ¿Dónde está el Kanban/tablero de tarjetas?

**Archivo:** `gestion_mantenimiento/solicitudes/templates/solicitudes/gestion_ot.html`

**Estructura HTML:**
```html
<div class="kanban-container">
  <div class="kanban-column" id="solicitudes">...</div>
  <div class="kanban-column" id="ot_en_proceso">...</div>
  <div class="kanban-column" id="ot_en_revision">...</div>
  <div class="kanban-column" id="ot_finalizada">...</div>
</div>
```

**Tarjetas:**
```html
<div class="kanban-card" id="card-{{ id }}" draggable="true" data-numero-activo="{{ id }}">
  <h3>Solicitud 00{{ id }}</h3>
  <h4>PDV: {{ pdv }}</h4>
  <p>{{ descripcion }}</p>
  <small>{{ fecha }}</small>
</div>
```

---

### 2️⃣ ¿Dónde está la estructura de lista?

**Archivo:** `gestion_mantenimiento/solicitudes/templates/solicitudes/lista_solicitudes.html`

**Estructura:**
```html
<table>
  <thead>
    <tr>
      <th>N°solicitud</th>
      <th>CO</th>
      <th>Ubicación</th>
      <th>Fecha de Creación</th>
      <th>Solicitado por</th>
      <th>Equipo</th>
      <th>Prioridad</th>
      <th>Estado</th>
    </tr>
  </thead>
  <tbody>
    <!-- Filas generadas con Django template -->
  </tbody>
</table>
```

---

### 3️⃣ ¿Dónde está el calendario?

**Archivo:** `gestion_mantenimiento/solicitudes/templates/solicitudes/fracttal.html`

**Tipo:** Componente compilado React/JavaScript (no es un template Django puro)

**Implementación Real:** `static/js/calendarView.js`

```javascript
let calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    events: eventos_desde_solicitudes,
    eventClick: openSolicitudModal
});
```

**Estados/Colores:**
- Solicitado → Gray
- En Proceso → Orange
- En Revisión → Blue
- Finalizada → Green

---

### 4️⃣ ¿Dónde se maneja el desplegable/modal de información?

**Archivo:** `static/js/modals.js`

**Función:** `openSolicitudModal(consecutivo)`

```javascript
function openSolicitudModal(consecutivo) {
    fetch(`/Gestion_ot/detalles_solicitud/${consecutivo}/`)
        .then(response => response.json())
        .then(data => {
            // Renderiza datos en modal
            document.getElementById('solicitudModal').style.display = 'block';
        });
}
```

**HTML Modal:**
```html
<div id="solicitudModal" class="modal">
  <div class="modal-content">
    <div id="asignacionInfo">
      <!-- Detalles de solicitud -->
    </div>
    <div id="cierreOTInfo">
      <!-- Detalles de OT (técnico, fecha, etc) -->
    </div>
    <button id="finalizarOTBtn">Finalizar OT</button>
  </div>
</div>
```

---

### 5️⃣ ¿Dónde está la lógica de asignar técnicos?

**Flujo:**

1. **Frontend:** Drag-drop tarjeta a "OT en Proceso"
   - Archivo: `static/js/kanbanColumns.js`
   - Función: `drop(event)` → detecta `column.id === "ot_en_proceso"`

2. **Modal aparece:** `openModal(solicitud)`
   - Archivo: `static/js/modals.js`
   - Muestra inputs: fecha_actividad + tecnico_asignado

3. **Submit:**
   ```javascript
   fetch('/Gestion_ot/actualizar_estado_solicitud/', {
       method: 'POST',
       body: JSON.stringify({
           numero: 123,
           estado: "en proceso",
           tecnico: "Juan González",
           fecha: "2026-04-02T14:00:00"
       })
   })
   ```

4. **Backend:** `Gestion_ot/views.py`
   ```python
   @csrf_exempt
   def actualizar_estado_solicitud(request):
       # Actualiza Solicitud y crea OrdenTrabajo
       # Retorna: {"status": "ok"}
   ```

5. **Resultado:** 
   - Tarjeta se mueve a "OT en Proceso"
   - BD actualizada: `OrdenTrabajo` con técnico y fecha

---

## 🔗 EVENTOS Y CLICK HANDLERS PRINCIPALES

| Evento | Archivo | Función | Acción |
|--------|---------|---------|--------|
| `ondragstart` | gestion_ot.html | `drag(event)` | Inicia arrastre |
| `ondragover` | gestion_ot.html | `allowDrop(event)` | Permite soltar |
| `ondrop` | gestion_ot.html | `drop(event)` | Suelta en columna |
| `click` kanban-card | modals.js | `openSolicitudModal()` | Abre detalles |
| `touchstart` | kanbanColumns.js | `touchStart(event)` | Soporte mobile |
| `submit` OrdenTrabajoForm | modals.js | POST /actualizar_estado | Asigna técnico |
| `click` finalizarOTBtn | modals.js | POST /actualizar_estado | Finaliza OT |
| eventClick (FullCalendar) | calendarView.js | `openSolicitudModal()` | Click calendario |

---

## 📡 URLs/ENDPOINTS CLAVE

### Obtener Detalles de Solicitud
```
GET /Gestion_ot/detalles_solicitud/<consecutivo>/

Respuesta:
{
  "consecutivo": 123,
  "pdv": "Tienda Centro",
  "descripcion": "Equipo no enciende",
  "estado": "en proceso",
  "ordenes_trabajo": [
    {
      "tecnico_asignado": "Juan González",
      "fecha_actividad": "2026-04-02T14:00:00Z",
      ...
    }
  ]
}
```

### Actualizar Estado + Asignar Técnico
```
POST /Gestion_ot/actualizar_estado_solicitud/

Headers:
  Content-Type: application/json
  X-CSRFToken: <token>

Body:
{
  "numero": 123,
  "estado": "en proceso",
  "tecnico": "Juan González",
  "fecha": "2026-04-02T14:00:00"
}

Respuesta:
{
  "status": "ok",
  "message": "Solicitud y Orden de Trabajo actualizadas correctamente"
}
```

### Renderizar Kanban
```
GET /Gestion_ot/gestion_ot/

Query Params (opcionales):
  - fecha_inicio: YYYY-MM-DD
  - fecha_fin: YYYY-MM-DD
  - pdv: Ubicación

Context Django:
{
  'solicitudes': QuerySet[Solicitud],
  'ordenes_trabajo': QuerySet[OrdenTrabajo],
  'tecnicos': QuerySet[User],
  'pdvs': list,
  ...
}
```

---

## 🎨 MANEJO DE ESTADOS

### Tabla de Estados
```
┌─────────────────────────────────────────────────────────────┐
│ Estado          │ Columna      │ Color    │ Descripción    │
├─────────────────────────────────────────────────────────────┤
│ solicitado      │ solicitudes  │ Gray     │ Inicial        │
│ en proceso      │ ot_en_proceso│ Orange   │ Con técnico    │
│ en revision     │ ot_en_revision │ Blue   │ Revisando      │
│ finalizada      │ ot_finalizada  │ Green   │ Completada     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 ARCHIVOS IMPORTANTES

```
gestion_mantenimiento/
├── solicitudes/
│   └── templates/solicitudes/
│       ├── gestion_ot.html              ← KANBAN PRINCIPAL
│       ├── lista_solicitudes.html       ← VISTA LISTA
│       └── fracttal.html                ← CALENDARIO EXTERNO
│
├── Gestion_ot/
│   ├── models.py                        ← OrdenTrabajo, Estado, CierreOt
│   ├── views.py                         ← actualizar_estado_solicitud()
│   └── forms.py                         ← OrdenTrabajoForm
│
└── static/js/
    ├── gestion_ot.js                    ← ENTRY POINT JS
    ├── kanbanColumns.js                 ← DRAG-DROP LOGIC
    ├── modals.js                        ← MODAL DETALLES + ASIGNACIÓN
    ├── calendarView.js                  ← FULLCALENDAR
    ├── solicitudes.js                   ← CREAR SOLICITUD
    ├── csrf.js                          ← UTILIDADES CSRF
    └── kanban.js                        ← FUNCIONES BÁSICAS
```

---

## 🔄 MODELO CONCEPTUAL DE DATOS

```
Solicitud (1)
    ├─ campo: tecnico_asignado (CharField)      ← Nombre técnico
    ├─ campo: fecha_actividad (DateTimeField)   ← Fecha asignación
    ├─ campo: estado (ForeignKey → Estado)
    │
    └─ Relación: 1:N con OrdenTrabajo
           │
           └─ OrdenTrabajo
              ├─ tecnico_asignado (CharField)
              ├─ fecha_actividad (DateTimeField)
              ├─ estado (ForeignKey → Estado)
              │
              └─ Relación: 1:1 con CierreOt
                     │
                     └─ CierreOt
                        ├─ tipo_mantenimiento
                        ├─ materiales_utilizados
                        ├─ [Relación 1:N] ImagenCierreOt
                        └─ se_soluciono (Boolean)
```

---

## 🚀 FLUJO RÁPIDO DE ASIGNACIÓN

```
┌─ Usuario ve tarjeta en "Solicitudes"
├─ Arrastra a "OT en Proceso"
│  ├─ drop(event) detecta columna
│  ├─ openModal(solicitud) abre modal
│  └─ Muestra: fecha + técnico
│
├─ Usuario completa datos
├─ Envía formulario
│  ├─ POST /Gestion_ot/actualizar_estado_solicitud/
│  ├─ Backend crea OrdenTrabajo
│  └─ Retorna {"status": "ok"}
│
├─ Frontend actualiza:
│  ├─ Mueve tarjeta visualmente
│  ├─ Cierra modal
│  └─ Muestra confirmación
│
└─ Fin: Tarjeta en "OT en Proceso" con técnico asignado
```

---

## 📊 COMPONENTES PRINCIPALES

### Frontend (JavaScript)
- **kanbanColumns.js** - Drag-drop, manejo de columnas
- **modals.js** - Abrir/cerrar modales, asignar técnico
- **calendarView.js** - FullCalendar inicialización
- **solicitudes.js** - Crear nuevas solicitudes

### Backend (Django)
- **Solicitud model** - Solicitud base
- **OrdenTrabajo model** - OT con técnico y fecha
- **actualizar_estado_solicitud(request)** - API POST principal

### Database
- **4 Estados** - solicitado, en proceso, en revisión, finalizada
- **3 Tablas principales** - Solicitud, OrdenTrabajo, CierreOt

---

## ✅ RESUMEN FINAL

| Aspecto | Ubicación | Tecnología |
|---------|-----------|-----------|
| **Kanban** | gestion_ot.html | HTML5 Drag-Drop |
| **Lista** | lista_solicitudes.html | HTML Table |
| **Calendario** | calendarView.js | FullCalendar 5+ |
| **Modal Info** | modals.js | Vanilla JS |
| **Asignar Técnico** | kanbanColumns.js + modals.js | Drag-Drop + Modal Form |
| **Backend** | Gestion_ot/views.py | Django REST (JSON) |
| **BD** | OrdenTrabajo model | Django ORM |

---

## 📖 DOCUMENTOS CREADOS

He generado 3 documentos detallados en tu carpeta raíz:

1. **EXPLORACION_CODEBASE.md** - Exploración completa y detallada
2. **CODIGO_SNIPPETS_Y_ENDPOINTS.md** - Snippets de código y endpoints
3. **DIAGRAMAS_ARQUITECTURA.md** - Diagramas visuales ASCII
4. **RESUMEN_EJECUTIVO.md** - Este documento (respuestas rápidas)

**Ubicación:** `c:\Users\Juan Esteban\Downloads\gestion_mantenimiento (1)\`
