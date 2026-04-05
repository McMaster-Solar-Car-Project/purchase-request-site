"""Utility module for setting up consistent logging across the application.

Provides a `setup_logger` function that configures a logger with:
- Console output (stdout) for local debugging
- File output for persistent logs
- Sentry structured logs for centralized monitoring
- Email notifications for errors
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.emailer import Emailer

# Load environment variables
load_dotenv()


class SentryLoggerWrapper:
    """Wrapper that logs to both Python standard logging and Sentry structured logs.

    Provides the same interface as logging.Logger but also sends logs to Sentry
    using sentry_sdk.logger for structured, searchable logs.
    """

    def __init__(self, name: str, std_logger: logging.Logger):
        self.name = name
        self._std_logger = std_logger

    def _log_to_sentry(self, level: str, msg: str, *args, **kwargs) -> None:
        """Send log to Sentry using native API.

        Uses lazy import to handle cases where logger is created before Sentry init.
        """
        try:
            import sentry_sdk
        except ImportError:
            return

        # Format message with args if provided (like standard logging)
        if args:
            try:
                formatted_msg = msg % args
            except (TypeError, ValueError):
                formatted_msg = msg
        else:
            formatted_msg = msg

        # Extract extra fields as Sentry attributes
        extra = kwargs.get("extra", {})

        # Map python log levels to sentry log levels
        sentry_level = level if level != "critical" else "fatal"

        if sentry_level == "error":
            sentry_sdk.capture_message(
                formatted_msg,
                level="error",
                extras={"logger.name": self.name, **extra},
            )
        elif sentry_level == "fatal":
            sentry_sdk.capture_message(
                formatted_msg,
                level="fatal",
                extras={"logger.name": self.name, **extra},
            )
        else:
            sentry_sdk.add_breadcrumb(
                category=self.name,
                message=formatted_msg,
                level=sentry_level,
                data=extra,
            )

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message to console/file and Sentry."""
        self._std_logger.debug(msg, *args, **kwargs)
        self._log_to_sentry("debug", msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message to console/file and Sentry."""
        self._std_logger.info(msg, *args, **kwargs)
        self._log_to_sentry("info", msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message to console/file and Sentry."""
        self._std_logger.warning(msg, *args, **kwargs)
        self._log_to_sentry("warning", msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message to console/file and Sentry."""
        self._std_logger.error(msg, *args, **kwargs)
        self._log_to_sentry("error", msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message to console/file and Sentry (as fatal)."""
        self._std_logger.critical(msg, *args, **kwargs)
        self._log_to_sentry("fatal", msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback to console/file and Sentry."""
        self._std_logger.exception(msg, *args, **kwargs)
        self._log_to_sentry("error", msg, *args, **kwargs)

    # Proxy other common logger attributes
    @property
    def handlers(self) -> list:
        return self._std_logger.handlers

    def setLevel(self, level: int) -> None:  # noqa: N802
        self._std_logger.setLevel(level)

    def addHandler(self, handler: logging.Handler) -> None:  # noqa: N802
        self._std_logger.addHandler(handler)


def setup_logger(name: str) -> SentryLoggerWrapper:
    """Set up a logger with the specified name.

    Returns a wrapper that logs to both standard Python logging (console/file)
    and Sentry structured logs for centralized monitoring.

    Args:
        name (str): The name of the logger.

    Returns:
        SentryLoggerWrapper: A logger that outputs to console, file, and Sentry.
    """
    std_logger = logging.getLogger(name)
    std_logger.setLevel(logging.INFO)

    if not std_logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        std_logger.addHandler(console_handler)

        # File handler for persistent logging
        file_handler = _setup_file_handler()
        if file_handler:
            std_logger.addHandler(file_handler)

        # Email handler for errors (if configured)
        email_handler = _setup_email_handler()
        if email_handler:
            std_logger.addHandler(email_handler)

    return SentryLoggerWrapper(name, std_logger)


def _setup_file_handler() -> logging.Handler | None:
    """Set up file handler for persistent logging.

    Returns:
        logging.Handler or None: File handler if successful, None otherwise.
    """
    try:
        # Create logs directory if it doesn't exist
        logs_dir = Path(__file__).parent.parent / "logs"
        os.makedirs(logs_dir, exist_ok=True)

        # Create log file path with date
        log_filename = f"purchase_request_site_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = Path(logs_dir) / log_filename

        # Create rotating file handler (max 10MB, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_filepath,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )

        # Set detailed formatter for file logs
        file_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)

        return file_handler

    except Exception as e:
        print(f"CRITICAL: Could not set up file handler: {e}")
        return None


def _setup_email_handler() -> logging.Handler | None:
    """Set up email handler for error notifications.

    Returns:
        logging.Handler or None: Email handler if properly configured, None otherwise.
    """
    try:
        # Get email configuration from Emailer class
        emailer = Emailer()

        smtp_server = emailer.smtp_server
        smtp_port = emailer.smtp_port
        smtp_username = emailer.smtp_username
        smtp_password = emailer.smtp_password
        from_email = emailer.from_email
        to_emails = os.getenv("ERROR_EMAIL_TO")

        # Check if all required email settings are provided
        if not all(
            [
                smtp_server,
                smtp_port,
                smtp_username,
                smtp_password,
                from_email,
                to_emails,
            ]
        ):
            return None

        assert smtp_server is not None
        assert smtp_port is not None
        assert smtp_username is not None
        assert smtp_password is not None
        assert from_email is not None
        assert to_emails is not None

        # Parse multiple email addresses (comma-separated)
        to_email_list = [email.strip() for email in to_emails.split(",")]

        # Create SMTP handler
        email_handler = logging.handlers.SMTPHandler(
            mailhost=(smtp_server, int(smtp_port)),
            fromaddr=from_email,
            toaddrs=to_email_list,
            subject="🚨 Purchase Request Site - Application Error",
            credentials=(smtp_username, smtp_password),
            secure=(),  # Use TLS
        )

        # Set level to ERROR (will catch ERROR and CRITICAL)
        email_handler.setLevel(logging.ERROR)

        # Create detailed formatter for emails
        email_formatter = logging.Formatter(
            """
Application Error Alert

Time: %(asctime)s
Level: %(levelname)s
Logger: %(name)s
File: %(pathname)s:%(lineno)d
Function: %(funcName)s

Error Message:
%(message)s

---
Purchase Request Site Error Notification System
        """.strip(),
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        email_handler.setFormatter(email_formatter)

        return email_handler

    except Exception as e:
        # Don't let email setup failure break the application
        print(f"CRITICAL: Could not set up email handler: {e}")
        return None
