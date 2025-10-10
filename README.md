# Purchase Request Site

A FastAPI web application for managing purchase requests and expense reports. Users can submit purchase requests with invoices, which automatically generates Excel reports and uploads files to Google Drive.

## Setup

### 1. Install Dependencies

These setup instructions are for macOS and WSL. If you are using Windows, please use WSL and install Brew before running the setup instructions.


```bash
# Install system dependencies
brew install uv gitleaks lefthook ruff

# Clone the repo (you can use https instead of ssh if you prefer)
git clone git@github.com:McMaster-Solar-Car-Project/purchase-request-site.git
cd purchase-request-site

# Create a venv
uv venv

# Activate the venv
source .venv/bin/activate

# Install project dependencies
uv sync

# Install git hooks
lefthook install

# Reach out to Raj for environment variables before running the application.
uv run run.py
```

Alternatively, you can run the application using the Docker build instructions below. For Docker, you will need to access the site at the first port in the port mapping.
```bash
docker build -t purchase-request-site .
docker run -p 8000:80 purchase-request-site

# If you encounter errors with environment variables, you can include them in the docker run command.
docker run -e GOOGLE_CLIENT_ID=... -e DATABASE_URL=... -p 8000:80 purchase-request-site

```

### 4. Contributing to the Project

To contribute to this project, please make a separate branch and make your changes there. After pushing these changes, create a Pull Request on the GitHub repo. For the staging environment to run, you will need write access to the repository. After the build has finished (this may take a few minutes due to caching/propagation), you should be able to access the PR deployment at [https://purchase-request-site-staging-864928778234.northamerica-northeast2.run.app/login](https://purchase-request-site-staging-864928778234.northamerica-northeast2.run.app/login). Only the latest commit to any given pull request will be visible at this URL. **DO NOT MERGE WITHOUT APPROVAL AND AT LEAST ONE REVIEWER**

### 5. Long Term Maintenance

This project relies of a few key API's and Services.

- Google API's
  - Drive API (Access, update, and modify files in Google Drive)
  - Sheets API (Access, update, and modify values in Google Sheets)
  - Place API (Address Autocomplete, not needed but nice to have)
- Google Service Account (Accessing Drive files)
- Gmail Account (Emailing warnings)
- Google Cloud Run (Deploying the Docker image)
- Supabase (Store credentials and backup data)
