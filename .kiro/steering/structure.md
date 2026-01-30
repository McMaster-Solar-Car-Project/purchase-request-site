# Project Structure

## Root Directory Layout
```
purchase-request-site/
├── src/                    # Main application source code
├── sessions/              # Session file storage (created at runtime)
├── logs/                  # Application logs
├── .kiro/                 # Kiro AI assistant configuration
├── .github/               # GitHub workflows and templates
├── node_modules/          # Node.js dependencies (Tailwind CSS)
├── .venv/                 # Python virtual environment
├── pyproject.toml         # Python project configuration
├── package.json           # Node.js dependencies for Tailwind
├── docker-compose.yml     # Docker development setup
├── Dockerfile             # Production container definition
└── README.md              # Project documentation
```

## Source Code Organization (`src/`)

### Core Application
- `main.py` - FastAPI application entry point, middleware setup, route registration
- `request_logging.py` - Custom middleware for request/response logging

### Routers (`src/routers/`)
FastAPI route handlers organized by functionality:
- `auth.py` - Authentication and login routes
- `dashboard.py` - Main dashboard and purchase request routes  
- `profile.py` - User profile management
- `success.py` - Success/confirmation pages
- `download.py` - File download endpoints
- `utils.py` - Shared router utilities (templates, rate limiting)

### Core Modules (`src/core/`)
- Shared utilities and configuration
- Logging setup and configuration

### Database (`src/db/`)
- `schema.py` - Database schema definitions and initialization
- SQLAlchemy models and database setup

### Models (`src/models/`)
- Pydantic models for data validation
- Request/response schemas

### Data Processing
- `data_processing.py` - Business logic for processing requests
- `google_sheets.py` - Google Sheets API integration
- `google_drive.py` - Google Drive API integration
- `emailer.py` - Email notification system
- `image_processing.py` - Image upload and processing utilities

### Frontend Assets (`src/static/`)
- `css/` - Tailwind CSS input and compiled output files
- Static assets served by FastAPI

### Templates (`src/templates/`)
- Jinja2 HTML templates for server-side rendering
- Error pages (404.html, error.html)

### Excel Templates (`src/excel_templates/`)
- Template files for generating Excel reports

## Architecture Patterns

### Router Pattern
- Each major feature area has its own router module
- Routers are registered in `main.py` using `app.include_router()`
- Shared utilities in `routers/utils.py`

### Middleware Stack
1. `RequestLoggingMiddleware` - Custom request logging
2. `SessionMiddleware` - Session management for authentication
3. `SlowAPI` rate limiting - Integrated via exception handlers

### Static File Serving
- `/static` - Application CSS, JS, images
- `/sessions` - User session files (created dynamically)

### Error Handling
- Custom exception handlers for HTTP errors
- Template-based error pages
- Centralized logging for unhandled exceptions

### Configuration Management
- Environment variables via `.env` file
- Runtime directory creation for required folders
- Health check endpoint at `/health`

## Development Conventions

### File Naming
- Snake_case for Python files and directories
- Descriptive module names reflecting functionality
- Router files named after their primary feature

### Import Organization
- Standard library imports first
- Third-party imports second  
- Local application imports last
- Relative imports for same-package modules

### Directory Creation
- Required directories created at application startup
- `sessions/` folder managed automatically
- Static file directories must exist before mounting