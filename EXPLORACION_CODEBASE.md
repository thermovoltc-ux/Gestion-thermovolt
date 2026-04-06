# Exploración del Codebase - Gestión de Mantenimiento

## 📍 UBICACIÓN DE ARCHIVOS CLAVE

### Templates HTML
```
solicitudes/templates/solicitudes/
├── gestion_ot.html          ← Tablero Kanban principal
├── lista_solicitudes.html   ← Vista de lista (tabla)
├── fracttal.html            ← Componente React externo (calendario)
├── crear_solicitud.html
├── listar_ot.html
└── indexpadre.html
```

### JavaScript Modularizado
```
static/js/
├── gestion_ot.js             ← Entry point módulos OT
├── kanbanColumns.js          ← Lógica drag-drop Kanban
├── calendarView.js           ← Inicialización calendario FullCalendar
├── modals.js                 ← Modales de información y asignación
├── solicitudes.js            ← Formulario de solicitudes
├── kanban.js                 ← Funciones básicas Kanban
├── kanbanBoard.js
├── main.js
├── csrf.js                   ← Helper CSRF tokens
└── calendarView.js
```

### Modelos Python
```
Gestion_ot/models.py
├── Estado                    ← Estados: solicitado, en proceso, en revisión, finalizada
├── GestionOt                 ← Relaciona solicitud con técnico
├── OrdenTrabajo              ← Orden de trabajo con técnico y fecha
├── CierreOt                  ← Cierre de OT con materiales, firmas, fotos
└── ImagenCierreOt            ← Imágenes antes/después
```

---

## 1️⃣ ARCHIVO: gestion_ot.html - KANBAN/TABLERO

### Estructura HTML del Kanban

```html
<div class="kanban-container">
    <!-- Columna 1: Solicitudes -->
    <div class="kanban-column" id="solicitudes" ondrop="drop(event)" ondragover="allowDrop(event)">
        <h2>Solicitudes</h2>
        <!-- Tarjetas renderizadas con Django template -->
        {% for solicitud in solicitudes %}
            <div class="kanban-card" 
                 id="card-{{ solicitud.numero_activo }}" 
                 draggable="true" 
                 ondragstart="drag(event)"
                 data-numero-activo="{{ solicitud.consecutivo }}">
                <h3>Solicitud 00{{ solicitud.numero_activo }}</h3>
                <h4>PDV: {{ solicitud.PDV }}</h4>
                <p>{{ solicitud.descripcion_problema|slice:":50" }}...</p>
                <small>{{ solicitud.fecha_creacion }}</small>
            </div>
        {% endfor %}
    </div>

    <!-- Columna 2: OT en Proceso -->
    <div class="kanban-column" id="ot_en_proceso" ondrop="drop(event)" ondragover="allowDrop(event)">
        <h2>OT en Proceso</h2>
    </div>

    <!-- Columna 3: OT en Revisión -->
    <div class="kanban-column" id="ot_en_revision" ondrop="drop(event)" ondragover="allowDrop(event)">
        <h2>OT en Revisión</h2>
    </div>

    <!-- Columna 4: OT Finalizada -->
    <div class="kanban-column" id="ot_finalizada" ondrop="drop(event)" ondragover="allowDrop(event)">
        <h2>OT Finalizada</h2>
    </div>
</div>
```

### Estructura de Tarjeta (kanban-card)

```html
<div class="kanban-card" 
     id="card-{{ solicitud.numero_activo }}" 
     draggable="true" 
     ondragstart="drag(event)"
     data-numero-activo="{{ solicitud.consecutivo }}">
    <h3>Solicitud 00{{ solicitud.numero_activo }}</h3>
    <h4>PDV: {{ solicitud.PDV }}</h4>
    <p>{{ solicitud.descripcion_problema|slice:":50" }}...</p>
    <small>{{ solicitud.fecha_creacion }}</small>
</div>
```

