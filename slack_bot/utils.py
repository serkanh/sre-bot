"""
Shared utility functions for the Slack bot.
"""

import os
import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: Optional[str] = None,
    format_string: Optional[str] = None,
    include_timestamp: bool = True,
    include_module: bool = True,
) -> logging.Logger:
    """
    Set up a standardized logger for Slack bot modules.

    This utility provides consistent logging configuration across all modules
    with environment-based level control and standardized formatting.

    Args:
        name (str): Logger name (typically __name__ from the calling module)
        level (Optional[str]): Log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                              If None, uses LOG_LEVEL environment variable or defaults to INFO
        format_string (Optional[str]): Custom format string for log messages
        include_timestamp (bool): Whether to include timestamp in log format
        include_module (bool): Whether to include module name in log format

    Returns:
        logging.Logger: Configured logger instance

    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Slack bot initialized successfully")
        >>>
        >>> # Custom configuration
        >>> logger = setup_logger(__name__, level="DEBUG", include_timestamp=False)
    """
    # Get or create logger
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Determine log level
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    try:
        log_level = getattr(logging, level)
    except AttributeError:
        log_level = logging.INFO
        print(
            f"Warning: Invalid log level '{level}', defaulting to INFO", file=sys.stderr
        )

    logger.setLevel(log_level)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Build format string
    if format_string is None:
        format_parts = []

        if include_timestamp:
            format_parts.append("%(asctime)s")

        format_parts.append("%(levelname)s")

        if include_module:
            format_parts.append("%(name)s")

        format_parts.append("%(message)s")

        format_string = " - ".join(format_parts)

    # Create formatter and add to handler
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with standard Slack bot configuration.

    This is a convenience function that calls setup_logger with default settings.
    Use this for quick logger setup in most modules.

    Args:
        name (str): Logger name (typically __name__ from the calling module)

    Returns:
        logging.Logger: Configured logger instance

    Example:
        >>> from utils import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Message processed successfully")
    """
    return setup_logger(name)
