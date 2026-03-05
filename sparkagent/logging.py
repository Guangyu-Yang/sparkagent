"""Logging configuration for SparkAgent."""

import logging
import logging.config


def configure_logging(level: str = "INFO") -> None:
    """Configure application-wide logging.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "standard",
            },
        },
        "loggers": {
            "sparkagent": {
                "level": level.upper(),
                "handlers": ["console"],
                "propagate": False,
            },
        },
    })
