const DATABASE = "purchase-request-drafts";
const VERSION = 1;
const STORAGE_TIMEOUT_MS = 15000;
let connection;

export class DraftConflict extends Error {}
export class DraftIncompatible extends Error {}

export function newDraftId() {
    // getRandomValues also works on deployments without HTTPS.
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function openDatabase() {
    if (connection) return connection;
    connection = new Promise((resolve, reject) => {
        const request = indexedDB.open(DATABASE, VERSION);
        let blocked = false;
        const timeout = setTimeout(() => {
            blocked = true;
            reject(new Error("Draft storage did not respond"));
        }, STORAGE_TIMEOUT_MS);
        request.onupgradeneeded = () => {
            if (blocked) { request.transaction.abort(); return; }
            const db = request.result;
            db.createObjectStore("drafts", { keyPath: "ownerId" });
            const files = db.createObjectStore("attachments", { keyPath: ["ownerId", "draftId", "name"] });
            files.createIndex("draft", ["ownerId", "draftId"]);
        };
        request.onerror = () => {
            clearTimeout(timeout);
            reject(request.error);
        };
        request.onblocked = () => {
            clearTimeout(timeout);
            blocked = true;
            reject(new Error("Close other tabs to enable autosave"));
        };
        request.onsuccess = () => {
            clearTimeout(timeout);
            const db = request.result;
            if (blocked) { db.close(); return; }
            db.onversionchange = () => {
                db.close();
                connection = undefined;
            };
            resolve(db);
        };
    }).catch(error => {
        connection = undefined;
        throw error;
    });
    return connection;
}

async function transact(mode, work) {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(["drafts", "attachments"], mode);
        let result;
        let failure;
        const timeout = setTimeout(() => {
            failure = new Error("Draft storage did not respond");
            // Abort queued writes before allowing manual entry. A late result
            // must never restore old fields over what the user has just typed.
            try { tx.abort(); } catch { /* The transaction already finished. */ }
            reject(failure);
        }, STORAGE_TIMEOUT_MS);
        tx.oncomplete = () => { clearTimeout(timeout); resolve(result); };
        tx.onabort = () => {
            clearTimeout(timeout);
            reject(failure || tx.error || new Error("Draft save interrupted"));
        };
        const fail = error => {
            failure = error;
            tx.abort();
        };
        try {
            work(tx, value => { result = value; }, fail);
        } catch (error) {
            fail(error);
        }
    });
}

function assertCompatible(draft) {
    if (draft && (draft.schemaVersion !== VERSION || !Array.isArray(draft.forms) ||
        typeof draft.ownerId !== "string" || typeof draft.draftId !== "string" ||
        !Number.isSafeInteger(draft.revision) || draft.revision < 0 ||
        !["active", "submitting", "cleared"].includes(draft.state))) {
        throw new DraftIncompatible("This saved draft cannot be opened by this version of the site");
    }
}

function assertCurrent(current, expected) {
    assertCompatible(current);
    if (!current || current.draftId !== expected.draftId || current.revision !== expected.revision || current.state !== "active") {
        throw new DraftConflict("This draft changed in another tab. Reload to continue.");
    }
}

function emptyDraft(ownerId) {
    return { ownerId, draftId: newDraftId(), schemaVersion: VERSION, revision: 0, updatedAt: null, state: "active", forms: [] };
}

export function loadDraft(ownerId) {
    return transact("readwrite", (tx, done, fail) => {
        const drafts = tx.objectStore("drafts");
        drafts.get(ownerId).onsuccess = event => {
            try {
                let draft = event.target.result;
                assertCompatible(draft);
                if (!draft || draft.state === "cleared") {
                    draft = emptyDraft(ownerId);
                    drafts.put(draft);
                }
                const query = IDBKeyRange.only([ownerId, draft.draftId]);
                tx.objectStore("attachments").index("draft").getAll(query).onsuccess = filesEvent => {
                    done({ draft, files: new Map(filesEvent.target.result.map(record => [record.name, record.file])) });
                };
            } catch (error) { fail(error); }
        };
    });
}

