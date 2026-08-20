import {
    formatMoneyCents,
    parseMoneyCents,
    todayIsoDate,
} from "./money.js";

export function validateSubmission(maxForms) {
    let hasValidForm = false;
    const today = todayIsoDate();

    for (let formNumber = 1; formNumber <= maxForms; formNumber++) {
        const vendorName = document.getElementById(`vendor_name_${formNumber}`);
        const purchaseDate = document.getElementById(`purchase_date_${formNumber}`);
        const invoiceFile = document.getElementById(`invoice_file_${formNumber}`);
        const currencySelect = document.getElementById(`currency_${formNumber}`);
        const proofOfPaymentFile = document.getElementById(`proof_of_payment_${formNumber}`);

        if (!vendorName || !vendorName.value.trim()) {
            continue;
        }

        if (!purchaseDate || !purchaseDate.value) {
            alert("Please enter a purchase date for Invoice #" + formNumber + " before submitting.");
            return false;
        }

        if (purchaseDate.value > today) {
            alert("Purchase date for Invoice #" + formNumber + " cannot be in the future.");
            return false;
        }

        if (!invoiceFile || !invoiceFile.files || invoiceFile.files.length === 0) {
            alert("Please upload an invoice file to Invoice #" + formNumber + " before submitting.");
            return false;
        }

        if (currencySelect && currencySelect.value === "USD") {
            if (!proofOfPaymentFile || !proofOfPaymentFile.files || proofOfPaymentFile.files.length === 0) {
                alert("Please upload a proof of payment file to Invoice #" + formNumber + " before submitting.");
                return false;
            }
        }

        let hasValidItem = false;
        const itemsContainer = document.getElementById(`items-container-${formNumber}`);
        if (itemsContainer) {
            const itemRows = itemsContainer.querySelectorAll(".item-row");
            const completedItemNumbers = [];
            let hasPartialItemRow = false;

            for (const row of itemRows) {
                const nameInput = row.querySelector('input[name*="_name_"]');
                const usageInput = row.querySelector('input[name*="_usage_"]');
                const quantityInput = row.querySelector('input[name*="_quantity_"]');
                const priceInput = row.querySelector('input[name*="_price_"]');

                const itemName = nameInput ? nameInput.value.trim() : "";
                const itemUsage = usageInput ? usageInput.value.trim() : "";
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
        alert("Please complete at least one invoice form before submitting.\n\nTo complete a form, you need:\n• Vendor/Store Name\n• Purchase Date\n• Invoice file uploaded\n• At least one item with name, usage, quantity, and price\n• Proof of payment (for USD purchases only)");
        return false;
    }

    let totalCanadianCents = 0n;
    for (let formNumber = 1; formNumber <= maxForms; formNumber++) {
        const vendorName = document.getElementById(`vendor_name_${formNumber}`);
        if (!vendorName || !vendorName.value.trim()) {
            continue;
        }
        const totalField = document.getElementById(`total_cad_amount_${formNumber}`);
        if (totalField && totalField.value) {
            totalCanadianCents += parseMoneyCents(totalField.value);
        }
    }
    if (totalCanadianCents < 10000n) {
        alert(`Total Canadian amount must be at least $100.00 CAD.\nCurrent total: $${formatMoneyCents(totalCanadianCents)} CAD`);
        return false;
    }

    return true;
}
