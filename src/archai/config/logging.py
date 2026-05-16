"""
Logging configuration for ArchAI.

Provides structured JSON logging for better debugging and tracing.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields from record (excluding reserved LogRecord attributes)
        reserved_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "thread", "threadName", "exc_info", "exc_text", "stack_info",
            "message", "asctime",
        }
        for key, value in record.__dict__.items():
            if key not in reserved_attrs and not key.startswith("_"):
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create root logger
    logger = logging.getLogger("archai")
    logger.setLevel(level.upper())  # Python 3.4+ accepts strings directly

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler for DEBUG and INFO (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    console_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    logger.addHandler(console_handler)

    # Error handler for WARNING and above (stderr)
    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setFormatter(JSONFormatter())
    error_handler.setLevel(logging.WARNING)
    logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"archai.{name}")
