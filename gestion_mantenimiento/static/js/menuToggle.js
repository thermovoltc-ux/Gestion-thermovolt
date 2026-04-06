

// Agregar la clase 'hovered' al elemento seleccionado
function activeLink() {
    list.forEach((item) => {
        item.classList.remove("hovered");
    });
    this.classList.add("hovered");
}

// Menú Toggle: mostrar y ocultar el menú de navegación
const toggle = document.querySelector(".toggle");
const navigation = document.querySelector(".navigation");
const main = document.querySelector(".main");
const overlay = document.querySelector(".overlay");
const submenuItems = document.querySelectorAll(".navigation .has-submenu");

function openNavigation() {
    navigation.classList.add("active");
    main.classList.add("active");
    overlay.classList.add("active");
}

function closeNavigation() {
    navigation.classList.remove("active");
    main.classList.remove("active");
    overlay.classList.remove("active");
    submenuItems.forEach((item) => item.classList.remove("active"));
}

toggle.onclick = function () {
    if (navigation.classList.contains("active")) {
        closeNavigation();
    } else {
        openNavigation();
    }
};

// Cerrar el menú si se hace clic en el overlay
overlay.onclick = function (event) {
    closeNavigation();
    event.stopPropagation();
};

// Cerrar el menú si se hace clic fuera de él (en el contenido principal)
document.addEventListener("click", function (event) {
    if (!navigation.contains(event.target) && !toggle.contains(event.target) && !overlay.contains(event.target)) {
        closeNavigation();
    }
});

// Abrir/cerrar submenú de la barra lateral
const submenuLinks = document.querySelectorAll(".navigation .has-submenu > a");
submenuLinks.forEach((link) => {
    link.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        const parent = this.parentElement;
        parent.classList.toggle("active");
    });
});

// Asegurar que los enlaces del submenu naveguen correctamente
const submenuNavLinks = document.querySelectorAll(".navigation .submenu li a");
submenuNavLinks.forEach((link) => {
    link.addEventListener("click", function (event) {
        event.stopPropagation();
        const href = this.getAttribute('href');
        if (href && href !== '#') {
            window.location.href = href;
        }
    });
});
