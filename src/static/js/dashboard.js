import { formatMoneyFields, initializeDashboardUi } from "./dashboard/form-ui.js";
import { validateSubmission } from "./dashboard/validation.js";
import { DashboardAutosave } from "./dashboard/autosave.js";

const profileCompleteField = document.getElementById("profile-is-complete");
const profileIsComplete = profileCompleteField?.value === "true";
const maxItemsField = document.getElementById("max-items-per-form");
const maxItems = Number.parseInt(maxItemsField?.value ?? "50", 10) || 50;
const maxFormsField = document.getElementById("max-forms");
const maxForms = Number.parseInt(maxFormsField?.value ?? "25", 10) || 25;
const minimumTotalField = document.getElementById("minimum-total-cad-cents");
const minimumTotalCents = BigInt(minimumTotalField?.value || "10000");

let isSubmitting = false;

document.addEventListener("DOMContentLoaded", async function () {
    initializeDashboardUi({ maxForms, maxItems });

    const form = document.querySelector('form[action="/submit-all-requests"]');
    const submitBtn = document.getElementById("submit-all-btn");

    if (!form || !submitBtn) {
        return;
    }

    const autosave = new DashboardAutosave(form, maxForms);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!profileIsComplete) {
            return;
        }

        if (isSubmitting) {
            return;
        }

        formatMoneyFields();

        if (!validateSubmission(maxForms, minimumTotalCents)) {
            return;
        }

        isSubmitting = true;
        const draftId = await autosave.prepareSubmission();
        if (!draftId) {
            isSubmitting = false;
            return;
        }
        document.getElementById("draft-id").value = draftId;
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting… (This may take a few minutes)";

        HTMLFormElement.prototype.submit.call(form);
    });
    await autosave.initialize();
});
