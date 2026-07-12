"""Structured logging for Source2Launch.

Provides JSON-structured logging for production environments while
maintaining human-readable output for development.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


# Default log level from environment or INFO
DEFAULT_LEVEL = LogLevel.INFO
_env_level = os.environ.get("PROMOAGENT_LOG_LEVEL", "").upper()
if _env_level:
    try:
        DEFAULT_LEVEL = LogLevel[_env_level]
    except KeyError:
        pass

# Log format from environment
LOG_FORMAT = os.environ.get("PROMOAGENT_LOG_FORMAT", "text")  # "text" or "json"

# Component name for structured logs
COMPONENT = "promoagent"


class Logger:
    """Simple structured logger with both text and JSON output modes."""

    def __init__(self, name: str = COMPONENT, level: LogLevel = DEFAULT_LEVEL):
        self.name = name
        self.level = level
        self._use_json = LOG_FORMAT == "json"
        self._stderr_is_tty = sys.stderr.isatty()

    def _should_log(self, level: LogLevel) -> bool:
        return level >= self.level

    def set_level(self, level: LogLevel) -> None:
        """Change the minimum log level at runtime.

        Mutates the instance in place so every module that imported the global
        ``logger`` singleton picks up the new level immediately — unlike
        ``configure()``, which rebinds the module attribute and leaves stale
        references in callers that did ``from .logger import logger``.
        """
        self.level = level

    def _format_text(self, level: LogLevel, message: str, **kwargs: Any) -> str:
        """Format log entry as human-readable text."""
        level_names = {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO",
            LogLevel.WARNING: "WARN",
            LogLevel.ERROR: "ERROR",
            LogLevel.CRITICAL: "CRIT",
        }
        level_name = level_names.get(level, "UNKNOWN")

        # Color codes for TTY
        if self._stderr_is_tty:
            colors = {
                LogLevel.DEBUG: "\033[36m",    # Cyan
                LogLevel.INFO: "\033[32m",     # Green
                LogLevel.WARNING: "\033[33m",  # Yellow
                LogLevel.ERROR: "\033[31m",    # Red
                LogLevel.CRITICAL: "\033[35m", # Magenta
            }
            reset = "\033[0m"
            level_str = f"{colors.get(level, '')}{level_name}{reset}"
        else:
            level_str = level_name

        # Build message
        prefix = f"{self.name}: [{level_str}]"

        # Add extra context
        extra = " ".join(f"{k}={v!r}" for k, v in kwargs.items())
        if extra:
            return f"{prefix} {message} ({extra})"
        return f"{prefix} {message}"

    def _format_json(self, level: LogLevel, message: str, **kwargs: Any) -> str:
        """Format log entry as JSON."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.name,
            "component": self.name,
            "message": message,
        }
        if kwargs:
            entry["context"] = kwargs
        return json.dumps(entry, ensure_ascii=False, default=str)

    def _log(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        if not self._should_log(level):
            return

        if self._use_json:
            output = self._format_json(level, message, **kwargs)
        else:
            output = self._format_text(level, message, **kwargs)

        print(output, file=sys.stderr, flush=True)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.ERROR, message, **kwargs)

    # Aliases for compatibility
    warn = warning


# Global logger instance
logger = Logger()


def log_duration(operation: str, start_time: float, **context: Any) -> None:
    """Log the duration of an operation.

    Args:
        operation: Name of the operation
        start_time: Start time from time.time()
        **context: Additional context to log
    """
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f"{operation} completed",
        duration_ms=round(duration_ms, 2),
        **context
    )


class LogTimer:
    """Context manager for timing operations.

    Example:
        with LogTimer("pdf_extract"):
            text = extract_pdf(path)
    """

    def __init__(self, operation: str, **context: Any):
        self.operation = operation
        self.context = context
        self.start_time: float | None = None

    def __enter__(self) -> LogTimer:
        self.start_time = time.time()
        logger.debug(f"{self.operation} started", **self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is None:
            return

        duration_ms = (time.time() - self.start_time) * 1000

        if exc_type is not None:
            logger.error(
                f"{self.operation} failed",
                duration_ms=round(duration_ms, 2),
                error_type=exc_type.__name__,
                **self.context
            )
        else:
            logger.info(
                f"{self.operation} completed",
                duration_ms=round(duration_ms, 2),
                **self.context
            )