import './csrf.js';
import './solicitudes.js';
import './gestion_ot.js';
import './CrearActivos.js';
import './menuToggle.js';
import './userManagement.js';







document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM completamente cargado y analizado');

    if (typeof $.fn.nestedSortable === 'undefined') {
        console.error('nestedSortable no está definido');
    } else {
        console.log('nestedSortable está definido');
    }

    $("#items-container").nestedSortable({
        handle: 'div',
        items: 'li',
        toleranceElement: '> div',
        isTree: true,
        expandOnHover: 700,
        startCollapsed: true
    });
});