# Snippets de Código Importante - Gestion OT

## 📍 ESTRUCTURA COMPLETA DE KANBAN-CARD

### HTML Template (gestion_ot.html)
```html
<!-- Tarjeta con todos los atributos -->
<div class="kanban-card" 
     id="card-{{ solicitud.numero_activo }}"           <!-- ID único para drag-drop -->
     draggable="true"                                   <!-- Habilita drag-drop -->
     ondragstart="drag(event)"                          <!-- Handler inicio arrastre -->
     data-numero-activo="{{ solicitud.consecutivo }}"  <!-- Almacena consecutivo -->
     style="cursor: move;">
    
    <!-- Contenido visible -->
    <h3>Solicitud 00{{ solicitud.numero_activo }}</h3>
    <h4>PDV: {{ solicitud.PDV }}</h4>
    <p>{{ solicitud.descripcion_problema|slice:":50" }}...</p>
    <small>{{ solicitud.fecha_creacion|date:"Y-m-d H:i" }}</small>
</div>
```

### CSS Relevante
```css
.kanban-card {
    padding: 15px;
    margin: 10px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    cursor: move;
    transition: opacity 0.2s;
    user-select: none;
}

.kanban-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.kanban-card[draggable="true"]:active {
    opacity: 0.7;
}

.kanban-column {
    flex: 1;
    min-width: 250px;
    background: #f5f5f5;
    padding: 20px;
    border-radius: 8px;
    border: 2px dashed #ccc;
}

.kanban-column.drag-over {
    border-color: #4CAF50;
    background: #e8f5e9;
}
```

---

## 🔧 JAVASCRIPT - FUNCIONES CLAVE

### kanbanColumns.js - Drag-Drop Desktop

```javascript
// Cuando usuario inicia arrastre
function drag(event) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", event.target.id);
    // ID será: "card-123" donde 123 es el consecutivo
}

// Cuando arrastra sobre una columna
function allowDrop(event) {
    event.preventDefault();  // Necesario para permitir drop
    event.dataTransfer.dropEffect = "move";
    
    // Visual: agregar clase de highlighting
    event.target.closest('.kanban-column')?.classList.add('drag-over');
}

// Cuando suelta en una columna
function dropDesktop(event) {
    event.preventDefault();
    
    // Remover clase visual
    event.target.closest('.kanban-column')?.classList.remove('drag-over');
    
    const cardId = event.dataTransfer.getData("text/plain");
    const card = document.getElementById(cardId);
    const column = event.target.closest('.kanban-column');
    
    if (!card || !column) return;
    
    // LÓGICA ESPECIAL: Si suelta en "OT en Proceso", abre modal para asignar técnico
    if (column.id === "ot_en_proceso") {
        const numeroSolicitud = cardId.split('-')[1];  // Extrae "123" de "card-123"
        
        // Abre modal de asignación de técnico
        openModal({ 
            numero: numeroSolicitud,
            descripcion: card.querySelector('p').textContent
        });
        
        return;  // NO mueve la tarjeta aún
    }
    
    // Para otras columnas, mueve la tarjeta normalmente
    column.appendChild(card);
    updateSolicitudState(card, column.id);
}

// Alias para compatibilidad
function drop(event) {
    return dropDesktop(event);
}
```

### Touch Support (Mobile)

```javascript
let draggedElement = null;

function touchStart(event) {
    draggedElement = event.target.closest('.kanban-card');
    if (draggedElement) {
        draggedElement.style.opacity = '0.5';
        draggedElement.style.transform = 'scale(1.05)';
    }
}

function touchMove(event) {
    if (draggedElement) {
        event.preventDefault();
    }
}

function touchEnd(event) {
    if (!draggedElement) return;
    
    draggedElement.style.opacity = '1';
    draggedElement.style.transform = 'scale(1)';
    
    const touch = event.changedTouches[0];
    const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
    const column = dropTarget?.closest('.kanban-column');
    
    if (column) {
        if (column.id === "ot_en_proceso") {
            const numeroSolicitud = draggedElement.id.split('-')[1];
            openModal({ numero: numeroSolicitud });
            return;
        }
        
        column.appendChild(draggedElement);
        updateSolicitudState(draggedElement, column.id);
    }
    
    draggedElement = null;
}

// Registrar listeners
document.addEventListener('touchstart', touchStart, { passive: false });
document.addEventListener('touchmove', touchMove, { passive: false });
document.addEventListener('touchend', touchEnd, { passive: false });
```

### Actualizar Estado en Backend

