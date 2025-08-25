"""Centralized safe logging module that handles exceptions gracefully.

This module provides a wrapper around Python's logging module that ensures
logging operations never raise exceptions, preventing logging from breaking
the application flow.
"""

import contextlib
import logging
import sys
from typing import Any


class SafeLogger:
    """A logger wrapper that safely handles all logging operations.

    This class wraps a standard Python logger and ensures that any exceptions
    during logging are caught and handled gracefully, preventing them from
    propagating to the caller.
    """

    def __init__(self, name: str, fallback_to_stderr: bool = True):
        """Initialize a safe logger.

        Args:
            name: The name for the underlying logger.
            fallback_to_stderr: If True, write to stderr when logging fails.
        """
        self._name = name
        self._fallback_to_stderr = fallback_to_stderr
        self._logger: logging.Logger | None = None
        self._initialize_logger()

    def _initialize_logger(self) -> None:
        """Initialize the underlying logger safely."""
        try:
            self._logger = logging.getLogger(self._name)
        except Exception as e:
            self._fallback_log(f"Failed to initialize logger '{self._name}': {e}")
            self._logger = None

    def _fallback_log(self, message: str) -> None:
        """Write a message to stderr as a fallback when logging fails."""
        if self._fallback_to_stderr:
            with contextlib.suppress(Exception):
                # Even stderr might fail in extreme cases
                print(f"[FALLBACK LOG] {message}", file=sys.stderr)

    def _safe_log(self, level: int, msg: Any, *args, **kwargs) -> None:
        """Safely perform a logging operation.

        Args:
            level: The logging level (e.g., logging.DEBUG, logging.INFO).
            msg: The message to log.
            *args: Positional arguments for the logging method.
            **kwargs: Keyword arguments for the logging method.
        """
        try:
            if self._logger is not None:
                # Temporarily disable logging.raiseExceptions to prevent error messages
                old_raise = logging.raiseExceptions
                try:
                    logging.raiseExceptions = False
                    self._logger.log(level, msg, *args, **kwargs)
                finally:
                    logging.raiseExceptions = old_raise
            else:
                # Logger initialization failed, use fallback
                level_name = logging.getLevelName(level)
                formatted_msg = str(msg) % args if args else str(msg)
                self._fallback_log(f"[{level_name}] {formatted_msg}")
        except Exception:
            # Handle any exception during logging
            # Note: We don't use fallback_log here during shutdown to avoid noise
            # The exception is already suppressed, which is the main goal
            pass

    def debug(self, msg: Any, *args, **kwargs) -> None:
        """Log a debug message safely."""
        self._safe_log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: Any, *args, **kwargs) -> None:
        """Log an info message safely."""
        self._safe_log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: Any, *args, **kwargs) -> None:
        """Log a warning message safely."""
        self._safe_log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: Any, *args, **kwargs) -> None:
        """Log an error message safely."""
        self._safe_log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: Any, *args, **kwargs) -> None:
        """Log a critical message safely."""
        self._safe_log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: Any, *args, exc_info=True, **kwargs) -> None:
        """Log an exception message safely.

        This method is similar to error() but will also log the current
        exception information if exc_info is True.
        """
        kwargs["exc_info"] = exc_info
        self._safe_log(logging.ERROR, msg, *args, **kwargs)

    def log(self, level: int, msg: Any, *args, **kwargs) -> None:
        """Log a message at the specified level safely."""
        self._safe_log(level, msg, *args, **kwargs)

    def setLevel(self, level: int) -> None:
        """Set the effective level for this logger safely."""
        try:
            if self._logger is not None:
                self._logger.setLevel(level)
        except Exception as e:
            self._fallback_log(f"Failed to set log level for '{self._name}': {e}")

    def isEnabledFor(self, level: int) -> bool:
        """Check if this logger is enabled for the specified level safely."""
        try:
            if self._logger is not None:
                return self._logger.isEnabledFor(level)
            else:
                return False
        except Exception:
            return False

    def addHandler(self, handler: logging.Handler) -> None:
        """Add a handler to this logger safely."""
        try:
            if self._logger is not None:
                self._logger.addHandler(handler)
        except Exception as e:
            self._fallback_log(f"Failed to add handler to '{self._name}': {e}")

    def removeHandler(self, handler: logging.Handler) -> None:
        """Remove a handler from this logger safely."""
        try:
            if self._logger is not None:
                self._logger.removeHandler(handler)
        except Exception as e:
            self._fallback_log(f"Failed to remove handler from '{self._name}': {e}")

    @property
    def level(self) -> int:
        """Get the effective level for this logger."""
        try:
            if self._logger is not None:
                return self._logger.level
            else:
                return logging.NOTSET
        except Exception:
            return logging.NOTSET

    @property
    def handlers(self) -> list:
        """Get the list of handlers for this logger."""
        try:
            if self._logger is not None:
                return self._logger.handlers
            else:
                return []
        except Exception:
            return []

    @property
    def name(self) -> str:
        """Get the name of this logger."""
        return self._name

    def close(self) -> None:
        """Safely close the logger and remove all handlers."""
        try:
            if self._logger is not None:
                # Remove all handlers to prevent I/O errors during shutdown
                for handler in self._logger.handlers[:]:
                    with contextlib.suppress(Exception):
                        handler.close()
                    with contextlib.suppress(Exception):
                        self._logger.removeHandler(handler)
        except Exception:
            pass


# Global logger factory function
def get_safe_logger(name: str, fallback_to_stderr: bool = True) -> SafeLogger:
    """Get a safe logger instance.

    This is the primary way to obtain a SafeLogger instance. It ensures
    consistent logger creation across the application.

    Args:
        name: The name for the logger, typically __name__.
        fallback_to_stderr: If True, write to stderr when logging fails.

    Returns:
        A SafeLogger instance.
    """
    return SafeLogger(name, fallback_to_stderr)


# Convenience function to set up safe logging globally
def setup_safe_logging(
    level: int = logging.INFO,
    format_string: str | None = None,
    datefmt: str | None = None,
    debug: bool = False,
) -> None:
    """Set up safe logging configuration globally.

    This function configures the root logger with safe defaults and can be
    called at application startup.

    Args:
        level: The default logging level.
        format_string: The format string for log messages.
        datefmt: The date format string.
        debug: If True, use debug-level logging with verbose format.
    """
    try:
        if debug:
            level = logging.DEBUG
            format_string = format_string or (
                "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - "
                "[%(filename)s:%(lineno)d] - %(message)s"
            )
        else:
            format_string = format_string or (
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        datefmt = datefmt or "%Y-%m-%d %H:%M:%S"

        logging.basicConfig(level=level, format=format_string, datefmt=datefmt, force=True)
    except Exception as e:
        # Even setting up logging might fail in extreme cases
        print(f"[FALLBACK LOG] Failed to configure logging: {e}", file=sys.stderr)
