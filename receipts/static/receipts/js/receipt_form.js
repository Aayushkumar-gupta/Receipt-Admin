(function () {
    var form = document.querySelector("[data-receipt-form]");
    if (!form) {
        return;
    }

    var rows = document.getElementById("item-rows");
    var template = document.getElementById("item-row-template");
    var itemsInput = document.getElementById("items-input");
    var taxInput = document.getElementById("tax_rate");

    function field(row, name) {
        return row.querySelector('[data-item="' + name + '"]');
    }

    function cents(value) {
        var number = parseFloat(value);
        return isFinite(number) && number > 0 ? Math.round(number * 100) : 0;
    }

    function money(amount) {
        return "$" + (amount / 100).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function addRow(item) {
        var row = template.content.firstElementChild.cloneNode(true);
        field(row, "description").value = item.description || "";
        field(row, "quantity").value = item.quantity == null ? 1 : item.quantity;
        field(row, "unit_price").value = item.unit_price == null ? "" : item.unit_price;
        rows.appendChild(row);
        return row;
    }

    function update() {
        var subtotal = 0;
        Array.prototype.forEach.call(rows.children, function (row) {
            var quantity = Math.max(0, Math.floor(Number(field(row, "quantity").value) || 0));
            var amount = quantity * cents(field(row, "unit_price").value);
            field(row, "amount").textContent = money(amount);
            subtotal += amount;
        });

        var rateBasisPoints = Math.round((parseFloat(taxInput.value) || 0) * 100);
        var tax = Math.floor((subtotal * Math.max(rateBasisPoints, 0) + 5000) / 10000);
        form.querySelector('[data-total="subtotal"]').textContent = money(subtotal);
        form.querySelector('[data-total="tax"]').textContent = money(tax);
        form.querySelector('[data-total="total"]').textContent = money(subtotal + tax);

        var onlyOne = rows.children.length === 1;
        rows.querySelectorAll("[data-remove-item]").forEach(function (button) {
            button.disabled = onlyOne;
        });
    }

    function initialItems() {
        var source = document.getElementById("items-data");
        try {
            var items = JSON.parse(source ? source.textContent : form.dataset.items || "[]");
            return Array.isArray(items) && items.length ? items : [{}];
        } catch (error) {
            return [{}];
        }
    }

    form.addEventListener("input", update);

    form.addEventListener("click", function (event) {
        if (event.target.closest("[data-add-item]")) {
            addRow({}).querySelector('[data-item="description"]').focus();
            update();
            return;
        }

        var remove = event.target.closest("[data-remove-item]");
        if (remove) {
            var row = remove.closest(".item-row");
            var next = row.nextElementSibling || row.previousElementSibling;
            row.remove();
            update();
            if (next) {
                field(next, "description").focus();
            }
        }
    });

    form.addEventListener("submit", function () {
        var items = Array.prototype.map.call(rows.children, function (row) {
            return {
                description: field(row, "description").value.trim(),
                quantity: field(row, "quantity").value,
                unit_price: field(row, "unit_price").value
            };
        });
        itemsInput.value = JSON.stringify(items);
    });

    initialItems().forEach(addRow);
    update();
})();
