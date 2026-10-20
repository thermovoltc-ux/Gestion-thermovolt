document.addEventListener('DOMContentLoaded', function () {
    const addModal = document.getElementById('modal-agregar-material');
    const createModal = document.getElementById('modal-nuevo-material');
    const select = document.getElementById('select-material');
    if (!addModal || !createModal || !select) {
        return;
    }

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const pageContainer = document.querySelector('.cierre-ot-form-container[data-material-add-url]');
    const tableBody = document.getElementById('lista-materiales');
    const searchInput = document.getElementById('buscar-material');
    const costInput = document.getElementById('input-costo-real');
    const quantityInput = document.getElementById('input-cantidad');
    const photoInput = document.getElementById('input-foto-factura');
    const observationInput = document.getElementById('input-observaciones-material');
    const addError = document.getElementById('error-material');
    const createError = document.getElementById('error-nuevo-material');
    const addButton = document.getElementById('btn-guardar-material');
    const createButton = document.getElementById('btn-crear-nuevo');
    let activeTrigger = null;
    let returnToAddModal = false;

    function showModal(modal) {
        modal.hidden = false;
    }

    function hideModal(modal) {
        modal.hidden = true;
    }

    function displayErrors(target, payload) {
        if (payload && payload.errors) {
            target.textContent = Object.values(payload.errors).flat().join(' ');
        } else {
            target.textContent = (payload && payload.error) || 'No se pudo completar la operación.';
        }
    }

    async function readResponse(response) {
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw payload;
        }
        return payload;
    }

    function appendMaterialRow(material) {
        if (!tableBody) {
            return;
        }
        const emptyRow = document.getElementById('sin-materiales');
        if (emptyRow) {
            emptyRow.remove();
        }

        const row = document.createElement('tr');
        const nameCell = document.createElement('td');
        const quantityCell = document.createElement('td');
        const costCell = document.createElement('td');
        const invoiceCell = document.createElement('td');
        const observationCell = document.createElement('td');
        nameCell.textContent = material.material;
        quantityCell.textContent = material.cantidad;
        costCell.textContent = `$${material.costo_real}`;

        if (material.foto_url) {
            const link = document.createElement('a');
            link.href = material.foto_url;
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = 'Ver factura';
            invoiceCell.appendChild(link);
        } else {
            invoiceCell.textContent = '—';
        }
        observationCell.textContent = material.observaciones || '—';

        row.append(nameCell, quantityCell, costCell, invoiceCell, observationCell);
        tableBody.appendChild(row);
    }

    function openAddModal(trigger) {
        activeTrigger = trigger;
        const endpoint = trigger.dataset.materialAddUrl
            || (pageContainer && pageContainer.dataset.materialAddUrl);
        const createEndpoint = trigger.dataset.materialCreateUrl
            || (pageContainer && pageContainer.dataset.materialCreateUrl);
        addModal.dataset.materialAddUrl = endpoint || '';
        addModal.dataset.materialCreateUrl = createEndpoint || '';
        addError.textContent = '';
        showModal(addModal);
        select.focus();
    }

    document.querySelectorAll('.btn-abrir-modal-material, #btn-abrir-modal-material')
        .forEach(function (trigger) {
            trigger.addEventListener('click', function () {
                openAddModal(trigger);
            });
        });

    document.getElementById('btn-cancelar-material').addEventListener('click', function () {
        hideModal(addModal);
    });

    document.getElementById('btn-abrir-modal-nuevo-material').addEventListener('click', function () {
        createError.textContent = '';
        returnToAddModal = !addModal.hidden;
        hideModal(addModal);
        showModal(createModal);
        document.getElementById('nuevo-categoria').focus();
    });

    document.getElementById('btn-cancelar-nuevo').addEventListener('click', function () {
        hideModal(createModal);
        if (returnToAddModal) {
            showModal(addModal);
            select.focus();
        }
    });

    select.addEventListener('change', function () {
        const option = select.options[select.selectedIndex];
        if (option && option.dataset.costo) {
            costInput.value = option.dataset.costo;
        }
    });

    searchInput.addEventListener('input', function () {
        const query = searchInput.value.trim().toLocaleLowerCase();
        Array.from(select.options).forEach(function (option, index) {
            option.hidden = index !== 0 && !option.textContent.toLocaleLowerCase().includes(query);
        });
        if (select.options[select.selectedIndex]?.hidden) {
            select.value = '';
        }
    });

    addButton.addEventListener('click', async function () {
        addError.textContent = '';
        const formData = new FormData();
        formData.append('material', select.value);
        formData.append('cantidad', quantityInput.value);
        formData.append('costo_real', costInput.value);
        formData.append('observaciones', observationInput.value);
        if (photoInput.files[0]) {
            formData.append('foto_factura', photoInput.files[0]);
        }

        addButton.disabled = true;
        try {
            const response = await fetch(addModal.dataset.materialAddUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData,
                credentials: 'same-origin',
            });
            const material = await readResponse(response);
            appendMaterialRow(material);
            if (activeTrigger && activeTrigger.dataset.materialCount !== undefined) {
                const count = Number(activeTrigger.dataset.materialCount) + 1;
                activeTrigger.dataset.materialCount = String(count);
                activeTrigger.textContent = `➕ Materiales (${count})`;
            }
            quantityInput.value = '1';
            costInput.value = '';
            photoInput.value = '';
            observationInput.value = '';
            select.value = '';
            searchInput.value = '';
            hideModal(addModal);
        } catch (error) {
            displayErrors(addError, error);
        } finally {
            addButton.disabled = false;
        }
    });

    createButton.addEventListener('click', async function () {
        createError.textContent = '';
        createButton.disabled = true;
        try {
            const response = await fetch(addModal.dataset.materialCreateUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    categoria: document.getElementById('nuevo-categoria').value,
                    nombre: document.getElementById('nuevo-nombre').value,
                    costo_base: document.getElementById('nuevo-costo').value,
                }),
            });
            const material = await readResponse(response);
            const option = document.createElement('option');
            option.value = material.id;
            option.dataset.costo = material.costo_base;
            option.textContent = `${material.codigo} — ${material.nombre}`;
            select.appendChild(option);
            select.value = String(material.id);
            costInput.value = material.costo_base;
            searchInput.value = '';
            document.getElementById('nuevo-categoria').selectedIndex = 0;
            document.getElementById('nuevo-nombre').value = '';
            document.getElementById('nuevo-costo').value = '';
            hideModal(createModal);
            if (returnToAddModal) {
                showModal(addModal);
            }
            returnToAddModal = false;
            select.focus();
        } catch (error) {
            displayErrors(createError, error);
        } finally {
            createButton.disabled = false;
        }
    });

    addModal.addEventListener('click', function (event) {
        if (event.target === addModal) hideModal(addModal);
    });
    createModal.addEventListener('click', function (event) {
        if (event.target === createModal) {
            hideModal(createModal);
            if (returnToAddModal) showModal(addModal);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !createModal.hidden) {
            hideModal(createModal);
            if (returnToAddModal) showModal(addModal);
            returnToAddModal = false;
        } else if (event.key === 'Escape' && !addModal.hidden) {
            hideModal(addModal);
        }
    });
});
