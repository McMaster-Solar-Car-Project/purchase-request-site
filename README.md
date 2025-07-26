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

Or with Docker:

```bash
./build.sh
./run-docker.sh
```

### 4. Long Term Maintenance

This project relies of a few key API's and Services.

- Google API's
  - Drive API (Access, update, and modify files in Google Drive)
  - Sheets API (Access, update, and modify values in Google Sheets)
  - Place API (Address Autocomplete, not needed but nice to have)
- Google Service Account (Accessing Drive files)
- Gmail Account (Emailing warnings)
- Google Cloud Run (Building/Storing/Deploying the Docker image)
- Supabase (Store credentials so any container can access them)
