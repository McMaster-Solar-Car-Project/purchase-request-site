"""Utility module for setting up consistent logging across the application.

Provides a `setup_logger` function that configures a logger with a standardized
format and outputs logs to stdout. Also supports email notifications for errors.
"""

import logging
import logging.handlers
import os
import sys

from dotenv import load_dotenv

from src.emailer import Emailer

# Load environment variables
load_dotenv()


def setup_logger(name: str) -> logging.Logger:
    """Set up a logger with the specified name.

    Args:
        name (str): The name of the logger.

    Returns:
        logging.Logger: The configured logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Changed from DEBUG to INFO to reduce verbosity

    if not logger.handlers:
        # Console handler (existing functionality)
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler for persistent logging
        file_handler = _setup_file_handler()
        if file_handler:
            logger.addHandler(file_handler)

        # Email handler for errors (if configured)
        email_handler = _setup_email_handler()
        if email_handler:
            logger.addHandler(email_handler)

    return logger


def _setup_file_handler() -> logging.Handler:
    """Set up file handler for persistent logging.

    Returns:
        logging.Handler or None: File handler if successful, None otherwise.
    """
    try:
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Create log file path with date
        from datetime import datetime

        log_filename = f"purchase_request_site_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = os.path.join(logs_dir, log_filename)

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


def _setup_email_handler() -> logging.Handler:
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
        if not all([smtp_server, smtp_username, smtp_password, from_email, to_emails]):
            return None

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
