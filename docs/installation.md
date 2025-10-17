<!-- Copying CONTRIBUTING for now -->

## Getting Started

### Prerequisites

- **Operating System**: macOS or WSL (Windows users should use WSL)
- **Package Manager**: Homebrew (install via [brew.sh](https://brew.sh/))

### Required Tools

Install the following system dependencies:

```bash
brew install uv gitleaks lefthook ruff git
```

## Development Setup

### 1. Clone the Repository

```bash
# Ideally use SSH, but if you have issues, use HTTPS
git clone git@github.com:McMaster-Solar-Car-Project/purchase-request-site.git
cd purchase-request-site
```

### 2. Environment Setup

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install project dependencies
uv sync

# Install git hooks (required for development)
lefthook install
```

### 3. Environment Variables

Contact Raj for the required environment variables before running the application. 

### 4. Run the Application

```bash
# Only run the application this way if you want to make code changes that get reflected instantly
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Run the Application with Docker

**Important**: Even though you can run the application with uvicorn, it is recommended to use Docker to run the application since this is how it's run in production

```bash
docker-compose --env-file .env up --build
```

The application will be available at `http://localhost:8000` (or the port specified in your configuration).

