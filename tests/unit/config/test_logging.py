"""
Tests for logging configuration (T-003).

"""

import json
import logging
import pytest


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_returns_valid_json(self):
        """JSONFormatter should output valid JSON string."""
        from archai.config.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_format_includes_timestamp(self):
        """JSON output should include timestamp field."""
        from archai.config.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "timestamp" in data

    def test_format_includes_level(self):
        """JSON output should include log level."""
        from archai.config.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "level" in data
        assert data["level"] == "INFO"

    def test_format_includes_message(self):
        """JSON output should include log message."""
        from archai.config.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="warning message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "message" in data
        assert data["message"] == "warning message"

    def test_format_includes_module(self):
        """JSON output should include module name."""
        from archai.config.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "module" in data


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger_instance(self):
        """get_logger should return a logger instance."""
        from archai.config.logging import get_logger

        logger = get_logger("test")

        assert isinstance(logger, logging.Logger)

    def test_get_logger_has_correct_prefix(self):
        """get_logger should add 'archai.' prefix to name."""
        from archai.config.logging import get_logger

        logger = get_logger("test")

        assert logger.name == "archai.test"


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_configures_logger(self):
        """setup_logging should configure the archai logger."""
        from archai.config.logging import setup_logging

        # Should not raise exception
        setup_logging()

        logger = logging.getLogger("archai")
        assert logger.level != logging.NOTSET

    def test_setup_logging_has_handler(self):
        """setup_logging should add at least one handler."""
        from archai.config.logging import setup_logging

        setup_logging()

        logger = logging.getLogger("archai")
        assert len(logger.handlers) > 0
