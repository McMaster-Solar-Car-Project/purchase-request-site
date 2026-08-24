import {
    formatMoneyCents,
    formatMoneyFromPreciseAmount,
    formatMoneyInput,
    formatPreciseAmount,
    parseMoneyCents,
    parseQuantity,
    parseScaledAmount,
    preciseDecimalPlaces,
    todayIsoDate,
} from "./money.js";

let maxItems = 50;

export function formatMoneyFields() {
    const formsToRecalculate = new Set();

    document.querySelectorAll('input[data-format="money"]').forEach(input => {
        formatMoneyInput(input);
        if (input.dataset.action === "recalc-total") {
            formsToRecalculate.add(Number(input.dataset.form));
        }
    });

    formsToRecalculate.forEach(formNumber => calculateFinalTotal(formNumber));
}

function toggleForm(formNumber) {
    const content = document.getElementById(`form-${formNumber}`);
    const toggle = content.previousElementSibling.querySelector('[data-role="accordion-toggle"]');

    if (content.style.display === "none" || content.style.display === "") {
        content.style.display = "block";
        toggle.textContent = "-";
    } else {
        content.style.display = "none";
        toggle.textContent = "+";
    }
}

function getItemsContainer(formNumber) {
    return document.getElementById(`items-container-${formNumber}`);
}

function getItemRows(formNumber) {
    const container = getItemsContainer(formNumber);
    if (!container) return [];
    return Array.from(container.querySelectorAll(".item-row"));
}

function renumberItemRows(formNumber) {
    getItemRows(formNumber).forEach((row, index) => {
        const itemNumber = index + 1;
        const itemSuffixPattern = new RegExp(`_${formNumber}_\\d+$`);
        const itemSuffix = `_${formNumber}_${itemNumber}`;

        row.dataset.form = String(formNumber);
        row.dataset.item = String(itemNumber);

        row.querySelectorAll("[name]").forEach(field => {
            field.name = field.name.replace(itemSuffixPattern, itemSuffix);
        });

        row.querySelectorAll("[data-form]").forEach(element => {
            element.dataset.form = String(formNumber);
        });

        row.querySelectorAll("[data-item]").forEach(element => {
            element.dataset.item = String(itemNumber);
        });
    });
}

function instantiateItemRow(formNumber, itemNumber, currency) {
    const tpl = document.getElementById("item-row-template");
    const row = tpl.content.firstElementChild.cloneNode(true);

    const substitute = value => value
        .replace(/__FORM__/g, String(formNumber))
        .replace(/__ITEM__/g, String(itemNumber));

    const walker = document.createTreeWalker(row, NodeFilter.SHOW_ELEMENT);
    let node = row;
    do {
        for (const attr of Array.from(node.attributes)) {
            if (attr.value.includes("__FORM__") || attr.value.includes("__ITEM__")) {
                node.setAttribute(attr.name, substitute(attr.value));
            }
        }
    } while ((node = walker.nextNode()));

    row.querySelectorAll(`.currency-label-${formNumber}`).forEach(el => {
        el.textContent = currency;
    });

    return row;
}

function wireItemRow(row) {
    row.querySelectorAll('[data-action="calc-item"]').forEach(input => {
        input.addEventListener("input", () => {
            calculateItemTotal(Number(input.dataset.form), Number(input.dataset.item));
        });
    });
    row.querySelectorAll('[data-action="remove-item"]').forEach(btn => {
        btn.addEventListener("click", () => removeItem(btn, Number(btn.dataset.form)));
    });
}

function addItem(formNumber) {
    const itemCount = getItemRows(formNumber).length;
    if (itemCount >= maxItems) {
        alert(`Maximum of ${maxItems} items allowed per form.`);
        return;
    }

    const container = getItemsContainer(formNumber);
    if (!container) return;

    const currencySelect = document.getElementById(`currency_${formNumber}`);
    const currentCurrency = currencySelect ? currencySelect.value : "CAD";

    const newRow = instantiateItemRow(formNumber, itemCount + 1, currentCurrency);
    container.appendChild(newRow);
    wireItemRow(newRow);
    renumberItemRows(formNumber);
    updateRemoveButtons(formNumber);
}

function removeItem(button, formNumber) {
    const row = button.closest(".item-row");
    if (!row) return;

    row.remove();
    renumberItemRows(formNumber);
    updateRemoveButtons(formNumber);
    calculateSubtotal(formNumber);
}

function updateRemoveButtons(formNumber) {
    const container = getItemsContainer(formNumber);
    if (!container) return;

    const itemCount = getItemRows(formNumber).length;
    const removeButtons = container.querySelectorAll(".btn-remove");
    removeButtons.forEach(btn => {
        btn.style.display = itemCount > 1 ? "block" : "none";
    });
}

