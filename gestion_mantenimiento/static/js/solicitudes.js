import './csrf.js';

let equiposPorUbicacion = [];

function clearEquipoSelection({ preserveCodigo = false, preserveUbicacion = true } = {}) {
    $('#nombre_equipo').val('');
    if (!preserveCodigo) {
        $('#codigo').val('');
    }
    $('#numero_serie').val('');
    $('#centro_costo').val('');
    $('#PDV').val('');
    $('#co').val('');

    const equipoField = document.getElementById('id_equipo') || document.getElementById('equipo');
    if (equipoField) equipoField.value = '';

    $('#equipo_por_ubicacion').empty().append(new Option('Seleccione un equipo', ''));
    $('#equipo_por_ubicacion').prop('disabled', true);
    equiposPorUbicacion = [];

    if (!preserveUbicacion) {
        $('#ubicacion_id').val('');
    }
}

function applyEquipoSelection({ equipoId, equipoNombre, equipoCodigo, ubicacionNombre, ubicacionId, centroCosto, numeroSerie }) {
    const equipoField = document.getElementById('id_equipo') || document.getElementById('equipo');
    if (equipoField) equipoField.value = equipoId || '';

    $('#nombre_equipo').val(equipoNombre || '');
    $('#codigo').val(equipoCodigo || '');
    $('#nombre_ubicacion').val(ubicacionNombre || '');
    $('#ubicacion_id').val(ubicacionId || $('#ubicacion_id').val() || '');
    $('#centro_costo').val(centroCosto || '');
    $('#numero_serie').val(numeroSerie || '');
    $('#PDV').val(ubicacionNombre || '');
    $('#co').val(centroCosto || '');
}

