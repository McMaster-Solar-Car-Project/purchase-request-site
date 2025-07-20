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

#### Login Authentication

To secure your purchase request site, add these login credentials to your `.env` file:

```env
# Login credentials (required)
LOGIN_EMAIL=admin@yourcompany.com
LOGIN_PASSWORD=your_secure_password

# Session security (recommended)
SESSION_SECRET_KEY=your-very-long-random-secret-key-here
```

**Security Note:** 
- Change the default credentials immediately
- Use a strong password
- Generate a random session secret key (32+ characters)

#### User Profile Storage

The system automatically stores user profiles in a SQLite database (`purchase_request_site/purchase_requests.db`) including:
- Name, email addresses, address, team information
- User passwords (stored as plain text for admin access)
- Digital signatures (stored as binary data)
- Creation and update timestamps

User data is automatically saved when submitting purchase requests and can be viewed at `/profile?user_email=user@domain.com`.

#### Creating Users Programmatically

You can create users in code using the `user_service` module:

```python
# Method 1: Use the create_users.py script
python create_users.py

# Method 2: In your own Python code
import sys
sys.path.append('purchase_request_site')

from database import get_db, init_database
from user_service import create_user_from_cli

# Initialize database
init_database()

# Create a user
db = next(get_db())
user = create_user_from_cli(
    db=db,
    name="John Doe",
    email="john.doe@mcmaster.ca", 
    personal_email="john.doe@gmail.com",
    address="123 Main St, Hamilton, ON",
    team="Engineering",
    signature_path="path/to/signature.png"
)
print(f"User created: {user.name}")
db.close()
```

**Note:** Signature files are mandatory and stored as binary data in SQLite.

### 3. Run the Application

From the project root directory:

```bash
cd purchase_request_site
uv run python main.py
```

The application will start on `http://localhost:8000` with login authentication enabled.

**Note:** The FastAPI app runs from the `purchase_request_site` directory, where the database file `purchase_requests.db` is located.

## Requirements

- Python 3.11+
- Google Service Account with access to Google Sheets and Google Drive APIs
- Excel template files (included in `excel_templates/`)
