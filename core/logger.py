"""
Centralized logging configuration using Loguru.
Follows Single Responsibility Principle - only handles logging setup.

Features:
- Structured logging with Loguru
- Standard library logging interception (routes stdlib logging to Loguru)
- Third-party library logger configuration (httpx, urllib3, boto3)
- Script logging helper for standalone scripts
- JSON logging format option for production
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from loguru import logger  # type: ignore


# =============================================================================
# Standard Library Logging Interception
# =============================================================================


class InterceptHandler(logging.Handler):
    """
    Intercept standard library logging and route to Loguru.

    This allows third-party libraries that use stdlib logging to have their
    logs captured and formatted consistently through Loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where logging call originated
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def intercept_standard_logging() -> None:
    """
    Intercept Python standard library logging and route to Loguru.

    This ensures all logs from third-party libraries using stdlib logging
    are captured and formatted consistently through Loguru.
    """
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def configure_third_party_loggers() -> None:
    """
    Configure third-party library loggers to reduce noise.

    Sets appropriate log levels for common libraries to prevent
    verbose debug output from cluttering application logs.
    """
    # Suppress verbose logs from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # AWS SDK loggers - INFO level to see important operations
    logging.getLogger("botocore").setLevel(logging.INFO)
    logging.getLogger("boto3").setLevel(logging.INFO)

    # Uvicorn loggers - keep at INFO for server events
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # FastAPI/Starlette
    logging.getLogger("fastapi").setLevel(logging.INFO)


# =============================================================================
# Script Logging Helper
# =============================================================================


def configure_script_logging(level: str = "INFO", json_format: bool = False) -> None:
    """
    Configure logging for standalone scripts.

    Provides a simplified logging setup for scripts that run outside
    the main application context. Console output only (no file logging).

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output logs in JSON format

    Example:
        from core.logger import logger, configure_script_logging

        configure_script_logging(level="DEBUG")
        logger.info("Script started")
    """
    # Remove all existing handlers
    logger.remove()

    # Validate log level
    level = level.upper()
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        level = "INFO"

    if json_format:
        # JSON format for production/log aggregation
        logger.add(
            sys.stdout,
            format="{message}",
            level=level,
            serialize=True,  # Loguru's built-in JSON serialization
        )
    else:
        # Simplified colored format for scripts
        logger.add(
            sys.stdout,
            colorize=True,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            level=level,
        )

    # Also intercept stdlib logging for scripts
    intercept_standard_logging()
    configure_third_party_loggers()


def format_exception_short(exception: Exception, context: Optional[str] = None) -> str:
    """
    Format exception to be short and readable.

    Args:
        exception: Exception object
        context: Optional context message

    Returns:
        Short formatted error message

    Example:
        >>> try:
        ...     raise ValueError("Invalid input")
        ... except ValueError as e:
        ...     print(format_exception_short(e, "Processing file"))
        Processing file: ValueError: Invalid input (file: core/utils.py, line: 123)
    """
    try:
        exc_type = type(exception).__name__
        exc_message = str(exception)

        # Get the last frame from traceback (where error actually occurred)
        tb = exception.__traceback__
        if tb:
            while tb.tb_next:
                tb = tb.tb_next
            frame = tb.tb_frame
            filename = Path(frame.f_code.co_filename).name
            lineno = tb.tb_lineno
            location = f"{filename}:{lineno}"
        else:
            location = "unknown"

        # Build short message
        parts = []
        if context:
            parts.append(context)
        parts.append(f"{exc_type}: {exc_message}")
        parts.append(f"({location})")

        return " | ".join(parts)

    except Exception:
        # Fallback to simple format if something goes wrong
        return f"{type(exception).__name__}: {str(exception)}"


