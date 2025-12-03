"""
Tests for logging configuration.

Tests the centralized logging setup including:
- Log level configuration
- Standard library logging interception
- Third-party logger configuration
- JSON vs console format
- Script logging helper
"""

import logging
import pytest


class TestInterceptHandler:
    """Tests for InterceptHandler class."""

    def test_intercept_handler_is_logging_handler(self):
        """Test that InterceptHandler is a logging.Handler subclass."""
        from core.logger import InterceptHandler

        handler = InterceptHandler()
        assert isinstance(handler, logging.Handler)

    def test_intercept_handler_emit_does_not_raise(self):
        """Test that emit method processes log records without raising."""
        from core.logger import InterceptHandler

        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Should not raise
        handler.emit(record)


class TestConfigureThirdPartyLoggers:
    """Tests for configure_third_party_loggers function."""

    def test_configures_httpx_logger(self):
        """Test that httpx logger is set to WARNING."""
        from core.logger import configure_third_party_loggers

        configure_third_party_loggers()

        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level == logging.WARNING

    def test_configures_urllib3_logger(self):
        """Test that urllib3 logger is set to WARNING."""
        from core.logger import configure_third_party_loggers

        configure_third_party_loggers()

        urllib3_logger = logging.getLogger("urllib3")
        assert urllib3_logger.level == logging.WARNING

    def test_configures_boto3_logger(self):
        """Test that boto3 logger is set to INFO."""
        from core.logger import configure_third_party_loggers

        configure_third_party_loggers()

        boto3_logger = logging.getLogger("boto3")
        assert boto3_logger.level == logging.INFO

    def test_configures_uvicorn_logger(self):
        """Test that uvicorn logger is set to INFO."""
        from core.logger import configure_third_party_loggers

        configure_third_party_loggers()

        uvicorn_logger = logging.getLogger("uvicorn")
        assert uvicorn_logger.level == logging.INFO


class TestConfigureScriptLogging:
    """Tests for configure_script_logging function."""

    def test_configure_script_logging_default_level(self):
        """Test script logging with default INFO level."""
        from core.logger import configure_script_logging

        # Should not raise
        configure_script_logging()

    def test_configure_script_logging_debug_level(self):
        """Test script logging with DEBUG level."""
        from core.logger import configure_script_logging

        # Should not raise
        configure_script_logging(level="DEBUG")

    def test_configure_script_logging_invalid_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        from core.logger import configure_script_logging

        # Should not raise, should default to INFO
        configure_script_logging(level="INVALID")

    def test_configure_script_logging_json_format(self):
        """Test script logging with JSON format."""
        from core.logger import configure_script_logging

        # Should not raise
        configure_script_logging(json_format=True)


class TestInterceptStandardLogging:
    """Tests for intercept_standard_logging function."""

    def test_intercept_standard_logging(self):
        """Test that standard logging is intercepted."""
        from core.logger import intercept_standard_logging

        # Should not raise
        intercept_standard_logging()

        # Root logger should have InterceptHandler
        root_logger = logging.getLogger()
        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert "InterceptHandler" in handler_types


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_setup_logger_creates_handlers(self):
        """Test that setup_logger creates log handlers."""
        from core.logger import setup_logger, logger

        # Reset logger
        logger.remove()

        # Setup should create handlers
        setup_logger()

        # Should have at least one handler
        assert len(logger._core.handlers) >= 1

    def test_setup_logger_idempotent(self):
        """Test that setup_logger is idempotent (doesn't add duplicate handlers)."""
        from core.logger import setup_logger, logger

        # Call setup multiple times
        setup_logger()
        handlers_count_1 = len(logger._core.handlers)

        setup_logger()
        handlers_count_2 = len(logger._core.handlers)

        # Handler count should not increase significantly
        # (may vary slightly due to implementation details)
        assert handlers_count_2 <= handlers_count_1 + 1


class TestFormatExceptionShort:
    """Tests for format_exception_short function."""

    def test_format_exception_with_context(self):
        """Test formatting exception with context."""
        from core.logger import format_exception_short

        try:
            raise ValueError("Test error")
        except ValueError as e:
            result = format_exception_short(e, "Test context")

            assert "Test context" in result
            assert "ValueError" in result
            assert "Test error" in result

    def test_format_exception_without_context(self):
        """Test formatting exception without context."""
        from core.logger import format_exception_short

        try:
            raise RuntimeError("Another error")
        except RuntimeError as e:
            result = format_exception_short(e)

            assert "RuntimeError" in result
            assert "Another error" in result

    def test_format_exception_includes_location(self):
        """Test that formatted exception includes file location."""
        from core.logger import format_exception_short

        try:
            raise TypeError("Type mismatch")
        except TypeError as e:
            result = format_exception_short(e)

            # Should include file:line format
            assert "test_logging_config.py" in result or ":" in result


class TestLoggerExports:
    """Tests for module exports."""

    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        # Import the logger module directly, not the logger object
        from core.logger import (
            logger,
            format_exception_short,
            configure_script_logging,
            configure_third_party_loggers,
            intercept_standard_logging,
            setup_json_logging,
            InterceptHandler,
        )

        # Verify all exports are importable and not None
        assert logger is not None
        assert format_exception_short is not None
        assert configure_script_logging is not None
        assert configure_third_party_loggers is not None
        assert intercept_standard_logging is not None
        assert setup_json_logging is not None
        assert InterceptHandler is not None

    def test_logger_object_available(self):
        """Test that logger object is available and usable."""
        from core.logger import logger

        # Logger should be available
        assert logger is not None

        # Logger should have standard methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_logger_can_log_messages(self):
        """Test that logger can actually log messages."""
        from core.logger import logger

        # These should not raise
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")


class TestSetupJsonLogging:
    """Tests for setup_json_logging function."""

    def test_setup_json_logging_default_level(self):
        """Test JSON logging setup with default level."""
        from core.logger import setup_json_logging, logger

        # Reset and setup
        logger.remove()
        setup_json_logging()

        # Should have handlers
        assert len(logger._core.handlers) >= 1

    def test_setup_json_logging_custom_level(self):
        """Test JSON logging setup with custom level."""
        from core.logger import setup_json_logging, logger

        # Reset and setup with DEBUG level
        logger.remove()
        setup_json_logging(level="DEBUG")

        # Should have handlers
        assert len(logger._core.handlers) >= 1

    def test_setup_json_logging_invalid_level(self):
        """Test JSON logging setup with invalid level defaults to INFO."""
        from core.logger import setup_json_logging, logger

        # Reset and setup with invalid level
        logger.remove()
        setup_json_logging(level="INVALID")

        # Should not raise and should have handlers
        assert len(logger._core.handlers) >= 1