```javascript
function updateSolicitudState(card, columnId) {
    const numeroSolicitud = card.id.split('-')[1];
    
    // Mapeo: ID columna → Estado
    const estadoMap = {
        'solicitudes': 'solicitado',
        'ot_en_proceso': 'en proceso',
        'ot_en_revision': 'en revision',
        'ot_finalizada': 'finalizada'
    };
    
    const nuevoEstado = estadoMap[columnId];
    
    fetch('/Gestion_ot/actualizar_estado_solicitud/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            numero: numeroSolicitud,
            estado: nuevoEstado,
            tecnico: null,
            fecha: null
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Error en actualización');
        return response.json();
    })
    .then(data => {
        console.log('✓ Estado actualizado:', nuevoEstado);
    })
    .catch(error => {
        console.error('✗ Error:', error);
        // Revertir movimiento visual
        card.parentElement.appendChild(card);
    });
}
```

---

## 📋 MODALS.JS - APERTURA DE MODAL

### Abrir Modal de Detalles

```javascript
function openSolicitudModal(consecutivo) {
    // 1. Hacer fetch de datos complementarios
    fetch(`/Gestion_ot/detalles_solicitud/${consecutivo}/`)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            // 2. Función auxiliar para actualizar elementos HTML
            const actualizarElemento = (id, valor) => {
                const elemento = document.getElementById(id);
                if (elemento) {
                    if (valor) {
                        elemento.textContent = valor;
                        elemento.parentElement.style.display = 'block';
                    } else {
                        elemento.textContent = '';
                        elemento.parentElement.style.display = 'none';
                    }
                }
            };
            
            // 3. Llenar datos de solicitud
            actualizarElemento('modalNumeroActivo', data.consecutivo);
            actualizarElemento('modalPDV', data.pdv);
            actualizarElemento('modalDescripcion', data.descripcion);
            actualizarElemento('modalFechaCreacion', data.fecha_creacion);
            actualizarElemento('modalEstado', data.estado);
            
            // 4. Llenar datos de orden de trabajo (si existen)
            if (data.ordenes_trabajo && data.ordenes_trabajo.length > 0) {
                const ot = data.ordenes_trabajo[0];
                actualizarElemento('modalTecnicoAsignado', ot.tecnico_asignado);
                actualizarElemento('modalFechaActividad', ot.fecha_actividad);
                actualizarElemento('modalTipoMantenimiento', ot.tipo_mantenimiento);
                document.getElementById('asignacionInfo').style.display = 'block';
            } else {
                document.getElementById('asignacionInfo').style.display = 'none';
            }
            
            // 5. Mostrar botón de finalizar solo si está en revisión
            const finalizarBtn = document.getElementById('finalizarOTBtn');
            if (data.estado === 'en revision') {
                finalizarBtn.style.display = 'block';
            } else {
                finalizarBtn.style.display = 'none';
            }
            
            // 6. Abrir modal
            document.getElementById('solicitudModal').style.display = 'block';
        })
        .catch(error => console.error('Error:', error));
}

// Disponible globalmente
window.openSolicitudModal = openSolicitudModal;
```

### Abrir Modal de Asignación de Técnico

```javascript
function openModal(solicitud) {
    // Prellenar campos del modal
    document.getElementById("consecutivo").value = solicitud.numero;
    document.getElementById("fecha_actividad").value = "";  // Vacío para usuario
    document.getElementById("tecnico_asignado").value = "";  // Vacío para usuario
    
    // Mostrar modal
    document.getElementById("tecnicoModal").style.display = "block";
}

window.openModal = openModal;

function closeModal() {
    document.getElementById("tecnicoModal").style.display = "none";
}

window.closeModal = closeModal;
```

### HTML de Modal de Técnico

```html
<div id="tecnicoModal" class="modal" style="display: none;">
    <div class="modal-content">
        <span class="close" onclick="closeModal()">&times;</span>
        <h2>Asignar Técnico a Orden de Trabajo</h2>
        
        <form id="OrdenTrabajoForm">
            <!-- Campo oculto para el número de solicitud -->
            <input type="hidden" id="consecutivo" name="consecutivo">
            
            <!-- Fecha de la Actividad -->
            <div class="form-group">
                <label for="fecha_actividad">Fecha de la Actividad:</label>
                <input type="datetime-local" 
                       id="fecha_actividad" 
                       name="fecha_actividad" 
                       required
                       placeholder="Seleccione fecha y hora">
                <small>Requerido para crear la OT</small>
            </div>
            
            <!-- Nombre del Técnico -->
            <div class="form-group">
                <label for="tecnico_asignado">Nombre del Técnico:</label>
                <input type="text" 
                       id="tecnico_asignado" 
                       name="tecnico_asignado" 
                       required
                       placeholder="Ej: Juan González"
                       autocomplete="off">
                <small>El técnico responsable de ejecutar la OT</small>
            </div>
            
            <!-- Estado (hidden, siempre = "en proceso") -->
            <input type="hidden" 
                   id="estado" 
                   name="estado" 
                   value="en proceso">
            
            <!-- Botones -->
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Asignar Técnico</button>
                <button type="button" 
                        class="btn btn-secondary" 
                        onclick="closeModal()">Cancelar</button>
            </div>
        </form>
        
        <div id="modalError" style="color: red; display: none; margin-top: 10px;">
            Error al actualizar. Intente de nuevo.
        </div>
    </div>
</div>
```

