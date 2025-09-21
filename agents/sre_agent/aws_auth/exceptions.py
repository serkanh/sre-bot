"""
AWS Authentication Custom Exceptions.

Defines custom exceptions for authentication failures with specific error codes
and helpful error messages for troubleshooting.
"""

from typing import Optional


class AWSAuthError(Exception):
    """Base exception for AWS authentication errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize AWS authentication error.

        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.original_error = original_error

    def __str__(self) -> str:
        """Return formatted error message."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class AuthenticationError(AWSAuthError):
    """Exception raised when AWS role assumption fails due to authentication issues."""

    def __init__(
        self,
        message: str,
        role_arn: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize authentication error.

        Args:
            message: Human-readable error message
            role_arn: Optional role ARN that failed authentication
            original_error: Original exception that caused this error
        """
        error_code = "AUTH_FAILED"
        if role_arn:
            message = f"{message} (Role: {role_arn})"
        super().__init__(message, error_code, original_error)
        self.role_arn = role_arn


class ConfigurationError(AWSAuthError):
    """Exception raised when AWS authentication configuration is invalid."""

    def __init__(
        self,
        message: str,
        config_field: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize configuration error.

        Args:
            message: Human-readable error message
            config_field: Optional configuration field that caused the error
            original_error: Original exception that caused this error
        """
        error_code = "CONFIG_INVALID"
        if config_field:
            message = f"{message} (Field: {config_field})"
        super().__init__(message, error_code, original_error)
        self.config_field = config_field


class CredentialExpiredError(AWSAuthError):
    """Exception raised when AWS credentials have expired."""

    def __init__(
        self,
        message: str = "AWS credentials have expired",
        role_name: Optional[str] = None,
    ):
        """
        Initialize credential expired error.

        Args:
            message: Human-readable error message
            role_name: Optional role name for which credentials expired
        """
        error_code = "CREDENTIALS_EXPIRED"
        if role_name:
            message = f"{message} (Role: {role_name})"
        super().__init__(message, error_code)
        self.role_name = role_name


class RoleNotFoundError(AWSAuthError):
    """Exception raised when a requested role configuration is not found."""

    def __init__(self, role_name: str):
        """
        Initialize role not found error.

        Args:
            role_name: Name of the role that was not found
        """
        message = f"Role configuration not found: {role_name}"
        error_code = "ROLE_NOT_FOUND"
        super().__init__(message, error_code)
        self.role_name = role_name


class AssumeRoleError(AWSAuthError):
    """Exception raised when AWS STS AssumeRole operation fails."""

    def __init__(
        self,
        message: str,
        role_arn: str,
        aws_error_code: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize assume role error.

        Args:
            message: Human-readable error message
            role_arn: ARN of the role that failed to be assumed
            aws_error_code: AWS-specific error code from the STS response
            original_error: Original boto3/botocore exception
        """
        error_code = (
            f"ASSUME_ROLE_FAILED_{aws_error_code}"
            if aws_error_code
            else "ASSUME_ROLE_FAILED"
        )
        full_message = f"{message} (Role: {role_arn})"
        super().__init__(full_message, error_code, original_error)
        self.role_arn = role_arn
        self.aws_error_code = aws_error_code


class ClientCreationError(AWSAuthError):
    """Exception raised when AWS client creation fails."""

    def __init__(
        self,
        service: str,
        message: str = "Failed to create AWS client",
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize client creation error.

        Args:
            service: AWS service name for which client creation failed
            message: Human-readable error message
            original_error: Original exception that caused this error
        """
        error_code = "CLIENT_CREATION_FAILED"
        full_message = f"{message} for service: {service}"
        super().__init__(full_message, error_code, original_error)
        self.service = service


def create_auth_error_from_boto_error(
    boto_error, context: str = "AWS operation"
) -> AWSAuthError:
    """
    Create appropriate AWSAuthError from a boto3/botocore exception.

    Args:
        boto_error: The original boto3/botocore exception
        context: Context description for better error messages

    Returns:
        AWSAuthError: Appropriate authentication error based on the boto error
    """
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

    if isinstance(boto_error, NoCredentialsError):
        return AuthenticationError(
            "AWS credentials not found. Please configure AWS credentials or check environment variables.",
            original_error=boto_error,
        )

    if isinstance(boto_error, ProfileNotFound):
        return ConfigurationError(
            f"AWS profile not found: {boto_error}",
            config_field="aws_profile",
            original_error=boto_error,
        )

    if isinstance(boto_error, ClientError):
        error_code = boto_error.response.get("Error", {}).get("Code", "Unknown")
        error_message = boto_error.response.get("Error", {}).get(
            "Message", str(boto_error)
        )

        if error_code == "AccessDenied":
            return AuthenticationError(
                f"Access denied during {context}: {error_message}",
                original_error=boto_error,
            )
        elif error_code == "InvalidParameterValue":
            return ConfigurationError(
                f"Invalid parameter during {context}: {error_message}",
                original_error=boto_error,
            )
        elif error_code == "TokenRefreshRequired":
            return CredentialExpiredError(
                f"AWS token refresh required during {context}: {error_message}"
            )
        else:
            return AssumeRoleError(
                f"AWS error during {context}: {error_message}",
                role_arn="unknown",
                aws_error_code=error_code,
                original_error=boto_error,
            )

    # Generic fallback for unknown errors
    return AWSAuthError(
        f"Unknown error during {context}: {str(boto_error)}",
        error_code="UNKNOWN_ERROR",
        original_error=boto_error,
    )
