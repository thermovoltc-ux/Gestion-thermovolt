document.addEventListener('DOMContentLoaded', function () {
    const addModal = document.getElementById('modal-agregar-material');
    const searchInput = document.getElementById('buscar-material-unificado');
    const materialsList = document.getElementById('materiales-catalogo');
    if (!addModal || !searchInput || !materialsList) {
        return;
    }

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const pageContainer = document.querySelector('.cierre-ot-form-container[data-material-add-url]');
    const tableBody = document.getElementById('lista-materiales');
    const costInput = document.getElementById('input-costo-real');
    const quantityInput = document.getElementById('input-cantidad');
    const photoInput = document.getElementById('input-foto-factura');
    const observationInput = document.getElementById('input-observaciones-material');
    const addError = document.getElementById('error-material');
    const addButton = document.getElementById('btn-guardar-material');
    let activeTrigger = null;
    const numberFormat = new Intl.NumberFormat('es-CO', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    const catalogOptions = Array.from(materialsList.options);

    function normalizeSearchText(text) {
        return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
    }

    function updateMaterialSuggestions() {
        const query = normalizeSearchText(searchInput.value.trim());
        const matchingOptions = catalogOptions.filter(function (option) {
            return normalizeSearchText(option.value).includes(query);
        });
        materialsList.replaceChildren(...matchingOptions.map(option => option.cloneNode(true)));
    }

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
            target.textContent = (payload && (payload.error || payload.message))
                || 'No se pudo completar la operación.';
        }
    }

    function validateNumber(input, minimum) {
        const rawValue = input.value.trim();
        if (!rawValue) {
            return false;
        }
        const value = Number(rawValue);
        return Number.isFinite(value) && value >= minimum;
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
        quantityCell.textContent = numberFormat.format(Number(material.cantidad));
        costCell.textContent = `$ ${numberFormat.format(Number(material.costo_real))}`;

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
        searchInput.focus();
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

    function findMaterialOption(name) {
        const normalizedName = normalizeSearchText(name.trim());
        return catalogOptions.find(function (option) {
            return normalizeSearchText(option.value.trim()) === normalizedName;
        });
    }

    searchInput.addEventListener('input', function () {
        updateMaterialSuggestions();
        const option = findMaterialOption(searchInput.value);
        costInput.value = option ? option.dataset.costo : '';
    });

    addButton.addEventListener('click', async function () {
        addError.textContent = '';
        const materialName = searchInput.value.trim();
        if (!materialName) {
            addError.textContent = 'Escribe o selecciona un material.';
            searchInput.focus();
            return;
        }
        if (materialName.length > 150) {
            addError.textContent = 'El nombre del material no puede superar 150 caracteres.';
            searchInput.focus();
            return;
        }
        if (!validateNumber(quantityInput, 0.01)) {
            addError.textContent = 'Ingresa una cantidad válida, mayor que cero.';
            quantityInput.focus();
            return;
        }
        if (!validateNumber(costInput, 0)) {
            addError.textContent = 'Ingresa un costo real válido (cero o mayor).';
            costInput.focus();
            return;
        }

        addButton.disabled = true;
        try {
            let materialId;
            const option = findMaterialOption(materialName);
            if (option) {
                materialId = option.dataset.id;
            } else {
                if (!addModal.dataset.materialCreateUrl) {
                    throw new Error('No está disponible la creación automática de materiales.');
                }
                const createResponse = await fetch(addModal.dataset.materialCreateUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        categoria: 'repuestos',
                        nombre: materialName,
                        costo_base: costInput.value,
                    }),
                });
                const createdMaterial = await readResponse(createResponse);
                materialId = String(createdMaterial.id);
                const createdOption = document.createElement('option');
                createdOption.value = createdMaterial.nombre;
                createdOption.dataset.id = materialId;
                createdOption.dataset.costo = createdMaterial.costo_base;
                createdOption.label = `${createdMaterial.codigo} — ${createdMaterial.nombre}`;
                catalogOptions.push(createdOption);
                updateMaterialSuggestions();
            }

            const formData = new FormData();
            formData.append('material', materialId);
            formData.append('cantidad', quantityInput.value);
            formData.append('costo_real', costInput.value);
            formData.append('observaciones', observationInput.value);
            if (photoInput.files[0]) {
                formData.append('foto_factura', photoInput.files[0]);
            }

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
            searchInput.value = '';
            updateMaterialSuggestions();
            hideModal(addModal);
        } catch (error) {
            displayErrors(addError, error);
        } finally {
            addButton.disabled = false;
        }
    });

    addModal.addEventListener('click', function (event) {
        if (event.target === addModal) hideModal(addModal);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !addModal.hidden) {
            hideModal(addModal);
        }
    });
});
