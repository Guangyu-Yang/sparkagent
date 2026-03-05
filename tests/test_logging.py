"""Tests for sparkagent.logging module."""

import json
import logging
import os
from unittest.mock import patch

import pytest

from sparkagent.logging import (
    JsonFormatter,
    _create_file_handler,
    configure_logging,
    shutdown_logging,
)


@pytest.fixture(autouse=True)
def _cleanup_logging():
    """Ensure clean logging state between tests."""
    yield
    shutdown_logging()
    logger = logging.getLogger("sparkagent")
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)


class TestJsonFormatter:
    def test_produces_valid_json_with_required_fields(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="sparkagent.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "sparkagent.test"
        assert parsed["message"] == "hello world"
        assert parsed["module"] == "test"
        assert parsed["line"] == 42
        assert "timestamp" in parsed
        assert parsed["timestamp"].endswith("+00:00")

    def test_includes_exception_info(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                name="sparkagent.test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="error occurred",
                args=(),
                exc_info=True,
            )
            # LogRecord captures exc_info from sys.exc_info() when exc_info=True
            import sys

            record.exc_info = sys.exc_info()

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert any("ValueError" in line for line in parsed["exception"])
        assert any("boom" in line for line in parsed["exception"])


class TestEnvVarFallback:
    def test_env_var_sets_level_when_no_explicit_arg(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            configure_logging()

        logger = logging.getLogger("sparkagent")
        # The logger itself is always DEBUG; the console handler filters
        assert logger.level == logging.DEBUG
        # Find the QueueHandler -> listener -> console handler
        queue_handler = logger.handlers[0]
        assert isinstance(queue_handler, logging.handlers.QueueHandler)

    def test_explicit_level_overrides_env_var(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            configure_logging(level="WARNING")

        # The console handler should be at WARNING, not DEBUG
        from sparkagent.logging import _log_listener

        console_handler = _log_listener.handlers[0]
        assert console_handler.level == logging.WARNING


class TestReconfigurationSafety:
    def test_no_handler_duplication(self):
        configure_logging()
        configure_logging()
        configure_logging()

        logger = logging.getLogger("sparkagent")
        # Should have exactly one QueueHandler, no matter how many times configured
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.QueueHandler)


class TestFileHandlerDegradation:
    def test_returns_none_on_oserror(self, tmp_path):
        bad_path = tmp_path / "nonexistent" / "deep" / "path"
        with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
            handler = _create_file_handler(bad_path)
        assert handler is None

    def test_creates_handler_on_valid_path(self, tmp_path):
        log_dir = tmp_path / "logs"
        handler = _create_file_handler(log_dir)
        assert handler is not None
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.level == logging.DEBUG
        assert isinstance(handler.formatter, JsonFormatter)
        handler.close()


class TestJsonConsoleFormat:
    def test_json_format_applies_to_console(self):
        configure_logging(log_format="json")

        from sparkagent.logging import _log_listener

        console_handler = _log_listener.handlers[0]
        assert isinstance(console_handler.formatter, JsonFormatter)

    def test_text_format_is_default(self):
        configure_logging()

        from sparkagent.logging import _log_listener

        console_handler = _log_listener.handlers[0]
        assert not isinstance(console_handler.formatter, JsonFormatter)


class TestShutdownLogging:
    def test_shutdown_is_idempotent(self):
        configure_logging()
        shutdown_logging()
        shutdown_logging()  # Should not raise
