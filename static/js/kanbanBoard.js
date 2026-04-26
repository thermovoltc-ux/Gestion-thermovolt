import './csrf.js';

// Declarar la variable calendar en el ámbito global
let calendar;

// Permitir arrastrar y soltar en las columnas
function allowDrop(event) {
    event.preventDefault();
}

// Función que se ejecuta cuando se inicia el arrastre
function drag(event) {
    event.dataTransfer.setData("text", event.target.id);
}

// Hacer que las funciones estén disponibles en el ámbito global
window.allowDrop = allowDrop;
window.drag = drag;
window.drop = drop;


// Función para manejar el evento de 'drop'
function drop(event) {
    event.preventDefault();
    const data = event.dataTransfer.getData("text/plain");
    const card = document.getElementById(data);
    const column = event.target.closest('.kanban-column');

    if (column) {
        const columnId = column.id;

        if (columnId === "ot_en_proceso") {
            const numeroSolicitud = card.id.split('-')[1];
            const solicitud = { numero: numeroSolicitud };
            openModal(solicitud);
            return;
        }

        column.appendChild(card);
        updateSolicitudState(card, columnId);
    }
}


// Actualiza el estado de la solicitud en el backend
function updateSolicitudState(card, columnId) {
    const numeroSolicitud = card.id.split('-')[1];
    let nuevoEstado = "";

    if (columnId === "solicitado") {
        nuevoEstado = "solicitado";
    } else if (columnId === "ot_en_proceso") {
        nuevoEstado = "en proceso";
    } else if (columnId === "ot_en_revision") {
        nuevoEstado = "en revision";
    } else if (columnId === "ot_finalizada") {
        nuevoEstado = "finalizada";
    }

    fetch('/Gestion_ot/actualizar_estado_solicitud/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            numero: numeroSolicitud,
            estado: nuevoEstado,
            fecha_creacion: fechaActividad, 
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            console.log('Estado actualizado exitosamente');
        } else {
            console.log('Error al actualizar el estado:', data.message);
        }
    })
    .catch(error => console.log('Error:', error));
}

