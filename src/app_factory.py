import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from src.core.logging_utils import setup_logger
from src.core.observability import (
    HEALTH_PATH_PREFIX,
    configure_uvicorn_access_log_filter,
    init_sentry,
)
from src.core.settings import Settings, get_settings
from src.db.schema import init_database
from src.request_logging import RequestLoggingMiddleware
from src.routers.auth import router as auth_router
from src.routers.dashboard import router as dashboard_router
from src.routers.download import router as download_router
from src.routers.profile import router as profile_router
from src.routers.success import router as success_router
from src.routers.utils import limiter, templates

logger = setup_logger(__name__)


def create_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        Path("sessions").mkdir(parents=True, exist_ok=True)

        init_sentry(settings)
        configure_uvicorn_access_log_filter()
        init_database()
        yield

    return lifespan


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)

    # Generate a random secret key for this session (users are logged out on restart).
    session_secret = secrets.token_urlsafe(32)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
    )


def register_routes(app: FastAPI) -> None:
    app.mount("/static", StaticFiles(directory="src/static"), name="static")
    app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(profile_router)
    app.include_router(success_router)
    app.include_router(download_router)

    @app.get("/")
    async def home():
        """Redirect home page to login"""
        return RedirectResponse(url="/login", status_code=303)

    @app.get("/health")
    async def health_check():
        """Health check endpoint for Docker health monitoring"""
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}


def register_exception_handlers(app: FastAPI) -> None:
    async def handle_exceed_limit(request: Request, exc: Exception):
        """Handle rate limit exceeded errors by redirecting to login with error message"""
        if not isinstance(exc, RateLimitExceeded):
            raise exc
        return RedirectResponse(url="/login?error=ratelimit", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return templates.TemplateResponse(
                request=request,
                name="404.html",
                context={"request": request},
                status_code=404,
            )
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"request": request},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        if request.url.path.startswith(HEALTH_PATH_PREFIX):
            return JSONResponse(status_code=500, content={"status": "unhealthy"})
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"request": request},
            status_code=500,
        )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, handle_exceed_limit)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Purchase Request Site",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=create_lifespan(settings),
    )
    register_middleware(app)
    register_routes(app)
    register_exception_handlers(app)
    return app
