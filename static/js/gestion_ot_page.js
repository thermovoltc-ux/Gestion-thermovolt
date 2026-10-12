// Manejo de tarjetas de mantenimiento preventivo
document.addEventListener('DOMContentLoaded', function() {
    // Agregar event listeners a tarjetas preventivas
    const tarjetasPreventivas = document.querySelectorAll('.kanban-card-preventivo');
    
    tarjetasPreventivas.forEach(tarjeta => {
        tarjeta.style.cursor = 'pointer';
        let touchHandled = false;

        tarjeta.addEventListener('click', function(e) {
            if (touchHandled) {
                touchHandled = false;
                return;
            }
            e.stopPropagation();
            openPreventivoModal(this);
        });

        tarjeta.addEventListener('touchstart', function(event) {
            if (event.touches && event.touches.length === 1) {
                this._touchStartX = event.touches[0].clientX;
                this._touchStartY = event.touches[0].clientY;
                this._touchStartTime = Date.now();
            }
        }, { passive: true });

        tarjeta.addEventListener('touchend', function(event) {
            if (!event.changedTouches || event.changedTouches.length !== 1) return;
            const touchEndX = event.changedTouches[0].clientX;
            const touchEndY = event.changedTouches[0].clientY;
            const touchDuration = Date.now() - (this._touchStartTime || 0);
            const moveDistance = Math.hypot(touchEndX - (this._touchStartX || 0), touchEndY - (this._touchStartY || 0));

            if (touchDuration < 300 && moveDistance < 10) {
                touchHandled = true;
                event.stopPropagation();
                event.preventDefault();
                openPreventivoModal(this);
            }
        }, { passive: false });
    });

    const crearSolicitudPreventivoBtn = document.getElementById('crearSolicitudPreventivoBtn');
    if (crearSolicitudPreventivoBtn) {
        crearSolicitudPreventivoBtn.addEventListener('click', function() {
            const preventivoModal = document.getElementById('preventivoModal');
            const tareaId = preventivoModal?.dataset?.tareaId;
            if (tareaId) {
                closePreventivoModal();
                // Usar el mismo flujo de asignación que solicitudes
                openTecnicoModal({ numero: '', tareaId: tareaId });
            }
        });
    }

    // Manejo táctil para tarjetas de solicitudes OT normales
    const tarjetasOT = document.querySelectorAll('.kanban-card:not(.kanban-card-preventivo)');
    tarjetasOT.forEach(card => {
        let touchHandledOT = false;

        card.addEventListener('click', function(e) {
            if (touchHandledOT) {
                touchHandledOT = false;
                return;
            }
            const numeroActivo = this.dataset.numeroActivo;
            if (numeroActivo) {
                e.stopPropagation();
                openSolicitudModal(numeroActivo);
            }
        });

        card.addEventListener('touchstart', function(event) {
            if (event.touches && event.touches.length === 1) {
                this._touchStartX = event.touches[0].clientX;
                this._touchStartY = event.touches[0].clientY;
                this._touchStartTime = Date.now();
            }
        }, { passive: true });

        card.addEventListener('touchend', function(event) {
            if (!event.changedTouches || event.changedTouches.length !== 1) return;
            const touchEndX = event.changedTouches[0].clientX;
            const touchEndY = event.changedTouches[0].clientY;
            const touchDuration = Date.now() - (this._touchStartTime || 0);
            const moveDistance = Math.hypot(touchEndX - (this._touchStartX || 0), touchEndY - (this._touchStartY || 0));

            if (touchDuration < 300 && moveDistance < 10) {
                const numeroActivo = this.dataset.numeroActivo;
                if (numeroActivo) {
                    touchHandledOT = true;
                    event.stopPropagation();
                    event.preventDefault();
                    openSolicitudModal(numeroActivo);
                }
            }
        }, { passive: false });
    });

    function openPreventivoModal(tarjeta) {
        const preventivoModal = document.getElementById('preventivoModal');
        if (!preventivoModal) return;

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

    // Soporta taps móviles en tarjetas preventivas
    tarjetasPreventivas.forEach(tarjeta => {
        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartTime = 0;

        tarjeta.addEventListener('touchstart', function(event) {
            if (event.touches && event.touches.length === 1) {
                touchStartX = event.touches[0].clientX;
                touchStartY = event.touches[0].clientY;
                touchStartTime = Date.now();
            }
        }, { passive: true });

        tarjeta.addEventListener('touchend', function(event) {
            if (!event.changedTouches || event.changedTouches.length !== 1) return;
            const touchEndX = event.changedTouches[0].clientX;
            const touchEndY = event.changedTouches[0].clientY;
            const touchDuration = Date.now() - touchStartTime;
            const moveDistance = Math.hypot(touchEndX - touchStartX, touchEndY - touchStartY);

            if (touchDuration < 300 && moveDistance < 10) {
                event.stopPropagation();
                openPreventivoModal(this);
            }
        }, { passive: true });
    });
    window.closePreventivoModal = function() {
        const preventivoModal = document.getElementById('preventivoModal');
        if (preventivoModal) {
            preventivoModal.style.display = 'none';
        }
    };
    
    // Actualizar estado de tarea
    function actualizarTareaMantenimiento(tareaId, nuevoEstado) {
        const formData = new FormData();
        formData.append('estado', nuevoEstado);
        
        // Obtener CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                          document.querySelector('[name=_csrftoken]')?.value ||
                          getCookie('csrftoken');
        
        fetch(`/Gestion_ot/tarea/${tareaId}/actualizar/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Actualizar la tarjeta visualmente
                const tarjeta = document.querySelector(`[data-tarea-id="${tareaId}"]`);
                if (tarjeta) {
                    // Cambiar color según estado
                    if (nuevoEstado === 'completada') {
                        tarjeta.style.opacity = '0.7';
                        tarjeta.style.backgroundColor = '#f0fdf4';
                    } else if (nuevoEstado === 'cancelada') {
                        tarjeta.style.opacity = '0.5';
                        tarjeta.style.backgroundColor = '#fee2e2';
                    }
                    
                    // Mostrar notificación
                    mostrarNotificacion(data.message, 'success');
                }
            } else {
                mostrarNotificacion('Error al actualizar tarea', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            mostrarNotificacion('Error al actualizar tarea', 'error');
        });
    }

    function abrirAsignarPreventivo(tareaId) {
        const tareaInput = document.getElementById('tarea_id');
        const consecutivoInput = document.getElementById('consecutivo');
        const fechaActividadInput = document.getElementById('fecha_actividad');
        const tecnicoAsignadoInput = document.getElementById('tecnico_asignado');

        if (tareaInput && consecutivoInput && fechaActividadInput && tecnicoAsignadoInput) {
            tareaInput.value = tareaId;
            consecutivoInput.value = '';
            fechaActividadInput.value = '';
            tecnicoAsignadoInput.value = '';
            document.getElementById('tecnicoModal').style.display = 'block';
        }
    }
    
    // Utilidad: obtener cookie
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Mostrar notificación
    function mostrarNotificacion(mensaje, tipo = 'info') {
        const notif = document.createElement('div');
        notif.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 20px;
            background-color: ${tipo === 'success' ? '#22c55e' : '#ef4444'};
            color: white;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            font-weight: 500;
            animation: slideIn 0.3s ease;
        `;
        notif.textContent = mensaje;
        document.body.appendChild(notif);
        
        setTimeout(() => {
            notif.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notif.remove(), 300);
        }, 3000);
    }
});

// Estilos de animación
const styles = document.createElement('style');
styles.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(styles);