**Atributos importantes:**
- `id="card-{{ solicitud.numero_activo }}"` - ID único para arrastrar
- `data-numero-activo="{{ solicitud.consecutivo }}"` - Almacena consecutivo
- `draggable="true"` - Permite drag-drop
- `ondragstart="drag(event)"` - Event listener para inicio de arrastre

### Modal para Asignar Técnico

```html
<div id="tecnicoModal" class="modal">
    <div class="modal-content">
        <span class="close" onclick="closeModal()">&times;</span>
        <h2>Asignar Técnico</h2>
        
        <form id="OrdenTrabajoForm" method="POST" action="{% url 'gestion_ot' %}">
            {% csrf_token %}
            
            <input type="hidden" id="numero_activo" name="numero_activo">
            
            <label for="fecha_actividad">Fecha de la Actividad:</label>
            <input type="date" id="fecha_actividad" name="fecha_actividad" required>

            <label for="tecnico_asignado">Nombre del Técnico:</label>
            <input type="text" id="tecnico_asignado" name="tecnico_asignado" required>

            <label for="estado">Estado:</label>
            <input type="text" id="estado" name="estado" value="OT en Proceso" required>
    
            <button type="submit" name="actualizar">Guardar</button>
        </form>
        
        <div id="modalError" style="color: red; display: none;">
            Error al actualizar la solicitud. Intente de nuevo.
        </div>
    </div>
</div>
```

---

## 2️⃣ ARCHIVO: lista_solicitudes.html - ESTRUCTURA DE LISTA

```html
{% extends "solicitudes/indexpadre.html" %}

{% block title %}Lista de Solicitudes{% endblock %}

{% block content %}
    <h1>Lista de Solicitudes</h1>
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
            {% for solicitud in solicitudes %}
                <tr>
                    <td>00{{ solicitud.consecutivo }}</td>
                    <td>{{ solicitud.co }}</td>
                    <td>{{ solicitud.PDV }}</td>
                    <td>{{ solicitud.fecha_creacion }}</td>
                    <td>{{ solicitud.solicitado_por }}</td>
                    <td>{{ solicitud.equipo }}</td>
                    <td>{{ solicitud.prioridad }}</td>
                    <td>{{ solicitud.estado }}</td>
                </tr>
            {% endfor %}
        </tbody>
    </table>
{% endblock %}
```

**Estructura:** Tabla HTML simple con campos de solicitud

---

## 3️⃣ ARCHIVO: fracttal.html - CALENDARIO

**Nota:** No es un template Django tradicional. Es una salida compilada de un cliente React/JavaScript compilado que genera HTML dinámico.

**Integración:** El calendario usa FullCalendar.js (versión 5+)

```javascript
// Inicialización desde calendarView.js
let calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    events: events,  // Array de eventos de solicitudes
    eventClick: function(info) {
        // Abre modal con detalles
        window.openSolicitudModal(info.event.extendedProps.consecutivo);
    },
    height: '100%'
});
```

**Mapeo de colores por estado:**
- `solicitado` → Gray
- `en proceso` → Orange
- `en revision` → Blue
- `finalizada` → Green

---

## 4️⃣ DESPLEGABLE/MODAL DE INFORMACIÓN

### Archivo: modals.js

```javascript
function openSolicitudModal(consecutivo) {
    // 1. Fetch a endpoint Django
    fetch(`/Gestion_ot/detalles_solicitud/${consecutivo}/`)
        .then(response => response.json())
        .then(data => {
            // 2. Renderiza datos en modal
            document.getElementById('modalNumeroActivo').textContent = data.consecutivo;
            document.getElementById('modalPDV').textContent = data.pdv;
            document.getElementById('modalDescripcion').textContent = data.descripcion;
            document.getElementById('modalEstado').textContent = data.estado;
            
            // 3. Renderiza info de técnico (si existe)
            if (data.ordenes_trabajo && data.ordenes_trabajo.length > 0) {
                const cierre = data.ordenes_trabajo[0];
                document.getElementById('modalTecnicoAsignado').textContent = cierre.tecnico_asignado;
                document.getElementById('modalFechaActividad').textContent = cierre.fecha_actividad;
            }
            
            // 4. Muestra secciones contextuales
            if (data.estado === 'en revision') {
                document.getElementById('finalizarOTBtn').style.display = 'block';
            }
            
            // 5. Abre modal
            document.getElementById('solicitudModal').style.display = 'block';
        });
}
```

