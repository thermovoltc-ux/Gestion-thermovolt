# Diagramas Visuales - Arquitectura del Sistema

## 🏗️ ARQUITECTURA DE COMPONENTES

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         NAVEGACIÓN PRINCIPAL                             │
├──────────────────────────────────────────────────────────────────────────┤
│  [Tablero] [Calendario] [Lista]  [Filtro Fecha] [Aplicar Filtro]       │
└──────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                          VISTA KANBAN (Por Defecto)                        │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│ SOLICITUDES     │ OT EN PROCESO    │ OT EN REVISIÓN │ OT FINALIZADA        │
│ (Gris)          │ (Naranja)        │ (Azul)         │ (Verde)              │
├─────────────────┼─────────────────┼─────────────────┼──────────────────────┤
│ ┌─────────────┐ │ ┌─────────────┐ │ ┌─────────────┐ │ ┌──────────────────┐ │
│ │ Solicitud 1 │ │ │ Solicitud 2 │ │ │ Solicitud 3 │ │ │ Solicitud 4      │ │
│ │             │ │ │             │ │ │             │ │ │                  │ │
│ │ PDV: Tienda │ │ │ PDV: Centro │ │ │ PDV: Mall   │ │ │ PDV: Almacén    │ │
│ │ Desc...     │ │ │ Desc...     │ │ │ Desc...     │ │ │ Desc...          │ │
│ │ 02-04-2026  │ │ │ 02-04-2026  │ │ │ 02-04-2026  │ │ │ 01-04-2026      │ │
│ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │ │ Técnico: Juan    │ │
│                 │ │                 │ │                 │ │ 01-04-2026      │ │
│ (Arrastrar     │ │ (Click abre     │ │                 │ │ └──────────────────┘ │
│  para asignar) │ │  detalles)      │ │                 │ │                      │
│                 │ │                 │ │                 │ │                      │
└─────────────────┴─────────────────┴─────────────────┴──────────────────────┘
     ↑ DRAGGABLE        ↑ DROPPABLE       ↑ DROPPABLE      ↑ DROPPABLE
```

---

## 🔄 FLUJO DE INTERACCIÓN - ASIGNAR TÉCNICO

```
┌────────────────────────────────────────────────────────────────────┐
│ USUARIO VE TARJETA EN COLUMNA "SOLICITUDES"                        │
│ ID: card-123                                                       │
└────────────────────────────────────────────────────────────────────┘
           ↓ USUARIO ARRASTRA
┌────────────────────────────────────────────────────────────────────┐
│ JavaScript: drag(event)                                            │
│ - event.dataTransfer.setData("text/plain", "card-123")           │
└────────────────────────────────────────────────────────────────────┘
           ↓ USUARIO SUELTA SOBRE "OT EN PROCESO"
┌────────────────────────────────────────────────────────────────────┐
│ JavaScript: drop(event) o dropDesktop(event)                      │
│ - Detecta: column.id === "ot_en_proceso"                         │
│ - Acción: openModal({ numero: "123" })                           │
│ - NO mueve la tarjeta aún                                         │
└────────────────────────────────────────────────────────────────────┘
           ↓ MODAL ABIERTO
┌────────────────────────────────────────────────────────────────────┐
│ <div id="tecnicoModal">                                            │
│   ├─ Input: fecha_actividad (datetime-local)                     │
│   ├─ Input: tecnico_asignado (text)                              │
│   └─ Botón: "Asignar Técnico"                                    │
└────────────────────────────────────────────────────────────────────┘
           ↓ USUARIO COMPLETA Y ENVÍA
┌────────────────────────────────────────────────────────────────────┐
│ JavaScript: OrdenTrabajoForm.addEventListener("submit")           │
│ POST /Gestion_ot/actualizar_estado_solicitud/                    │
│ Body: {                                                            │
│   "numero": 123,                                                  │
│   "estado": "en proceso",                                         │
│   "tecnico": "Juan González",                                     │
│   "fecha": "2026-04-02T14:00:00+00:00"                           │
│ }                                                                  │
└────────────────────────────────────────────────────────────────────┘
           ↓ BACKEND PROCESA
