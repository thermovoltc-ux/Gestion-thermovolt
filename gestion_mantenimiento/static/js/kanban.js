
document.addEventListener("DOMContentLoaded", function () {
    const cards = document.querySelectorAll(".kanban-card");
    const columns = document.querySelectorAll(".kanban-column");

    // Configura las tarjetas como arrastrables
    cards.forEach(card => {
        card.draggable = true;
        card.addEventListener("dragstart", dragStart);
    });

    // Configura las columnas para aceptar tarjetas arrastradas
    columns.forEach(column => {
        column.addEventListener("dragover", dragOver);
        column.addEventListener("drop", drop);
    });

    function crearTarjeta(solicitud) {
        const columnaSolicitudes = document.querySelector('.kanban-column[data-columna="Solicitudes"]');
        const nuevaTarjeta = document.createElement('div');
        nuevaTarjeta.className = 'kanban-card';
        nuevaTarjeta.id = `card-${solicitud.id}`; // Asigna un ID a la tarjeta
        nuevaTarjeta.innerHTML = `<h3>${solicitud.titulo}</h3><p>${solicitud.descripcion}</p>`; // Asigna contenido
        columnaSolicitudes.appendChild(nuevaTarjeta);
        console.log("Tarjeta creada:", nuevaTarjeta); // Verificar tarjeta creada
    }

    // Funciones de arrastre
    function dragStart(e) {
        e.dataTransfer.setData("text/plain", e.target.id);
    }

    function dragOver(e) {
        e.preventDefault(); // Permitir el arrastre
    }

    function drop(e) {
        e.preventDefault(); // Asegúrate de prevenir el comportamiento por defecto
        const id = e.dataTransfer.getData("text/plain");
        const card = document.getElementById(id);
        
        const column = e.target.closest(".kanban-column");
        if (column) {
            column.appendChild(card); // Mover la tarjeta a la columna
        }
    }
});

// Funciones para mostrar diferentes vistas
function showKanban() {
    document.querySelector(".kanban-container").style.display = "flex";
    document.querySelector(".calendar-view").style.display = "none";
    document.querySelector(".list-view").style.display = "none";
}

function showCalendar() {
    document.querySelector(".kanban-container").style.display = "none";
    document.querySelector(".calendar-view").style.display = "block";
    document.querySelector(".list-view").style.display = "none";
}

function showList() {
    document.querySelector(".kanban-container").style.display = "none";
    document.querySelector(".calendar-view").style.display = "none";
    document.querySelector(".list-view").style.display = "block";
}

function applyDateFilter() {
    const startDate = document.getElementById("filter-date-start").value;
    const endDate = document.getElementById("filter-date-end").value;
    // Lógica para filtrar tarjetas por fecha
    // Aquí deberías implementar el código para ocultar/mostrar tarjetas según las fechas
}