function calculateItemTotal(formNumber, itemNumber) {
    const quantityInput = document.querySelector(`input[name="item_quantity_${formNumber}_${itemNumber}"]`);
    const priceInput = document.querySelector(`input[name="item_price_${formNumber}_${itemNumber}"]`);
    const totalInput = document.querySelector(`input[name="item_total_${formNumber}_${itemNumber}"]`);

    if (quantityInput && priceInput && totalInput) {
        const quantity = parseQuantity(quantityInput.value);
        const price = parseScaledAmount(priceInput.value, preciseDecimalPlaces);
        const total = quantity * price;

        totalInput.value = formatPreciseAmount(total);
        calculateSubtotal(formNumber);
    }
}

function calculateSubtotal(formNumber) {
    const container = document.getElementById(`items-container-${formNumber}`);
    const totalInputs = container.querySelectorAll('input[name^="item_total_"]');
    let subtotal = 0n;

    totalInputs.forEach(input => {
        subtotal += parseScaledAmount(input.value, preciseDecimalPlaces);
    });

    const formattedSubtotal = formatMoneyFromPreciseAmount(subtotal);
    const subtotalField = document.getElementById(`subtotal_amount_${formNumber}`);
    if (subtotalField) subtotalField.value = formattedSubtotal;
    const usSubtotalField = document.getElementById(`us_subtotal_${formNumber}`);
    if (usSubtotalField) usSubtotalField.value = formattedSubtotal;

    const currencySelect = document.getElementById(`currency_${formNumber}`);
    if (!currencySelect || currencySelect.value === "CAD") {
        updateHstRequirement(formNumber, subtotal);
        calculateFinalTotal(formNumber);
    }
}

function updateHstRequirement(formNumber, subtotal) {
    const currencySelect = document.getElementById(`currency_${formNumber}`);
    const hstGstInput = document.getElementById(`hst_gst_amount_${formNumber}`);
    const requiredIndicator = document.querySelector(`.required-indicator-${formNumber}`);
    const taxHelp = document.querySelector(`.tax-help-${formNumber}`);

    if (!currencySelect || !hstGstInput) return;

    const isCAD = currencySelect.value === "CAD";
    const hasSubtotal = typeof subtotal === "bigint" ? subtotal > 0n : subtotal > 0;
    const shouldBeRequired = isCAD && hasSubtotal;

    if (shouldBeRequired) {
        hstGstInput.setAttribute("required", "required");
        if (requiredIndicator) requiredIndicator.textContent = "*";
        if (taxHelp) taxHelp.textContent = "Harmonized Sales Tax / Goods and Services Tax (required when items are added)";
    } else {
        hstGstInput.removeAttribute("required");
        if (requiredIndicator) requiredIndicator.textContent = "";
        if (taxHelp) taxHelp.textContent = "Harmonized Sales Tax / Goods and Services Tax";
    }
}

function calculateFinalTotal(formNumber) {
    const subtotal = parseMoneyCents(document.getElementById(`subtotal_amount_${formNumber}`).value);
    const discount = parseMoneyCents(document.getElementById(`discount_amount_${formNumber}`).value);
    const hstGst = parseMoneyCents(document.getElementById(`hst_gst_amount_${formNumber}`).value);
    const shipping = parseMoneyCents(document.getElementById(`shipping_amount_${formNumber}`).value);

    const total = subtotal - discount + hstGst + shipping;
    document.getElementById(`total_cad_amount_${formNumber}`).value = formatMoneyCents(total > 0n ? total : 0n);
}

