import './csrf.js';

function openSolicitudModal(consecutivo) {
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

// Función para cerrar el modal
function closeModal() {
    document.getElementById("tecnicoModal").style.display = "none"; // Oculta el modal
}

window.closeModal = closeModal;

// Enviar el formulario del modal al servidor
document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll('.kanban-card').forEach(card => {
        card.addEventListener('click', function() {
            const consecutivo = this.getAttribute('data-numero-activo');
            openSolicitudModal(consecutivo);
        });
    });

    document.querySelectorAll('.ver-solicitud').forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            const consecutivo = this.getAttribute('data-consecutivo');
            openSolicitudModal(consecutivo);
        });
    });

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

    document.getElementById("OrdenTrabajoForm").addEventListener("submit", function(event) {
        event.preventDefault();

        const nombreTecnico = document.getElementById("tecnico_asignado").value;
        const fechaActividad = document.getElementById("fecha_actividad").value;
        const numeroSolicitud = document.getElementById("consecutivo").value;

        console.log("Asignar Técnico - Datos enviados:");
        console.log("Número de Solicitud:", numeroSolicitud);
        console.log("Nombre del Técnico:", nombreTecnico);
        console.log("Fecha de Actividad:", fechaActividad);

        if (!fechaActividad) {
            alert("La fecha de actividad es obligatoria.");
            return;
        }

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
        .then(response => {
            console.log("Respuesta del servidor:", response);
            if (!response.ok) {
                throw new Error('Error en la actualización');
            }
            return response.json();
        })
        .then(data => {
            console.log('Actualización exitosa:', data);
            const targetColumn = document.getElementById("ot_en_proceso");
            const card = document.getElementById("card-" + numeroSolicitud);
            targetColumn.appendChild(card);
            closeModal();
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

window.openModal = openModal;

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
}

// Función para actualizar estado en vistas (si es necesaria)
function actualizarEstadoEnVistas(numeroSolicitud, estado) {
    // Implementación si es necesaria
}