$(document).ready(function() {
    $("#codigo").on("change", function() {
        let codigoVal = $(this).val();
        if (codigoVal) {
            $.ajax({
                url: "/solicitudes/get-equipo-por-codigo/",
                method: "GET",
                data: { codigo: codigoVal },
                success: function(response) {
                    console.log(response);
                    if (response.error) {
                        console.error(response.error);
                        clearEquipoSelection();
                        $("#nombre_ubicacion").val('');
                        $("#nombre_ubicacion_area").empty();
                        $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
                        return;
                    }
                    $("#nombre_equipo").val(response.equipo);
                    const equipoField = document.getElementById('id_equipo') || document.getElementById('equipo');
                    if (equipoField) {
                        equipoField.value = response.equipo_id;
                    }
                    $("#nombre_ubicacion").val(response.ubicacion);
                    $('#ubicacion_id').val('');
                    $("#nombre_ubicacion_area").empty();
                    $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
                    response.areas.forEach(function(area) {
                        $("#nombre_ubicacion_area").append(new Option(area.nombre, area.id));
                    });
                    $("#centro_costo").val(response.centro_costo);
                    $("#numero_serie").val(response.numero_serie);
                    $("#PDV").val(response.ubicacion);
                    $("#co").val(response.centro_costo);
                },
                error: function() {
                    console.error("Error al obtener el equipo por código");
                    clearEquipoSelection();
                    $("#nombre_ubicacion").val('');
                    $("#nombre_ubicacion_area").empty();
                    $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
                }
            });
        } else {
            clearEquipoSelection();
            $("#nombre_ubicacion").val('');
            $("#nombre_ubicacion_area").empty();
            $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
        }
    });

    $('#nombre_ubicacion').on('input', function() {
        const query = $(this).val().trim();
        const container = $('#ubicacion_busqueda_results');
        if (!query) {
            container.hide().empty();
            return;
        }

        $.ajax({
            url: '/solicitudes/buscar-ubicaciones/',
            method: 'GET',
            data: { q: query },
            success: function(response) {
                const results = response.results || [];
                if (!results.length) {
                    container.html('<div style="padding:8px; color:#6b7280;">No se encontraron ubicaciones.</div>').show();
                    return;
                }

                const items = results.map(item => `
                    <div class="ubicacion-search-item" data-id="${item.id}" data-nombre="${item.nombre}" data-codigo="${item.codigo}" style="padding:8px 10px; cursor:pointer; border-bottom:1px solid #e5e7eb;">
                        ${item.nombre}${item.codigo ? ` (${item.codigo})` : ''}
                    </div>
                `).join('');

                container.html(items).show();
                container.find('.ubicacion-search-item').on('click', function() {
                    const ubicacionId = $(this).data('id');
                    const ubicacionNombre = $(this).data('nombre');

                    $('#ubicacion_id').val(ubicacionId);
                    $('#nombre_ubicacion').val(ubicacionNombre);
                    $('#nombre_ubicacion_area').empty().append(new Option('Seleccione una ubicación', ''));
                    clearEquipoSelection({ preserveCodigo: false, preserveUbicacion: true });
                    $('#equipo_por_ubicacion').empty().append(new Option('Buscando equipos...', ''));
                    $('#equipo_por_ubicacion').prop('disabled', true);
                    container.hide().empty();

                    $.ajax({
                        url: '/solicitudes/get-equipos-por-ubicacion/',
                        method: 'GET',
                        data: { ubicacion_id: ubicacionId },
                        success: function(equiposResponse) {
                            const results = equiposResponse.results || [];
                            const select = $('#equipo_por_ubicacion');
                            equiposPorUbicacion = results;
                            select.empty().append(new Option('Seleccione un equipo', ''));

                            if (!results.length) {
                                select.append(new Option('No hay equipos para esta ubicación', ''));
                                select.prop('disabled', true);
                                return;
                            }

                            results.forEach(function(item) {
                                select.append(new Option(`${item.nombre}${item.codigo ? ` (${item.codigo})` : ''}`, item.id));
                            });
                            select.prop('disabled', false);
                        },
                        error: function() {
                            equiposPorUbicacion = [];
                            $('#equipo_por_ubicacion').empty().append(new Option('Error cargando equipos', ''));
                            $('#equipo_por_ubicacion').prop('disabled', true);
                        }
                    });
                });
            },
            error: function() {
                container.html('<div style="padding:8px; color:#6b7280;">Error buscando ubicaciones.</div>').show();
            }
        });
    });

    $('#equipo_por_ubicacion').on('change', function() {
        const equipoId = $(this).val();
        const ubicacionId = $('#ubicacion_id').val();

        if (!equipoId || !ubicacionId) {
            clearEquipoSelection({ preserveCodigo: false, preserveUbicacion: true });
            return;
        }

        const selected = equiposPorUbicacion.find(function(item) {
            return String(item.id) === String(equipoId);
        });

        if (!selected) {
            clearEquipoSelection({ preserveCodigo: false, preserveUbicacion: true });
            return;
        }

        const ubicacionNombre = $('#nombre_ubicacion').val();
        applyEquipoSelection({
            equipoId: selected.id,
            equipoNombre: selected.nombre,
            equipoCodigo: selected.codigo,
            ubicacionNombre: ubicacionNombre,
            ubicacionId: ubicacionId,
            centroCosto: $('#centro_costo').val() || '',
            numeroSerie: $('#numero_serie').val() || ''
        });
    });

    $('#ubicacion_id').on('change', function() {
        if (!$(this).val()) {
            clearEquipoSelection({ preserveCodigo: false, preserveUbicacion: false });
        }
    });

    $("#solicitud-form").on("submit", function(event) {
        event.preventDefault();

        let now = new Date();
        let year = now.getFullYear();
        let month = String(now.getMonth() + 1).padStart(2, '0');
        let day = String(now.getDate()).padStart(2, '0');
        let hours = String(now.getHours()).padStart(2, '0');
        let minutes = String(now.getMinutes()).padStart(2, '0');
        let fecha = `${year}-${month}-${day}T${hours}:${minutes}`;

        $("#fecha-creacion").val(fecha);

        let codigoVal = $("#codigo").val();
        let equipoId = $("#equipo").val();
        let equipoVal = $("#nombre_equipo").val();

        if (!equipoId) {
            alert('Selecciona primero un equipo válido.');
            return;
        }

        if (codigoVal && equipoVal) {
            $.ajax({
                url: "/solicitudes/verificar-solicitud/",
                method: "GET",
                data: { codigo: codigoVal, equipo: equipoVal },
                success: function(response) {
                    if (response.exists) {
                        if (confirm("Esta solicitud ya fue creada. Espere hasta que se finalice la solicitud. ¿Desea continuar?")) {
                            clearForm();
                        }
                    } else {
                        $("#solicitud-form")[0].submit();
                    }
                },
                error: function() {
                    console.error("Error al verificar la solicitud existente");
                }
            });
        } else {
            $("#solicitud-form")[0].submit();
        }
    });

    function clearForm() {
        $("#solicitud-form")[0].reset();
    }
});
