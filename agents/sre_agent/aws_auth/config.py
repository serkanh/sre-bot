"""
AWS Authentication Configuration Module.

Provides Pydantic models for AWS role configuration, environment variable loading,
and validation for the AWS authentication service.
"""

import os
import json
from typing import Dict, Optional
from pydantic import BaseModel, Field, validator
from ..utils import get_logger

logger = get_logger(__name__)


class RoleConfig(BaseModel):
    """Configuration for a single AWS role."""

    role_arn: str = Field(..., description="ARN of the role to assume")
    account_id: str = Field(..., description="AWS account ID")
    role_session_name: str = Field(
        default="SREBotSession", description="Session name for role assumption"
    )
    duration_seconds: int = Field(
        default=3600, ge=900, le=43200, description="Session duration in seconds"
    )
    external_id: Optional[str] = Field(
        None, description="External ID for third-party access"
    )

    @validator("role_arn")
    def validate_role_arn(cls, v):
        """Validate that role_arn follows proper ARN format."""
        if not v.startswith("arn:aws:iam::"):
            raise ValueError(
                "role_arn must be a valid IAM role ARN starting with arn:aws:iam::"
            )
        if ":role/" not in v:
            raise ValueError("role_arn must contain :role/ and specify a role name")
        return v

    @validator("account_id")
    def validate_account_id(cls, v):
        """Validate that account_id is a 12-digit string."""
        if not v.isdigit() or len(v) != 12:
            raise ValueError("account_id must be a 12-digit string")
        return v

    @validator("role_session_name")
    def validate_session_name(cls, v):
        """Validate session name follows AWS requirements."""
        import re

        if not re.match(r"^[\w+=,.@-]+$", v):
            raise ValueError(
                "role_session_name can only contain alphanumeric characters and +=,.@-"
            )
        if len(v) > 64:
            raise ValueError("role_session_name must be 64 characters or less")
        return v


class AWSCredentials(BaseModel):
    """Temporary AWS credentials from STS."""

    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str
    region: str


class AWSAuthConfig(BaseModel):
    """Main configuration for AWS authentication."""

    default_region: str = Field(default="us-east-1", description="Default AWS region")
    default_profile: Optional[str] = Field(None, description="Default AWS profile")
    roles: Dict[str, RoleConfig] = Field(
        default_factory=dict, description="Named role configurations"
    )
    enable_role_chaining: bool = Field(default=False, description="Allow role chaining")
    enable_caching: bool = Field(default=True, description="Enable credential caching")
    cache_ttl_seconds: int = Field(
        default=3000, ge=300, le=43200, description="Cache TTL in seconds"
    )

    @classmethod
    def from_env(cls) -> "AWSAuthConfig":
        """
        Create configuration from environment variables.

        Environment variables:
        - AWS_AUTH_DEFAULT_REGION: Default AWS region
        - AWS_AUTH_DEFAULT_PROFILE: Default AWS profile
        - AWS_AUTH_ROLES: JSON string of role configurations
        - AWS_AUTH_ENABLE_CACHING: Enable credential caching
        - AWS_AUTH_CACHE_TTL: Cache TTL in seconds
        - AWS_AUTH_ENABLE_ROLE_CHAINING: Enable role chaining

        Returns:
            AWSAuthConfig: Configuration instance
        """
        config_data = {}

        # Basic configuration
        if default_region := os.getenv("AWS_AUTH_DEFAULT_REGION"):
            config_data["default_region"] = default_region
        elif aws_region := os.getenv("AWS_REGION"):
            config_data["default_region"] = aws_region

        if default_profile := os.getenv("AWS_AUTH_DEFAULT_PROFILE"):
            config_data["default_profile"] = default_profile
        elif aws_profile := os.getenv("AWS_PROFILE"):
            config_data["default_profile"] = aws_profile

        # Feature flags
        if enable_caching := os.getenv("AWS_AUTH_ENABLE_CACHING"):
            config_data["enable_caching"] = enable_caching.lower() in (
                "true",
                "1",
                "yes",
            )

        if cache_ttl := os.getenv("AWS_AUTH_CACHE_TTL"):
            try:
                config_data["cache_ttl_seconds"] = int(cache_ttl)
            except ValueError:
                logger.warning(
                    f"Invalid AWS_AUTH_CACHE_TTL value: {cache_ttl}, using default"
                )

        if enable_chaining := os.getenv("AWS_AUTH_ENABLE_ROLE_CHAINING"):
            config_data["enable_role_chaining"] = enable_chaining.lower() in (
                "true",
                "1",
                "yes",
            )

        # Role configurations
        if roles_json := os.getenv("AWS_AUTH_ROLES"):
            try:
                roles_data = json.loads(roles_json)
                roles = {}
                for name, role_data in roles_data.items():
                    roles[name] = RoleConfig(**role_data)
                config_data["roles"] = roles
                logger.info(f"Loaded {len(roles)} role configurations from environment")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AWS_AUTH_ROLES: {e}")
                config_data["roles"] = {}

        # Single role configuration (simplified setup)
        default_role_arn = os.getenv("AWS_AUTH_DEFAULT_ROLE_ARN")
        default_account_id = os.getenv("AWS_AUTH_DEFAULT_ACCOUNT_ID")

        if default_role_arn and default_account_id:
            default_role_name = os.getenv("AWS_AUTH_DEFAULT_ROLE_NAME", "default")
            config_data.setdefault("roles", {})[default_role_name] = RoleConfig(
                role_arn=default_role_arn,
                account_id=default_account_id,
                role_session_name=os.getenv(
                    "AWS_AUTH_DEFAULT_SESSION_NAME", "SREBotSession"
                ),
                duration_seconds=int(os.getenv("AWS_AUTH_DEFAULT_DURATION", "3600")),
                external_id=os.getenv("AWS_AUTH_DEFAULT_EXTERNAL_ID"),
            )
            logger.info(f"Configured default role: {default_role_name}")

        return cls(**config_data)

    def get_role(self, role_name: str) -> Optional[RoleConfig]:
        """
        Get role configuration by name.

        Args:
            role_name: Name of the role configuration

        Returns:
            RoleConfig if found, None otherwise
        """
        return self.roles.get(role_name)

    def add_role(self, name: str, role_config: RoleConfig) -> None:
        """
        Add a role configuration.

        Args:
            name: Name for the role configuration
            role_config: Role configuration to add
        """
        self.roles[name] = role_config
        logger.info(f"Added role configuration: {name}")

    def list_roles(self) -> list[str]:
        """
        List all configured role names.

        Returns:
            List of role names
        """
        return list(self.roles.keys())
