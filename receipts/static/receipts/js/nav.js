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

document.addEventListener("click", function (event) {
    document.querySelectorAll("details.row-menu[open]").forEach(function (menu) {
        if (!menu.contains(event.target)) {
            menu.removeAttribute("open");
        }
    });
});

document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
        return;
    }
    document.querySelectorAll("details.row-menu[open]").forEach(function (menu) {
        menu.removeAttribute("open");
        menu.querySelector("summary").focus();
    });
});

document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-toggle]");
    if (!trigger) {
        return;
    }
    var panel = document.getElementById(trigger.dataset.toggle);
    var open = panel.hidden;
    panel.hidden = !open;
    document.querySelectorAll('[data-toggle="' + panel.id + '"][aria-expanded]').forEach(function (button) {
        button.setAttribute("aria-expanded", String(open));
    });
    if (open) {
        var field = panel.querySelector("input:not([type=hidden]), textarea");
        if (field) {
            field.focus();
        }
    }
});

document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-dismiss]");
    if (button) {
        button.closest(".message").remove();
    }
});
