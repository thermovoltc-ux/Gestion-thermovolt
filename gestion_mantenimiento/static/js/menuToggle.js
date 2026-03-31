

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

toggle.onclick = function () {
    navigation.classList.toggle("active");
    main.classList.toggle("active");
    overlay.classList.toggle("active");
};

// Cerrar el menú si se hace clic en el overlay
overlay.onclick = function (event) {
    navigation.classList.remove("active");
    main.classList.remove("active");
    overlay.classList.remove("active");
    event.stopPropagation();
};

// Cerrar el menú si se hace clic fuera de él (en el contenido principal)
document.addEventListener("click", function (event) {
    if (!navigation.contains(event.target) && !toggle.contains(event.target) && !overlay.contains(event.target)) {
        navigation.classList.remove("active");
        main.classList.remove("active");
        overlay.classList.remove("active");
    }
});
