import { captureDashboardDraft, restoreDashboardDraft } from "./form-ui.js";
import {
    DraftConflict, clearDraft, getSubmissionStatus, loadDraft, newDraftId,
    notifyDraftChange, readDraft, resumeDraft, saveDraft,
} from "./draft-storage.js";

export class DashboardAutosave {
    constructor(form, maxForms) {
        this.form = form;
        this.maxForms = maxForms;
        this.ownerId = form.dataset.draftOwner;
        this.fields = document.getElementById("draft-fields");
        this.status = document.getElementById("draft-status");
        this.discard = document.getElementById("discard-draft");
        this.refresh = document.getElementById("draft-reload");
        this.draft = null;
        this.savedFiles = new Map();
        this.queue = Promise.resolve();
        this.dirty = false;
        this.suspended = true;
        this.storageAvailable = true;
        this.canDiscard = false;
        this.channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("reimbursement-drafts") : null;
        this.channel?.addEventListener("message", event => {
            if (event.data.ownerId === this.ownerId) this.checkOtherTab();
        });
    }

    show(message, problem = false) {
        this.status.textContent = message;
        this.status.classList.toggle("notice--warning", problem);
    }

    lock(locked) {
        // Inert blocks mouse, keyboard and drop controls without excluding form
        // values from the normal multipart POST when submission starts.
        this.fields.disabled = false;
        this.fields.inert = locked;
        document.getElementById("submit-all-btn").disabled = locked;
        this.canDiscard = !locked && this.storageAvailable;
        this.discard.disabled = !this.canDiscard;
    }

    cancelTimers() {
        clearTimeout(this.debounce);
        clearTimeout(this.maximumWait);
        this.debounce = this.maximumWait = null;
    }

    conflict(message = "This draft changed in another tab. Reload to continue.") {
        this.cancelTimers();
        this.suspended = true;
        this.lock(true);
        this.refresh.hidden = false;
        this.show(message, true);
    }

    storageFailed(error) {
        this.storageAvailable = false;
        this.canDiscard = false;
        this.discard.disabled = true;
        this.cancelTimers();
        this.show("Autosave is unavailable. Keep this page open until you submit; recent changes may not be saved on this device.", true);
        console.warn("Draft storage unavailable:", error.name);
    }

    async initialize() {
        this.lock(true);
        this.show("Loading saved draft…");
        let saved;
        try {
            saved = await loadDraft(this.ownerId);
            this.draft = saved.draft;
        } catch (error) {
            this.storageFailed(error);
            this.suspended = false;
            this.lock(false);
            this.bindEvents();
            return;
        }
        let status;
        try {
            status = await getSubmissionStatus(this.ownerId, this.draft.draftId);
        } catch (error) {
            this.conflict(error.message);
            this.bindEvents();
            return;
        }
        try {
            if (status.status === "succeeded") {
                await clearDraft(this.ownerId, this.draft.draftId);
                notifyDraftChange(this.channel, this.draft);
                saved = await loadDraft(this.ownerId);
                this.draft = saved.draft;
            }
            restoreDashboardDraft(this.draft.forms, saved.files, this.maxForms);
            if (status.status === "processing" || status.status === "needs_review") {
                this.blockSubmission(status);
                this.bindEvents();
                return;
            }
            if (this.draft.state === "submitting") this.draft = await resumeDraft(this.draft);
            this.savedFiles = captureDashboardDraft(this.maxForms).files;
            this.show(this.draft.updatedAt ? "Draft restored. Saved on this device." : "Your changes and receipts will be saved on this device.");
        } catch (error) {
            if (error instanceof DraftConflict) {
                this.conflict();
                this.bindEvents();
                return;
            }
            // Preserve an incompatible record and let the user enter a separate
            // manual batch. It must not clear the preserved record on success.
            this.draft = null;
            restoreDashboardDraft([], new Map(), this.maxForms);
            this.storageFailed(error);
        }
        this.suspended = false;
        this.lock(false);
        this.bindEvents();
    }

    blockSubmission(status) {
        if (status.status === "processing" && !status.stale) {
            this.conflict("This batch is still being processed. Your draft has been kept. Reload to check its status.");
        } else {
            this.conflict("This submission needs attention. Your draft has been kept. Check with finance before submitting again.");
            this.canDiscard = this.storageAvailable;
            this.discard.disabled = !this.canDiscard;
        }
    }

