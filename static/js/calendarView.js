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
            events.push({
                id: solicitud.consecutivo,
                title: `Solicitud ${solicitud.consecutivo}`,
                start: solicitud.fecha_creacion,
                color: color,
                extendedProps: solicitud
            });
        }

        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: events,
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

