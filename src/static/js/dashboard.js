const profileCompleteField = document.getElementById("profile-is-complete");
const profileIsComplete = profileCompleteField?.value === "true";

const itemCounts = {};
const maxItems = 15;
let isSubmitting = false;

for (let i = 1; i <= 10; i++) {
    itemCounts[i] = 1;
}

function toggleForm(formNumber) {
    const content = document.getElementById(`form-${formNumber}`);
    const toggle = content.previousElementSibling.querySelector('[data-role="accordion-toggle"]');

    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        toggle.textContent = '▲';
    } else {
        content.style.display = 'none';
        toggle.textContent = '▼';
    }
}

// Instantiate a new item row from the <template id="item-row-template">.
// The template uses __FORM__ and __ITEM__ as placeholders in attribute values
// so a single source of truth (the template element) can be parameterised at
// runtime instead of duplicating the row's markup in this file.
function instantiateItemRow(formNumber, itemNumber, currency) {
    const tpl = document.getElementById('item-row-template');
    const row = tpl.content.firstElementChild.cloneNode(true);

    const substitute = (value) => value
        .replace(/__FORM__/g, String(formNumber))
        .replace(/__ITEM__/g, String(itemNumber));

    const walker = document.createTreeWalker(row, NodeFilter.SHOW_ELEMENT);
    let node = row;
    do {
        for (const attr of Array.from(node.attributes)) {
            if (attr.value.includes('__FORM__') || attr.value.includes('__ITEM__')) {
                node.setAttribute(attr.name, substitute(attr.value));
            }
        }
    } while ((node = walker.nextNode()));

    row.querySelectorAll(`.currency-label-${formNumber}`).forEach(el => {
        el.textContent = currency;
    });

    return row;
}

// Wire up event listeners for a dynamically-added item row. Mirrors the
// data-action handlers attached by initializeStaticHandlers() at page load.
function wireItemRow(row) {
    row.querySelectorAll('[data-action="calc-item"]').forEach(input => {
        input.addEventListener('input', () => {
            calculateItemTotal(Number(input.dataset.form), Number(input.dataset.item));
        });
    });
    row.querySelectorAll('[data-action="remove-item"]').forEach(btn => {
        btn.addEventListener('click', () => removeItem(btn, Number(btn.dataset.form)));
    });
}

function addItem(formNumber) {
    if (itemCounts[formNumber] >= maxItems) {
        alert(`Maximum of ${maxItems} items allowed per form.`);
        return;
    }

    itemCounts[formNumber]++;
    const container = document.getElementById(`items-container-${formNumber}`);
    const currencySelect = document.getElementById(`currency_${formNumber}`);
    const currentCurrency = currencySelect ? currencySelect.value : 'CAD';

    const newRow = instantiateItemRow(formNumber, itemCounts[formNumber], currentCurrency);
    container.appendChild(newRow);
    wireItemRow(newRow);
    updateRemoveButtons(formNumber);
}

function removeItem(button, formNumber) {
    const row = button.closest('.item-row');
    row.remove();
    itemCounts[formNumber]--;
    updateRemoveButtons(formNumber);
    calculateSubtotal(formNumber);
}

function updateRemoveButtons(formNumber) {
    const container = document.getElementById(`items-container-${formNumber}`);
    const removeButtons = container.querySelectorAll('.btn-remove');
    removeButtons.forEach(btn => {
        btn.style.display = itemCounts[formNumber] > 1 ? 'block' : 'none';
    });
}

