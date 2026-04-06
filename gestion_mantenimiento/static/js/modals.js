// Función para obtener CSRF token
function getCSRFToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || 
           document.body.dataset.csrftoken || '';
}

function handleJsonResponse(response) {
    const contentType = response.headers.get('content-type') || '';

    if (!response.ok) {
        return response.text().then(text => {
            const message = text ? text : response.statusText;
            throw new Error(`HTTP ${response.status}: ${message}`);
        });
    }

    if (!contentType.includes('application/json')) {
        return response.text().then(text => {
            throw new Error(`Respuesta inválida del servidor: ${text || response.statusText}`);
        });
    }

    return response.json();
}

function validateServerResponse(data) {
    if (!data || data.status === 'error') {
        throw new Error(data?.message || 'Respuesta inesperada del servidor');
    }
    return data;
}

// Función para formatear fechas ISO a formato legible
function formatearFecha(fechaISO) {
    if (!fechaISO) return '';
    try {
        // Si ya es un formato legible, devolverlo tal cual
        if (!fechaISO.includes('T')) return fechaISO;
        
        const fecha = new Date(fechaISO);
        const opciones = { year: 'numeric', month: '2-digit', day: '2-digit' };
        return fecha.toLocaleDateString('es-ES', opciones);
    } catch (e) {
        return fechaISO;
    }
}

function openSolicitudModal(consecutivo) {
    if (!consecutivo) {
        console.warn('OpenSolicitudModal called without consecutivo');
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
                        // Formatear fechas automáticamente
                        let valorFormateado = valor;
                        if ((id.includes('Fecha') || id.includes('fecha')) && typeof valor === 'string' && valor.includes('T')) {
                            valorFormateado = formatearFecha(valor);
                        }
                        elemento.textContent = valorFormateado;
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

            const estadoNormalized = data.estado ? data.estado.toString().toLowerCase().trim() : '';
            
            // Mostrar finalizarOTBtn cuando estado es 'en revision'
            const finalizarOTBtn = document.getElementById('finalizarOTBtn');
            if (estadoNormalized === 'en revision') {
                finalizarOTBtn.style.display = 'block';
            } else {
                finalizarOTBtn.style.display = 'none';
            }

            // Mostrar asignarTecnicoBtn cuando estado es 'solicitado'
            const asignarTecnicoBtn = document.getElementById('asignarTecnicoBtn');
            if (estadoNormalized === 'solicitado') {
                asignarTecnicoBtn.style.display = 'block';
            } else {
                asignarTecnicoBtn.style.display = 'none';
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
    const modalError = document.getElementById('modalError');
    if (modalError) {
        modalError.style.display = 'none';
        modalError.textContent = '';
    }
}

window.closeModal = closeModal;

// Enviar el formulario del modal al servidor
document.addEventListener("DOMContentLoaded", function() {
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

    const finalizarOTBtn = document.getElementById("finalizarOTBtn");

    if (finalizarOTBtn) {
        finalizarOTBtn.addEventListener("click", function() {
                const numeroSolicitud = document.getElementById("modalNumeroActivo")?.textContent.trim();

                if (!numeroSolicitud) {
                    alert('No se pudo identificar la solicitud a finalizar.');
                    return;
                }

                finalizarOTBtn.disabled = true;

                fetch('/Gestion_ot/actualizar_estado_solicitud/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: JSON.stringify({
                        numero: numeroSolicitud,
                        estado: "finalizada"
                    })
                })
                .then(handleJsonResponse)
                .then(validateServerResponse)
                .then(data => {
                    console.log('Actualización exitosa:', data);
                    closeSolicitudModal();
                    window.location.reload();
                })
                .catch((error) => {
                    console.error('Error:', error);
                    alert('Error al finalizar la OT: ' + error.message);
                })
                .finally(() => {
                    finalizarOTBtn.disabled = false;
                });
        });
    }

    // Event listener para el botón "Asignar Técnico"
    const asignarTecnicoBtn = document.getElementById("asignarTecnicoBtn");
    if (asignarTecnicoBtn) {
        asignarTecnicoBtn.addEventListener("click", function() {
            const numeroSolicitud = document.getElementById("modalNumeroActivo").textContent.trim();
            
            // Cerrar el modal de información
            document.getElementById("solicitudModal").style.display = "none";
            
            // Establecer el número de solicitud en el formulario del modal
            document.getElementById("consecutivo").value = numeroSolicitud;
            document.getElementById("tarea_id").value = '';
            
            // Abrir el formulario para asignar técnico
            document.getElementById("tecnicoModal").style.display = "block";
        });
    }

    // Validar que el formulario existe antes de agregar listener
    const ordenTrabajoForm = document.getElementById("OrdenTrabajoForm");
    if (ordenTrabajoForm) {
        ordenTrabajoForm.addEventListener("submit", function(event) {
            event.preventDefault();

            const nombreTecnico = document.getElementById("tecnico_asignado").value;
            const fechaActividad = document.getElementById("fecha_actividad").value;
            const numeroSolicitud = document.getElementById("consecutivo").value;
            const tareaId = document.getElementById("tarea_id").value;

            if (!fechaActividad) {
                alert("La fecha de actividad es obligatoria.");
                return;
            }

            const url = tareaId ? `/Gestion_ot/tarea/${tareaId}/asignar/` : '/Gestion_ot/actualizar_estado_solicitud/';
            const payload = tareaId
                ? {
                    tecnico: nombreTecnico,
                    fecha: fechaActividad,
                    estado: "en_progreso"
                }
                : {
                    numero: numeroSolicitud,
                    estado: "en proceso",
                    tecnico: nombreTecnico,
                    fecha: fechaActividad
                };

            fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify(payload)
            })
            .then(handleJsonResponse)
            .then(validateServerResponse)
            .then(data => {
                console.log('Asignación exitosa:', data);
                closeModal();
                if (data.consecutivo) {
                    window.location.reload();
                } else if (numeroSolicitud) {
                    const targetColumn = document.getElementById("ot_en_proceso");
                    const card = document.getElementById("card-" + numeroSolicitud);
                    if (card && targetColumn) {
                        targetColumn.appendChild(card);
                    }
                }
            })
            .catch((error) => {
                console.error('Error:', error);
                const modalError = document.getElementById('modalError');
                if (modalError) {
                    modalError.textContent = 'Error al asignar la OT: ' + error.message;
                    modalError.style.display = 'block';
                }
            });
        });
    }
});

