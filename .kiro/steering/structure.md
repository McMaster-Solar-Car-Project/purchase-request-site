# Project Structure

## Root Directory Layout
```
├── src/                    # Main application source code
├── sessions/              # Session file storage (created at runtime)
├── logs/                  # Application logs
├── .kiro/                 # Kiro AI assistant configuration
├── .venv/                 # Python virtual environment
├── node_modules/          # Node.js dependencies for Tailwind
├── .github/               # GitHub workflows and templates
└── purchase_request_site/ # Legacy directory (consider cleanup)
```

## Source Code Organization (`src/`)

### Core Application
- `main.py` - FastAPI application entry point and configuration
- `request_logging.py` - Custom middleware for request logging

### Routers (API Endpoints)
- `routers/auth.py` - Authentication and login endpoints
- `routers/dashboard.py` - Main dashboard functionality
- `routers/profile.py` - User profile management
- `routers/success.py` - Success page handling
- `routers/download.py` - File download endpoints
- `routers/utils.py` - Shared router utilities (templates, rate limiting)

### Core Modules
- `core/` - Core application utilities and configuration
- `db/` - Database models, schema, and connection handling
- `models/` - Pydantic models and data structures

### External Services
- `google_drive.py` - Google Drive API integration
- `google_sheets.py` - Google Sheets API integration
- `emailer.py` - Email notification service
- `data_processing.py` - Data transformation utilities
- `image_processing.py` - Image handling and processing

### Frontend Assets
- `templates/` - Jinja2 HTML templates
- `static/` - Static assets (CSS, JS, images)
- `static/css/input.css` - Tailwind CSS source file
- `excel_templates/` - Excel file templates

## Architecture Patterns

### Router Pattern
- Each major feature area has its own router module
- Routers are included in `main.py` using `app.include_router()`
- Shared utilities (templates, rate limiter) in `routers/utils.py`

### Middleware Stack
- Session middleware for authentication
- Custom request logging middleware
- Rate limiting via SlowAPI

### Static File Serving
- `/static` - Application assets (CSS, JS, images)
- `/sessions` - User session files (created dynamically)

### Configuration Management
- Environment variables loaded via `python-dotenv`
- Database initialization on startup
- Required directories created automatically

## File Naming Conventions
- Snake_case for Python files and directories
- Descriptive module names (e.g., `google_sheets.py`, `data_processing.py`)
- Router files named by feature area (e.g., `auth.py`, `dashboard.py`)

## Import Organization
- Standard library imports first
- Third-party imports second
- Local application imports last
- Relative imports used for local modules (`from src.core import ...`)