### Manejador de Envío de Formulario

```javascript
document.getElementById("OramenTrabajoForm").addEventListener("submit", function(event) {
    event.preventDefault();
    
    // Recopilar datos del formulario
    const numeroSolicitud = document.getElementById("consecutivo").value;
    const nombreTecnico = document.getElementById("tecnico_asignado").value;
    const fechaActividad = document.getElementById("fecha_actividad").value;
    const estado = document.getElementById("estado").value;
    
    // Validaciones
    if (!numeroSolicitud || !nombreTecnico || !fechaActividad) {
        document.getElementById("modalError").textContent = "Todos los campos son requeridos";
        document.getElementById("modalError").style.display = "block";
        return;
    }
    
    // Convertir fecha local a ISO string
    const fecha = new Date(fechaActividad).toISOString();
    
    // Enviar al server
    fetch('/Gestion_ot/actualizar_estado_solicitud/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            numero: numeroSolicitud,
            estado: estado,
            tecnico: nombreTecnico,
            fecha: fecha
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Error en la actualización');
        return response.json();
    })
    .then(data => {
        console.log('✓ Técnico asignado exitosamente');
        
        // Mover tarjeta visualmente
        const targetColumn = document.getElementById("ot_en_proceso");
        const card = document.getElementById("card-" + numeroSolicitud);
        if (card) {
            targetColumn.appendChild(card);
        }
        
        // Cerrar modal
        closeModal();
        
        // Mostrar mensaje de éxito
        alert(`Técnico ${nombreTecnico} asignado a la OT`);
    })
    .catch((error) => {
        console.error('✗ Error:', error);
        document.getElementById("modalError").textContent = "Error: " + error.message;
        document.getElementById("modalError").style.display = "block";
    });
});
```

---

## 🔌 ENDPOINTS DJANGO

### 1. Listar OT con Filtros

```
URL: /Gestion_ot/gestion_ot/
Método: GET
Parámetros Query:
  - fecha_inicio: YYYY-MM-DD
  - fecha_fin: YYYY-MM-DD
  - pdv: Ubicación del PDV
  
Respuesta: HTML con contexto:
{
  'solicitudes': QuerySet[Solicitud],
  'ordenes_trabajo': QuerySet[OrdenTrabajo],
  'tecnicos': QuerySet[User],
  'pdvs': list de PDV únicos,
  'filtro_fecha_inicio': date,
  'filtro_fecha_fin': date,
  'filtro_pdv': string
}
```

### 2. Obtener Detalles de Solicitud

```
URL: /Gestion_ot/detalles_solicitud/<consecutivo>/
Método: GET
Path Params:
  - consecutivo: int (número de solicitud)

Respuesta JSON:
{
  "consecutivo": 123,
  "pdv": "Tienda Centro",
  "descripcion": "Equipo no enciende",
  "fecha_creacion": "2026-04-01T10:00:00Z",
  "estado": "en proceso",
  "ordenes_trabajo": [
    {
      "id": 5,
      "tecnico_asignado": "Juan González",
      "fecha_actividad": "2026-04-02T14:00:00Z",
      "tipo_mantenimiento": "Preventivo",
      "materiales_utilizados": "Cableado, terminales",
      "correo_tecnico": "juan@example.com",
      "descripcion_falla": "Cable suelto",
      "fecha_inicio_actividad": "2026-04-02T14:30:00Z",
      "observaciones": "Se reemplazó cable",
      "nombre_tecnico": "Juan González",
      "causa_falla": "Conexión defectuosa",
      "hora_inicio": "14:30",
      "hora_fin": "15:00",
      "documento_tecnico": "1234567890",
      "tipo_intervencion": "Correctivo"
    }
  ]
}

Códigos de Error:
  404: Solicitud no encontrada
  500: Error del servidor
```

### 3. Actualizar Estado + Asignar Técnico

```
URL: /Gestion_ot/actualizar_estado_solicitud/
Método: POST
Headers requeridos:
  - Content-Type: application/json
  - X-CSRFToken: <csrf_token>

Body JSON:
{
  "numero": 123,                                    // Consecutivo de solicitud
  "estado": "en proceso",                          // Estado: solicitado|en proceso|en revision|finalizada
  "tecnico": "Juan González",                      // Nombre del técnico
  "fecha": "2026-04-02T14:00:00+05:00"            // ISO-8601 datetime
}

Respuesta Éxito:
{
  "status": "ok",
  "message": "Solicitud y Orden de Trabajo actualizadas correctamente"
}

Respuesta Error:
{
  "status": "error",
  "message": "Descripción del error"
}

Códigos HTTP:
  200: Éxito
  400: Validación fallida (campos requeridos)
  404: Solicitud no encontrada
  500: Error del servidor
```