function calculateItemTotal(formNumber, itemNumber) {
    const quantityInput = document.querySelector(`input[name="item_quantity_${formNumber}_${itemNumber}"]`);
    const priceInput = document.querySelector(`input[name="item_price_${formNumber}_${itemNumber}"]`);
    const totalInput = document.querySelector(`input[name="item_total_${formNumber}_${itemNumber}"]`);

    if (quantityInput && priceInput && totalInput) {
        const quantity = parseFloat(quantityInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const total = quantity * price;

        totalInput.value = total.toFixed(8);
        calculateSubtotal(formNumber);
    }
}

function calculateSubtotal(formNumber) {
    const container = document.getElementById(`items-container-${formNumber}`);
    const totalInputs = container.querySelectorAll('input[name^="item_total_"]');
    let subtotal = 0;

    totalInputs.forEach(input => {
        const value = parseFloat(input.value) || 0;
        subtotal += value;
    });

    const formattedSubtotal = subtotal.toFixed(8);
    const subtotalField = document.getElementById(`subtotal_amount_${formNumber}`);
    if (subtotalField) subtotalField.value = formattedSubtotal;
    const usSubtotalField = document.getElementById(`us_subtotal_${formNumber}`);
    if (usSubtotalField) usSubtotalField.value = formattedSubtotal;

    const currencySelect = document.getElementById(`currency_${formNumber}`);
    if (!currencySelect || currencySelect.value === 'CAD') {
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

    const isCAD = currencySelect.value === 'CAD';
    const hasSubtotal = subtotal > 0;
    const shouldBeRequired = isCAD && hasSubtotal;

    if (shouldBeRequired) {
        hstGstInput.setAttribute('required', 'required');
        if (requiredIndicator) requiredIndicator.textContent = '*';
        if (taxHelp) taxHelp.textContent = 'Harmonized Sales Tax / Goods and Services Tax (required when items are added)';
    } else {
        hstGstInput.removeAttribute('required');
        if (requiredIndicator) requiredIndicator.textContent = '';
        if (taxHelp) taxHelp.textContent = 'Harmonized Sales Tax / Goods and Services Tax';
    }
}

function calculateFinalTotal(formNumber) {
    const subtotal = parseFloat(document.getElementById(`subtotal_amount_${formNumber}`).value) || 0;
    const discount = parseFloat(document.getElementById(`discount_amount_${formNumber}`).value) || 0;
    const hstGst = parseFloat(document.getElementById(`hst_gst_amount_${formNumber}`).value) || 0;
    const shipping = parseFloat(document.getElementById(`shipping_amount_${formNumber}`).value) || 0;

    const total = subtotal - discount + hstGst + shipping;
    document.getElementById(`total_cad_amount_${formNumber}`).value = Math.max(0, total).toFixed(8);
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

    if (selectedCurrency === 'USD') {
        taxLabels.forEach(label => {
            label.textContent = 'Taxes';
        });
        if (taxHelp) {
            taxHelp.textContent = 'Sales tax, state tax, or other applicable taxes';
        }
        if (hstGstInput) {
            hstGstInput.removeAttribute('required');
        }
        if (hstGstLabel) {
            hstGstLabel.innerHTML = `<span class="tax-label-${formNumber}">Taxes</span> (<span class="currency-label-${formNumber}">USD</span>)`;
        }

        if (cadBreakdown) cadBreakdown.style.display = 'none';
        if (usdBreakdown) usdBreakdown.style.display = 'block';

        if (totalInput) {
            totalInput.removeAttribute('readonly');
            totalInput.value = '';
        }
        if (totalLabel) totalLabel.textContent = 'Canadian Amount';
        if (totalHelp) totalHelp.textContent = 'Equivalent amount in Canadian dollars for reimbursement';
    } else {
        taxLabels.forEach(label => {
            label.textContent = 'HST/GST';
        });
        if (hstGstLabel) {
            hstGstLabel.innerHTML = `<span class="tax-label-${formNumber}">HST/GST</span> (<span class="currency-label-${formNumber}">CAD</span>) <span class="required-indicator-${formNumber}"></span>`;
        }

        const subtotalInput = document.getElementById(`subtotal_amount_${formNumber}`);
        const currentSubtotal = parseFloat(subtotalInput ? subtotalInput.value : 0) || 0;
        updateHstRequirement(formNumber, currentSubtotal);

        if (cadBreakdown) cadBreakdown.style.display = 'block';
        if (usdBreakdown) usdBreakdown.style.display = 'none';

        if (totalInput) totalInput.setAttribute('readonly', '');
        if (totalLabel) totalLabel.textContent = 'Total Reimbursement Amount';
        if (totalHelp) totalHelp.textContent = 'Automatically calculated (Subtotal - Discount + Tax + Shipping)';
        calculateSubtotal(formNumber);
    }

    if (selectedCurrency === 'USD') {
        proofOfPaymentSection.style.display = 'block';
        const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
        if (proofOfPaymentInput) {
            proofOfPaymentInput.required = true;
        }
    } else {
        proofOfPaymentSection.style.display = 'none';
        const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
        if (proofOfPaymentInput) {
            proofOfPaymentInput.required = false;
            proofOfPaymentInput.value = '';
            const filenameSpan = document.getElementById(`payment-filename-${formNumber}`);
            if (filenameSpan) {
                filenameSpan.textContent = 'No file chosen';
            }
        }
    }
}

function updateFileName(input, spanId) {
    const filenameSpan = document.getElementById(spanId);
    const dropArea = input.closest('[data-role="file-drop-area"]');
    const dropTextSpan = dropArea ? dropArea.querySelector('[data-role="file-upload-text"]') : null;

    if (input.files && input.files[0]) {
        const name = input.files[0].name;
        filenameSpan.textContent = name;
        if (dropTextSpan) dropTextSpan.textContent = name;
    } else {
        filenameSpan.textContent = 'No file chosen';
        if (dropTextSpan) dropTextSpan.innerHTML = '<b>Choose a file</b> or drag it here';
    }
}

function validateSubmission() {
    let hasValidForm = false;

    for (let formNumber = 1; formNumber <= 10; formNumber++) {
        const vendorName = document.getElementById(`vendor_name_${formNumber}`);
        const invoiceFile = document.getElementById(`invoice_file_${formNumber}`);
        const currencySelect = document.getElementById(`currency_${formNumber}`);
        const proofOfPaymentFile = document.getElementById(`proof_of_payment_${formNumber}`);

        if (!vendorName || !vendorName.value.trim()) {
            continue;
        }

        if (!invoiceFile || !invoiceFile.files || invoiceFile.files.length === 0) {
            alert('Please upload an invoice file to Invoice #' + formNumber + ' before submitting.');
            return false;
        }

        if (currencySelect && currencySelect.value === 'USD') {
            if (!proofOfPaymentFile || !proofOfPaymentFile.files || proofOfPaymentFile.files.length === 0) {
                alert('Please upload a proof of payment file to Invoice #' + formNumber + ' before submitting.');
                return false;
            }
        }

        let hasValidItem = false;
        const itemsContainer = document.getElementById(`items-container-${formNumber}`);
        if (itemsContainer) {
            const itemRows = itemsContainer.querySelectorAll('.item-row');
            const completedItemNumbers = [];
            let hasPartialItemRow = false;

            for (let row of itemRows) {
                const nameInput = row.querySelector('input[name*="_name_"]');
                const usageInput = row.querySelector('input[name*="_usage_"]');
                const quantityInput = row.querySelector('input[name*="_quantity_"]');
                const priceInput = row.querySelector('input[name*="_price_"]');

                const itemName = nameInput ? nameInput.value.trim() : '';
                const itemUsage = usageInput ? usageInput.value.trim() : '';
                const itemQuantity = quantityInput ? parseFloat(quantityInput.value) : 0;
                const itemPrice = priceInput ? parseFloat(priceInput.value) : 0;

                const hasAnyValue =
                    Boolean(itemName) ||
                    Boolean(itemUsage) ||
                    Boolean(quantityInput && quantityInput.value) ||
                    Boolean(priceInput && priceInput.value);

                const isComplete =
                    Boolean(itemName) &&
                    Boolean(itemUsage) &&
                    itemQuantity > 0 &&
                    itemPrice > 0;

                if (hasAnyValue && !isComplete) {
                    hasPartialItemRow = true;
                }

                if (isComplete && nameInput) {
                    const match = nameInput.name.match(new RegExp(`^item_name_${formNumber}_(\\d+)$`));
                    if (match) {
                        completedItemNumbers.push(parseInt(match[1], 10));
                    }
                }
            }

            if (hasPartialItemRow) {
                alert(
                    `Invoice #${formNumber} has an incomplete item row. Please fully complete each item (name, usage, quantity, and cost) or clear the row before submitting.`
                );
                return false;
            }

            if (completedItemNumbers.length > 0) {
                const sortedUnique = [...new Set(completedItemNumbers)].sort((a, b) => a - b);
                const hasGap =
                    sortedUnique[0] !== 1 ||
                    sortedUnique.some((num, index) => index > 0 && num !== sortedUnique[index - 1] + 1);

                if (hasGap) {
                    alert(
                        `Invoice #${formNumber} has skipped item rows. Please ensure items are filled contiguously starting from Item 1.`
                    );
                    return false;
                }
                hasValidItem = true;
            }
        }

        if (hasValidItem) {
            hasValidForm = true;
        }
    }

    if (!hasValidForm) {
        alert('Please complete at least one invoice form before submitting.\n\nTo complete a form, you need:\n• Vendor/Store Name\n• Invoice file uploaded\n• At least one item with name, usage, quantity, and price\n• Proof of payment (for USD purchases only)');
        return false;
    }

    let totalCanadianAmount = 0;
    for (let formNumber = 1; formNumber <= 10; formNumber++) {
        const vendorName = document.getElementById(`vendor_name_${formNumber}`);
        if (!vendorName || !vendorName.value.trim()) {
            continue;
        }
        const totalField = document.getElementById(`total_cad_amount_${formNumber}`);
        if (totalField && totalField.value) {
            totalCanadianAmount += parseFloat(totalField.value) || 0;
        }
    }
    if (totalCanadianAmount < 100) {
        alert(`Total Canadian amount must be greater than $100.00 CAD.\nCurrent total: $${totalCanadianAmount.toFixed(8)} CAD`);
        return false;
    }

    return true;
}

function clearForm(formNumber) {
    if (!confirm(`Are you sure you want to clear all data in Purchase Request #${formNumber}? This action cannot be undone.`)) {
        return;
    }

    const vendorNameInput = document.getElementById(`vendor_name_${formNumber}`);
    if (vendorNameInput) vendorNameInput.value = '';

    const currencySelect = document.getElementById(`currency_${formNumber}`);
    if (currencySelect) {
        currencySelect.value = 'CAD';
        updateCurrencyLabels(formNumber);
    }

    const invoiceFileInput = document.getElementById(`invoice_file_${formNumber}`);
    const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
    const invoiceFilenameSpan = document.getElementById(`invoice-filename-${formNumber}`);
    const paymentFilenameSpan = document.getElementById(`payment-filename-${formNumber}`);

    if (invoiceFileInput) {
        invoiceFileInput.value = '';
        invoiceFileInput.files = null;
    }
    if (proofOfPaymentInput) {
        proofOfPaymentInput.value = '';
        proofOfPaymentInput.files = null;
    }
    if (invoiceFilenameSpan) invoiceFilenameSpan.textContent = 'No file chosen';
    if (paymentFilenameSpan) paymentFilenameSpan.textContent = 'No file chosen';

    const itemsContainer = document.getElementById(`items-container-${formNumber}`);
    if (itemsContainer) {
        const itemRows = itemsContainer.querySelectorAll('.item-row');
        for (let i = 1; i < itemRows.length; i++) {
            itemRows[i].remove();
        }

        const firstRow = itemRows[0];
        if (firstRow) {
            const inputs = firstRow.querySelectorAll('input');
            inputs.forEach(input => {
                if (input.name.includes('_quantity_')) {
                    input.value = '1';
                } else {
                    input.value = '';
                }
            });
        }

        itemCounts[formNumber] = 1;
        updateRemoveButtons(formNumber);
    }

    const financialFields = [
        `subtotal_amount_${formNumber}`,
        `discount_amount_${formNumber}`,
        `hst_gst_amount_${formNumber}`,
        `shipping_amount_${formNumber}`,
        `us_subtotal_${formNumber}`,
        `us_additional_fees_${formNumber}`,
        `total_cad_amount_${formNumber}`
    ];

    financialFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) field.value = '';
    });

    const hstGstInput = document.getElementById(`hst_gst_amount_${formNumber}`);
    const requiredIndicator = document.querySelector(`.required-indicator-${formNumber}`);
    if (hstGstInput) hstGstInput.removeAttribute('required');
    if (requiredIndicator) requiredIndicator.textContent = '';

    console.log(`Form ${formNumber} has been cleared successfully.`);
}

function handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add('border-indigo-400', 'bg-indigo-500/10');
}

function handleDragLeave(event) {
    event.currentTarget.classList.remove('border-indigo-400', 'bg-indigo-500/10');
}

function handleFileDrop(event, inputId, spanId) {
    event.preventDefault();
    event.currentTarget.classList.remove('border-indigo-400', 'bg-indigo-500/10');

    const fileInput = document.getElementById(inputId);
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        updateFileName(fileInput, spanId);
    }
}

function initializeStaticHandlers() {
    document.querySelectorAll('[data-action="toggle-form"]').forEach(header => {
        header.addEventListener('click', () => toggleForm(Number(header.dataset.form)));
    });

    document.querySelectorAll('[data-action="clear-form"]').forEach(btn => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            clearForm(Number(btn.dataset.form));
        });
    });

    document.querySelectorAll('[data-action="currency-select"]').forEach(select => {
        select.addEventListener('change', () => updateCurrencyLabels(Number(select.dataset.form)));
    });

    document.querySelectorAll('[data-action="add-item"]').forEach(btn => {
        btn.addEventListener('click', () => addItem(Number(btn.dataset.form)));
    });

    document.querySelectorAll('[data-action="remove-item"]').forEach(btn => {
        btn.addEventListener('click', () => removeItem(btn, Number(btn.dataset.form)));
    });

    document.querySelectorAll('[data-action="calc-item"]').forEach(input => {
        input.addEventListener('input', () => {
            calculateItemTotal(Number(input.dataset.form), Number(input.dataset.item));
        });
    });

    document.querySelectorAll('[data-action="recalc-total"]').forEach(input => {
        input.addEventListener('input', () => calculateFinalTotal(Number(input.dataset.form)));
    });

    document.querySelectorAll('[data-role="file-upload-text"]').forEach(trigger => {
        trigger.addEventListener('click', () => {
            const input = document.getElementById(trigger.dataset.inputId);
            if (input) input.click();
        });
    });

    document.querySelectorAll('[data-role="file-drop-area"]').forEach(area => {
        area.addEventListener('dragover', handleDragOver);
        area.addEventListener('dragleave', handleDragLeave);
        area.addEventListener('drop', (event) => {
            handleFileDrop(event, area.dataset.inputId, area.dataset.filenameId);
        });
    });

    document.querySelectorAll('input[type="file"][data-filename-id]').forEach(input => {
        input.addEventListener('change', () => updateFileName(input, input.dataset.filenameId));
    });
}

