import './csrf.js';

// ---------------------------------------------------
// MODULO DE SOLICITUDES
// ---------------------------------------------------
// Este bloque centraliza la lógica del formulario de solicitudes:
// - búsqueda por código
// - búsqueda por ubicación
// - búsqueda por equipo según ubicación
// - selección y sincronización de campos ocultos y visibles
// ---------------------------------------------------

console.log('[UBICACION-SEARCH-TEST] JS CARGADO');

// normalizeText: normaliza el texto para comparar sin distinguir mayúsculas, minúsculas ni tildes.
function normalizeText(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();
}

// clearEquipoSelection: limpia la selección actual de equipo y los campos derivados.
// Sirve para resetear el estado cuando cambia la ubicación o se invalida un equipo.
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

    if (!preserveUbicacion) {
        $('#ubicacion_id').val('');
    }
}

// applyEquipoSelection: toma un equipo seleccionado y rellena los campos del formulario con sus datos reales.
// También mantiene la ubicación activa y sincroniza los inputs ocultos del backend.
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
    console.log('[UBICACION-TEST] solicitudes.js activo');
    console.log('[UBICACION-SEARCH-TEST] LISTENER REGISTRADO');
    console.log('[UBICACION-SEARCH] Listener registrado');

    // initUbicacionInputStatus: marca visualmente cuando el input de ubicación está activo.
    // Sirve como depuración rápida para confirmar que JavaScript está respondiendo al escribir.
    $('#nombre_ubicacion')
        .off('input.ubicacionTest')
        .on('input.ubicacionTest', function() {
            const texto = $(this).val() || '';
            console.log('[UBICACION-TEST] input detectado:', texto);

            if (texto.length >= 1) {
                $('#ubicacion_test_status').show().text('JS ACTIVO - buscando ubicación...');
            } else {
                $('#ubicacion_test_status').hide().text('');
            }
        });

    // initCodigoLookup: cuando el usuario escribe o cambia el código, consulta el equipo asociado.
    // Si encuentra un equipo, rellena ubicación, centro de costo y serie automáticamente.
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
                        return;
                    }
                    $("#nombre_equipo").val(response.equipo);
                    const equipoField = document.getElementById('id_equipo') || document.getElementById('equipo');
                    if (equipoField) {
                        equipoField.value = response.equipo_id;
                    }
                    $("#nombre_ubicacion").val(response.ubicacion);
                    $('#ubicacion_id').val('');
                    $("#centro_costo").val(response.centro_costo);
                    $("#numero_serie").val(response.numero_serie);
                    $("#PDV").val(response.ubicacion);
                    $("#co").val(response.centro_costo);
                },
                error: function() {
                    console.error("Error al obtener el equipo por código");
                    clearEquipoSelection();
                    $("#nombre_ubicacion").val('');
                }
            });
        } else {
            clearEquipoSelection();
            $("#nombre_ubicacion").val('');
        }
    });

    // initUbicacionSearch: escucha el input de ubicación y consulta ubicaciones coincidentes por texto.
    // Si el texto tiene longitud suficiente, envía AJAX a /solicitudes/buscar-ubicaciones/ y muestra un dropdown.
    $('#nombre_ubicacion')
        .off('input.ubicacionSearch')
        .on('input.ubicacionSearch', function() {
            const searchUrl = $('#nombre_ubicacion').data('search-url') || '/solicitudes/buscar-ubicaciones/';
            const query = $(this).val().trim();
            const container = $('#ubicacion_busqueda_results');

            console.log('[UBICACION-SEARCH] Input detectado:', query);
            console.log('[UBICACION-SEARCH] URL final:', searchUrl);

            if (!query) {
                console.log('[UBICACION-SEARCH] Input vacío, ocultando contenedor');
                container.hide().empty();
                return;
            }

            if (query.length < 2) {
                console.log('[UBICACION-SEARCH] Longitud insuficiente:', query.length);
                container.html('<div style="padding:10px 12px; color:#6b7280; font-size:14px;">Buscando ubicaciones...</div>').show();
                return;
            }

            console.log('[UBICACION-SEARCH] Enviando AJAX:', searchUrl, 'q=', query);
            container.html('<div style="padding:10px 12px; color:#6b7280; font-size:14px;">Buscando ubicaciones...</div>').show();

            $.ajax({
                url: searchUrl,
                method: 'GET',
                data: { q: query },
                success: function(response) {
                    console.log('[UBICACION-SEARCH] Respuesta recibida:', response);
                    const results = Array.isArray(response && response.results) ? response.results : [];
                    console.log('[UBICACION-SEARCH] Cantidad de resultados:', results.length);

                    if (!results.length) {
                        console.log('[UBICACION-SEARCH] Sin resultados');
                        container.html('<div style="padding:10px 12px; color:#6b7280; font-size:14px;">No se encontraron ubicaciones.</div>').show();
                        console.log('[UBICACION-SEARCH] Contenedor visible:', container.is(':visible'));
                        return;
                    }

                    console.log('[UBICACION-SEARCH] Renderizando resultados');
                    const items = results.map(item => `
                        <div class="ubicacion-search-item" data-id="${item.id}" data-nombre="${item.nombre || ''}" data-codigo="${item.codigo || ''}" style="padding:10px 12px; cursor:pointer; border-bottom:1px solid #e5e7eb; background:#fff; color:#111827; font-size:14px;">
                            ${(item.nombre || '')}${item.codigo ? ` (${item.codigo})` : ''}
                        </div>
                    `).join('');

                    container.html(items).show();
                    console.log('[UBICACION-SEARCH] Contenedor visible:', container.is(':visible'));
                    container.off('click.ubicacionSearchItem').on('click.ubicacionSearchItem', '.ubicacion-search-item', function() {
                        const ubicacionId = $(this).data('id');
                        const ubicacionNombre = $(this).data('nombre');

                        console.log('[UBICACION-SEARCH] Seleccionando ubicación:', ubicacionId, ubicacionNombre);
                        $('#ubicacion_id').val(ubicacionId);
                        $('#nombre_ubicacion').val(ubicacionNombre);
                        clearEquipoSelection({ preserveCodigo: false, preserveUbicacion: true });
                        $('#nombre_equipo').val('').trigger('focus');
                        container.hide().empty();

                        $.ajax({
                            url: '/solicitudes/get-equipos-por-ubicacion/',
                            method: 'GET',
                            data: { ubicacion_id: ubicacionId },
                            success: function(equiposResponse) {
                                const results = equiposResponse.results || [];
                                if (!results.length) {
                                    return;
                                }
                            }
                        });
                    });
                },
                error: function(xhr, status, error) {
                    console.log('[UBICACION-SEARCH] ERROR AJAX');
                    console.error(error);
                    console.error(xhr && xhr.responseText ? xhr.responseText : '');
                    container.html('<div style="padding:10px 12px; color:#b91c1c; font-size:14px;">Error al buscar ubicaciones.</div>').show();
                }
            });
        });

    // initEquipoSearch: escucha el input del equipo pero solo si ya hay una ubicación seleccionada.
    // Consulta los equipos de esa ubicación y muestra solo los resultados válidos para ese contexto.
    $('#nombre_equipo')
        .off('input.equipoSearch')
        .on('input.equipoSearch', function() {
            const ubicacionId = $('#ubicacion_id').val();
            const searchUrl = $('#nombre_equipo').data('search-url') || '/solicitudes/get-equipos-por-ubicacion/';
            const query = $(this).val().trim();
            const container = $('#equipo_busqueda_results');

            console.log('[EQUIPO-SEARCH] Input detectado:', query);

            if (!ubicacionId) {
                console.log('[EQUIPO-SEARCH] No hay ubicación seleccionada');
                container.hide().empty();
                return;
            }

            if (!query) {
                console.log('[EQUIPO-SEARCH] Input vacío, ocultando contenedor');
                container.hide().empty();
                return;
            }

            if (query.length < 2) {
                console.log('[EQUIPO-SEARCH] Longitud insuficiente:', query.length);
                container.html('<div style="padding:10px 12px; color:#6b7280; font-size:14px;">Escriba más letras para buscar equipos.</div>').show();
                return;
            }

            console.log('[EQUIPO-SEARCH] Enviando AJAX:', searchUrl, 'ubicacion_id=', ubicacionId, 'q=', query);
            container.html('<div style="padding:10px 12px; color:#6b7280; font-size:14px;">Buscando equipos...</div>').show();

            $.ajax({
                url: searchUrl,
                method: 'GET',
                data: { ubicacion_id: ubicacionId, q: query },
                success: function(response) {
                    const results = Array.isArray(response && response.results) ? response.results : [];
                    console.log('[EQUIPO-SEARCH] Resultados:', results.length);

                    if (!results.length) {
                        container.html('<div style="padding:10px 12px; color:#6b7280; font-size:14px;">No se encontraron equipos para esta ubicación.</div>').show();
                        return;
                    }

                    const items = results.map(item => `
                        <div class="equipo-search-item" data-id="${item.id}" data-nombre="${item.nombre || ''}" data-codigo="${item.codigo || ''}" style="padding:10px 12px; cursor:pointer; border-bottom:1px solid #e5e7eb; background:#fff; color:#111827; font-size:14px;">
                            ${(item.nombre || '')}${item.codigo ? ` (${item.codigo})` : ''}
                        </div>
                    `).join('');

                    container.html(items).show();
                    container.off('click.equipoSearchItem').on('click.equipoSearchItem', '.equipo-search-item', function() {
                        const equipoId = $(this).data('id');
                        const equipoNombre = $(this).data('nombre');
                        const equipoCodigo = $(this).data('codigo');

                        console.log('[EQUIPO-SEARCH] Seleccionando equipo:', equipoId, equipoNombre, equipoCodigo);
                        const equipoField = document.getElementById('id_equipo') || document.getElementById('equipo');
                        if (equipoField) equipoField.value = equipoId;

                        $('#nombre_equipo').val(equipoNombre);
                        $('#codigo').val(equipoCodigo || '');
                        $('#equipo_busqueda_results').hide().empty();
                    });
                },
                error: function(xhr, status, error) {
                    console.log('[EQUIPO-SEARCH] ERROR AJAX');
                    console.error(error);
                    console.error(xhr && xhr.responseText ? xhr.responseText : '');
                    container.html('<div style="padding:10px 12px; color:#b91c1c; font-size:14px;">Error al buscar equipos.</div>').show();
                }
            });
        });

    // onUbicacionIdChange: si la ubicación se limpia, también limpia la selección de equipo y el estado derivado.
    $('#ubicacion_id').on('change', function() {
        if (!$(this).val()) {
            clearEquipoSelection({ preserveCodigo: false, preserveUbicacion: false });
        }
    });

    // submitSolicitud: valida antes de enviar el formulario y comprueba si ya existe una solicitud activa.
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

    // clearForm: reinicia el formulario y deja el estado inicial limpio para una nueva solicitud.
    function clearForm() {
        $("#solicitud-form")[0].reset();
    }
});