def setup_logger() -> None:
    """
    Configure logger handlers for the main application.

    Only configures once even if called multiple times.
    Supports both console (colored) and JSON formats based on LOG_FORMAT setting.
    """
    from .config import get_settings

    settings = get_settings()

    # Get log level: LOG_LEVEL takes precedence over DEBUG flag
    if settings.log_level:
        log_level = settings.log_level.upper()
        if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            log_level = "INFO"
    else:
        log_level = "DEBUG" if settings.debug else "INFO"

    # Check if logger already has our handlers configured
    handlers_count_before = len(logger._core.handlers.values())
    if handlers_count_before >= 3:
        return

    # Remove all existing handlers first
    logger.remove()
    handlers_count_after_remove = len(logger._core.handlers.values())

    if handlers_count_after_remove == 0:
        # Get log format from settings (console or json)
        log_format = getattr(settings, "log_format", "console").lower()
        log_file_enabled = getattr(settings, "log_file_enabled", True)

        # Check if JSON format is requested
        if log_format == "json":
            # JSON format for production/log aggregation
            logger.add(
                sys.stdout,
                format=serialize_log_record,
                level=log_level,
                colorize=False,
            )

            if log_file_enabled:
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)

                logger.add(
                    log_dir / "app.json.log",
                    rotation="100 MB",
                    retention="30 days",
                    compression="zip",
                    format=serialize_log_record,
                    level="DEBUG",
                    colorize=False,
                )

                logger.add(
                    log_dir / "error.json.log",
                    rotation="100 MB",
                    retention="30 days",
                    compression="zip",
                    format=serialize_log_record,
                    level="ERROR",
                    colorize=False,
                )
        else:
            # Console format (default) - colored, human-readable
            def filter_reloader_logs(record):
                """Filter out logs from __main__ and __mp_main__ (reloader processes)."""
                module_name = record.get("name", "")
                if module_name in ("__main__", "__mp_main__"):
                    return False
                return True

            logger.add(
                sys.stdout,
                colorize=True,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                level=log_level,
                filter=filter_reloader_logs,
            )

            if log_file_enabled:
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)

                logger.add(
                    log_dir / "app.log",
                    rotation="100 MB",
                    retention="30 days",
                    compression="zip",
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                    level="DEBUG",
                )

                logger.add(
                    log_dir / "error.log",
                    rotation="100 MB",
                    retention="30 days",
                    compression="zip",
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                    level="ERROR",
                )

        # Intercept standard library logging and configure third-party loggers
        intercept_standard_logging()
        configure_third_party_loggers()


# =============================================================================
# JSON Logging Format
# =============================================================================


def serialize_log_record(record: dict) -> str:
    """
    Serialize log record to a flat JSON dictionary.

    This replaces Loguru's default nested JSON serialization with a cleaner,
    flattened structure suitable for log aggregation (ELK, Datadog, etc.).

    Args:
        record: Loguru record dictionary

    Returns:
        JSON string representation of the log record
    """
    import json

    # Base fields
    log_record = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add exception info if present
    if record.get("exception"):
        exception = record["exception"]
        log_record["exception"] = {
            "type": exception.type.__name__ if exception.type else "Unknown",
            "message": str(exception.value),
            # Avoid full traceback in JSON to keep it clean, or include it if needed
            # "traceback": str(exception.traceback)
        }

    # Flatten extra fields
    # Note: 'extra' contains context variables bound via logger.bind()
    if record.get("extra"):
        for key, value in record["extra"].items():
            # Check if value is JSON serializable
            try:
                json.dumps(value)
                log_record[key] = value
            except (TypeError, OverflowError):
                # Fallback to string representation for non-serializable objects
                log_record[key] = str(value)

    # Escape curly braces for Loguru's format string since it calls format() on the result
    # Also escape < to prevent Loguru from interpreting it as a color tag
    return (
        json.dumps(log_record).replace("{", "{{").replace("}", "}}").replace("<", "\\<")
        + "\n"
    )


def setup_json_logging(level: str = "INFO") -> None:
    """
    Configure JSON logging format for production environments.

    JSON format is ideal for log aggregation systems like ELK, Datadog, etc.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove all existing handlers
    logger.remove()

    # Validate log level
    level = level.upper()
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        level = "INFO"

    # Console handler with JSON format
    logger.add(
        sys.stdout,
        format=serialize_log_record,
        level=level,
        colorize=False,
    )

    # File handler with JSON format
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "app.json.log",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        format=serialize_log_record,
        level="DEBUG",
        colorize=False,
    )

    # Error file handler with JSON format
    logger.add(
        log_dir / "error.json.log",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        format=serialize_log_record,
        level="ERROR",
        colorize=False,
    )

    # Intercept stdlib logging
    intercept_standard_logging()
    configure_third_party_loggers()

    # Note: Using print() here might break JSON parsing if mixed with logs
    # logger.info(f"JSON logging configured (level={level})")


# Configure logger on module import
setup_logger()

__all__ = [
    "logger",
    "format_exception_short",
    "configure_script_logging",
    "configure_third_party_loggers",
    "intercept_standard_logging",
    "setup_json_logging",
    "serialize_log_record",
    "InterceptHandler",
]
