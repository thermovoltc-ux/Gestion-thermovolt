import './csrf.js';

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
                        $("#nombre_equipo").val('');
                        $("#equipo, #id_equipo").val('');
                        $("#nombre_ubicacion").val('');
                        $("#nombre_ubicacion_area").empty();
                        $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
                        $("#centro_costo").val('');
                        $("#numero_serie").val('');
                        return;
                    }
                    $("#nombre_equipo").val(response.equipo);
                    $("#equipo, #id_equipo").val(response.equipo_id);
                    $("#nombre_ubicacion").val(response.ubicacion);
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
                    $("#nombre_equipo").val('');
                    $("#equipo, #id_equipo").val('');
                    $("#nombre_ubicacion").val('');
                    $("#nombre_ubicacion_area").empty();
                    $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
                    $("#centro_costo").val('');
                    $("#numero_serie").val('');
                }
            });
        } else {
            $("#nombre_equipo").val('');
            $("#equipo, #id_equipo").val('');
            $("#nombre_ubicacion").val('');
            $("#nombre_ubicacion_area").empty();
            $("#nombre_ubicacion_area").append(new Option("Seleccione una ubicación", ""));
            $("#centro_costo").val('');
            $("#numero_serie").val('');
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
        let equipoId = $("#equipo, #id_equipo").val();
        let equipoVal = $("#nombre_equipo").val();

        if (!equipoId) {
            alert('Selecciona primero un equipo válido.');
            return;
        }

        if (codigoVal && equipoVal) {
            $.ajax({
                url: "/solicitudes/verificar-solicitud/",
                method: "GET",
                data: { codigo: codigoVal, equipo_id: equipoId, equipo: equipoVal },
                success: function(response) {
                    if (response.exists) {
                        if (confirm("Esta solicitud ya fue creada. Espere hasta que se finalice la solicitud. ¿Desea continuar?")) {
                            $("#solicitud-form")[0].submit();
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
