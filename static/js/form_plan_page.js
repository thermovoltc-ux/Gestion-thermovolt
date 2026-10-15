// Actualizar preview de período
    function actualizarPreview() {
        const cantidad = document.getElementById('id_cantidad').value;
        const unidad = document.getElementById('id_unidad');
        const unidadText = unidad.options[unidad.selectedIndex].text;
        const preview = document.getElementById('preview-periodo');
        preview.textContent = `Cada ${cantidad} ${unidadText}`;
    }

    document.getElementById('id_cantidad').addEventListener('change', actualizarPreview);
    document.getElementById('id_unidad').addEventListener('change', actualizarPreview);