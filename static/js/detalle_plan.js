function getCsrfToken() {
    const tokenInput = document.querySelector('#preventivoAssignForm [name=csrfmiddlewaretoken]');
    return tokenInput ? tokenInput.value : null;
}

function openPreventivoAssignModal(button) {
    const tareaId = button.dataset.tareaId;
    const planNombre = button.dataset.plan;
    const equipoNombre = button.dataset.equipo;
    const actividadNombre = button.dataset.actividad;
    const fechaProgramada = button.dataset.fecha;
    const tecnicoUsername = button.dataset.tecnico;

    document.getElementById('preventivo_tarea_id').value = tareaId;
    document.getElementById('preventivo_plan').value = planNombre || '';
    document.getElementById('preventivo_equipo').value = equipoNombre || '';
    document.getElementById('preventivo_actividad').value = actividadNombre || '';
    document.getElementById('preventivo_fecha').value = fechaProgramada || '';
    document.getElementById('preventivo_tecnico').value = tecnicoUsername || '';
    document.getElementById('preventivoAssignError').style.display = 'none';
    document.getElementById('preventivoAssignModal').style.display = 'block';
}

function closePreventivoAssignModal() {
    const modal = document.getElementById('preventivoAssignModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function marcarTareaCompletada(tareaId) {
    const csrfToken = getCsrfToken();
    const formData = new FormData();
    formData.append('estado', 'completada');

    fetch(`/Gestion_ot/tarea/${tareaId}/actualizar/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'No se pudo marcar la tarea como completada.');
        }
    })
    .catch(error => {
        console.error(error);
        alert('Error al marcar la tarea como completada.');
    });
}

window.openPreventivoAssignModal = openPreventivoAssignModal;
window.closePreventivoAssignModal = closePreventivoAssignModal;
window.marcarTareaCompletada = marcarTareaCompletada;

const assignButton = document.getElementById('preventivoAssignButton');
if (assignButton) {
    assignButton.addEventListener('click', function () {
        const tareaId = document.getElementById('preventivo_tarea_id').value;
        const tecnico = document.getElementById('preventivo_tecnico').value;
        const fecha = document.getElementById('preventivo_fecha').value;
        const errorDiv = document.getElementById('preventivoAssignError');

        if (!tecnico || !fecha) {
            errorDiv.textContent = 'Debes seleccionar un técnico y una fecha.';
            errorDiv.style.display = 'block';
            return;
        }

        const csrfToken = getCsrfToken();
        fetch(`/Gestion_ot/tarea/${tareaId}/asignar/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ tecnico: tecnico, fecha: fecha, estado: 'en_progreso' })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                closePreventivoAssignModal();
                window.location.reload();
            } else {
                errorDiv.textContent = data.message || 'Error al asignar la tarea preventiva.';
                errorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            errorDiv.textContent = 'Error de red al asignar la tarea preventiva.';
            errorDiv.style.display = 'block';
            console.error(error);
        });
    });
}

window.onclick = function(event) {
    const modal = document.getElementById('preventivoAssignModal');
    if (event.target === modal) {
        closePreventivoAssignModal();
    }
};