document.addEventListener('DOMContentLoaded', function () {
    for (let i = 1; i <= 10; i++) {
        const content = document.getElementById(`form-${i}`);
        content.style.display = 'none';

        updateCurrencyLabels(i);

        const proofOfPaymentWrapper = document.querySelector(`.proof-of-payment-section-${i}`);
        if (proofOfPaymentWrapper) {
            const currencySelect = document.getElementById(`currency_${i}`);
            if (currencySelect && currencySelect.value === 'USD') {
                proofOfPaymentWrapper.style.display = 'block';
            } else {
                proofOfPaymentWrapper.style.display = 'none';
            }
        }
    }
    initializeStaticHandlers();

    const form = document.querySelector('form[action="/submit-all-requests"]');
    const submitBtn = document.getElementById("submit-all-btn");

    form.addEventListener("submit", (e) => {
        if (!profileIsComplete) {
            e.preventDefault();
            return;
        }

        if (isSubmitting) {
            e.preventDefault();
            return;
        }

        if (!validateSubmission()) {
            e.preventDefault();
            return;
        }

        isSubmitting = true;
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting… (This may take a few minutes)";

        // Safety net: if submission hasn't navigated away after 45s, re-enable
        // so the user isn't permanently locked out on an unexpected failure.
        setTimeout(() => {
            if (isSubmitting) {
                isSubmitting = false;
                submitBtn.disabled = false;
                submitBtn.textContent = "Submit All Purchase Requests";
            }
        }, 45000);
    });
});
