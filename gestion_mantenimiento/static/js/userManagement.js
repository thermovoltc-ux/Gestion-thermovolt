// usuario
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');

    var userIcon = document.getElementById('user-icon');
    var userDropdownContent = document.getElementById('user-dropdown-content');

    if (userIcon) {
        console.log('User icon found');
    } else {
        console.log('User icon not found');
    }

    if (userDropdownContent) {
        console.log('User dropdown found');
    } else {
        console.log('User dropdown not found');
    }

    userIcon.addEventListener('click', function(event) {
        event.preventDefault();
        console.log('User icon clicked');
        userDropdownContent.style.display = userDropdownContent.style.display === 'block' ? 'none' : 'block';
        console.log('User dropdown display:', userDropdownContent.style.display);
    });

    // Cerrar el menú desplegable si se hace clic fuera de él
    document.addEventListener('click', function(event) {
        if (!userIcon.contains(event.target) && !userDropdownContent.contains(event.target)) {
            if (userDropdownContent.style.display === 'block') {
                userDropdownContent.style.display = 'none';
                console.log('User dropdown closed');
            }
        }
    });
});