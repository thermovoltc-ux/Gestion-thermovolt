import './csrf.js';

// Declarar la variable calendar en el ámbito global
let calendar;
let calendarRendered = false;

// Inicialización del calendario
document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    const solicitudes = calendarEl ? JSON.parse(calendarEl.getAttribute('data-events')) : [];

    if (calendarEl) {
        const events = [];

        const getEventColor = (estado) => {
            switch (estado) {
                case 'solicitado':
                    return '#6c757d';
                case 'en proceso':
                    return '#fd7e14';
                case 'en revision':
                    return '#0d6efd';
                case 'finalizada':
                    return '#198754';
                default:
                    return '#212529';
            }
        };

        const capitalizeStatus = (estado) => {
            if (!estado) return '';
            return estado
                .toString()
                .toLowerCase()
                .split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        };

        for (let solicitud of solicitudes) {
            const color = getEventColor(solicitud.estado);
            events.push({
                id: solicitud.consecutivo,
                title: `OT ${solicitud.consecutivo}`,
                start: solicitud.fecha_creacion,
                backgroundColor: color,
                borderColor: color,
                textColor: '#ffffff',
                extendedProps: {
                    ...solicitud,
                    statusLabel: capitalizeStatus(solicitud.estado)
                }
            });
        }

        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: events,
            eventContent: function(info) {
                const statusText = info.event.extendedProps.statusLabel;
                const container = document.createElement('div');
                container.className = 'fc-event-custom';

                const title = document.createElement('div');
                title.className = 'fc-event-custom-title';
                title.textContent = info.event.title;
                container.appendChild(title);

                if (statusText) {
                    const status = document.createElement('div');
                    status.className = 'fc-event-custom-status';
                    status.textContent = statusText;
                    container.appendChild(status);
                }

                return { domNodes: [container] };
            },
            eventClick: function(info) {
                if (typeof window.openSolicitudModal === 'function') {
                    window.openSolicitudModal(info.event.extendedProps.consecutivo);
                }
            },
            height: '100%'
        });

        window.calendar = calendar;

        window.renderCalendar = function () {
            if (!calendarRendered) {
                calendar.render();
                calendarRendered = true;
            }
            calendar.updateSize();
        };
    }
});

// Exponer calendar globalmente si no se ha creado aún
if (!window.calendar) {
    window.calendar = calendar;
}

