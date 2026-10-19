function easeOutQuad(t) {
    return t * (2 - t);
}

function animateValue(element, start, end, duration) {
    const startTime = performance.now();
    const range = end - start;

    function step(currentTime) {
        const progress = Math.min((currentTime - startTime) / duration, 1);
        const ease = easeOutQuad(progress);
        element.textContent = Math.round(start + range * ease);
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }

    requestAnimationFrame(step);
}

function updateDashboardCards(data) {
    animateValue(document.getElementById('planificadasCount'), parseInt(document.getElementById('planificadasCount').textContent, 10), data.tareas_planificadas, 900);
    animateValue(document.getElementById('noPlanificadasCount'), parseInt(document.getElementById('noPlanificadasCount').textContent, 10), data.tareas_no_planificadas, 900);
    animateValue(document.getElementById('totalTareasCount'), parseInt(document.getElementById('totalTareasCount').textContent, 10), data.total_tareas, 900);
    animateValue(document.getElementById('planificadasPct'), parseInt(document.getElementById('planificadasPct').textContent, 10), data.planificadas_pct, 900);
    animateValue(document.getElementById('noPlanificadasPct'), parseInt(document.getElementById('noPlanificadasPct').textContent, 10), data.no_planificadas_pct, 900);

    const chart = document.getElementById('planChart');
    chart.style.transform = 'scale(1.03)';
    chart.style.background = `conic-gradient(#2563eb 0 ${data.planificadas_pct}%, #ef4444 ${data.planificadas_pct}% 100%)`;
    setTimeout(() => {
        chart.style.transform = 'scale(1)';
    }, 250);
}

async function fetchDashboardData() {
    const equipoId = document.getElementById('equipoFilter').value;
    const ubicacionId = document.getElementById('ubicacionFilter').value;
    const url = new URL(window.location.href);
    if (equipoId) {
        url.searchParams.set('equipo_id', equipoId);
    } else {
        url.searchParams.delete('equipo_id');
    }
    if (ubicacionId) {
        url.searchParams.set('ubicacion_id', ubicacionId);
    } else {
        url.searchParams.delete('ubicacion_id');
    }
    history.replaceState(null, '', url.toString());

    const response = await fetch(url.toString(), {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    });
    if (!response.ok) {
        console.error('Error al obtener datos de dashboard');
        return;
    }
    const data = await response.json();
    updateDashboardCards(data);
}

document.getElementById('equipoFilter').addEventListener('change', fetchDashboardData);
document.getElementById('ubicacionFilter').addEventListener('change', fetchDashboardData);
document.getElementById('clearFilters').addEventListener('click', function () {
    document.getElementById('equipoFilter').value = '';
    document.getElementById('ubicacionFilter').value = '';
    fetchDashboardData();
});
