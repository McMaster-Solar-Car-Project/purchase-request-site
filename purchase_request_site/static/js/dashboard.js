// Track item counts for each form
const itemCounts = {};
const maxItems = 15;

// Initialize item counts
for (let i = 1; i <= 10; i++) {
    itemCounts[i] = 1;
}

function toggleForm(formNumber) {
    const content = document.getElementById(`form-${formNumber}`);
    const toggle = content.previousElementSibling.querySelector('.form-toggle');
    
    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        toggle.textContent = '▲';
    } else {
        content.style.display = 'none';
        toggle.textContent = '▼';
    }
}

function addItem(formNumber) {
    if (itemCounts[formNumber] >= maxItems) {
        alert(`Maximum of ${maxItems} items allowed per form.`);
        return;
    }

    itemCounts[formNumber]++;
    const container = document.getElementById(`items-container-${formNumber}`);
    const newRow = document.createElement('div');
    newRow.className = 'item-row';
    newRow.innerHTML = `
        <div class="item-input-group">
            <label>Item Name</label>
            <input type="text" name="item_name_${formNumber}_${itemCounts[formNumber]}" placeholder="Enter item name">
        </div>
        <div class="item-input-group">
            <label>Usage/Purpose</label>
            <input type="text" name="item_usage_${formNumber}_${itemCounts[formNumber]}" placeholder="What is this item for?">
        </div>
        <div class="item-input-group">
            <label>Quantity</label>
            <input type="number" name="item_quantity_${formNumber}_${itemCounts[formNumber]}" min="1" value="1" oninput="calculateItemTotal(${formNumber}, ${itemCounts[formNumber]})">
        </div>
        <div class="item-input-group">
            <label>Unit Price</label>
            <input type="number" name="item_price_${formNumber}_${itemCounts[formNumber]}" min="0" step="0.01" placeholder="0.00" oninput="calculateItemTotal(${formNumber}, ${itemCounts[formNumber]})">
        </div>
        <div class="item-input-group">
            <label>Total</label>
            <input type="number" name="item_total_${formNumber}_${itemCounts[formNumber]}" readonly placeholder="0.00" class="total-field">
        </div>
        <div class="item-actions">
            <button type="button" class="btn-remove" onclick="removeItem(this, ${formNumber})">Remove</button>
        </div>
    `;
    container.appendChild(newRow);
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
        
        totalInput.value = total.toFixed(2);
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
    
    // Always update the subtotal field (even if hidden for USD)
    const subtotalField = document.getElementById(`subtotal_amount_${formNumber}`);
    if (subtotalField) {
        subtotalField.value = subtotal.toFixed(2);
    }
    
    updateHstRequirement(formNumber, subtotal);
    calculateFinalTotal(formNumber);
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
    document.getElementById(`total_amount_${formNumber}`).value = Math.max(0, total).toFixed(2);
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
    
    currencyLabels.forEach(label => {
        label.textContent = selectedCurrency;
    });
    
    // Update tax labels and requirements based on currency
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
        
        // Show USD breakdown, hide CAD breakdown
        if (cadBreakdown) cadBreakdown.style.display = 'none';
        if (usdBreakdown) usdBreakdown.style.display = 'block';
        
    } else {
        taxLabels.forEach(label => {
            label.textContent = 'HST/GST';
        });
        if (hstGstLabel) {
            hstGstLabel.innerHTML = `<span class="tax-label-${formNumber}">HST/GST</span> (<span class="currency-label-${formNumber}">CAD</span>) <span class="required-indicator-${formNumber}"></span>`;
        }
        
        // Update HST requirement based on current subtotal
        const subtotalInput = document.getElementById(`subtotal_amount_${formNumber}`);
        const currentSubtotal = parseFloat(subtotalInput ? subtotalInput.value : 0) || 0;
        updateHstRequirement(formNumber, currentSubtotal);
        
        // Show CAD breakdown, hide USD breakdown
        if (cadBreakdown) cadBreakdown.style.display = 'block';
        if (usdBreakdown) usdBreakdown.style.display = 'none';
    }
    
    // Show/hide proof of payment section based on currency
    if (selectedCurrency === 'USD') {
        proofOfPaymentSection.style.display = 'block';
        // Make proof of payment required for USD
        const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
        if (proofOfPaymentInput) {
            proofOfPaymentInput.required = true;
        }
    } else {
        proofOfPaymentSection.style.display = 'none';
        // Remove required attribute for non-USD currencies
        const proofOfPaymentInput = document.getElementById(`proof_of_payment_${formNumber}`);
        if (proofOfPaymentInput) {
            proofOfPaymentInput.required = false;
            proofOfPaymentInput.value = ''; // Clear the field
            // Reset filename display
            const filenameSpan = document.getElementById(`payment-filename-${formNumber}`);
            if (filenameSpan) {
                filenameSpan.textContent = 'No file chosen';
            }
        }
    }
}

function updateFileName(input, spanId) {
    const filenameSpan = document.getElementById(spanId);
    if (input.files && input.files[0]) {
        filenameSpan.textContent = input.files[0].name;
    } else {
        filenameSpan.textContent = 'No file chosen';
    }
}