export function readDraft(ownerId) {
    return transact("readonly", (tx, done) => {
        tx.objectStore("drafts").get(ownerId).onsuccess = event => done(event.target.result);
    });
}

export function saveDraft(expected, forms, fileChanges, state = "active") {
    return transact("readwrite", (tx, done, fail) => {
        const drafts = tx.objectStore("drafts");
        drafts.get(expected.ownerId).onsuccess = event => {
            try {
                assertCurrent(event.target.result, expected);
                const draft = { ...expected, forms, state, revision: expected.revision + 1, updatedAt: Date.now() };
                drafts.put(draft);
                const files = tx.objectStore("attachments");
                for (const [name, file] of fileChanges) {
                    if (file) files.put({ ownerId: draft.ownerId, draftId: draft.draftId, name, file });
                    else files.delete([draft.ownerId, draft.draftId, name]);
                }
                done(draft);
            } catch (error) { fail(error); }
        };
    });
}

// A tombstone keeps queued writes in older tabs from recreating deleted data.
export function clearDraft(ownerId, draftId, expectedRevision = null) {
    return transact("readwrite", (tx, done, fail) => {
        const drafts = tx.objectStore("drafts");
        drafts.get(ownerId).onsuccess = event => {
            try {
                const current = event.target.result;
                assertCompatible(current);
                if (!current || current.draftId !== draftId || current.state === "cleared") {
                    if (expectedRevision !== null) throw new DraftConflict("This draft changed in another tab. Reload to continue.");
                    done(false);
                    return;
                }
                if (expectedRevision !== null && current.revision !== expectedRevision) {
                    throw new DraftConflict("This draft changed in another tab. Reload to continue.");
                }
                drafts.put({ ...current, revision: current.revision + 1, state: "cleared", forms: [], updatedAt: Date.now() });
                const range = IDBKeyRange.only([ownerId, draftId]);
                tx.objectStore("attachments").index("draft").openCursor(range).onsuccess = cursorEvent => {
                    const cursor = cursorEvent.target.result;
                    if (cursor) { cursor.delete(); cursor.continue(); }
                };
                done(true);
            } catch (error) { fail(error); }
        };
    });
}

export function resumeDraft(expected) {
    return transact("readwrite", (tx, done, fail) => {
        const drafts = tx.objectStore("drafts");
        drafts.get(expected.ownerId).onsuccess = event => {
            const current = event.target.result;
            if (!current || current.draftId !== expected.draftId || current.revision !== expected.revision) {
                fail(new DraftConflict("This draft changed in another tab. Reload to continue."));
                return;
            }
            const next = { ...current, state: "active", revision: current.revision + 1 };
            drafts.put(next);
            done(next);
        };
    });
}

export async function getSubmissionStatus(ownerId, draftId) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const unavailable = "Could not check submission status. Your draft has been kept. Reload to try again.";
    let response;
    let result;
    try {
        response = await fetch(`/draft-submissions/${encodeURIComponent(draftId)}`, {
            cache: "no-store", headers: { Accept: "application/json" }, signal: controller.signal,
        });
        if (response.ok) result = await response.json();
    } catch {
        throw new Error(unavailable);
    } finally {
        clearTimeout(timeout);
    }
    if (response.status === 401) throw new Error("Please log in again to check your saved draft.");
    if (!response.ok || !result) throw new Error(unavailable);
    if (String(result.user_id) !== ownerId) throw new Error("The signed-in account changed. Reload before continuing.");
    if (!["not_submitted", "processing", "succeeded", "rejected", "needs_review"].includes(result.status)) throw new Error("Unknown submission status. Your draft has been kept.");
    return result;
}

export function notifyDraftChange(channel, draft) {
    channel?.postMessage({ ownerId: draft.ownerId, draftId: draft.draftId, revision: draft.revision });
}
