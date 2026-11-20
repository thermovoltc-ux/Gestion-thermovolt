(() => {
    const showDialog = (id) => {
        const dialog = document.getElementById(id);
        if (dialog instanceof HTMLDialogElement && !dialog.open) {
            dialog.classList.remove('is-closing');
            dialog.showModal();
            requestAnimationFrame(() => dialog.classList.add('is-visible'));
            dialog.classList.add('ds-modal-enter');
            window.setTimeout(
                () => dialog.classList.remove('ds-modal-enter'),
                220,
            );
            dialog.querySelector('input:not([type=hidden]), select, textarea')?.focus({
                preventScroll: true,
            });
        }
    };

    const closeDialog = (dialog) => {
        if (!(dialog instanceof HTMLDialogElement) || !dialog.open) {
            return;
        }
        dialog.classList.remove('is-visible', 'ds-modal-enter');
        dialog.classList.add('is-closing');
        const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches
            ? 0
            : 220;
        window.setTimeout(() => {
            if (dialog.open) {
                dialog.close();
            }
        }, delay);
    };

    document.querySelectorAll('.warehouse-dialog').forEach((dialog) => {
        dialog.addEventListener('cancel', (event) => {
            event.preventDefault();
            closeDialog(dialog);
        });
        dialog.addEventListener('click', (event) => {
            if (event.target === dialog) {
                closeDialog(dialog);
            }
        });
        dialog.addEventListener('close', () => {
            dialog.classList.remove('is-visible', 'is-closing', 'ds-modal-enter');
            dialog.querySelector('form')?.reset();
            dialog.querySelector('[data-form-feedback]')?.replaceChildren();
        });
    });

    document.addEventListener('click', (event) => {
        const openButton = event.target.closest('[data-open-dialog]');
        if (openButton) {
            showDialog(openButton.dataset.openDialog);
            return;
        }

        const closeButton = event.target.closest('[data-close-dialog]');
        if (closeButton) {
            closeDialog(closeButton.closest('dialog'));
        }
    });

    document.querySelectorAll('[data-product-search]').forEach((input) => {
        const hiddenProduct = document.getElementById(input.dataset.productIdField);
        const datalist = document.getElementById(input.getAttribute('list'));
        const errorMessage = input
            .closest('.warehouse-form-field')
            ?.querySelector('[data-product-error]');
        if (!hiddenProduct || !datalist) {
            return;
        }

        const updateSelection = () => {
            const option = Array.from(datalist.options).find(
                (item) => item.value === input.value,
            );
            hiddenProduct.value = option?.dataset.id || '';
            if (hiddenProduct.value) {
                input.removeAttribute('aria-invalid');
                if (errorMessage) {
                    errorMessage.hidden = true;
                }
            } else if (input.dataset.selectionAttempted === 'true') {
                input.setAttribute('aria-invalid', 'true');
                if (errorMessage) {
                    errorMessage.hidden = false;
                }
            }
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
        if (element.matches('[data-page-feedback]')) {
            element.classList.toggle('warehouse-message', Boolean(message));
            element.classList.toggle(
                'warehouse-message--error',
                isError && Boolean(message),
            );
            element.classList.toggle(
                'warehouse-message--success',
                !isError && Boolean(message),
            );
        }
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

    document.querySelectorAll('[data-ajax-form], [data-product-selection-required]').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            const search = document.getElementById(form.dataset.productSearchId);
            const hiddenProduct = document.getElementById(form.dataset.productHiddenId);
            if (
                (form.dataset.ajaxForm === 'tool' || form.dataset.productSelectionRequired !== undefined)
                && search
                && hiddenProduct
                && !hiddenProduct.value
            ) {
                event.preventDefault();
                search.dataset.selectionAttempted = 'true';
                search.setAttribute('aria-invalid', 'true');
                const errorMessage = search
                    .closest('.warehouse-form-field')
                    ?.querySelector('[data-product-error]');
                if (errorMessage) {
                    errorMessage.hidden = false;
                }
                search.focus();
                return;
            }

            if (!form.matches('[data-ajax-form]')) {
                return;
            }
            event.preventDefault();
            const feedback = form.querySelector('[data-form-feedback]');
            const submit = form.querySelector('[type=submit]');

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
                        search.removeAttribute('aria-invalid');
                        search.dataset.selectionAttempted = 'false';
                    }
                    closeDialog(form.closest('dialog'));
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
                    closeDialog(form.closest('dialog'));
                    const row = document.querySelector('[data-tools-table-body] tr');
                    row?.classList.add('ds-fade-in');
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