---

## 📡 JAVASCRIPT UTILS

### Obtener Token CSRF

```javascript
function getCSRFToken() {
    // Opción 1: Buscar en elemento HTML (si está en template)
    let token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    
    if (!token) {
        // Opción 2: Buscar en cookies
        token = document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
    }
    
    return token || '';
}

// Disponible globalmente (definido en csrf.js)
window.getCSRFToken = getCSRFToken;
```

### Funciones de Vista

```javascript
// Mostrar/Ocultar vistas
function showKanban() {
    document.querySelector('.kanban-container').style.display = 'flex';
    document.querySelector('.calendar-container').style.display = 'none';
    document.querySelector('.list-container').style.display = 'none';
}

function showCalendar() {
    document.querySelector('.kanban-container').style.display = 'none';
    document.querySelector('.calendar-container').style.display = 'block';
    document.querySelector('.list-container').style.display = 'none';
    
    // Renderizar calendario si existe
    if (window.calendar) {
        window.calendar.render();
        window.calendar.updateSize();
    }
}

function showList() {
    document.querySelector('.kanban-container').style.display = 'none';
    document.querySelector('.calendar-container').style.display = 'none';
    document.querySelector('.list-container').style.display = 'flex';
}

// Disponibles globalmente
window.showKanban = showKanban;
window.showCalendar = showCalendar;
window.showList = showList;
```

---

## 🎯 FLUJO COMPLETO CON CÓDIGOS

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USUARIO VE TABLERO KANBAN                                        │
│    - Django renderiza gestion_ot.html                               │
│    - Se cargan todos los JS modules                                 │
│    - Se inicializa FullCalendar (calendarView.js)                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 2. USUARIO ARRASTRA TARJETA                                         │
│    kanban-card (id="card-123") con ondragstart="drag(event)"      │
│    → drag() → event.dataTransfer.setData("text/plain", "card-123") │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 3. USUARIO SUELTA EN COLUMNA "OT en Proceso"                       │
│    kanban-column (id="ot_en_proceso") ondrop="drop(event)"        │
│    → dropDesktop(event)                                             │
│    → Detecta event.target.closest('.kanban-column').id == "ot_en_proceso" │
│    → openModal({ numero: "123" })                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 4. MODAL APARECE                                                    │
│    <div id="tecnicoModal"> muestra:                                │
│    - Input fecha_actividad                                         │
│    - Input tecnico_asignado                                        │
│    - Botón "Asignar Técnico"                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 5. USUARIO COMPLETA FORM Y SUBMIT                                   │
│    #OrdenTrabajoForm addEventListener("submit")                   │
│    → POST /Gestion_ot/actualizar_estado_solicitud/                │
│    Body: {numero: 123, estado: "en proceso", tecnico: "Juan", fecha: "..."} │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 6. BACKEND PROCESA                                                  │
│    @csrf_exempt                                                     │
│    def actualizar_estado_solicitud(request):                       │
│    ├─ data = json.loads(request.body)                             │
│    ├─ solicitud = Solicitud.objects.get(consecutivo=data['numero']) │
│    ├─ estado = Estado.objects.get(nombre=data['estado'])           │
│    ├─ solicitud.estado = estado                                    │
│    ├─ solicitud.tecnico_asignado = data['tecnico']               │
│    ├─ solicitud.fecha_actividad = isoparse(data['fecha'])         │
│    ├─ solicitud.save()                                             │
│    ├─ OrdenTrabajo.objects.update_or_create(...)                   │
│    └─ return JsonResponse({'status': 'ok'})                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 7. FRONTEND ACTUALIZA                                               │
│    .then(data => {                                                  │
│    ├─ const card = document.getElementById("card-123")             │
│    ├─ const targetColumn = document.getElementById("ot_en_proceso") │
│    ├─ targetColumn.appendChild(card)  [MUEVE VISUALMENTE]         │
│    ├─ closeModal()                                                  │
│    └─ alert('Técnico asignado')                                    │
│    })                                                                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 8. RESULTADO FINAL                                                  │
│    - Tarjeta ahora está en columna "OT en Proceso"                │
│    - Solicitud.tecnico_asignado = "Juan González"                 │
│    - Solicitud.fecha_actividad = 2026-04-02T14:00:00             │
│    - OrdenTrabajo creada/actualizada en BD                        │
│    - Modal cerrado                                                  │
└─────────────────────────────────────────────────────────────────────┘
```
