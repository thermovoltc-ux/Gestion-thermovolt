document.addEventListener('DOMContentLoaded', function() {
    // Modal info OT
    var infoModal = document.getElementById('infoOtModal');
    var closeInfo = document.getElementById('closeInfoOtModal');
    var equipoSpan = document.getElementById('infoEquipo');
    var descripcionSpan = document.getElementById('infoDescripcion');
    var ubicacionSpan = document.getElementById('infoUbicacion');
    var fechaSpan = document.getElementById('infoFecha');
    var gestionarBtn = document.getElementById('gestionarOtBtn');
    document.querySelectorAll('.info-ot-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            equipoSpan.textContent = btn.getAttribute('data-equipo') || '';
            descripcionSpan.textContent = btn.getAttribute('data-descripcion') || '';
            // fallback if data-ubicacion is empty: try to extract from data-equipo (display_label)
            let ubic = btn.getAttribute('data-ubicacion') || '';
            if (!ubic) {
                const equipoStr = btn.getAttribute('data-equipo') || '';
                // equipo.display_label is like "CODE/PDV/Name" — attempt to extract middle segment
                const parts = equipoStr.split('/').map(p=>p.trim()).filter(Boolean);
                if (parts.length >= 2) {
                    ubic = parts[1];
                }
            }
            ubicacionSpan.textContent = ubic;
            fechaSpan.textContent = btn.getAttribute('data-fecha') || '';
            if (gestionarBtn) {
                gestionarBtn.href = btn.getAttribute('data-gestionar-url') || btn.nextElementSibling?.href || '#';
            }
            infoModal.style.display = 'block';
        });
    });
    if (closeInfo && infoModal) {
        closeInfo.addEventListener('click', function() {
            infoModal.style.display = 'none';
        });
        window.addEventListener('click', function(event) {
            if (event.target === infoModal) {
                infoModal.style.display = 'none';
            }
        });
    }
});

window.addEventListener('load', function() {
    const tableButton = document.getElementById('table-view-button');
    const calendarButton = document.getElementById('calendar-view-button');
    const tableView = document.getElementById('table-view');
    const calendarView = document.getElementById('calendar-view');
    const calendarElement = document.getElementById('calendar');
    const calendarEventsData = document.getElementById('calendar-events-data');

    let events = [];
    try {
        events = JSON.parse(calendarEventsData.textContent || '[]');
    } catch (error) {
        console.error('Error parsing calendar events:', error);
    }

    let calendar = null;
    if (window.FullCalendar && calendarElement) {
        calendar = new FullCalendar.Calendar(calendarElement, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            selectable: true,
            events: events,
            eventClick: function(info) {
                info.jsEvent.preventDefault();
                var fila = null;

                // Primero intentar buscar la fila por el enlace de gestión de la OT.
                if (info.event.url) {
                    var link = document.querySelector('.list-container table tbody tr .action-link[href="' + info.event.url + '"]');
                    if (link) {
                        fila = link.closest('tr');
                    }
                }

                // Si no hay coincidencia por URL, buscar por el número de OT en el título.
                if (!fila) {
                    var otMatch = info.event.title.match(/OT-0*(\d+)/);
                    var consecutivo = otMatch ? otMatch[1] : null;
                    if (consecutivo) {
                        document.querySelectorAll('.list-container table tbody tr').forEach(function(tr) {
                            var td = tr.querySelector('td[data-label="Número de OT"]');
                            if (td && td.textContent.replace(/\D/g, '') === consecutivo) {
                                fila = tr;
                            }
                        });
                    }
                }

                if (fila) {
                    var btn = fila.querySelector('.info-ot-btn');
                    if (btn) {
                        btn.click();
                    }
                }
            }
        });
    }

    function setActiveView(view) {
        if (view === 'calendar') {
            tableView.style.display = 'none';
            calendarView.style.display = 'block';
            calendarButton.classList.add('active');
            tableButton.classList.remove('active');
            if (calendar) {
                calendar.render();
                calendar.updateSize();
            }
        } else {
            tableView.style.display = 'block';
            calendarView.style.display = 'none';
            tableButton.classList.add('active');
            calendarButton.classList.remove('active');
        }
    }

    tableButton.addEventListener('click', function() {
        setActiveView('table');
    });

    calendarButton.addEventListener('click', function() {
        setActiveView('calendar');
    });

    const container = document.querySelector('[data-vista-inicial]');
    const vistaInicial = container ? container.dataset.vistaInicial : 'table';
    setActiveView(vistaInicial);
});