### HTML del Modal

```html
<div id="solicitudModal" class="modal">
    <div class="modal-content">
        <span class="close" onclick="closeSolicitudModal()">&times;</span>
        
        <!-- Información de la solicitud -->
        <div id="asignacionInfo">
            <h3>Información de Asignación</h3>
            <p><strong>Número:</strong> <span id="modalNumeroActivo"></span></p>
            <p><strong>PDV:</strong> <span id="modalPDV"></span></p>
            <p><strong>Descripción:</strong> <span id="modalDescripcion"></span></p>
            <p><strong>Estado:</strong> <span id="modalEstado"></span></p>
        </div>
        
        <!-- Información de la OT -->
        <div id="cierreOTInfo">
            <h3>Detalles de la OT</h3>
            <p><strong>Técnico:</strong> <span id="modalTecnicoAsignado"></span></p>
            <p><strong>Fecha Actividad:</strong> <span id="modalFechaActividad"></span></p>
            <p><strong>Tipo Mantenimiento:</strong> <span id="modalTipoMantenimiento"></span></p>
            <p><strong>Materiales:</strong> <span id="modalMaterialesUtilizados"></span></p>
        </div>
        
        <!-- Botón de finalizar -->
        <button id="finalizarOTBtn" onclick="finalizarOT()">Finalizar OT</button>
    </div>
</div>
```

---

## 5️⃣ LÓGICA DE ASIGNAR TÉCNICOS

### Flujo de Asignación

```
Usuario arrastra tarjeta → dropDesktop() → Detecta destino "ot_en_proceso" → openModal() → Modal aparece
Usuario llena: {fecha_actividad, tecnico_asignado} → Submit → Fetch POST → actualizar_estado_solicitud()
```

### Endpoint: `/Gestion_ot/actualizar_estado_solicitud/`

```python
# views.py
@csrf_exempt
@require_POST
@login_required
def actualizar_estado_solicitud(request):
    try:
        data = json.loads(request.body)
        
        numero_solicitud = data.get('numero')
        nuevo_estado_nombre = data.get('estado')
        tecnico = data.get('tecnico')
        fecha = data.get('fecha')
        
        # Busca solicitud
        solicitud = Solicitud.objects.get(consecutivo=numero_solicitud)
        
        # Obtiene estado
        nuevo_estado = Estado.objects.get(nombre=nuevo_estado_nombre)
        
        # Actualiza solicitud
        solicitud.estado = nuevo_estado
        solicitud.tecnico_asignado = tecnico
        solicitud.fecha_actividad = isoparse(fecha)
        solicitud.save()
        
        # Crea/Actualiza OrdenTrabajo
        orden_trabajo, created = OrdenTrabajo.objects.update_or_create(
            solicitud=solicitud,
            defaults={
                'tecnico_asignado': tecnico,
                'fecha_actividad': fecha,
                'estado': nuevo_estado
            }
        )
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
```

### Llamada desde JavaScript (modals.js)

```javascript
document.getElementById("OrdenTrabajoForm").addEventListener("submit", function(event) {
    event.preventDefault();

    const nombreTecnico = document.getElementById("tecnico_asignado").value;
    const fechaActividad = document.getElementById("fecha_actividad").value;
    const numeroSolicitud = document.getElementById("consecutivo").value;

    fetch('/Gestion_ot/actualizar_estado_solicitud/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            numero: numeroSolicitud,
            estado: "en proceso",
            tecnico: nombreTecnico,
            fecha: fechaActividad
        })
    })
    .then(response => response.json())
    .then(data => {
        const targetColumn = document.getElementById("ot_en_proceso");
        const card = document.getElementById("card-" + numeroSolicitud);
        targetColumn.appendChild(card);  // Mueve tarjeta visualmente
        closeModal();
    })
    .catch(error => console.error('Error:', error));
});
```

