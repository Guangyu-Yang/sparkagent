"""Logging configuration for SparkAgent."""

import atexit
import json
import logging
import logging.handlers
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

_log_listener: logging.handlers.QueueListener | None = None


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line (JSONL format)."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON object."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_entry, default=str)


def _create_file_handler(log_dir: Path) -> logging.handlers.RotatingFileHandler | None:
    """Create a rotating file handler writing JSON at DEBUG level.

    Returns None if the log directory cannot be created.
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "sparkagent.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    return handler


def configure_logging(level: str | None = None, log_format: str = "text") -> None:
    """Configure application-wide logging.

    Args:
        level: Log level name. Precedence: this arg > LOG_LEVEL env var > "INFO".
        log_format: Console output format -- "text" (default) or "json".

    """
    global _log_listener

    # Stop any prior listener and clear handlers
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None

    logger = logging.getLogger("sparkagent")
    logger.handlers.clear()

    # Resolve effective level: CLI flag > env var > default
    effective_level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, effective_level, logging.INFO))
    if log_format == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    # File handler (always JSON, always DEBUG)
    log_dir = Path.home() / ".sparkagent" / "logs"
    file_handler = _create_file_handler(log_dir)

    # Collect actual handlers for the listener
    handlers: list[logging.Handler] = [console_handler]
    if file_handler is not None:
        handlers.append(file_handler)

    # QueueHandler / QueueListener for non-blocking I/O
    log_queue: Queue = Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)
    logger.propagate = False

    _log_listener = logging.handlers.QueueListener(log_queue, *handlers, respect_handler_level=True)
    _log_listener.start()
    atexit.register(_log_listener.stop)


def shutdown_logging() -> None:
    """Explicitly stop the background log listener.

    Also handled by atexit, but useful for gateway shutdown and tests.
    """
    global _log_listener
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None
