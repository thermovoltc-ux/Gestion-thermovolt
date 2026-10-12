// Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const tabName = this.getAttribute('data-tab');
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.querySelectorAll('.tab-btn').forEach(b => {
                    b.classList.remove('active');
                });
                document.getElementById(tabName).classList.add('active');
                this.classList.add('active');
            });
        });

        // Type account visibility
        document.addEventListener('DOMContentLoaded', function() {
            var tipoCuentaField = document.getElementById('id_tipo_cuenta');
            var coFieldDiv = document.getElementById('div_id_co');

            function updateCoField() {
                if (tipoCuentaField && tipoCuentaField.value === 'administrador') {
                    coFieldDiv.classList.remove('hidden');
                } else {
                    coFieldDiv.classList.add('hidden');
                }
            }

            if (tipoCuentaField) {
                tipoCuentaField.addEventListener('change', updateCoField);
                updateCoField();
            }
        });