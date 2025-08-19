# Purchase Request Site

A FastAPI web application for managing purchase requests and expense reports. Users can submit purchase requests with invoices, which automatically generates Excel reports and uploads files to Google Drive.

## What it does

- **Purchase Request Forms**: Submit up to 10 invoices per session with vendor details, items, and file uploads
- **Automatic Excel Generation**: Creates purchase request and expense report spreadsheets
- **Google Integration**: Uploads files to Google Drive and logs session data to Google Sheets
- **Multi-Currency Support**: Handles both CAD and USD purchases with exchange rate calculations
- **Digital Signatures**: Processes and crops signature images for reports

## Setup

### 1. Install Dependencies

These setup instructions are for macOS, if you are using windows, download the dependencies by visiting their website and following their instructions

```bash
# Install system dependencies (macOS)
brew install uv gitleaks lefthook

# Create a venv
uv venv

# Activate the venv
source .venv/bin/activate

# Install project dependencies
uv sync

# Install git hooks
lefthook install
```

### 2. Environment Variables

Reach out to Raj for environment variables.


### 3. Run the Application

From the project root directory:

```bash
uv run run.py
```

Docker build instructions coming soon

### 4. Contributing to the Project

To contribute to this project, **please make a separate branch and make your changes there**. After pushing these changes, create a Pull Request on the Github repo, after the build has been finished, you should be able to access the repo with the PR at [https://purchase-request-site-staging-864928778234.northamerica-northeast2.run.app/login](https://purchase-request-site-staging-864928778234.northamerica-northeast2.run.app/login). Only the latest commit to any given pull request will be visible at this url, so keep this in mind.

#### DO NOT MERGE THIS PR IN WITHOUT APPROVAL AND ATLEAST 1 REVIEW

### 5. Long Term Maintenance

This project relies of a few key API's and Services.

- Google API's
  - Drive API (Access, update, and modify files in Google Drive)
  - Sheets API (Access, update, and modify values in Google Sheets)
  - Place API (Address Autocomplete, not needed but nice to have)
- Google Service Account (Accessing Drive files)
- Gmail Account (Emailing warnings)
- Google Cloud Run (Building/Storing/Deploying the Docker image)
- Supabase (Store credentials so any container can access them)