// Función para abrir el modal de asignación de técnico (para solicitudes y preventivos)
function openTecnicoModal(params) {
    // params puede ser: { numero, tareaId }
    const form = document.getElementById("OrdenTrabajoForm");
    if (!form) {
        console.error("No se encontró el formulario OrdenTrabajoForm");
        return;
    }

    // Rellenar valores
    const consecutivoInput = document.getElementById("consecutivo");
    const tareaIdInput = document.getElementById("tarea_id");
    const fechaActividadInput = document.getElementById("fecha_actividad");
    const tecnicoAsignadoInput = document.getElementById("tecnico_asignado");

    if (consecutivoInput) consecutivoInput.value = params.numero || '';
    if (tareaIdInput) tareaIdInput.value = params.tareaId || '';
    if (fechaActividadInput) fechaActividadInput.value = '';
    if (tecnicoAsignadoInput) tecnicoAsignadoInput.value = '';

    const modalError = document.getElementById('modalError');
    if (modalError) {
        modalError.style.display = 'none';
        modalError.textContent = '';
    }

    document.getElementById("tecnicoModal").style.display = "block";
}

window.openTecnicoModal = openTecnicoModal;

// Función para abrir el modal y establecer los valores (compatibilidad con drag-drop)
function openModal(solicitud) {
    openTecnicoModal({ numero: solicitud.numero, tareaId: '' });
}

window.openModal = openModal;

// Función para abrir el modal de preventivo (para drag-drop)
function openPreventivoModalForDragDrop(tareaId) {
    const tarjeta = document.getElementById(`tarea-${tareaId}`);
    if (!tarjeta) {
        console.error(`No se encontró la tarjeta con ID: tarea-${tareaId}`);
        return;
    }

    const preventivoModal = document.getElementById('preventivoModal');
    if (!preventivoModal) {
        console.error('No se encontró el modal de preventivos');
        return;
    }

    // Rellenar los datos del modal con los atributos de la tarjeta
    preventivoModal.dataset.tareaId = tarjeta.dataset.tareaId;
    document.getElementById('preventivoPlan').textContent = tarjeta.dataset.planNombre || 'N/A';
    document.getElementById('preventivoEquipo').textContent = tarjeta.dataset.equipoNombre || 'N/A';
    document.getElementById('preventivoActividad').textContent = tarjeta.dataset.actividadNombre || 'N/A';
    document.getElementById('preventivoFecha').textContent = tarjeta.dataset.fechaProgramada || 'N/A';
    document.getElementById('preventivoEstado').textContent = tarjeta.dataset.estado || 'N/A';
    document.getElementById('preventivoTecnico').textContent = tarjeta.dataset.tecnico || 'N/A';
    document.getElementById('preventivoObservaciones').textContent = tarjeta.dataset.observaciones || 'N/A';
    
    preventivoModal.style.display = 'block';
}

window.openPreventivoModalForDragDrop = openPreventivoModalForDragDrop;

window.addEventListener('click', function(event) {
    const tecnicoModal = document.getElementById('tecnicoModal');
    const solicitudModal = document.getElementById('solicitudModal');

    if (event.target === tecnicoModal) {
        closeModal();
    }
    if (event.target === solicitudModal) {
        closeSolicitudModal();
    }
});

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

// Función para actualizar estado en vistas
function actualizarEstadoEnVistas(numeroSolicitud, estado) {
    // Actualizar en la vista Kanban
    const card = document.getElementById("card-" + numeroSolicitud);
    if (card) {
        const targetColumn = document.getElementById("ot_finalizada");
        if (targetColumn) {
            targetColumn.querySelector('.kanban-content').appendChild(card);
            console.log('Tarjeta movida a columna finalizada');
        }
    }

    // Actualizar en la vista de la lista
    const listItem = document.querySelector(`.ver-solicitud[data-consecutivo="${numeroSolicitud}"]`);
    if (listItem) {
        const estadoElement = listItem.querySelector('td:nth-child(6)');
        if (estadoElement) {
            estadoElement.textContent = estado;
        }
    }
}