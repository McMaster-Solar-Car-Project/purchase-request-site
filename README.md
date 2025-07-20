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
```bash
# Install uv (if not already installed)
brew install uv

# Install system dependencies (macOS)
brew install poppler

# Install project dependencies
uv sync

# Install git hooks
lefthook install
```

### 2. Environment Variables

Reach out to Raj for environment variables.

### 3. Run the Application
```bash
# From project root
uv run run.py
```

Visit `http://localhost:8000` or `http://0.0.0.0:8000/` to access the application.

## Requirements

- Python 3.11+
- Google Service Account with access to Google Sheets and Google Drive APIs
- Excel template files (included in `excel_templates/`)