"""
AWS Authentication Module.

Provides centralized AWS authentication with STS role assumption,
credential caching, and boto3 client factory functionality.

Main exports:
- AWSAuthService: Core authentication service class
- AWSAuthConfig: Configuration management
- RoleConfig: Role configuration model
- get_authenticated_client: Convenience function for client creation
- get_auth_service: Global service instance

Example usage:
    # Simple usage with environment configuration
    from agents.sre_agent.aws_auth import get_authenticated_client

    # Get S3 client with default credentials
    s3_client = await get_authenticated_client('s3')

    # Get EC2 client with assumed role
    ec2_client = await get_authenticated_client('ec2', role_name='production')

    # Advanced usage with custom configuration
    from agents.sre_agent.aws_auth import AWSAuthService, AWSAuthConfig, RoleConfig

    config = AWSAuthConfig(
        roles={
            'prod': RoleConfig(
                role_arn='arn:aws:iam::123456789012:role/MyRole',
                account_id='123456789012'
            )
        }
    )
    auth_service = AWSAuthService(config)
    client = await auth_service.get_client('s3', role_name='prod')
"""

__version__ = "1.0.0"
__author__ = "SRE Bot Team"

# Core classes
from .auth_service import AWSAuthService, get_auth_service, get_authenticated_client
from .config import AWSAuthConfig, RoleConfig, AWSCredentials
from .exceptions import (
    AWSAuthError,
    AuthenticationError,
    ConfigurationError,
    CredentialExpiredError,
    RoleNotFoundError,
    AssumeRoleError,
    ClientCreationError,
    create_auth_error_from_boto_error,
)


# Convenience functions
async def create_client(
    service: str, role_name: str = None, region: str = None, **kwargs
):
    """
    Create authenticated AWS client (convenience function).

    Args:
        service: AWS service name (e.g., 's3', 'ec2')
        role_name: Optional role to assume
        region: Optional region override
        **kwargs: Additional client arguments

    Returns:
        boto3.client: Authenticated AWS service client

    Example:
        # Create S3 client with default credentials
        s3 = await create_client('s3')

        # Create EC2 client with assumed role
        ec2 = await create_client('ec2', role_name='production')
    """
    return await get_authenticated_client(service, role_name, region, **kwargs)


async def test_auth(role_name: str = None):
    """
    Test AWS authentication credentials.

    Args:
        role_name: Optional role to test

    Returns:
        Dict containing caller identity information

    Example:
        # Test default credentials
        identity = await test_auth()

        # Test specific role
        identity = await test_auth('production')
    """
    auth_service = get_auth_service()
    return await auth_service.test_credentials(role_name)


def configure_auth(
    default_region: str = "us-east-1",
    default_profile: str = None,
    enable_caching: bool = True,
    cache_ttl_seconds: int = 3000,
    **roles,
) -> AWSAuthConfig:
    """
    Create AWS authentication configuration.

    Args:
        default_region: Default AWS region
        default_profile: Default AWS profile
        enable_caching: Enable credential caching
        cache_ttl_seconds: Cache TTL in seconds
        **roles: Role configurations as keyword arguments

    Returns:
        AWSAuthConfig: Authentication configuration

    Example:
        config = configure_auth(
            default_region='us-west-2',
            production=RoleConfig(
                role_arn='arn:aws:iam::123456789012:role/ProdRole',
                account_id='123456789012'
            )
        )
    """
    role_configs = {}
    for name, role_config in roles.items():
        if isinstance(role_config, RoleConfig):
            role_configs[name] = role_config
        elif isinstance(role_config, dict):
            role_configs[name] = RoleConfig(**role_config)
        else:
            raise ValueError(f"Invalid role configuration for {name}: {role_config}")

    return AWSAuthConfig(
        default_region=default_region,
        default_profile=default_profile,
        enable_caching=enable_caching,
        cache_ttl_seconds=cache_ttl_seconds,
        roles=role_configs,
    )


def create_role_config(role_arn: str, account_id: str, **kwargs) -> RoleConfig:
    """
    Create role configuration with validation.

    Args:
        role_arn: ARN of the IAM role
        account_id: AWS account ID (12 digits)
        **kwargs: Additional role configuration options

    Returns:
        RoleConfig: Validated role configuration

    Example:
        role = create_role_config(
            role_arn='arn:aws:iam::123456789012:role/MyRole',
            account_id='123456789012',
            duration_seconds=7200
        )
    """
    return RoleConfig(role_arn=role_arn, account_id=account_id, **kwargs)


# Export all public APIs
__all__ = [
    # Core classes
    "AWSAuthService",
    "AWSAuthConfig",
    "RoleConfig",
    "AWSCredentials",
    # Exceptions
    "AWSAuthError",
    "AuthenticationError",
    "ConfigurationError",
    "CredentialExpiredError",
    "RoleNotFoundError",
    "AssumeRoleError",
    "ClientCreationError",
    "create_auth_error_from_boto_error",
    # Service functions
    "get_auth_service",
    "get_authenticated_client",
    # Convenience functions
    "create_client",
    "test_auth",
    "configure_auth",
    "create_role_config",
    # Module metadata
    "__version__",
    "__author__",
]