┌────────────────────────────────────────────────────────────────────┐
│ Django: actualizar_estado_solicitud(request)                      │
│ ├─ Busca: Solicitud.objects.get(consecutivo=123)                │
│ ├─ Actualiza:                                                     │
│ │  - solicitud.estado = Estado('en proceso')                     │
│ │  - solicitud.tecnico_asignado = "Juan González"               │
│ │  - solicitud.fecha_actividad = datetime_obj                   │
│ │  - solicitud.save()                                            │
│ ├─ Crea/Actualiza: OrdenTrabajo                                  │
│ └─ Retorna: {"status": "ok"}                                     │
└────────────────────────────────────────────────────────────────────┘
           ↓ FRONTEND ACTUALIZA (ClienteJS)
┌────────────────────────────────────────────────────────────────────┐
│ JavaScript: .then(data => {                                        │
│ ├─ card = document.getElementById("card-123")                    │
│ ├─ targetColumn = document.getElementById("ot_en_proceso")       │
│ ├─ targetColumn.appendChild(card)  [MUEVE VISUALMENTE]          │
│ ├─ closeModal()                                                   │
│ └─ alert('Técnico asignado')                                     │
│ })                                                                 │
└────────────────────────────────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────────────────────────────────┐
│ RESULTADO:                                                         │
│ ✓ Tarjeta ahora está en "OT EN PROCESO"                          │
│ ✓ BD actualizada con técnico y fecha                             │
│ ✓ Usuario ve confirmación                                         │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🖱️ CLICK HANDLER - VER DETALLES

```
┌─────────────────────────────────────────────────────────────┐
│ USUARIO HACE CLICK EN TARJETA (en cualquier columna)        │
│ <div class="kanban-card" data-numero-activo="123">         │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ JavaScript: kanban-card.addEventListener('click')          │
│ - consecutivo = this.getAttribute('data-numero-activo')   │
│ - openSolicitudModal(consecutivo)                          │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ Fetch: GET /Gestion_ot/detalles_solicitud/123/             │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ Backend retorna JSON:                                       │
│ {                                                           │
│   "consecutivo": 123,                                      │
│   "pdv": "Tienda Centro",                                  │
│   "descripcion": "Equipo no enciende",                    │
│   "estado": "en proceso",                                 │
│   "ordenes_trabajo": [                                     │
│     {                                                      │
│       "tecnico_asignado": "Juan González",                │
│       "fecha_actividad": "2026-04-02T14:00:00Z",          │
│       "tipo_mantenimiento": "Preventivo",                 │
│       "materiales_utilizados": "Cableado",                │
│       ...más campos                                        │
│     }                                                      │
│   ]                                                        │
│ }                                                          │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ Frontend renderiza Modal:                                   │
│ <div id="solicitudModal">                                  │
│   <div id="asignacionInfo">                               │
│     ├─ Número: 123                                         │
│     ├─ PDV: Tienda Centro                                 │
│     ├─ Descripción: Equipo no enciende                   │
│     └─ Estado: En Proceso                                 │
│   </div>                                                   │
│   <div id="cierreOTInfo">                                 │
│     ├─ Técnico: Juan González                            │
│     ├─ Fecha: 02-04-2026 14:00                           │
│     ├─ Tipo: Preventivo                                   │
│     └─ Materiales: Cableado                               │
│   </div>                                                   │
│   <button id="finalizarOTBtn">Finalizar OT</button>       │
│ </div>                                                     │
└─────────────────────────────────────────────────────────────┘
           ↓
        [MOSTRAR]
           ↓
┌─────────────────────────────────────────────────────────────┐
│ Modal visible para usuario                                  │
│ Puede:                                                      │
│ - Leer detalles                                             │
│ - Hacer click en "Finalizar OT" si estado == "en revision" │
│ - Cerrar modal (X button)                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 ESTRUCTURA DE DATOS - TARJETA KANBAN

```
<div class="kanban-card"
     ├─ id="card-123"
     │  └─ Identificador único para drag-drop
     │
     ├─ draggable="true"
     │  └─ Permite HTML5 drag-drop
     │
     ├─ ondragstart="drag(event)"
     │  └─ Handler para iniciar arrastre
     │
     ├─ data-numero-activo="123"
     │  └─ Almacena consecutivo para acceso por JS
     │
     └─ Contenido HTML:
        ├─ <h3>Solicitud 00123</h3>
        ├─ <h4>PDV: Tienda Centro</h4>
        ├─ <p>Descripción truncada...</p>
        └─ <small>02-04-2026</small>