function updateCurrencyLabels(formNumber) {
    const currencySelect = document.getElementById(`currency_${formNumber}`);
    const selectedCurrency = currencySelect.value;
    const currencyLabels = document.querySelectorAll(`.currency-label-${formNumber}`);
    const taxLabels = document.querySelectorAll(`.tax-label-${formNumber}`);
    const taxHelp = document.querySelector(`.tax-help-${formNumber}`);
    const proofOfPaymentSection = document.querySelector(`.proof-of-payment-section-${formNumber}`);
    const cadBreakdown = document.querySelector(`.cad-breakdown-${formNumber}`);
    const usdBreakdown = document.querySelector(`.usd-breakdown-${formNumber}`);
    const hstGstInput = document.getElementById(`hst_gst_amount_${formNumber}`);
    const hstGstLabel = document.querySelector(`label[for="hst_gst_amount_${formNumber}"]`);
    const totalInput = document.getElementById(`total_cad_amount_${formNumber}`);
    const totalLabel = document.querySelector(`.total-label-${formNumber}`);
    const totalHelp = document.querySelector(`.total-help-${formNumber}`);

    currencyLabels.forEach(label => {
        label.textContent = selectedCurrency;
    });

    if (selectedCurrency === "USD") {
        taxLabels.forEach(label => {
            label.textContent = "Taxes";
        });
        if (taxHelp) {
            taxHelp.textContent = "Sales tax, state tax, or other applicable taxes";
        }
        if (hstGstInput) {
            hstGstInput.removeAttribute("required");
        }
        if (hstGstLabel) {
            hstGstLabel.innerHTML = `<span class="tax-label-${formNumber}">Taxes</span> (<span class="currency-label-${formNumber}">USD</span>)`;
        }

        if (cadBreakdown) cadBreakdown.style.display = "none";
        if (usdBreakdown) usdBreakdown.style.display = "grid";

        if (totalInput) {
            totalInput.removeAttribute("readonly");
            totalInput.value = "";
        }
        if (totalLabel) totalLabel.textContent = "Canadian Amount";
        if (totalHelp) totalHelp.textContent = "Equivalent amount in Canadian dollars for reimbursement";
    } else {
        taxLabels.forEach(label => {
            label.textContent = "HST/GST";
        });
        if (hstGstLabel) {
            hstGstLabel.innerHTML = `<span class="tax-label-${formNumber}">HST/GST</span> (<span class="currency-label-${formNumber}">CAD</span>) <span class="required-indicator-${formNumber}"></span>`;
        }

        const subtotalInput = document.getElementById(`subtotal_amount_${formNumber}`);
        const currentSubtotal = parseMoneyCents(subtotalInput ? subtotalInput.value : "");
        updateHstRequirement(formNumber, currentSubtotal);

        if (cadBreakdown) cadBreakdown.style.display = "grid";
        if (usdBreakdown) usdBreakdown.style.display = "none";

        if (totalInput) totalInput.setAttribute("readonly", "");
        if (totalLabel) totalLabel.textContent = "Total Reimbursement Amount";
        if (totalHelp) totalHelp.textContent = "Automatically calculated (Subtotal - Discount + Tax + Shipping)";
        calculateSubtotal(formNumber);
    }

    if (selectedCurrency === "USD") {
        proofOfPaymentSection.style.display = "block";
        const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
        if (proofOfPaymentInput) {
            proofOfPaymentInput.required = true;
        }
    } else {
        proofOfPaymentSection.style.display = "none";
        const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
        if (proofOfPaymentInput) {
            proofOfPaymentInput.required = false;
            resetFileInput(proofOfPaymentInput, `payment-filename-${formNumber}`);
        }
    }
}

function updateFileName(input, spanId) {
    const filenameSpan = document.getElementById(spanId);
    const dropArea = input.closest('[data-role="file-drop-area"]');
    const dropTextSpan = dropArea ? dropArea.querySelector('[data-role="file-upload-text"]') : null;

    if (!filenameSpan) return;

    if (input.files && input.files[0]) {
        const name = input.files[0].name;
        filenameSpan.textContent = name;
        if (dropTextSpan) dropTextSpan.textContent = name;
    } else {
        filenameSpan.textContent = "No file chosen";
        if (dropTextSpan) dropTextSpan.innerHTML = "<b>Choose a file</b> or drag it here";
    }
}

function resetFileInput(input, spanId) {
    if (!input) return;
    input.value = "";
    updateFileName(input, spanId);
}

function clearForm(formNumber) {
    if (!confirm(`Are you sure you want to clear all data in Purchase Request #${formNumber}? This action cannot be undone.`)) {
        return;
    }

    const vendorNameInput = document.getElementById(`vendor_name_${formNumber}`);
    if (vendorNameInput) vendorNameInput.value = "";

    const purchaseDateInput = document.getElementById(`purchase_date_${formNumber}`);
    if (purchaseDateInput) purchaseDateInput.value = "";

    const currencySelect = document.getElementById(`currency_${formNumber}`);
    if (currencySelect) {
        currencySelect.value = "CAD";
        updateCurrencyLabels(formNumber);
    }

    const invoiceFileInput = document.getElementById(`invoice_file_${formNumber}`);
    const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);

    resetFileInput(invoiceFileInput, `invoice-filename-${formNumber}`);
    resetFileInput(proofOfPaymentInput, `payment-filename-${formNumber}`);

    const itemsContainer = document.getElementById(`items-container-${formNumber}`);
    if (itemsContainer) {
        const itemRows = itemsContainer.querySelectorAll(".item-row");
        for (let i = 1; i < itemRows.length; i++) {
            itemRows[i].remove();
        }

        const firstRow = itemRows[0];
        if (firstRow) {
            const inputs = firstRow.querySelectorAll("input");
            inputs.forEach(input => {
                if (input.name.includes("_quantity_")) {
                    input.value = "1";
                } else {
                    input.value = "";
                }
            });
        }

        renumberItemRows(formNumber);
        updateRemoveButtons(formNumber);
    }

    const financialFields = [
        `subtotal_amount_${formNumber}`,
        `discount_amount_${formNumber}`,
        `hst_gst_amount_${formNumber}`,
        `shipping_amount_${formNumber}`,
        `us_subtotal_${formNumber}`,
        `us_additional_fees_${formNumber}`,
        `total_cad_amount_${formNumber}`,
    ];

    financialFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) field.value = "";
    });

    const hstGstInput = document.getElementById(`hst_gst_amount_${formNumber}`);
    const requiredIndicator = document.querySelector(`.required-indicator-${formNumber}`);
    if (hstGstInput) hstGstInput.removeAttribute("required");
    if (requiredIndicator) requiredIndicator.textContent = "";

    console.log(`Form ${formNumber} has been cleared successfully.`);
}

function handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add("is-dragging");
}

function handleDragLeave(event) {
    event.currentTarget.classList.remove("is-dragging");
}

function handleFileDrop(event, inputId, spanId) {
    event.preventDefault();
    event.currentTarget.classList.remove("is-dragging");

    const fileInput = document.getElementById(inputId);
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        updateFileName(fileInput, spanId);
    }
}

function initializeStaticHandlers() {
    document.querySelectorAll('input[type="date"][name^="purchase_date_"]').forEach(input => {
        input.max = todayIsoDate();
    });

    document.querySelectorAll('[data-action="toggle-form"]').forEach(header => {
        header.addEventListener("click", () => toggleForm(Number(header.dataset.form)));
    });

    document.querySelectorAll('[data-action="clear-form"]').forEach(btn => {
        btn.addEventListener("click", event => {
            event.stopPropagation();
            clearForm(Number(btn.dataset.form));
        });
    });

    document.querySelectorAll('[data-action="currency-select"]').forEach(select => {
        select.addEventListener("change", () => updateCurrencyLabels(Number(select.dataset.form)));
    });

    document.querySelectorAll('[data-action="add-item"]').forEach(btn => {
        btn.addEventListener("click", () => addItem(Number(btn.dataset.form)));
    });

    document.querySelectorAll('[data-action="remove-item"]').forEach(btn => {
        btn.addEventListener("click", () => removeItem(btn, Number(btn.dataset.form)));
    });

    document.querySelectorAll('[data-action="calc-item"]').forEach(input => {
        input.addEventListener("input", () => {
            calculateItemTotal(Number(input.dataset.form), Number(input.dataset.item));
        });
    });

    document.querySelectorAll('[data-action="recalc-total"]').forEach(input => {
        input.addEventListener("input", () => calculateFinalTotal(Number(input.dataset.form)));
    });

    document.querySelectorAll('input[data-format="money"]').forEach(input => {
        input.addEventListener("blur", () => {
            formatMoneyInput(input);
            if (input.dataset.action === "recalc-total") {
                calculateFinalTotal(Number(input.dataset.form));
            }
        });
    });

    document.querySelectorAll('[data-role="file-upload-text"]').forEach(trigger => {
        trigger.addEventListener("click", () => {
            const input = document.getElementById(trigger.dataset.inputId);
            if (input) input.click();
        });
    });

    document.querySelectorAll('[data-role="file-drop-area"]').forEach(area => {
        area.addEventListener("dragover", handleDragOver);
        area.addEventListener("dragleave", handleDragLeave);
        area.addEventListener("drop", event => {
            handleFileDrop(event, area.dataset.inputId, area.dataset.filenameId);
        });
    });

    document.querySelectorAll('input[type="file"][data-filename-id]').forEach(input => {
        input.addEventListener("change", () => updateFileName(input, input.dataset.filenameId));
    });
}

export function initializeDashboardUi(config) {
    maxItems = config.maxItems;

    for (let i = 1; i <= config.maxForms; i++) {
        const content = document.getElementById(`form-${i}`);
        content.style.display = "none";

        updateCurrencyLabels(i);

        const proofOfPaymentWrapper = document.querySelector(`.proof-of-payment-section-${i}`);
        if (proofOfPaymentWrapper) {
            const currencySelect = document.getElementById(`currency_${i}`);
            if (currencySelect && currencySelect.value === "USD") {
                proofOfPaymentWrapper.style.display = "block";
            } else {
                proofOfPaymentWrapper.style.display = "none";
            }
        }
    }

    initializeStaticHandlers();
}