---

## 🔗 EVENT LISTENERS Y CLICK HANDLERS

### kanbanColumns.js

```javascript
// Funciones de drag-drop
function drag(event) {
    // Inicia arrastre
    event.dataTransfer.setData("text", event.target.id);
}

function allowDrop(event) {
    // Permite soltar en columnas
    event.preventDefault();
}

function drop(event) {
    // Maneja el evento de soltar
    event.preventDefault();
    const id = event.dataTransfer.getData("text");
    const card = document.getElementById(id);
    const column = event.target.closest('.kanban-column');

    if (column && column.id === "ot_en_proceso") {
        // Si cae en "en proceso", abre modal para asignar técnico
        window.openModal({ numero: id.split('-')[1] });
        return;
    }

    column.appendChild(card);
    updateSolicitudState(card, column.id);
}
```

### Touch Support (Mobile)

```javascript
function touchStart(event) {
    draggedElement = event.target.closest('.kanban-card');
    draggedElement.style.opacity = '0.5';
}

function touchEnd(event) {
    const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
    const column = dropTarget.closest('.kanban-column');
    
    if (column.id === "ot_en_proceso") {
        window.openModal(solicitud);
    }
    column.appendChild(draggedElement);
}
```

### Click Handlers en modals.js

```javascript
// Click en tarjeta abre detalles
document.querySelectorAll('.kanban-card').forEach(card => {
    card.addEventListener('click', function() {
        const consecutivo = this.getAttribute('data-numero-activo');
        openSolicitudModal(consecutivo);
    });
});

// Click en "Finalizar OT"
document.getElementById("finalizarOTBtn").addEventListener("click", function() {
    const numeroSolicitud = document.getElementById("modalNumeroActivo").textContent;
    
    fetch('/Gestion_ot/actualizar_estado_solicitud/', {
        method: 'POST',
        body: JSON.stringify({
            numero: numeroSolicitud,
            estado: "finalizada",
            tecnico: tecnicoAsignado,
            fecha: fechaActividad
        })
    })
    .then(data => {
        console.log('OT finalizada');
        closeSolicitudModal();
    });
});
```

---

## 🎨 MANEJO DE ESTADOS

### Modelo de Estados

```python
class Estado(models.Model):
    ESTADO_CHOICES = [
        ('solicitado', 'Solicitado'),
        ('en proceso', 'OT en Proceso'),
        ('en revision', 'OT en Revisión'),
        ('finalizada', 'OT Finalizada')
    ]
    nombre = models.CharField(max_length=20, choices=ESTADO_CHOICES, unique=True)
```

### Estados en el Kanban

```html
<!-- Columnas mapeadas a estados -->
id="solicitudes"        → estado='solicitado'
id="ot_en_proceso"      → estado='en proceso'
id="ot_en_revision"     → estado='en revision'
id="ot_finalizada"      → estado='finalizada'
```

### Cambio de Estado

```javascript
// En updateSolicitudState()
const estadoMap = {
    "solicitado": "solicitado",
    "ot_en_proceso": "en proceso",
    "ot_en_revision": "en revision",
    "ot_finalizada": "finalizada"
};
```

---

## 📡 URLs IMPORTANTES

### Endpoint: Obtener Detalles de Solicitud
```
GET /Gestion_ot/detalles_solicitud/<consecutivo>/
Retorna: JSON con datos completos + ordenes_trabajo
```

### Endpoint: Actualizar Estado
```
POST /Gestion_ot/actualizar_estado_solicitud/
Body: {
    "numero": consecutivo_solicitud,
    "estado": "en proceso",
    "tecnico": "Nombre Técnico",
    "fecha": "2026-04-03T14:30:00"
}
Retorna: {"status": "ok", "message": "..."}
```