// Función para manejar modal, vistas y filtros
document.addEventListener('DOMContentLoaded', function () {
    const djangoUrlEl = document.querySelector('#django-url');
    const baseUrl = djangoUrlEl ? djangoUrlEl.getAttribute('data-url') : '/solicitudes/lista-solicitudes/';

    const calendarEl = document.getElementById('calendar');
    const solicitudes = calendarEl ? JSON.parse(calendarEl.getAttribute('data-events')) : [];

    function showKanban() {
        document.querySelector('.kanban-container').style.display = 'flex';
        document.querySelector('.calendar-container').style.display = 'none';
        document.querySelector('.list-container').style.display = 'none';
    }

    function showCalendar() {
        document.querySelector('.kanban-container').style.display = 'none';
        document.querySelector('.calendar-container').style.display = 'block';
        document.querySelector('.list-container').style.display = 'none';
        calendar.updateSize();
        
    }

    function showList() {
        document.querySelector('.kanban-container').style.display = 'none';
        document.querySelector('.calendar-container').style.display = 'none';
        document.querySelector('.list-container').style.display = 'flex';
    }

    window.showKanban = showKanban;
    window.showCalendar = showCalendar;
    window.showList = showList;

    document.getElementById('kanbanButton').addEventListener('click', showKanban);
    document.getElementById('calendarButton').addEventListener('click', showCalendar);
    document.getElementById('listButton').addEventListener('click', showList);

    if (calendarEl) {
        var events = [];
        for (let solicitud of solicitudes) {
            let color;
            switch (solicitud.estado) {
                case 'solicitado':
                    color = 'gray';
                    break;
                case 'en proceso':
                    color = 'orange';
                    break;
                case 'en revision':
                    color = 'blue';
                    break;
                case 'finalizada':
                    color = 'green';
                    break;
                default:
                    color = 'black';
            }
            let event = {
                id: solicitud.consecutivo, // Asignar un ID único al evento
                title: `Solicitud ${solicitud.consecutivo}`,
                start: solicitud.fecha_creacion,
                color: color,
                extendedProps: solicitud
            };
            events.push(event);
        }

        // Asignar la instancia de FullCalendar.Calendar a la variable global calendar
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: events,
            eventClick: function(info) {
                openSolicitudModal(info.event.extendedProps.consecutivo);
            },
            height: '100%'
        });
        calendar.render();

        setTimeout(function() {
            calendar.updateSize();
        }, 100);
    }

    function openSolicitudModal(consecutivo) {
        if (!consecutivo) {
            console.warn('Intento de abrir solicitud sin consecutivo válido.');
            return;
        }

        fetch(`/Gestion_ot/detalles_solicitud/${consecutivo}/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
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
                    } else {
                        console.warn(`El elemento con id "${id}" no existe.`);
                    }
                };

                actualizarElemento('modalNumeroActivo', data.consecutivo);
                actualizarElemento('modalPDV', data.pdv);
                actualizarElemento('modalEquipo', data.equipo);
                actualizarElemento('modalDescripcion', data.descripcion);
                actualizarElemento('modalFechaCreacion', data.fecha_creacion);
                actualizarElemento('modalEstado', data.estado);

                const finalizarOTBtn = document.getElementById('finalizarOTBtn');
                if (data.estado === 'en revision') {
                    finalizarOTBtn.style.display = 'block';
                } else {
                    finalizarOTBtn.style.display = 'none';
                }

                if (data.ordenes_trabajo && data.ordenes_trabajo.length > 0) {
                    const cierre_ot = data.ordenes_trabajo[0];
                    actualizarElemento('modalTecnicoAsignado', cierre_ot.tecnico_asignado);
                    actualizarElemento('modalFechaActividad', cierre_ot.fecha_actividad);
                    actualizarElemento('modalTipoMantenimiento', cierre_ot.tipo_mantenimiento);
                    actualizarElemento('modalMaterialesUtilizados', cierre_ot.materiales_utilizados);
                    actualizarElemento('modalCorreoTecnico', cierre_ot.correo_tecnico);
                    actualizarElemento('modalDescripcionFalla', cierre_ot.descripcion_falla);
                    actualizarElemento('modalFechaInicioActividad', cierre_ot.fecha_inicio_actividad);
                    actualizarElemento('modalObservaciones', cierre_ot.observaciones);
                    actualizarElemento('modalNombreTecnico', cierre_ot.nombre_tecnico);
                    actualizarElemento('modalCausaFalla', cierre_ot.causa_falla);
                    actualizarElemento('modalHoraInicio', cierre_ot.hora_inicio);
                    actualizarElemento('modalDocumentoTecnico', cierre_ot.documento_tecnico);
                    actualizarElemento('modalTipoIntervencion', cierre_ot.tipo_intervencion);
                    document.getElementById('asignacionInfo').style.display = 'block';

                    if (data.estado === 'en revision' || data.estado === 'finalizada') {
                        document.getElementById('cierreOTInfo').style.display = 'block';
                    } else {
                        document.getElementById('cierreOTInfo').style.display = 'none';
                    }
                } else {
                    document.getElementById('asignacionInfo').style.display = 'none';
                    document.getElementById('cierreOTInfo').style.display = 'none';
                }

                document.getElementById('solicitudModal').style.display = 'block';
            })
            .catch(error => console.error('Error:', error));
    }
    window.openSolicitudModal = openSolicitudModal;
    window.closeSolicitudModal = function() {
        document.getElementById('solicitudModal').style.display = 'none';
    };

    document.querySelectorAll('.kanban-card[data-numero-activo]').forEach(card => {
        card.addEventListener('click', function() {
            const consecutivo = this.getAttribute('data-numero-activo');
            if (consecutivo) {
                openSolicitudModal(consecutivo);
            }
        });
    });

    document.querySelectorAll('.ver-solicitud').forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            const consecutivo = this.getAttribute('data-consecutivo');
            openSolicitudModal(consecutivo);
        });
    });

    function toggleFilterSidebar() {
        const filterSidebar = document.getElementById('filter-sidebar');
        filterSidebar.classList.toggle('visible');
    }

    window.toggleFilterSidebar = toggleFilterSidebar;

    function applyFilter() {
        const filterButton = document.querySelector('.filter-button');
        filterButton.classList.add('filter-applied');
        localStorage.setItem('filterApplied', 'true');
    }

    function clearFilter() {
        const filterButton = document.querySelector('.filter-button');
        filterButton.classList.remove('filter-applied');
        localStorage.removeItem('filterApplied');
    }

    function handleFilterFormSubmit(event) {
        event.preventDefault();
        const filterForm = document.getElementById('filter-form');
        const formData = new FormData(filterForm);

        const params = new URLSearchParams();
        for (const [key, value] of formData.entries()) {
            if (value) {
                params.append(key, value);
            }
        }

        const url = `${filterForm.action}?${params.toString()}`;

        fetch(url, {
            method: 'GET',
        })
        .then(response => response.text())
        .then(data => applyFilter())
        .catch(error => console.error('Error al aplicar los filtros:', error));
    }

    const filterButton = document.querySelector('.filter-button');
    if (localStorage.getItem('filterApplied') === 'true') {
        filterButton.classList.add('filter-applied');
    } else {
        clearFilter();
    }

    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        filterForm.addEventListener('submit', handleFilterFormSubmit);
    }

    window.onclick = function (event) {
        const filterSidebar = document.getElementById('filter-sidebar');
        if (!event.target.matches('.filter-button') && !filterSidebar.contains(event.target)) {
            filterSidebar.classList.remove('visible');
        }
        var modal = document.getElementById('myModal');
        if (modal && !modal.contains(event.target)) {
            modal.style.display = "none";
        }
    };

    if (filterButton) {
        filterButton.addEventListener('click', function (event) {
            event.stopPropagation();
        });
    }

    const finalizarOTBtn = document.getElementById("finalizarOTBtn");

    if (finalizarOTBtn) {
        finalizarOTBtn.addEventListener("click", function() {
            const numeroSolicitud = document.getElementById("modalNumeroActivo").textContent.trim();
            const fechaActividad = document.getElementById("modalFechaActividad").textContent.trim();
            const tecnicoAsignado = document.getElementById("modalTecnicoAsignado").textContent.trim();

            fetch('/Gestion_ot/actualizar_estado_solicitud/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({
                    numero: numeroSolicitud,
                    estado: "finalizada",
                    tecnico: tecnicoAsignado,
                    fecha: fechaActividad
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Error en la actualización');
                }
                return response.json();
            })
            .then(data => {
                console.log('Actualización exitosa:', data);
                actualizarEstadoEnVistas(numeroSolicitud, "finalizada");
                closeSolicitudModal();
            })
            .catch((error) => {
                console.error('Error:', error);
            });
        });
    }

    const filterIndicator = document.getElementById('filterIndicator');

    function showFilterIndicator() {
        filterIndicator.style.display = 'inline-block';
    }

    function hideFilterIndicator() {
        filterIndicator.style.display = 'none';
    }

    function applyFilter(event) {
        event.preventDefault();

        const fechaInicio = document.querySelector('input[name="fecha_inicio"]').value;
        const fechaFin = document.querySelector('input[name="fecha_fin"]').value;
        const pdv = document.querySelector('select[name="pdv"]').value;

        let url = `${baseUrl}?`;
        if (fechaInicio) url += `fecha_inicio=${fechaInicio}&`;
        if (fechaFin) url += `fecha_fin=${fechaFin}&`;
        if (pdv) url += `pdv=${pdv}&`;
        url = url.slice(0, -1);

        if (fechaInicio || fechaFin || pdv) {
            showFilterIndicator();
        } else {
            hideFilterIndicator();
        }

        window.location.href = url;
    }

    if (filterForm) {
        filterForm.addEventListener('submit', applyFilter);
    }

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('fecha_inicio') || urlParams.has('fecha_fin') || urlParams.has('pdv')) {
        showFilterIndicator();
    } else {
        hideFilterIndicator();
    }
});

// Función para cerrar el modal
function closeModal() {
    document.getElementById("tecnicoModal").style.display = "none"; // Oculta el modal
}

window.closeModal = closeModal;

// Enviar el formulario del modal al servidor
document.addEventListener("DOMContentLoaded", function() {
        const ordenTrabajoForm = document.getElementById("OrdenTrabajoForm");
        if (!ordenTrabajoForm) {
            return;
        }

        ordenTrabajoForm.addEventListener("submit", function(event) {
            event.preventDefault();

            const nombreTecnico = document.getElementById("tecnico_asignado").value;
            const fechaActividad = document.getElementById("fecha_actividad").value;
            const numeroSolicitud = document.getElementById("consecutivo").value;
            const tareaId = document.getElementById("tarea_id").value;

            console.log("Asignar Técnico - Datos enviados:");
            console.log("Número de Solicitud:", numeroSolicitud);
            console.log("Nombre del Técnico:", nombreTecnico);
            console.log("Fecha de Actividad:", fechaActividad);
            console.log("Tarea Preventiva ID:", tareaId);

            if (!fechaActividad) {
                alert("La fecha de actividad es obligatoria.");
                return;
            }

            const url = tareaId ? `/Gestion_ot/tarea/${tareaId}/asignar/` : '/Gestion_ot/actualizar_estado_solicitud/';
            const payload = tareaId ? {
                tecnico: nombreTecnico,
                fecha: fechaActividad,
                estado: "en_progreso"
            } : {
                numero: numeroSolicitud,
                estado: "en proceso",
                tecnico: nombreTecnico,
                fecha: fechaActividad
            };

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify(payload)
            })
            .then(response => {
                console.log("Respuesta del servidor:", response);
                if (!response.ok) {
                    throw new Error('Error en la actualización');
                }
                return response.json();
            })
            .then(data => {
                console.log('Actualización exitosa:', data);
                if (tareaId) {
                    closeModal();
                    window.location.reload();
                    return;
                }

                const targetColumn = document.getElementById("ot_en_proceso");
                const card = document.getElementById("card-" + numeroSolicitud);
                if (card && targetColumn) {
                    targetColumn.appendChild(card);
                }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    });
});

// Función para abrir el modal y establecer los valores
function openModal(solicitud) {
    const numeroActivoInput = document.getElementById("consecutivo");
    const fechaActividadInput = document.getElementById("fecha_actividad");
    const tecnicoAsignadoInput = document.getElementById("tecnico_asignado");

    // Verificar que los elementos existen antes de establecer sus valores
    if (numeroActivoInput && fechaActividadInput && tecnicoAsignadoInput) {
        numeroActivoInput.value = solicitud.numero; // Establece el número de solicitud en el campo del modal
        fechaActividadInput.value = "";  // Limpia el campo de fecha
        tecnicoAsignadoInput.value = "";  // Limpia el campo de técnico asignado
        document.getElementById("tecnicoModal").style.display = "block"; // Muestra el modal
    } else {
        console.error("No se encontraron los elementos del modal.");
    }
}

let clickStartTime;

function startClick(event) {
    clickStartTime = new Date().getTime();
}

function endClick(event, numeroActivo) {
    const clickEndTime = new Date().getTime();
    const clickDuration = clickEndTime - clickStartTime;

    // Si el tiempo de clic es menor a 200 ms, considerarlo como un clic
    if (clickDuration < 200) {
        openSolicitudModal(numeroActivo);
    }
}
window.startClick = startClick;
window.endClick = endClick;

// Función para actualizar datos del modal
function actualizarModalConDatos(ot) {
    if (!ot) {
        console.error('El objeto "ot" no existe o es nulo.');
        return;
    }

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
        } else {
            console.warn(`El elemento con id "${id}" no existe.`);
        }
    };

    actualizarElemento('modalTecnicoAsignado', ot.tecnico_asignado);
    actualizarElemento('modalFechaActividad', ot.fecha_actividad);
    actualizarElemento('modalTipoMantenimiento', cierre_ot.tipo_mantenimiento);
    actualizarElemento('modalMaterialesUtilizados', cierre_ot.materiales_utilizados);
    actualizarElemento('modalCorreoTecnico', cierre_ot.correo_tecnico);
    actualizarElemento('modalDescripcionFalla', cierre_ot.descripcion_falla);
    actualizarElemento('modalFechaInicioActividad', cierre_ot.fecha_inicio_actividad);
    actualizarElemento('modalObservaciones', cierre_ot.observaciones);
    actualizarElemento('modalNombreTecnico', cierre_ot.nombre_tecnico);
    actualizarElemento('modalCausaFalla', cierre_ot.causa_falla);
    actualizarElemento('modalHoraInicio', cierre_ot.hora_inicio);
    actualizarElemento('modalDocumentoTecnico', cierre_ot.documento_tecnico);
    actualizarElemento('modalTipoIntervencion', cierre_ot.tipo_intervencion);
}

// Función para actualizar el estado de la solicitud en todas las vistas
function actualizarEstadoEnVistas(numeroSolicitud, nuevoEstado) {
    // Actualizar en la vista Kanban
    const card = document.getElementById("card-" + numeroSolicitud);
    if (card) {
        const targetColumn = document.getElementById("ot_finalizada");
        if (targetColumn) {
            targetColumn.appendChild(card);
        }
    }

    // Actualizar en la vista del calendario
    const calendarEvent = calendar.getEventById(numeroSolicitud);
    if (calendarEvent) {
        calendarEvent.setProp('color', 'green'); // Cambiar el color del evento a verde
        calendarEvent.setExtendedProp('estado', nuevoEstado);
    }

    // Actualizar en la vista de la lista
    const listItem = document.querySelector(`.ver-solicitud[data-consecutivo="${numeroSolicitud}"]`);
    if (listItem) {
        const estadoElement = listItem.querySelector('td:nth-child(6)');
        if (estadoElement) {
            estadoElement.textContent = nuevoEstado;
        } else {
            console.warn(`No se encontró el elemento con la clase 'estado' dentro del elemento de la lista con data-consecutivo="${numeroSolicitud}"`);
        }
    } else {
        console.warn(`No se encontró el elemento de la lista con data-consecutivo="${numeroSolicitud}". Asegúrate de que el elemento de la lista tenga el atributo data-consecutivo="${numeroSolicitud}".`);
    }
}

// Modificar la función que maneja la finalización de una solicitud
const finalizarOTBtn = document.getElementById("finalizarOTBtn");

if (finalizarOTBtn) {
    finalizarOTBtn.addEventListener("click", function() {
        const numeroSolicitud = document.getElementById("modalNumeroActivo").textContent.trim();
        const fechaActividad = document.getElementById("modalFechaActividad").textContent.trim();
        const tecnicoAsignado = document.getElementById("modalTecnicoAsignado").textContent.trim();

        fetch('/Gestion_ot/actualizar_estado_solicitud/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                numero: numeroSolicitud,
                estado: "finalizada",
                tecnico: tecnicoAsignado,
                fecha: fechaActividad
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error en la actualización');
            }
            return response.json();
        })
        .then(data => {
            console.log('Actualización exitosa:', data);
            actualizarEstadoEnVistas(numeroSolicitud, "finalizada");
            closeSolicitudModal();
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    });
}

// Función para cerrar el modal de solicitud
function closeSolicitudModal() {
    document.getElementById('solicitudModal').style.display = 'none';
}

// Hacer que la función esté disponible en el ámbito global
window.closeSolicitudModal = closeSolicitudModal;




















document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM completamente cargado y parseado');

    var calendarEl = document.getElementById('calendar-view');
    if (!calendarEl) {
        console.error('No se encontró el elemento con id "calendar-view"');
        return;
    }

    var eventsData = calendarEl.getAttribute('data-events');
    if (!eventsData) {
        console.error('No se encontró el atributo "data-events" en el elemento "calendar-view"');
        return;
    }

    try {
        eventsData = JSON.parse(eventsData);
    } catch (e) {
        console.error('Error al parsear los datos de eventos:', e);
        return;
    }

    var events = eventsData.map(event => ({
        title: `${event.consecutivo} - ${event.tecnico_asignado}`,
        start: event.fecha_actividad,
        url: event.url
    }));

    console.log('Eventos para el calendario:', events);

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        events: events
    });

    calendar.render();
    console.log('Calendario renderizado');

    // Alternar entre vistas
    document.getElementById('table-view-button').addEventListener('click', function() {
        console.log('Vista de Tabla clickeada');
        document.getElementById('table-view').style.display = 'block';
        document.querySelector('.calendar-container').style.display = 'none';
    });

    document.getElementById('calendar-view-button').addEventListener('click', function() {
        console.log('Vista de Calendario clickeada');
        document.getElementById('table-view').style.display = 'none';
        document.querySelector('.calendar-container').style.display = 'block';
        calendar.render(); // Renderizar el calendario nuevamente
        calendar.updateSize(); // Actualizar el tamaño del calendario
    });
});