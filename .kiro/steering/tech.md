# Technology Stack

## Backend Framework
- **FastAPI** - Modern Python web framework with automatic API documentation
- **Python 3.13** - Required Python version (exact match)
- **Uvicorn** - ASGI server for running the FastAPI application

## Database & Storage
- **PostgreSQL** - Primary database (via psycopg2-binary)
- **SQLAlchemy** - ORM for database operations
- **Supabase** - Database hosting and additional services

## External Integrations
- **Google APIs** - Sheets and Drive integration for data storage
- **Google Places API** - Location services
- **SMTP** - Email notifications

## Frontend & Styling
- **Jinja2 Templates** - Server-side HTML templating
- **Tailwind CSS v4** - Utility-first CSS framework
- **Static file serving** - FastAPI StaticFiles for assets

## Development Tools
- **uv** - Python package manager and virtual environment
- **Ruff** - Fast Python linter and formatter
- **Lefthook** - Git hooks management
- **Gitleaks** - Secret scanning
- **Docker** - Containerization for deployment

## Common Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run development server
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Operations
```bash
# Build and run with Docker (recommended)
docker compose --env-file .env up --build

# Health check
curl http://localhost:8000/health
```

### Code Quality
```bash
# Lint and format code
ruff check --fix
ruff format

# Build Tailwind CSS
npm run build:css
```

### Git Hooks
```bash
# Install git hooks (required for development)
lefthook install
```

## Configuration
- Environment variables in `.env` file
- Python dependencies in `pyproject.toml`
- Docker configuration in `docker-compose.yml`
- Ruff configuration in `pyproject.toml`