function validateSubmission() {
    let hasValidForm = false;
    const errors = [];

    // Check each form for completeness
    for (let formNumber = 1; formNumber <= 10; formNumber++) {
        const vendorName = document.getElementById(`vendor_name_${formNumber}`);
        const invoiceFile = document.getElementById(`invoice_file_${formNumber}`);
        const currencySelect = document.getElementById(`currency_${formNumber}`);
        const proofOfPaymentFile = document.getElementById(`proof_of_payment_${formNumber}`);

        // Skip if vendor name is not filled
        if (!vendorName || !vendorName.value.trim()) {
            continue;
        }

        // Check if invoice file is uploaded
        if (!invoiceFile || !invoiceFile.files || invoiceFile.files.length === 0) {
            alert('Please upload an invoice file to Invoice #' + formNumber + ' before submitting.');
            return false;
        }

        // For USD currency, check if proof of payment is uploaded
        if (currencySelect && currencySelect.value === 'USD') {
            if (!proofOfPaymentFile || !proofOfPaymentFile.files || proofOfPaymentFile.files.length === 0) {
                alert('Please upload a proof of payment file to Invoice #' + formNumber + ' before submitting.');
                return false;
            }
        }

        // Check if at least one item is properly filled
        let hasValidItem = false;
        const itemsContainer = document.getElementById(`items-container-${formNumber}`);
        if (itemsContainer) {
            const itemRows = itemsContainer.querySelectorAll('.item-row');
            
            for (let row of itemRows) {
                const nameInput = row.querySelector('input[name*="_name_"]');
                const usageInput = row.querySelector('input[name*="_usage_"]');
                const quantityInput = row.querySelector('input[name*="_quantity_"]');
                const priceInput = row.querySelector('input[name*="_price_"]');

                if (nameInput && nameInput.value.trim() && 
                    usageInput && usageInput.value.trim() && 
                    quantityInput && quantityInput.value && parseFloat(quantityInput.value) > 0 &&
                    priceInput && priceInput.value && parseFloat(priceInput.value) > 0) {
                    hasValidItem = true;
                    break;
                }
            }
        }

        // If this form has vendor, invoice, and at least one valid item, it's complete
        if (hasValidItem) {
            hasValidForm = true;
        }
    }

    if (!hasValidForm) {
        alert('Please complete at least one invoice form before submitting.\n\nTo complete a form, you need:\n• Vendor/Store Name\n• Invoice file uploaded\n• At least one item with name, usage, quantity, and price\n• Proof of payment (for USD purchases only)');
        return false;
    }

    return true;
}

function clearForm(formNumber) {
    if (!confirm(`Are you sure you want to clear all data in Purchase Request #${formNumber}? This action cannot be undone.`)) {
        return;
    }

    // Clear basic form fields
    const vendorNameInput = document.getElementById(`vendor_name_${formNumber}`);
    if (vendorNameInput) vendorNameInput.value = '';

    // Reset currency to CAD (default)
    const currencySelect = document.getElementById(`currency_${formNumber}`);
    if (currencySelect) {
        currencySelect.value = 'CAD';
        updateCurrencyLabels(formNumber); // This will update visibility and labels
    }

    // Clear file inputs and reset filename displays
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

    // Clear all items except the first one
    const itemsContainer = document.getElementById(`items-container-${formNumber}`);
    if (itemsContainer) {
        // Remove all item rows except the first one
        const itemRows = itemsContainer.querySelectorAll('.item-row');
        for (let i = 1; i < itemRows.length; i++) {
            itemRows[i].remove();
        }

        // Clear the first item row
        const firstRow = itemRows[0];
        if (firstRow) {
            const inputs = firstRow.querySelectorAll('input');
            inputs.forEach(input => {
                if (input.name.includes('_quantity_')) {
                    input.value = '1'; // Reset quantity to 1
                } else {
                    input.value = '';
                }
            });
        }

        // Reset item count for this form
        itemCounts[formNumber] = 1;
        updateRemoveButtons(formNumber);
    }

    // Clear financial breakdown fields for CAD
    const cadFinancialFields = [
        `subtotal_amount_${formNumber}`,
        `discount_amount_${formNumber}`,
        `hst_gst_amount_${formNumber}`,
        `shipping_amount_${formNumber}`,
        `total_amount_${formNumber}`
    ];

    cadFinancialFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) field.value = '';
    });

    // Clear financial breakdown fields for USD
    const usdFinancialFields = [
        `us_total_${formNumber}`,
        `usd_taxes_${formNumber}`,
        `canadian_amount_${formNumber}`
    ];

    usdFinancialFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) field.value = '';
    });

    // Remove any required attributes and indicators that might have been set
    const hstGstInput = document.getElementById(`hst_gst_amount_${formNumber}`);
    const requiredIndicator = document.querySelector(`.required-indicator-${formNumber}`);
    if (hstGstInput) hstGstInput.removeAttribute('required');
    if (requiredIndicator) requiredIndicator.textContent = '';

    console.log(`Form ${formNumber} has been cleared successfully.`);
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', function() {
    for (let i = 1; i <= 10; i++) {
        const content = document.getElementById(`form-${i}`);
        content.style.display = 'none';

        // Initialize currency labels
        updateCurrencyLabels(i);

        // Initialize proof of payment section visibility
        const proofOfPaymentSection = document.getElementById(`proof_of_payment_${i}`);
        if (proofOfPaymentSection) {
            const currencySelect = document.getElementById(`currency_${i}`);
            if (currencySelect && currencySelect.value === 'USD') {
                proofOfPaymentSection.style.display = 'block';
            } else {
                proofOfPaymentSection.style.display = 'none';
            }
        }
    }
}); 