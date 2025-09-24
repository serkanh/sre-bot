"""
Shared utility functions for the SRE agent and sub-agents.
"""

import os
import logging
import sys
from typing import Optional


class ModelConfigurationError(Exception):
    """Raised when model configuration fails."""

    pass


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


def get_configured_model():
    """
    Determine model configuration based on available API keys.
    Priority: Google > Anthropic > Bedrock
    Provides clear error messages for each provider's requirements.

    Returns:
        Union[str, LiteLlm]: Model configuration object

    Raises:
        ModelConfigurationError: When no valid provider configuration is found

    Example:
        >>> from agents.sre_agent.utils import get_configured_model
        >>> model = get_configured_model()
    """
    logger = get_logger(__name__)

    # Check for Google API key first (direct model string)
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key and google_key.strip():
        model = os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash")
        logger.info(f"🚀 Using Google Gemini provider with model: {model}")
        logger.info("✓ GOOGLE_API_KEY found and validated")
        return model

    # Check for Anthropic API key (LiteLlm wrapper)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key.strip():
        try:
            from google.adk.models.lite_llm import LiteLlm
        except ImportError as e:
            logger.error(f"Failed to import LiteLlm: {e}")
            raise ModelConfigurationError(
                "LiteLlm is required for Anthropic Claude. Please ensure google-adk is properly installed."
            )

        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
        logger.info(f"🚀 Using Anthropic Claude provider with model: {model_name}")
        logger.info("✓ ANTHROPIC_API_KEY found and validated")
        return LiteLlm(model=model_name)

    # Check for Bedrock profile (LiteLlm wrapper)
    bedrock_profile = os.getenv("BEDROCK_INFERENCE_PROFILE")
    if bedrock_profile and bedrock_profile.strip():
        # Validate AWS credentials are available
        try:
            import boto3
        except ImportError:
            logger.error("❌ AWS Bedrock configuration error:")
            logger.error("   - boto3 is required for AWS Bedrock but not installed")
            logger.error("   - Please install boto3: pip install boto3")
            raise ModelConfigurationError(
                "Bedrock requires boto3 library. Please install with: pip install boto3"
            )

        try:
            # Test AWS credentials
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            logger.info(
                f"✓ AWS credentials validated for account: {identity['Account']}"
            )
        except Exception as e:
            logger.error("❌ AWS Bedrock configuration error:")
            logger.error(
                "   - BEDROCK_INFERENCE_PROFILE is set but AWS credentials are not configured"
            )
            logger.error("   - Please configure AWS credentials via:")
            logger.error(
                "     • AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
            )
            logger.error("     • AWS profile via AWS_PROFILE environment variable")
            logger.error("     • IAM role (if running on AWS)")
            logger.error(f"   - Error details: {str(e)}")
            raise ModelConfigurationError(
                "Bedrock requires valid AWS credentials. "
                "Please configure AWS access before using Bedrock models."
            )

        try:
            from google.adk.models.lite_llm import LiteLlm
        except ImportError as e:
            logger.error(f"Failed to import LiteLlm: {e}")
            raise ModelConfigurationError(
                "LiteLlm is required for AWS Bedrock. Please ensure google-adk is properly installed."
            )

        logger.info(f"🚀 Using AWS Bedrock provider with profile: {bedrock_profile}")
        return LiteLlm(model=bedrock_profile)

    # No valid configuration found - provide helpful error message
    logger.error("❌ No AI provider configured!")
    logger.error("")
    logger.error("Please configure one of the following providers:")
    logger.error("")
    logger.error("1. Google Gemini (Recommended for Google Cloud users):")
    logger.error("   export GOOGLE_API_KEY='your-api-key'")
    logger.error("   export GOOGLE_AI_MODEL='gemini-2.0-flash'  # optional")
    logger.error("")
    logger.error("2. Anthropic Claude (Via LiteLLM):")
    logger.error("   export ANTHROPIC_API_KEY='your-api-key'")
    logger.error("   export ANTHROPIC_MODEL='claude-3-5-sonnet-20240620'  # optional")
    logger.error("")
    logger.error("3. AWS Bedrock (Requires AWS credentials):")
    logger.error("   export BEDROCK_INFERENCE_PROFILE='arn:aws:bedrock:...'")
    logger.error("   export AWS_ACCESS_KEY_ID='your-access-key'")
    logger.error("   export AWS_SECRET_ACCESS_KEY='your-secret-key'")
    logger.error("   # OR use AWS_PROFILE for named profiles")
    logger.error("")
    logger.error("Priority order: Google > Anthropic > Bedrock")
    logger.error("See agents/.env.example for complete configuration examples")

    raise ModelConfigurationError(
        "No AI provider API key found. Please set GOOGLE_API_KEY, "
        "ANTHROPIC_API_KEY, or BEDROCK_INFERENCE_PROFILE. "
        "See logs above for detailed configuration instructions."
    )
