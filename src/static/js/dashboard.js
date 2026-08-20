import { formatMoneyFields, initializeDashboardUi } from "./dashboard/form-ui.js";
import { validateSubmission } from "./dashboard/validation.js";

const profileCompleteField = document.getElementById("profile-is-complete");
const profileIsComplete = profileCompleteField?.value === "true";
const maxItemsField = document.getElementById("max-items-per-form");
const maxItems = Number.parseInt(maxItemsField?.value ?? "50", 10) || 50;
const maxFormsField = document.getElementById("max-forms");
const maxForms = Number.parseInt(maxFormsField?.value ?? "25", 10) || 25;
const minimumTotalField = document.getElementById("minimum-total-cad-cents");
const minimumTotalCents = BigInt(minimumTotalField?.value || "10000");

let isSubmitting = false;

document.addEventListener("DOMContentLoaded", function () {
    initializeDashboardUi({ maxForms, maxItems });

    const form = document.querySelector('form[action="/submit-all-requests"]');
    const submitBtn = document.getElementById("submit-all-btn");

    if (!form || !submitBtn) {
        return;
    }

    form.addEventListener("submit", event => {
        if (!profileIsComplete) {
            event.preventDefault();
            return;
        }

        if (isSubmitting) {
            event.preventDefault();
            return;
        }

        formatMoneyFields();

        if (!validateSubmission(maxForms, minimumTotalCents)) {
            event.preventDefault();
            return;
        }

        isSubmitting = true;
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting… (This may take a few minutes)";

        setTimeout(() => {
            if (isSubmitting) {
                isSubmitting = false;
                submitBtn.disabled = false;
                submitBtn.textContent = "Submit All Purchase Requests";
            }
        }, 45000);
    });
});
