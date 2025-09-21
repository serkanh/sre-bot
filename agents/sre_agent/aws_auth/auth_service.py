"""
AWS Authentication Service Core.

Provides STS role assumption, credential caching, and boto3 client factory
for AWS service interactions across multiple accounts.
"""

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Optional, Any, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

from .config import AWSAuthConfig, RoleConfig, AWSCredentials
from .exceptions import (
    AWSAuthError,
    RoleNotFoundError,
    AssumeRoleError,
    ClientCreationError,
    create_auth_error_from_boto_error,
)
from ..utils import get_logger

# Thread pool for running blocking boto3 operations
_thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="aws_auth")

# Configure logging
logger = get_logger(__name__)


class AWSAuthService:
    """
    AWS Authentication Service for role assumption and client creation.

    Provides centralized AWS authentication with STS role assumption,
    credential caching, and boto3 client factory functionality.
    """

    def __init__(self, config: Optional[AWSAuthConfig] = None):
        """
        Initialize AWS authentication service.

        Args:
            config: AWS authentication configuration. If None, loads from environment.
        """
        self.config = config or AWSAuthConfig.from_env()
        self._credential_cache: Dict[str, Tuple[AWSCredentials, float]] = {}
        self._sts_client = None
        logger.info(
            f"AWS Auth Service initialized with {len(self.config.roles)} role configurations"
        )

    def _get_sts_client(self) -> Any:
        """
        Get the STS client, creating it lazily when first needed.

        Returns:
            boto3.client: STS client

        Raises:
            AWSAuthError: If STS client creation fails
        """
        if self._sts_client is None:
            try:
                # Use default profile if configured
                if self.config.default_profile:
                    session = boto3.Session(profile_name=self.config.default_profile)
                    self._sts_client = session.client(
                        "sts", region_name=self.config.default_region
                    )
                else:
                    self._sts_client = boto3.client(
                        "sts", region_name=self.config.default_region
                    )
                logger.debug("STS client created successfully")
            except (NoCredentialsError, ProfileNotFound) as e:
                logger.error(f"Failed to create STS client: {e}")
                raise create_auth_error_from_boto_error(e, "STS client creation")
            except Exception as e:
                logger.error(f"Unexpected error creating STS client: {e}")
                raise AWSAuthError(
                    f"Failed to initialize STS client: {e}", original_error=e
                )

        return self._sts_client

    async def _run_in_executor(self, func, *args, **kwargs):
        """
        Run a blocking function in a thread pool executor.

        Args:
            func: Blocking function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Any: Result of the function execution
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_thread_pool, lambda: func(*args, **kwargs))

    def _credentials_valid(self, role_name: str) -> bool:
        """
        Check if cached credentials are still valid.

        Args:
            role_name: Name of the role to check

        Returns:
            bool: True if credentials are valid and not expired
        """
        if not self.config.enable_caching:
            return False

        if role_name not in self._credential_cache:
            return False

        credentials, cache_time = self._credential_cache[role_name]

        # Check cache TTL
        if time.time() - cache_time > self.config.cache_ttl_seconds:
            logger.debug(f"Cached credentials for {role_name} expired due to TTL")
            return False

        # Check credential expiration (with 5-minute buffer for safety)
        try:
            expiration = datetime.fromisoformat(
                credentials.expiration.replace("Z", "+00:00")
            )
            buffer_time = 5 * 60  # 5 minutes buffer
            if (expiration.timestamp() - time.time()) < buffer_time:
                logger.debug(f"Cached credentials for {role_name} will expire soon")
                return False
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse expiration time for {role_name}: {e}")
            return False

        return True

    async def _assume_role(self, role_config: RoleConfig) -> AWSCredentials:
        """
        Assume AWS role and return temporary credentials.

        Args:
            role_config: Configuration for the role to assume

        Returns:
            AWSCredentials: Temporary credentials for the assumed role

        Raises:
            AssumeRoleError: If role assumption fails
            AWSAuthError: For other authentication errors
        """
        sts_client = self._get_sts_client()

        # Create unique session name with timestamp for audit trail
        session_name = f"{role_config.role_session_name}_{int(time.time())}"

        params = {
            "RoleArn": role_config.role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": role_config.duration_seconds,
        }

        # Add external ID if configured
        if role_config.external_id:
            params["ExternalId"] = role_config.external_id

        logger.info(
            f"Assuming role: {role_config.role_arn} with session: {session_name}"
        )

        try:
            # Execute role assumption in thread pool
            response = await self._run_in_executor(sts_client.assume_role, **params)

            credentials_data = response["Credentials"]
            credentials = AWSCredentials(
                access_key_id=credentials_data["AccessKeyId"],
                secret_access_key=credentials_data["SecretAccessKey"],
                session_token=credentials_data["SessionToken"],
                expiration=credentials_data["Expiration"].isoformat(),
                region=self.config.default_region,
            )

            logger.info(f"Successfully assumed role {role_config.role_arn}")
            return credentials

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            logger.error(
                f"AWS ClientError assuming role {role_config.role_arn}: {error_code} - {error_message}"
            )

            if error_code == "AccessDenied":
                raise AssumeRoleError(
                    "Access denied - check IAM permissions and trust relationships",
                    role_config.role_arn,
                    error_code,
                    e,
                )
            elif error_code == "InvalidParameterValue":
                raise AssumeRoleError(
                    f"Invalid parameter value: {error_message}",
                    role_config.role_arn,
                    error_code,
                    e,
                )
            elif error_code == "MalformedPolicyDocument":
                raise AssumeRoleError(
                    "Malformed policy document in role trust policy",
                    role_config.role_arn,
                    error_code,
                    e,
                )
            else:
                raise AssumeRoleError(
                    f"AWS error: {error_message}", role_config.role_arn, error_code, e
                )

        except Exception as e:
            logger.error(f"Unexpected error assuming role {role_config.role_arn}: {e}")
            raise AWSAuthError(
                f"Unexpected error during role assumption: {e}", original_error=e
            )

    async def _refresh_credentials(self, role_name: str) -> None:
        """
        Refresh cached credentials for a role.

        Args:
            role_name: Name of the role to refresh credentials for

        Raises:
            RoleNotFoundError: If role configuration is not found
            AWSAuthError: For other authentication errors
        """
        role_config = self.config.get_role(role_name)
        if not role_config:
            raise RoleNotFoundError(role_name)

        logger.debug(f"Refreshing credentials for role: {role_name}")
        credentials = await self._assume_role(role_config)

        if self.config.enable_caching:
            self._credential_cache[role_name] = (credentials, time.time())
            logger.debug(f"Cached credentials for role: {role_name}")

    async def get_client(
        self,
        service: str,
        role_name: Optional[str] = None,
        region: Optional[str] = None,
        **client_kwargs,
    ) -> Any:
        """
        Get authenticated boto3 client for any AWS service.

        Args:
            service: AWS service name (e.g., 's3', 'ec2', 'cost-explorer')
            role_name: Optional role name to assume. If None, uses default credentials.
            region: Optional region override. If None, uses default from config.
            **client_kwargs: Additional kwargs passed to boto3.client()

        Returns:
            boto3.client: Authenticated AWS service client

        Raises:
            RoleNotFoundError: If specified role is not found
            ClientCreationError: If client creation fails
            AWSAuthError: For other authentication errors
        """
        try:
            target_region = region or self.config.default_region

            if role_name:
                # Use role-based authentication
                if not self._credentials_valid(role_name):
                    await self._refresh_credentials(role_name)

                credentials, _ = self._credential_cache[role_name]
                logger.debug(
                    f"Creating {service} client with assumed role: {role_name}"
                )

                return boto3.client(
                    service,
                    aws_access_key_id=credentials.access_key_id,
                    aws_secret_access_key=credentials.secret_access_key,
                    aws_session_token=credentials.session_token,
                    region_name=target_region,
                    **client_kwargs,
                )
            else:
                # Use default credentials (backward compatibility)
                logger.debug(f"Creating {service} client with default credentials")

                if self.config.default_profile:
                    session = boto3.Session(profile_name=self.config.default_profile)
                    return session.client(
                        service, region_name=target_region, **client_kwargs
                    )
                else:
                    return boto3.client(
                        service, region_name=target_region, **client_kwargs
                    )

        except (RoleNotFoundError, AWSAuthError):
            # Re-raise our custom exceptions as-is
            raise
        except (NoCredentialsError, ProfileNotFound) as e:
            logger.error(f"Credential error creating {service} client: {e}")
            raise create_auth_error_from_boto_error(e, f"{service} client creation")
        except Exception as e:
            logger.error(f"Unexpected error creating {service} client: {e}")
            raise ClientCreationError(service, original_error=e)

    async def test_credentials(self, role_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Test AWS credentials by calling STS GetCallerIdentity.

        Args:
            role_name: Optional role name to test. If None, tests default credentials.

        Returns:
            Dict containing caller identity information

        Raises:
            AWSAuthError: If credential test fails
        """
        try:
            sts_client = await self.get_client("sts", role_name=role_name)
            response = await self._run_in_executor(sts_client.get_caller_identity)

            logger.info(
                f"Credential test successful for role: {role_name or 'default'}"
            )
            return {
                "account": response.get("Account"),
                "user_id": response.get("UserId"),
                "arn": response.get("Arn"),
                "role_name": role_name,
            }

        except Exception as e:
            logger.error(
                f"Credential test failed for role {role_name or 'default'}: {e}"
            )
            raise create_auth_error_from_boto_error(e, "credential test")

    def clear_cache(self, role_name: Optional[str] = None) -> None:
        """
        Clear cached credentials.

        Args:
            role_name: Optional specific role to clear. If None, clears all cached credentials.
        """
        if role_name:
            if role_name in self._credential_cache:
                del self._credential_cache[role_name]
                logger.info(f"Cleared cached credentials for role: {role_name}")
        else:
            self._credential_cache.clear()
            logger.info("Cleared all cached credentials")

    def get_cache_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about cached credentials.

        Returns:
            Dict containing cache information for each role
        """
        cache_info = {}
        for role_name, (credentials, cache_time) in self._credential_cache.items():
            try:
                expiration = datetime.fromisoformat(
                    credentials.expiration.replace("Z", "+00:00")
                )
                cache_info[role_name] = {
                    "cached_at": datetime.fromtimestamp(
                        cache_time, tz=timezone.utc
                    ).isoformat(),
                    "expires_at": expiration.isoformat(),
                    "valid": self._credentials_valid(role_name),
                    "region": credentials.region,
                }
            except Exception as e:
                cache_info[role_name] = {
                    "error": f"Failed to parse cache info: {e}",
                    "valid": False,
                }

        return cache_info


# Global service instance (optional - for simpler usage patterns)
_global_auth_service: Optional[AWSAuthService] = None


def get_auth_service(config: Optional[AWSAuthConfig] = None) -> AWSAuthService:
    """
    Get global AWS authentication service instance.

    Args:
        config: Optional configuration. If None, uses environment-based config.

    Returns:
        AWSAuthService: Global authentication service instance
    """
    global _global_auth_service

    if _global_auth_service is None or config is not None:
        _global_auth_service = AWSAuthService(config)

    return _global_auth_service


async def get_authenticated_client(
    service: str,
    role_name: Optional[str] = None,
    region: Optional[str] = None,
    config: Optional[AWSAuthConfig] = None,
    **client_kwargs,
) -> Any:
    """
    Convenience function to get authenticated AWS client.

    Args:
        service: AWS service name
        role_name: Optional role name to assume
        region: Optional region override
        config: Optional authentication config
        **client_kwargs: Additional client arguments

    Returns:
        boto3.client: Authenticated AWS service client
    """
    auth_service = get_auth_service(config)
    return await auth_service.get_client(service, role_name, region, **client_kwargs)
