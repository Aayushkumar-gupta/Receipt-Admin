(function () {
    function errorFor(input) {
        return document.getElementById(input.id + "-error");
    }

    function showError(input, message) {
        var error = errorFor(input);
        input.setAttribute("aria-invalid", "true");
        if (error) {
            error.textContent = message;
            error.hidden = false;
        }
    }

    function clearError(input) {
        var error = errorFor(input);
        input.removeAttribute("aria-invalid");
        if (error) {
            error.textContent = "";
            error.hidden = true;
        }
    }

    function problemWith(input) {
        var value = input.value.trim();
        var validity = input.validity;
        if (validity.valueMissing || (input.required && !value)) {
            return input.dataset.requiredMessage || "This field is required.";
        }
        if (validity.typeMismatch && input.type === "email") {
            return "Enter a valid email address.";
        }
        if (validity.patternMismatch) {
            return input.dataset.patternMessage || "Check the format of this field.";
        }
        if (input.minLength > 0 && input.value.length < input.minLength) {
            return "Use at least " + input.minLength + " characters.";
        }
        if (input.dataset.match) {
            var other = document.getElementById(input.dataset.match);
            if (other && other.value !== input.value) {
                return "The passwords do not match.";
            }
        }
        return "";
    }

    document.addEventListener("click", function (event) {
        var toggle = event.target.closest("[data-password-toggle]");
        if (!toggle) {
            return;
        }
        var input = document.getElementById(toggle.getAttribute("aria-controls"));
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        toggle.setAttribute("aria-pressed", String(show));
        toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });

    document.addEventListener("input", function (event) {
        if (event.target.matches("[aria-invalid]")) {
            clearError(event.target);
        }
    });

    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!form.matches("[data-validate]")) {
            return;
        }
        var firstInvalid = null;
        form.querySelectorAll("input:not([type=hidden])").forEach(function (input) {
            var message = problemWith(input);
            if (message) {
                showError(input, message);
                firstInvalid = firstInvalid || input;
            } else {
                clearError(input);
            }
        });
        if (firstInvalid) {
            event.preventDefault();
            firstInvalid.focus();
        }
    });
})();
