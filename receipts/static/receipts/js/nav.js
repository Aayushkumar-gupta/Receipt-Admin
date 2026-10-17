document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.getElementById("nav-toggle");
    var menu = document.getElementById("nav-menu");
    if (!toggle || !menu) {
        return;
    }

    toggle.addEventListener("click", function () {
        var open = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(open));
        menu.classList.toggle("hidden", !open);
        toggle.querySelector('[data-icon="open"]').classList.toggle("hidden", open);
        toggle.querySelector('[data-icon="close"]').classList.toggle("hidden", !open);
    });
});

document.addEventListener("submit", function (event) {
    var message = event.target.dataset.confirm;
    if (message && !window.confirm(message)) {
        event.preventDefault();
    }
});