    schedule(immediate = false) {
        if (this.suspended || !this.storageAvailable) return;
        this.dirty = true;
        this.show("Saving…");
        clearTimeout(this.debounce);
        if (immediate) {
            this.flush().catch(error => this.handleSaveError(error));
        } else {
            this.debounce = setTimeout(() => this.flush().catch(error => this.handleSaveError(error)), 500);
            if (!this.maximumWait) this.maximumWait = setTimeout(() => this.flush().catch(error => this.handleSaveError(error)), 2000);
        }
    }

    handleSaveError(error) {
        if (error instanceof DraftConflict) this.conflict();
        else this.storageFailed(error);
    }

    flush(state = "active", force = false) {
        this.cancelTimers();
        if (!this.storageAvailable || (!this.dirty && !force)) return this.queue;
        const snapshot = captureDashboardDraft(this.maxForms);
        this.dirty = false;
        const write = this.queue.then(async () => {
            if (!this.storageAvailable) return;
            const changes = new Map();
            for (const [name, file] of snapshot.files) {
                if (this.savedFiles.get(name) !== file) changes.set(name, file);
            }
            for (const name of this.savedFiles.keys()) {
                if (!snapshot.files.has(name)) changes.set(name, null);
            }
            this.draft = await saveDraft(this.draft, snapshot.forms, changes, state);
            this.savedFiles = snapshot.files;
            notifyDraftChange(this.channel, this.draft);
            if (!this.dirty && !this.suspended) this.show("Saved on this device.");
        });
        this.queue = write.catch(error => { this.handleSaveError(error); });
        return write;
    }

    async checkOtherTab() {
        if (!this.draft || !this.storageAvailable || this.suspended) return;
        await this.queue;
        try {
            const current = await readDraft(this.ownerId);
            if (!current || current.draftId !== this.draft.draftId || current.revision !== this.draft.revision || current.state !== "active") this.conflict();
        } catch (error) { this.storageFailed(error); }
    }

    async prepareSubmission() {
        if (this.suspended) return null;
        this.suspended = true;
        this.lock(true);
        this.cancelTimers();
        try {
            const draftId = this.draft?.draftId || newDraftId();
            const status = await getSubmissionStatus(this.ownerId, draftId);
            if (status.status === "succeeded") {
                if (this.draft) await clearDraft(this.ownerId, draftId);
                window.location.assign(`/success?submission_id=${encodeURIComponent(draftId)}`);
                return null;
            }
            if (["processing", "needs_review"].includes(status.status)) {
                this.blockSubmission(status);
                return null;
            }
            try {
                await this.flush("submitting", true);
            } catch (error) {
                if (error instanceof DraftConflict) throw error;
                this.storageFailed(error);
            }
            this.show("Submitting. Your draft will clear after your submission is confirmed.");
            return draftId;
        } catch (error) {
            this.conflict(error.message);
            return null;
        }
    }

    bindEvents() {
        this.form.addEventListener("input", event => this.schedule(event.target.type === "file"));
        this.form.addEventListener("change", event => this.schedule(event.target.type === "file" || event.target.tagName === "SELECT"));
        document.addEventListener("draftchange", event => this.schedule(event.detail.immediate));
        this.discard.addEventListener("click", async () => {
            if (!this.canDiscard || !confirm("Discard this draft and its saved receipts? This does not cancel a submission already received by finance.")) return;
            this.suspended = true;
            this.lock(true);
            this.cancelTimers();
            await this.queue;
            try {
                if (this.draft) {
                    await clearDraft(this.ownerId, this.draft.draftId, this.draft.revision);
                    notifyDraftChange(this.channel, this.draft);
                }
                window.location.assign("/dashboard");
            } catch (error) {
                this.conflict(error instanceof DraftConflict ? error.message : "Could not discard the saved draft. Reload to try again.");
            }
        });
        window.addEventListener("pageshow", event => {
            if (event.persisted) {
                this.lock(true);
                this.suspended = true;
                window.location.reload();
            }
        });
        window.addEventListener("focus", () => this.checkOtherTab());
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "hidden" && !this.suspended) this.flush().catch(error => this.handleSaveError(error));
            else if (document.visibilityState === "visible") this.checkOtherTab();
        });
        document.querySelectorAll('a[href="/home"], a[href="/logout"]').forEach(link => {
            link.addEventListener("click", async event => {
                if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || this.suspended) return;
                event.preventDefault();
                this.suspended = true;
                this.lock(true);
                try { await this.flush(); } catch (error) { this.handleSaveError(error); }
                window.location.assign(link.href);
            });
        });
    }
}
