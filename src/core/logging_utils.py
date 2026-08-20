"""Application logging configuration."""

import logging
import sys


def configure_logging() -> None:
    """Configure standard logging once, writing container-friendly logs to stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def setup_logger(name: str) -> logging.Logger:
    """Return a standard library logger for ``name``."""
    return logging.getLogger(name)
