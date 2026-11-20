(() => {
    const showDialog = (id) => {
        const dialog = document.getElementById(id);
        if (dialog instanceof HTMLDialogElement && !dialog.open) {
            dialog.showModal();
        }
    };

    document.addEventListener('click', (event) => {
        const openButton = event.target.closest('[data-open-dialog]');
        if (openButton) {
            showDialog(openButton.dataset.openDialog);
            return;
        }

        const closeButton = event.target.closest('[data-close-dialog]');
        if (closeButton) {
            closeButton.closest('dialog')?.close();
        }
    });

    document.querySelectorAll('[data-product-search]').forEach((input) => {
        const hiddenProduct = document.getElementById(input.dataset.productIdField);
        const datalist = document.getElementById(input.getAttribute('list'));
        if (!hiddenProduct || !datalist) {
            return;
        }

        const updateSelection = () => {
            const option = Array.from(datalist.options).find(
                (item) => item.value === input.value,
            );
            hiddenProduct.value = option?.dataset.id || '';
            input.setCustomValidity(
                input.value && !hiddenProduct.value
                    ? 'Selecciona un producto de la lista.'
                    : '',
            );
        };

        input.addEventListener('input', updateSelection);
        input.addEventListener('change', updateSelection);
        input.addEventListener('blur', updateSelection);
        updateSelection();
    });

    const addProductOption = (product, datalistId) => {
        const datalist = document.getElementById(datalistId);
        if (!datalist) {
            return;
        }
        const existing = Array.from(datalist.options).find(
            (option) => option.dataset.id === String(product.id),
        );
        if (existing) {
            return;
        }
        const option = document.createElement('option');
        option.value = product.label;
        option.dataset.id = product.id;
        datalist.append(option);
    };

    const showFeedback = (element, message, isError = false) => {
        if (!element) {
            return;
        }
        element.textContent = message;
        element.classList.toggle('is-error', isError);
        element.classList.toggle('is-success', !isError && Boolean(message));
    };

    const formErrorsToText = (errors) => Object.values(errors || {})
        .flat()
        .map((error) => error.message)
        .filter(Boolean)
        .join(' ');

    const appendToolRow = (tool, form) => {
        const body = document.querySelector('[data-tools-table-body]');
        if (!body) {
            return;
        }

        const row = document.createElement('tr');
        const values = [
            tool.producto_label,
            tool.identificador_unico,
            tool.estado,
            '—',
            '—',
        ];
        values.forEach((value) => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
        });

        const historyCell = document.createElement('td');
        const history = document.createElement('details');
        history.className = 'warehouse-tool-history';
        const historySummary = document.createElement('summary');
        historySummary.textContent = '0 registro(s)';
        const historyList = document.createElement('ul');
        const emptyHistory = document.createElement('li');
        emptyHistory.textContent = 'Sin asignaciones registradas.';
        historyList.append(emptyHistory);
        history.append(historySummary, historyList);
        historyCell.append(history);
        row.append(historyCell);

        const actionCell = document.createElement('td');
        actionCell.className = 'warehouse-tool-actions';
        const action = document.createElement('details');
        const actionSummary = document.createElement('summary');
        actionSummary.className = 'ds-button ds-button--small';
        actionSummary.textContent = 'Asignar';

        const assignForm = document.createElement('form');
        assignForm.method = 'post';
        assignForm.className = 'warehouse-tool-action-form';
        assignForm.action = form.dataset.assignUrlTemplate.replace(
            /\/0\/asignar\/$/,
            `/${tool.id}/asignar/`,
        );

        const csrf = document.createElement('input');
        csrf.type = 'hidden';
        csrf.name = 'csrfmiddlewaretoken';
        csrf.value = form.querySelector('[name=csrfmiddlewaretoken]').value;
        assignForm.append(csrf);

        const technicianField = document.createElement('div');
        technicianField.className = 'warehouse-form-field';
        const technicianLabel = document.createElement('label');
        technicianLabel.textContent = 'Técnico';
        const technicianSelect = document.createElement('select');
        technicianSelect.name = 'tecnico';
        technicianSelect.className = 'form-control';
        technicianSelect.required = true;
        document.querySelectorAll('#tool-technician-options option').forEach((item) => {
            technicianSelect.append(item.cloneNode(true));
        });
        technicianLabel.htmlFor = `technician-${tool.id}`;
        technicianSelect.id = technicianLabel.htmlFor;
        technicianField.append(technicianLabel, technicianSelect);
        assignForm.append(technicianField);

        const notesField = document.createElement('div');
        notesField.className = 'warehouse-form-field';
        const notesLabel = document.createElement('label');
        notesLabel.htmlFor = `notes-${tool.id}`;
        notesLabel.textContent = 'Observaciones';
        const notes = document.createElement('textarea');
        notes.id = notesLabel.htmlFor;
        notes.name = 'observaciones';
        notes.className = 'form-control';
        notes.rows = 2;
        notesField.append(notesLabel, notes);
        assignForm.append(notesField);

        const submit = document.createElement('button');
        submit.type = 'submit';
        submit.className = 'ds-button ds-button--small';
        submit.textContent = 'Confirmar asignación';
        assignForm.append(submit);
        action.append(actionSummary, assignForm);
        actionCell.append(action);
        row.append(actionCell);
        body.prepend(row);

        const emptyRow = body.querySelector('.warehouse-empty');
        if (emptyRow) {
            emptyRow.closest('tr')?.remove();
        }
    };

    document.querySelectorAll('[data-ajax-form]').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const feedback = form.querySelector('[data-form-feedback]');
            const submit = form.querySelector('[type=submit]');
            const search = document.getElementById(form.dataset.productSearchId);
            const hiddenProduct = document.getElementById(form.dataset.productHiddenId);

            if (
                form.dataset.ajaxForm === 'tool'
                && search
                && hiddenProduct
                && !hiddenProduct.value
            ) {
                search.setCustomValidity('Selecciona un producto de la lista.');
                search.reportValidity();
                return;
            }

            submit.disabled = true;
            showFeedback(feedback, '');
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    credentials: 'same-origin',
                });
                const result = await response.json();
                if (!response.ok) {
                    showFeedback(
                        feedback,
                        formErrorsToText(result.errors) || 'No se pudo guardar. Revisa los datos.',
                        true,
                    );
                    return;
                }

                if (form.dataset.ajaxForm === 'product') {
                    const product = {
                        id: result.id,
                        label: result.label,
                    };
                    addProductOption(product, form.dataset.productDatalist);
                    if (search && hiddenProduct) {
                        search.value = product.label;
                        hiddenProduct.value = product.id;
                        search.setCustomValidity('');
                    }
                    form.closest('dialog')?.close();
                    form.reset();
                    showFeedback(
                        document.querySelector('[data-page-feedback]'),
                        result.message,
                    );
                    return;
                }

                if (form.dataset.ajaxForm === 'tool') {
                    appendToolRow(result, form);
                    addProductOption({
                        id: result.producto_id,
                        label: result.producto_label,
                    }, form.dataset.productDatalist);
                    form.reset();
                    form.closest('dialog')?.close();
                    showFeedback(
                        document.querySelector('[data-page-feedback]'),
                        result.message,
                    );
                }
            } catch (error) {
                console.error('Error al guardar en almacén:', error);
                showFeedback(
                    feedback,
                    'No fue posible completar la solicitud. Intenta de nuevo.',
                    true,
                );
            } finally {
                submit.disabled = false;
            }
        });
    });
})();
