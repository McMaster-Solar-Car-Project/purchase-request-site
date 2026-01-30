# Technology Stack

## Backend Framework
- **FastAPI** - Modern Python web framework with automatic API documentation
- **Python 3.13** - Required Python version (exact match)
- **Uvicorn** - ASGI server for running the FastAPI application

## Database & Storage
- **PostgreSQL** - Primary database via Supabase
- **SQLAlchemy** - ORM for database operations with resilient error handling
- **Google Sheets API** - Data storage and integration
- **Google Drive API** - File management and storage

## Error Handling & Resilience
- **Graceful database failures** - Application starts even if database is unavailable
- **Service degradation** - Returns 503 errors for database-dependent endpoints when DB is down
- **Robust dependency injection** - Database dependency properly handles connection failures
- **Health monitoring** - Multiple endpoints for monitoring:
  - `/ping` - Basic application connectivity (no database required)
  - `/db-status` - Database connectivity status with error details
  - `/health` - Comprehensive health check including database status

## Frontend & Styling
- **Jinja2 Templates** - Server-side HTML templating
- **Tailwind CSS v4** - Utility-first CSS framework
- **Static Files** - Served via FastAPI StaticFiles

## Key Dependencies
- `fastapi[standard]` - Web framework with standard extras
- `pydantic` - Data validation and serialization
- `google-api-python-client` - Google APIs integration
- `supabase` - Database client
- `psycopg2-binary` - PostgreSQL adapter
- `openpyxl` - Excel file processing
- `pillow` - Image processing
- `slowapi` - Rate limiting middleware
- `itsdangerous` - Secure session management

## Development Tools
- **uv** - Python package manager and virtual environment
- **Ruff** - Fast Python linter and formatter
- **Lefthook** - Git hooks management
- **Gitleaks** - Secret scanning
- **Docker** - Containerization for deployment

## Security & File Handling
- **Custom secure_filename()** - Standard library replacement for werkzeug.utils.secure_filename
- **Path validation** - All file operations are constrained to safe directories

## Code Quality Configuration
```toml
# Ruff settings (pyproject.toml)
target-version = "py313"
line-length = 88
quote-style = "double"
indent-style = "space"
```

## Common Commands

### Development Setup
```bash
# Install system dependencies (macOS/WSL)
brew install uv gitleaks lefthook ruff git

# Create and activate virtual environment
uv venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install dependencies
uv sync

# Install git hooks
lefthook install
```

### Running the Application
```bash
# Development server with hot reload
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Production-like with Docker (recommended)
docker compose --env-file .env up --build
```

### Code Quality
```bash
# Lint and format code
ruff check
ruff check --fix
ruff format

# Build Tailwind CSS
npm run build:css
```

### Testing & Deployment
```bash
# Health check endpoint
curl http://localhost:8000/health

# Docker build for production
docker build -t purchase-request-site .
```

## Email Pipeline
The application includes an enhanced email confirmation system:
- **EmailerPipeline** - Main class for sending rich HTML emails
- **Automatic confirmations** - Sent after successful purchase request submission
- **Attachments** - Includes purchase request and expense report Excel files
- **Fallback support** - Gracefully handles missing email configuration

### Email Configuration
Required environment variables for email functionality:
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@domain.com
SMTP_PASSWORD=your-app-password
ERROR_EMAIL_FROM=noreply@mcmastersolarcar.com
```

## Environment Variables
Contact team lead for required environment variables including:
- Database connection strings
- Google API credentials
- **SMTP email configuration** (see Email Pipeline section)
- Application secrets