<p align="center">
  <img alt="Purchase Request Site" src="https://www.appliedprecision.ca/wp-content/uploads/2023/06/Png-Logo.png" width="600">
</p>

[Purchase Request Site](https://github.com/McMaster-Solar-Car-Project/purchase-request-site) is a FastAPI web application designed to streamline purchase request and expense report management for the McMaster Solar Car Project to quickly get members their money back.

Development of this application is done by the Operations and Finance teams at McMaster Solar Car, if you want to get involved, you can join us when applications open [here](https://www.mcmastersolarcar.com/join).

## Getting Started

Visit the [CONTRIBUTING.md](./CONTRIBUTING.md) file for more information on how to contribute to the project.

## Reimbursement drafts

The dashboard saves one batch per account in IndexedDB, including receipts and proof-of-payment files. Drafts survive logout and have no automatic expiry. They are available only on the same site, browser, and device; clearing browser data removes them. Profile edits, signatures, and banking details are not included.

Users can discard a draft or submit it. Submission clears the local draft only after report generation, Drive upload, and Sheets logging all succeed. The dashboard checks this outcome again on the next visit, so recovery also works if the submission response was lost. Partial or unresolved submissions retain the draft and ask the user to check with finance before submitting again.

Database initialization creates the `draft_submissions` table automatically. It records account IDs, draft IDs, statuses, and timestamps without storing draft contents or receipts. Keep these records while their accounts exist so old browser drafts can still be checked. If browser storage is unavailable, the dashboard warns the user and allows manual submission without autosave.
