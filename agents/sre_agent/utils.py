"""
Shared utility functions for the SRE agent and sub-agents.
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
    Set up a standardized logger for SRE bot modules.

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
        >>> logger.info("Agent initialized successfully")
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
    Get a logger with standard SRE bot configuration.

    This is a convenience function that calls setup_logger with default settings.
    Use this for quick logger setup in most modules.

    Args:
        name (str): Logger name (typically __name__ from the calling module)

    Returns:
        logging.Logger: Configured logger instance

    Example:
        >>> from agents.sre_agent.utils import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Operation completed successfully")
    """
    return setup_logger(name)


# Module-level logger for this utils module
logger = get_logger(__name__)


def load_instruction_from_file(file_path: str) -> str:
    """
    Load instruction text from a markdown file.

    This utility function is commonly used by agents to load their system prompts
    and instructions from external markdown files, allowing for better separation
    of agent logic and prompt content.

    Args:
        file_path (str): Path to the markdown file containing the instruction text

    Returns:
        str: The content of the file as a string, or an error message if loading fails

    Example:
        >>> instruction = load_instruction_from_file("prompts/system_prompt.md")
        >>> agent = Agent(instruction=instruction, ...)
    """
    try:
        if not os.path.exists(file_path):
            error_msg = f"Instruction file not found: {file_path}"
            logger.error(error_msg)
            return error_msg

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            warning_msg = f"Instruction file is empty: {file_path}"
            logger.warning(warning_msg)
            return warning_msg

        logger.debug(f"Successfully loaded instruction from {file_path}")
        return content

    except Exception as e:
        error_msg = f"Error loading instruction file {file_path}: {e}"
        logger.error(error_msg)
        return error_msg
