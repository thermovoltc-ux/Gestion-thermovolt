document.addEventListener('DOMContentLoaded', function() {
    var infoBtn = document.getElementById('infoOtBtn');
    var infoModal = document.getElementById('infoOtModal');
    var closeInfo = document.getElementById('closeInfoOtModal');
    if (infoBtn && infoModal && closeInfo) {
        infoBtn.addEventListener('click', function() {
            infoModal.style.display = 'block';
        });
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

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM cargado, inicializando firmas...');

    const canvasTecnico = document.getElementById('signature-canvas-tecnico');
    const canvasReceptor = document.getElementById('signature-canvas-receptor');

    if (!canvasTecnico) {
        console.error('Canvas del técnico no encontrado');
        return;
    }
    if (!canvasReceptor) {
        console.error('Canvas del receptor no encontrado');
        return;
    }

    function setupCanvasBackground(canvas) {
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    setupCanvasBackground(canvasTecnico);
    const signaturePadTecnico = new SignaturePad(canvasTecnico, {
        minWidth: 1,
        maxWidth: 3,
        penColor: 'rgb(0,0,0)',
        backgroundColor: 'rgb(255,255,255)'
    });
    console.log('✅ SignaturePad técnico inicializado:', signaturePadTecnico);
    console.log('Canvas técnico visible:', canvasTecnico.offsetWidth > 0 && canvasTecnico.offsetHeight > 0);

    const clearButtonTecnico = document.getElementById('clear-signature-tecnico');
    clearButtonTecnico.addEventListener('click', function() {
        signaturePadTecnico.clear();
        setupCanvasBackground(canvasTecnico);
        console.log('Firma del técnico limpiada');
    });

    setupCanvasBackground(canvasReceptor);
    const signaturePadReceptor = new SignaturePad(canvasReceptor, {
        minWidth: 1,
        maxWidth: 3,
        penColor: 'rgb(0,0,0)',
        backgroundColor: 'rgb(255,255,255)'
    });
    console.log('✅ SignaturePad receptor inicializado:', signaturePadReceptor);
    console.log('Canvas receptor visible:', canvasReceptor.offsetWidth > 0 && canvasReceptor.offsetHeight > 0);
    const clearButtonReceptor = document.getElementById('clear-signature-receptor');
    clearButtonReceptor.addEventListener('click', function() {
        signaturePadReceptor.clear();
        setupCanvasBackground(canvasReceptor);
    });

    const signatureOverlay = document.getElementById('signature-overlay');
    const overlayCanvas = document.getElementById('signature-canvas-overlay');
    const overlayTitle = document.getElementById('overlay-title');
    const closeOverlayBtn = document.getElementById('close-signature-overlay');
    const saveOverlayBtn = document.getElementById('save-signature-overlay');
    const clearOverlayBtn = document.getElementById('clear-signature-overlay');
    let overlayPad;
    let currentSignType = null;

    function resizeOverlayCanvas() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const width = overlayCanvas.offsetWidth;
        const height = overlayCanvas.offsetHeight;
        overlayCanvas.width = Math.round(width * ratio);
        overlayCanvas.height = Math.round(height * ratio);
        const ctx = overlayCanvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, overlayCanvas.offsetWidth, overlayCanvas.offsetHeight);
    }

    function openSignatureOverlay(type) {
        currentSignType = type;
        overlayTitle.textContent = type === 'tecnico' ? 'Firma del Técnico' : 'Firma de la Persona que Recibe';

        signatureOverlay.style.display = 'flex';

        requestAnimationFrame(() => {
            overlayCanvas.style.transform = 'none';
            overlayCanvas.style.width = '100%';
            overlayCanvas.style.height = '100%';
            resizeOverlayCanvas();

            overlayPad = new SignaturePad(overlayCanvas, {
                minWidth: 2,
                maxWidth: 4,
                penColor: 'rgb(0,0,0)',
                backgroundColor: 'rgb(255,255,255)'
            });

            const sourcePad = type === 'tecnico' ? signaturePadTecnico : signaturePadReceptor;
            if (!sourcePad.isEmpty()) {
                overlayPad.fromDataURL(sourcePad.toDataURL());
            } else {
                overlayPad.clear();
            }
        });
    }

    function closeSignatureOverlay() {
        signatureOverlay.style.display = 'none';
        overlayCanvas.style.transform = 'none';
        overlayCanvas.style.width = '100%';
        overlayCanvas.style.height = '100%';
    }

    document.querySelectorAll('.cierre-ot-mobile-sign-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            openSignatureOverlay(this.dataset.sign);
        });
    });

    closeOverlayBtn.addEventListener('click', closeSignatureOverlay);

    clearOverlayBtn.addEventListener('click', function() {
        if (overlayPad) {
            overlayPad.clear();
            const ctx = overlayCanvas.getContext('2d');
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        }
    });

    saveOverlayBtn.addEventListener('click', function() {
        if (!overlayPad || overlayPad.isEmpty()) {
            return;
        }

        const dataURL = overlayPad.toDataURL();
        if (currentSignType === 'tecnico') {
            signaturePadTecnico.clear();
            setupCanvasBackground(canvasTecnico);
            signaturePadTecnico.fromDataURL(dataURL);
        } else {
            signaturePadReceptor.clear();
            setupCanvasBackground(canvasReceptor);
            signaturePadReceptor.fromDataURL(dataURL);
        }

        closeSignatureOverlay();
    });

    const form = document.querySelector('form');
    if (!form) {
        console.error('Formulario no encontrado');
        return;
    }

    const firmaTecnicoTextarea = document.getElementById('firma-tecnico-data');
    const firmaReceptorTextarea = document.getElementById('firma-receptor-data');
    const submitButton = document.getElementById('submit-cierre-ot');
    const statusDiv = document.getElementById('cierre-ot-status');
    let formSubmitting = false;

    if (!firmaTecnicoTextarea) {
        console.error('Textarea de firma del técnico no encontrado');
        return;
    }
    if (!firmaReceptorTextarea) {
        console.error('Textarea de firma del receptor no encontrado');
        return;
    }

    if (!submitButton) {
        console.error('Botón de envío no encontrado');
        return;
    }

    console.log('Todos los elementos del DOM encontrados correctamente');

    form.addEventListener('submit', function(e) {
        if (formSubmitting) {
            console.log('Intento de envío duplicado bloqueado');
            e.preventDefault();
            return;
        }

        try {
            formSubmitting = true;
            console.log('Formulario enviado - iniciando procesamiento de firmas');

            if (!signaturePadTecnico.isEmpty()) {
                const dataURLTecnico = signaturePadTecnico.toDataURL();
                firmaTecnicoTextarea.value = dataURLTecnico;
                console.log('Firma del técnico guardada en textarea, longitud:', dataURLTecnico.length);
            } else {
                console.log('Firma del técnico está vacía');
            }

            if (!signaturePadReceptor.isEmpty()) {
                const dataURLReceptor = signaturePadReceptor.toDataURL();
                firmaReceptorTextarea.value = dataURLReceptor;
                console.log('Firma del receptor guardada en textarea, longitud:', dataURLReceptor.length);
            } else {
                console.log('Firma del receptor está vacía');
            }

            console.log('Firmas procesadas, permitiendo envío nativo del formulario');

            if (statusDiv) {
                statusDiv.textContent = 'El informe está siendo procesado. No cierre esta página ni vuelva a presionar el botón.';
            }
            submitButton.disabled = true;
            submitButton.textContent = 'Procesando informe...';
        } catch (error) {
            console.error('Error procesando formulario:', error);
            formSubmitting = false;
            e.preventDefault();
            alert('Error procesando el formulario: ' + error.message);
        }
    });

    submitButton.addEventListener('click', function(e) {
        if (formSubmitting) {
            e.preventDefault();
            console.log('Doble clic bloqueado');
        }
    });

    function actualizarEstadoInforme() {
        const operationInput = document.getElementById('operation-id');
        if (!operationInput) {
            return;
        }
        const operationId = operationInput.value;
        if (!operationId) {
            return;
        }

        const otId = document.querySelector('[data-ot-id]')?.dataset.otId;
        if (!otId) {
            return;
        }

        const statusUrl = `/Gestion_ot/informes/estado/${otId}/${encodeURIComponent(operationId)}/`;
        fetch(statusUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                const statusDiv = document.getElementById('cierre-ot-status');
                if (!statusDiv) return;

                statusDiv.textContent = `Estado: ${data.estado.replace(/_/g, ' ')} - ${data.mensaje}`;

                if (['ENVIADO', 'ERROR'].includes(data.estado)) {
                    const submitButton = document.getElementById('submit-cierre-ot');
                    if (submitButton) {
                        submitButton.disabled = false;
                        submitButton.textContent = 'Guardar y enviar informe';
                    }
                }
            })
            .catch(error => {
                console.error('Error consultando estado del informe:', error);
            });
    }

    const operationInput = document.getElementById('operation-id');
    if (operationInput && operationInput.value) {
        actualizarEstadoInforme();
        setInterval(actualizarEstadoInforme, 10000);
    }
});
