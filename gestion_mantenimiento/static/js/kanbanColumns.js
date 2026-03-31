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
window.dropDesktop = dropDesktop;

// Touch support for mobile
let draggedElement = null;

function touchStart(event) {
    draggedElement = event.target.closest('.kanban-card');
    if (draggedElement) {
        draggedElement.style.opacity = '0.5';
        event.preventDefault();
    }
}

function touchMove(event) {
    if (draggedElement) {
        event.preventDefault();
    }
}

function touchEnd(event) {
    if (draggedElement) {
        draggedElement.style.opacity = '1';
        const touch = event.changedTouches[0];
        const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
        const column = dropTarget ? dropTarget.closest('.kanban-column') : null;

        if (column) {
            const columnId = column.id;

            if (columnId === "ot_en_proceso") {
                const numeroSolicitud = draggedElement.id.split('-')[1];
                const solicitud = { numero: numeroSolicitud };
                window.openModal(solicitud); // Usar window para acceder a función de modals
                return;
            }

            column.appendChild(draggedElement);
            updateSolicitudState(draggedElement, columnId);
        }
        draggedElement = null;
    }
}

// Agregar event listeners para touch
document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('touchstart', touchStart, { passive: false });
    document.addEventListener('touchmove', touchMove, { passive: false });
    document.addEventListener('touchend', touchEnd, { passive: false });
});

// Función para manejar el evento de 'drop'
function dropDesktop(event) {
    event.preventDefault();
    const data = event.dataTransfer.getData("text/plain");
    const card = document.getElementById(data);
    const column = event.target.closest('.kanban-column');

    if (column) {
        const columnId = column.id;

        if (columnId === "ot_en_proceso") {
            const numeroSolicitud = card.id.split('-')[1];
            const solicitud = { numero: numeroSolicitud };
            window.openModal(solicitud); // Usar window para acceder a función de modals
            return;
        }

        column.appendChild(card);
        updateSolicitudState(card, columnId);
    }
}

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
            window.openModal(solicitud); // Usar window para acceder a función de modals
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

// Función para manejar vistas y filtros
document.addEventListener('DOMContentLoaded', function () {
    const djangoUrlEl = document.querySelector('#django-url');
    const baseUrl = djangoUrlEl ? djangoUrlEl.getAttribute('data-url') : '/solicitudes/lista-solicitudes/';

    function showKanban() {
        document.querySelector('.kanban-container').style.display = 'flex';
        document.querySelector('.calendar-container').style.display = 'none';
        document.querySelector('.list-container').style.display = 'none';
    }

    function showCalendar() {
        document.querySelector('.kanban-container').style.display = 'none';
        document.querySelector('.calendar-container').style.display = 'block';
        document.querySelector('.list-container').style.display = 'none';
        if (window.renderCalendar) {
            window.renderCalendar();
        } else if (window.calendar) {
            window.calendar.updateSize();
        }
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

    // Agregar event listeners para touch
    document.addEventListener('touchstart', touchStart, { passive: false });
    document.addEventListener('touchmove', touchMove, { passive: false });
    document.addEventListener('touchend', touchEnd, { passive: false });
});