### URL Django URL Patterns
```python
# Gestion_ot/urls.py
path('gestion_ot/', views.gestion_ot, name='gestion_ot'),
path('actualizar_estado_solicitud/', views.actualizar_estado_solicitud, name='actualizar_estado'),
path('detalles_solicitud/<int:consecutivo>/', views.detalles_solicitud, name='detalles_solicitud'),
```

---

## 🔍 SNIPPETS DE CÓDIGO IMPORTANTE

### 1. Asignación de Técnico - Modelo

```python
class OrdenTrabajo(models.Model):
    solicitud = models.ForeignKey('solicitudes.Solicitud', on_delete=models.CASCADE)
    tecnico_asignado = models.CharField(max_length=100)  # ← Nombre del técnico
    fecha_actividad = models.DateTimeField(blank=True, null=True)  # ← Fecha asignada
    estado = models.ForeignKey(Estado, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"OT-{self.solicitud.consecutivo} - {self.tecnico_asignado}"
```

### 2. Formulario Modal

```python
# forms.py
class OrdenTrabajoForm(forms.ModelForm):
    tecnico_asignado = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Tecnico')
    )
    
    class Meta:
        model = OrdenTrabajo
        fields = ['solicitud', 'tecnico_asignado', 'fecha_actividad', 'estado']
        widgets = {
            'fecha_actividad': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
```

### 3. Renderización de Tarjeta en Template

```django
{% for solicitud in solicitudes %}
    <div class="kanban-card" 
         id="card-{{ solicitud.numero_activo }}" 
         draggable="true" 
         ondragstart="drag(event)"
         data-numero-activo="{{ solicitud.consecutivo }}">
        <h3>Solicitud 00{{ solicitud.numero_activo }}</h3>
        <h4>PDV: {{ solicitud.PDV }}</h4>
        <p>{{ solicitud.descripcion_problema|slice:":50" }}...</p>
        <small>{{ solicitud.fecha_creacion }}</small>
    </div>
{% endfor %}
```

### 4. Obtener CSRF Token

```javascript
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
           document.cookie.split('; ')
               .find(row => row.startsWith('csrftoken='))
               ?.split('=')[1];
}
```

---

## 📋 RESUMEN FLUJO COMPLETO

### Flujo: Asignar Técnico a Solicitud

```
1. Usuario ve listado de solicitudes en columna "Solicitudes"
   ↓
2. Usuario arrastra tarjeta a columna "OT en Proceso"
   ↓
3. Se dispara event: dropDesktop() en kanbanColumns.js
   ↓
4. Detecta destino == "ot_en_proceso" → Abre modal
   ↓
5. Modal muestra:
   - Campo: Fecha de Actividad (date input)
   - Campo: Nombre Técnico (text input)
   - Campo: Estado (hidden, default="OT en Proceso")
   ↓
6. Usuario completa y hace Submit
   ↓
7. AJAX POST a /Gestion_ot/actualizar_estado_solicitud/
   ↓
8. Backend:
   - Busca Solicitud por consecutivo
   - Obtiene Estado "en proceso"
   - Crea/Actualiza OrdenTrabajo con técnico y fecha
   ↓
9. Frontend:
   - Cierra modal
   - Mueve tarjeta visualmente a columna "OT en Proceso"
   ↓
10. Tarjeta ahora aparece en nueva columna con estado actualizado
```

---

## 🎯 CONCLUSIÓN

**Estructura de visualización:**
- **Kanban**: 4 columnas (solicitado, en proceso, en revisión, finalizada)
- **Lista**: Tabla HTML simple
- **Calendario**: FullCalendar con eventos coloreados por estado

**Asignación de técnicos:**
- Se realiza via Modal que aparece al arrastrar a "OT en Proceso"
- Campos: Fecha actividad + Nombre técnico
- API: POST `/Gestion_ot/actualizar_estado_solicitud/`
- Modelo: `OrdenTrabajo` almacena técnico_asignado, fecha_actividad, estado

**Estados manejados:**
- `solicitado` (Gris)
- `en proceso` (Naranja)
- `en revision` (Azul)
- `finalizada` (Verde)
