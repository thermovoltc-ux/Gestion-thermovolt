function asignarTarea(tareaId) {
        alert('Asignar tarea ' + tareaId + ' (Funcionalidad a implementar)');
    }

    function marcarProgreso(tareaId) {
        actualizarTarea(tareaId, 'en_progreso');
    }

    function marcarCompletada(tareaId) {
        actualizarTarea(tareaId, 'completada');
    }

    function actualizarTarea(tareaId, estado) {
        fetch(`/Gestion_ot/tarea/${tareaId}/actualizar/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: `estado=${estado}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(data.message);
                location.reload();
            }
        })
        .catch(error => console.error('Error:', error));
    }
window.asignarTarea = asignarTarea;
window.marcarProgreso = marcarProgreso;
window.marcarCompletada = marcarCompletada;