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
brew install uv poppler gitleaks lefthook

# Install project dependencies
uv sync

# Install git hooks
lefthook install
```

### 2. Environment Variables

Reach out to Raj for environment variables.

#### Optional: Email Error Notifications

To receive email notifications when errors occur, add these optional environment variables to your `.env` file:

```env
# Email notifications for errors (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ERROR_EMAIL_FROM=your_email@gmail.com
ERROR_EMAIL_TO=admin@yourcompany.com,dev@yourcompany.com
```

**Note:** For Gmail, use an App Password instead of your regular password. Multiple recipient emails can be separated by commas.

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
