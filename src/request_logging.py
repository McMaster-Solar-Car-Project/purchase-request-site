"""
Middleware for logging HTTP requests and responses.
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging_utils import setup_logger

# Set up logger for request logging
request_logger = setup_logger("requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()

        # Get client IP (handle potential proxies)
        client_ip = request.client.host if request.client else "unknown"
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            client_ip = request.headers["x-real-ip"]

        # Only log important requests (skip static files)
        skip_paths = ["/static", "/favicon.ico", "/robots.txt"]
        should_log = not any(request.url.path.startswith(path) for path in skip_paths)

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Only log slow requests (>1s) or important endpoints or errors
            if should_log and (
                process_time > 1.0
                or response.status_code >= 400
                or request.method in ["POST", "PUT", "DELETE"]
            ):
                request_logger.info(
                    f"{request.method} {request.url.path} "
                    f"→ {response.status_code} ({process_time:.3f}s) from {client_ip}"
                )

            return response

        except Exception as e:
            # Always log errors
            process_time = time.time() - start_time
            request_logger.exception(
                f"❌ {request.method} {request.url.path} "
                f"failed after {process_time:.3f}s - {str(e)}"
            )
            raise
