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

function showLoading(control) {
    var spinner = document.createElement("span");
    spinner.className = "spinner";
    spinner.setAttribute("aria-hidden", "true");
    control.dataset.label = control.innerHTML;
    control.textContent = control.dataset.loading;
    control.prepend(spinner);
    control.setAttribute("aria-busy", "true");
    if (control.tagName === "BUTTON") {
        control.disabled = true;
    } else {
        control.setAttribute("aria-disabled", "true");
    }
}

function hideLoading(control) {
    control.innerHTML = control.dataset.label;
    control.removeAttribute("aria-busy");
    control.removeAttribute("aria-disabled");
    control.disabled = false;
}

// Downloads keep the page in place, so fetch the file to know when to stop the loading state.
function download(url, control) {
    showLoading(control);
    fetch(url, {credentials: "same-origin"})
        .then(function (response) {
            var type = response.headers.get("Content-Type") || "";
            if (!response.ok || type.indexOf("text/html") === 0) {
                window.location.href = url;
                return null;
            }
            var match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "");
            return response.blob().then(function (blob) {
                var link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = match ? match[1] : "";
                document.body.appendChild(link);
                link.click();
                link.remove();
                setTimeout(function () {
                    URL.revokeObjectURL(link.href);
                }, 1000);
            });
        })
        .catch(function () {
            window.location.href = url;
        })
        .finally(function () {
            hideLoading(control);
        });
}

document.addEventListener("click", function (event) {
    var link = event.target.closest("a[data-download]");
    if (!link) {
        return;
    }
    event.preventDefault();
    if (link.getAttribute("aria-busy") !== "true") {
        download(link.href, link);
    }
});

document.addEventListener("submit", function (event) {
    var form = event.target;
    var button = event.submitter || form.querySelector("[type=submit]");
    if (!button || !button.dataset.loading) {
        return;
    }
    if (button.hasAttribute("data-download")) {
        event.preventDefault();
        var query = new URLSearchParams(new FormData(form)).toString();
        download(form.action + (query ? "?" + query : ""), button);
        return;
    }
    // Wait until every submit handler has run, so a cancelled confirm or a failed check keeps the button.
    setTimeout(function () {
        if (!event.defaultPrevented) {
            showLoading(button);
        }
    }, 0);
});

window.addEventListener("pageshow", function () {
    document.querySelectorAll("[aria-busy=true][data-label]").forEach(hideLoading);
});
