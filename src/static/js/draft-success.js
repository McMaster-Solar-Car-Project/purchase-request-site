import { clearDraft, getSubmissionStatus, notifyDraftChange } from "./dashboard/draft-storage.js";

const receipt = document.getElementById("submitted-draft");
if (receipt) {
    const channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("reimbursement-drafts") : null;
    const ownerId = receipt.dataset.owner;
    const draftId = receipt.dataset.id;
    try {
        const result = await getSubmissionStatus(ownerId, draftId);
        if (result.status === "succeeded") {
            await clearDraft(ownerId, draftId);
            notifyDraftChange(channel, { ownerId, draftId });
            receipt.textContent = "Submitted. Your saved draft and receipts have been cleared from this device.";
        }
    } catch {
        receipt.textContent = "Your submission is confirmed. We could not clear the local draft yet; it will be checked again when you open the dashboard.";
    } finally {
        channel?.close();
    }
}