```

---

## 🗂️ ESTRUCTURA DE CARPETAS - JAVASCRIPT

```
static/js/
│
├── gestion_ot.js
│   └─ Import de módulos:
│      ├─ ./csrf.js
│      ├─ ./kanbanColumns.js
│      ├─ ./calendarView.js
│      ├─ ./modals.js
│      └─ Expone funciones globales
│
├── kanbanColumns.js
│   ├─ drag(event)
│   ├─ allowDrop(event)
│   ├─ drop(event)
│   ├─ dropDesktop(event)
│   ├─ updateSolicitudState(card, columnId)
│   ├─ touchStart(event)
│   ├─ touchMove(event)
│   ├─ touchEnd(event)
│   └─ showKanban(), showCalendar(), showList()
│
├── modals.js
│   ├─ openSolicitudModal(consecutivo)
│   │   └─ Fetch: GET /Gestion_ot/detalles_solicitud/<id>/
│   ├─ closeSolicitudModal()
│   ├─ openModal(solicitud)
│   ├─ closeModal()
│   └─ Event listeners para:
│      ├─ Envío de OrdenTrabajoForm
│      ├─ Click en kanban-card
│      ├─ Click en finalizarOTBtn
│      └─ Click en .ver-solicitud links
│
├── calendarView.js
│   ├─ Inicializa FullCalendar
│   ├─ Mapeo: evento.click → openSolicitudModal()
│   └─ Colores por estado
│
├── kanban.js (basicfunctions)
│   ├─ crearTarjeta(solicitud)
│   ├─ dragStart(e), dragOver(e), drop(e)
│   └─ applyDateFilter()
│
├── solicitudes.js
│   ├─ AJAX para crear solicitud
│   ├─ Validación de solicitud duplicada
│   └─ Poblamiento dinámico de selectores
│
├── csrf.js
│   ├─ getCSRFToken()
│   └─ Disponible como window.getCSRFToken()
│
├── main.js (inicialización general)
├── menuToggle.js
└── ...otros archivos
```

---

## 🎨 MAPEO DE ESTADOS Y COLORES

```
┌───────────────────┬──────────────────┬───────────────────┬──────────────────┐
│ ESTADO            │ COLUMNA ID       │ COLOR CALENDAR    │ DESCRIPCIÓN      │
├───────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ solicitado        │ solicitudes      │ Gray (#999)       │ Inicial, sin OT  │
├───────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ en proceso        │ ot_en_proceso    │ Orange (#FF9800)  │ Asignada a Técnico
├───────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ en revisión       │ ot_en_revision   │ Blue (#2196F3)    │ En revisión      │
├───────────────────┼──────────────────┼───────────────────┼──────────────────┤
│ finalizada        │ ot_finalizada    │ Green (#4CAF50)   │ Completada       │
└───────────────────┴──────────────────┴───────────────────┴──────────────────┘
```

---

## 👥 MODELOS DE BASE DE DATOS - RELACIONES

```
┌─────────────────────┐
│    Solicitud        │
├─────────────────────┤
│ id (PK)             │
│ consecutivo         │──┐
│ PDV                 │  │
│ descripcion         │  │
│ estado (FK)         │  │
│ tecnico_asignado    │  │
│ fecha_actividad     │  │
│ fecha_creacion      │  │
│ solicitado_por      │  │ 1:N
│ equipo              │  │
│ prioridad           │  │
└─────────────────────┘  │
                         │
         ┌───────────────┘
         │
┌────────────────────────────┐
│    OrdenTrabajo            │
├────────────────────────────┤
│ id (PK)                    │
│ solicitud_id (FK)  ────────┘
│ tecnico_asignado           │ ← Campo clave
│ fecha_actividad            │ ← Campo clave
│ estado (FK)                │
└────────────────────────────┘
         │
         │ 1:1
         │
┌────────────────────────────┐
│    CierreOt                │
├────────────────────────────┤
│ id (PK)                    │
│ orden_trabajo_id (FK o O2O)│
│ tipo_mantenimiento         │
│ materiales_utilizados      │
│ nombre_tecnico             │
│ firma_tecnico              │
│ fecha_inicio_actividad     │
│ se_soluciono (Boolean)     │
│ ...más campos              │
└────────────────────────────┘
         │
         │ 1:N
         │
┌────────────────────────────┐
│    ImagenCierreOt          │
├────────────────────────────┤
│ id (PK)                    │
│ cierre_ot_id (FK)  ────────┘
│ imagen (ImageField)        │
│ tipo (choices: antes/después)
│ descripcion                │
└────────────────────────────┘
```

---

## 🔀 FLUJO DE DATOS - PETICIÓN AJAX

```
FRONTEND (JavaScript)
│
├─ getCSRFToken()
│  └─ Busca token en:
│     ├─ [name=csrfmiddlewaretoken]
│     └─ document.cookie
│
└─ fetch('/Gestion_ot/actualizar_estado_solicitud/', {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json',
       'X-CSRFToken': '<token>'        ← Necesario para POST
     },
     body: JSON.stringify({
       numero: 123,
       estado: 'en proceso',
       tecnico: 'Juan González',
       fecha: '2026-04-02T14:00:00+00:00'
     })
   })
   │
   ↓
BACKEND (Django)
│
├─ @csrf_exempt decorator
├─ @require_POST decorator
├─ @login_required decorator
│
├─ json.loads(request.body)
│  └─ Parsed JSON body
│
├─ Validaciones:
│  ├─ numero y estado requeridos
│  ├─ fecha requerida
│  └─ Retorna 400 si error
│
├─ Operaciones DB:
│  ├─ Solicitud.objects.get(consecutivo=numero)
│  ├─ Estado.objects.get(nombre=estado)
│  ├─ solicitud.estado = nuevo_estado
│  ├─ solicitud.tecnico_asignado = tecnico
│  ├─ solicitud.fecha_actividad = isoparse(fecha)
│  ├─ solicitud.save()
│  └─ OrdenTrabajo.objects.update_or_create(...)
│
└─ return JsonResponse({'status': 'ok'})
   │
   ↓
FRONTEND (JavaScript)
│
├─ .then(response => response.json())
│  └─ Parse JSON response
│
├─ .then(data => {
│  ├─ if (data.status === 'ok')
│  │  ├─ card.move()
│  │  ├─ closeModal()
│  │  └─ alert('Éxito')
│  └─ })
│
└─ .catch(error => {
   ├─ console.error(error)
   └─ mostrar modal de error
   })
```

---

## 🗓️ CALENDARIO - INICIALIZACIÓN

```
┌──────────────────────────────────────────────────┐
│ calendarView.js DOMContentLoaded                 │
├──────────────────────────────────────────────────┤
│                                                  │
│ 1. Buscar elemento: #calendar                   │
│    └─ Contiene: data-events="[...]"             │
│                                                  │
│ 2. Parse JSON eventos:                          │
│    └─ solicitudes: [                            │
│       { consecutivo, fecha_creacion, estado },  │
│       ...                                        │
│    ]                                             │
│                                                  │
│ 3. Mapear estado → color:                       │
│    ├─ 'solicitado' → 'gray'                     │
│    ├─ 'en proceso' → 'orange'                   │
│    ├─ 'en revision' → 'blue'                    │
│    └─ 'finalizada' → 'green'                    │
│                                                  │
│ 4. Crear eventos para FullCalendar:             │
│    └─ {                                          │
│       id: consecutivo,                          │
│       title: "Solicitud XXX",                   │
│       start: fecha_creacion,                    │
│       color: color_por_estado,                  │
│       extendedProps: solicitud_completa         │
│    }                                             │
│                                                  │
│ 5. Inicializar FullCalendar.Calendar:           │
│    ├─ initialView: 'dayGridMonth'               │
│    ├─ events: [...]                             │
│    └─ eventClick: window.openSolicitudModal()   │
│                                                  │
│ 6. Guardar ref: window.calendar = calendar      │
│                                                  │
│ 7. Crear renderCalendar() función:              │
│    └─ window.renderCalendar = () => {           │
│       calendar.render()  [Solo 1ra vez]         │
│       calendar.updateSize()                     │
│    }                                             │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 📱 SOPORTE MOBILE - TOUCH EVENTS

```
┌─────────────────────────────────────────────────┐
│ Touch Start: touchStart(event)                  │
├─────────────────────────────────────────────────┤
│ ├─ draggedElement = event.target.closest(...)  │
│ ├─ draggedElement.style.opacity = '0.5'        │
│ └─ draggedElement.style.transform = 'scale...' │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│ Touch Move: touchMove(event)                    │
├─────────────────────────────────────────────────┤
│ └─ event.preventDefault() [Permite tracking]   │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│ Touch End: touchEnd(event)                      │
├─────────────────────────────────────────────────┤
│ ├─ draggedElement.style.opacity = '1'          │
│ ├─ Obtener elemento bajo touch point:          │
│ │  └─ document.elementFromPoint(x, y)          │
│ ├─ Detectar columna destino                    │
│ ├─ Si es "ot_en_proceso" → openModal()         │
│ ├─ Si no → appendChild(draggedElement)         │
│ └─ draggedElement = null                       │
└─────────────────────────────────────────────────┘
```
