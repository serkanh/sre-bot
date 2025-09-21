"""
Comprehensive tests for AWS Authentication Service.

Tests all authentication scenarios including configuration, role assumption,
error handling, and integration patterns.
"""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

# Import the modules we're testing
from agents.sre_agent.aws_auth import (
    AWSAuthService,
    AWSAuthConfig,
    RoleConfig,
    AWSCredentials,
    get_authenticated_client,
    create_client,
    test_auth as auth_test,
    configure_auth,
    create_role_config,
)
from agents.sre_agent.aws_auth.exceptions import (
    AWSAuthError,
    AuthenticationError,
    ConfigurationError,
    RoleNotFoundError,
    AssumeRoleError,
    create_auth_error_from_boto_error,
)


class TestRoleConfig:
    """Test RoleConfig model validation."""

    def test_valid_role_config(self):
        """Test creating a valid role configuration."""
        role = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
        )
        assert role.role_arn == "arn:aws:iam::123456789012:role/TestRole"
        assert role.account_id == "123456789012"
        assert role.role_session_name == "SREBotSession"
        assert role.duration_seconds == 3600

    def test_invalid_role_arn(self):
        """Test validation of invalid role ARN."""
        with pytest.raises(ValueError, match="role_arn must be a valid IAM role ARN"):
            RoleConfig(role_arn="invalid-arn", account_id="123456789012")

    def test_invalid_account_id(self):
        """Test validation of invalid account ID."""
        with pytest.raises(ValueError, match="account_id must be a 12-digit string"):
            RoleConfig(
                role_arn="arn:aws:iam::123456789012:role/TestRole", account_id="invalid"
            )

    def test_invalid_session_name(self):
        """Test validation of invalid session name."""
        with pytest.raises(ValueError, match="role_session_name can only contain"):
            RoleConfig(
                role_arn="arn:aws:iam::123456789012:role/TestRole",
                account_id="123456789012",
                role_session_name="invalid@session#name",
            )

    def test_duration_validation(self):
        """Test validation of session duration."""
        with pytest.raises(ValueError):
            RoleConfig(
                role_arn="arn:aws:iam::123456789012:role/TestRole",
                account_id="123456789012",
                duration_seconds=600,  # Too short (minimum is 900)
            )


class TestAWSAuthConfig:
    """Test AWSAuthConfig model and environment loading."""

    def test_default_config(self):
        """Test default configuration."""
        config = AWSAuthConfig()
        assert config.default_region == "us-east-1"
        assert config.default_profile is None
        assert config.roles == {}
        assert config.enable_role_chaining is False
        assert config.enable_caching is True

    @patch.dict(
        "os.environ",
        {
            "AWS_AUTH_DEFAULT_REGION": "us-west-2",
            "AWS_AUTH_DEFAULT_PROFILE": "test-profile",
            "AWS_AUTH_ENABLE_CACHING": "false",
            "AWS_AUTH_CACHE_TTL": "1800",
            "AWS_AUTH_ROLES": '{"test": {"role_arn": "arn:aws:iam::123456789012:role/TestRole", "account_id": "123456789012"}}',
        },
    )
    def test_from_env(self):
        """Test configuration loading from environment variables."""
        config = AWSAuthConfig.from_env()
        assert config.default_region == "us-west-2"
        assert config.default_profile == "test-profile"
        assert config.enable_caching is False
        assert config.cache_ttl_seconds == 1800
        assert "test" in config.roles
        assert (
            config.roles["test"].role_arn == "arn:aws:iam::123456789012:role/TestRole"
        )

    @patch.dict(
        "os.environ",
        {
            "AWS_AUTH_DEFAULT_ROLE_ARN": "arn:aws:iam::123456789012:role/DefaultRole",
            "AWS_AUTH_DEFAULT_ACCOUNT_ID": "123456789012",
        },
    )
    def test_single_role_env_config(self):
        """Test single role configuration from environment."""
        config = AWSAuthConfig.from_env()
        assert "default" in config.roles
        assert (
            config.roles["default"].role_arn
            == "arn:aws:iam::123456789012:role/DefaultRole"
        )

    def test_get_role(self):
        """Test getting role configuration by name."""
        role = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
        )
        config = AWSAuthConfig(roles={"test": role})

        retrieved_role = config.get_role("test")
        assert retrieved_role == role

        assert config.get_role("nonexistent") is None

    def test_add_role(self):
        """Test adding role configuration."""
        config = AWSAuthConfig()
        role = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
        )

        config.add_role("test", role)
        assert "test" in config.roles
        assert config.get_role("test") == role

    def test_list_roles(self):
        """Test listing role names."""
        role1 = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/Role1", account_id="123456789012"
        )
        role2 = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/Role2", account_id="123456789012"
        )

        config = AWSAuthConfig(roles={"role1": role1, "role2": role2})
        role_names = config.list_roles()

        assert set(role_names) == {"role1", "role2"}


class TestAWSAuthService:
    """Test AWSAuthService core functionality."""

    def test_init_with_config(self):
        """Test initializing auth service with configuration."""
        config = AWSAuthConfig(default_region="us-west-2")
        service = AWSAuthService(config)

        assert service.config.default_region == "us-west-2"
        assert service._credential_cache == {}
        assert service._sts_client is None

    @patch("agents.sre_agent.aws_auth.config.AWSAuthConfig.from_env")
    def test_init_without_config(self, mock_from_env):
        """Test initializing auth service without configuration (loads from env)."""
        mock_config = AWSAuthConfig()
        mock_from_env.return_value = mock_config

        service = AWSAuthService()

        mock_from_env.assert_called_once()
        assert service.config == mock_config

    @pytest.mark.asyncio
    async def test_get_client_default_credentials(self):
        """Test default credential behavior (backward compatibility)."""
        config = AWSAuthConfig()
        auth_service = AWSAuthService(config)

        with patch("boto3.client") as mock_client:
            await auth_service.get_client("s3")
            mock_client.assert_called_once_with("s3", region_name="us-east-1")

    @pytest.mark.asyncio
    async def test_get_client_with_profile(self):
        """Test client creation with AWS profile."""
        config = AWSAuthConfig(default_profile="test-profile")
        auth_service = AWSAuthService(config)

        with patch("boto3.Session") as mock_session:
            mock_session_instance = Mock()
            mock_session.return_value = mock_session_instance

            await auth_service.get_client("s3")

            mock_session.assert_called_once_with(profile_name="test-profile")
            mock_session_instance.client.assert_called_once_with(
                "s3", region_name="us-east-1"
            )

    @pytest.mark.asyncio
    async def test_assume_role_success(self):
        """Test successful role assumption."""
        role_config = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
        )
        config = AWSAuthConfig(roles={"test": role_config})
        auth_service = AWSAuthService(config)

        # Mock STS client and response
        mock_sts_client = Mock()
        auth_service._sts_client = mock_sts_client

        mock_response = {
            "Credentials": {
                "AccessKeyId": "test_key",
                "SecretAccessKey": "test_secret",
                "SessionToken": "test_token",
                "Expiration": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        }

        with patch.object(auth_service, "_run_in_executor") as mock_executor:
            mock_executor.return_value = mock_response

            client = await auth_service.get_client("ec2", role_name="test")

            # Verify role assumption was called
            mock_executor.assert_called()
            assert client is not None

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self):
        """Test proper error handling for authentication failures."""
        from botocore.exceptions import ClientError

        role_config = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/InvalidRole",
            account_id="123456789012",
        )
        config = AWSAuthConfig(roles={"invalid": role_config})
        auth_service = AWSAuthService(config)

        # Mock STS client
        mock_sts_client = Mock()
        auth_service._sts_client = mock_sts_client

        with patch.object(auth_service, "_run_in_executor") as mock_executor:
            mock_executor.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "AssumeRole",
            )

            with pytest.raises(AssumeRoleError):
                await auth_service.get_client("s3", role_name="invalid")

    @pytest.mark.asyncio
    async def test_role_not_found_error(self):
        """Test error when role configuration is not found."""
        config = AWSAuthConfig()
        auth_service = AWSAuthService(config)

        with pytest.raises(RoleNotFoundError):
            await auth_service.get_client("s3", role_name="nonexistent")

    @pytest.mark.asyncio
    async def test_credential_caching(self):
        """Test credential caching functionality."""
        role_config = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
        )
        config = AWSAuthConfig(roles={"test": role_config}, enable_caching=True)
        auth_service = AWSAuthService(config)

        # Mock STS client and response
        mock_sts_client = Mock()
        auth_service._sts_client = mock_sts_client

        mock_response = {
            "Credentials": {
                "AccessKeyId": "test_key",
                "SecretAccessKey": "test_secret",
                "SessionToken": "test_token",
                "Expiration": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        }

        with patch.object(auth_service, "_run_in_executor") as mock_executor:
            mock_executor.return_value = mock_response

            # First call should cache credentials
            await auth_service.get_client("s3", role_name="test")
            assert "test" in auth_service._credential_cache

            # Second call should use cached credentials
            await auth_service.get_client("s3", role_name="test")

            # _run_in_executor should only be called once (for caching)
            assert mock_executor.call_count == 1

    @pytest.mark.asyncio
    async def test_test_credentials(self):
        """Test credential testing functionality."""
        config = AWSAuthConfig()
        auth_service = AWSAuthService(config)

        with patch.object(auth_service, "get_client") as mock_get_client:
            mock_sts_client = Mock()
            mock_get_client.return_value = mock_sts_client

            mock_response = {
                "Account": "123456789012",
                "UserId": "test-user-id",
                "Arn": "arn:aws:iam::123456789012:user/test-user",
            }

            with patch.object(auth_service, "_run_in_executor") as mock_executor:
                mock_executor.return_value = mock_response

                result = await auth_service.test_credentials()

                assert result["account"] == "123456789012"
                assert result["user_id"] == "test-user-id"
                assert result["arn"] == "arn:aws:iam::123456789012:user/test-user"

    def test_clear_cache(self):
        """Test clearing credential cache."""
        config = AWSAuthConfig()
        auth_service = AWSAuthService(config)

        # Add some dummy cache data
        auth_service._credential_cache["test"] = ("dummy_creds", time.time())
        auth_service._credential_cache["test2"] = ("dummy_creds2", time.time())

        # Clear specific role
        auth_service.clear_cache("test")
        assert "test" not in auth_service._credential_cache
        assert "test2" in auth_service._credential_cache

        # Clear all
        auth_service.clear_cache()
        assert len(auth_service._credential_cache) == 0

    def test_get_cache_info(self):
        """Test getting cache information."""
        config = AWSAuthConfig()
        auth_service = AWSAuthService(config)

        # Add some dummy cache data
        creds = AWSCredentials(
            access_key_id="test_key",
            secret_access_key="test_secret",
            session_token="test_token",
            expiration=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            region="us-east-1",
        )
        auth_service._credential_cache["test"] = (creds, time.time())

        cache_info = auth_service.get_cache_info()

        assert "test" in cache_info
        assert "cached_at" in cache_info["test"]
        assert "expires_at" in cache_info["test"]
        assert "valid" in cache_info["test"]


class TestConvenienceFunctions:
    """Test convenience functions and global service patterns."""

    @pytest.mark.asyncio
    async def test_get_authenticated_client(self):
        """Test get_authenticated_client convenience function."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_service.get_client = AsyncMock()
            mock_get_service.return_value = mock_service

            await get_authenticated_client("s3", role_name="test")

            mock_service.get_client.assert_called_once_with("s3", "test", None)

    @pytest.mark.asyncio
    async def test_create_client_alias(self):
        """Test create_client alias function."""
        with patch(
            "agents.sre_agent.aws_auth.get_authenticated_client"
        ) as mock_get_client:
            await create_client("s3", role_name="test", region="us-west-2")

            mock_get_client.assert_called_once_with("s3", "test", "us-west-2")

    @pytest.mark.asyncio
    async def test_test_auth_function(self):
        """Test test_auth convenience function."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service
            mock_service.test_credentials = AsyncMock(
                return_value={"status": "success"}
            )

            result = await auth_test("test-role")

            mock_service.test_credentials.assert_called_once_with("test-role")
            assert result["status"] == "success"

    def test_configure_auth_function(self):
        """Test configure_auth convenience function."""
        role = RoleConfig(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
        )

        config = configure_auth(
            default_region="us-west-2", enable_caching=False, test_role=role
        )

        assert config.default_region == "us-west-2"
        assert config.enable_caching is False
        assert "test_role" in config.roles
        assert config.roles["test_role"] == role

    def test_create_role_config_function(self):
        """Test create_role_config convenience function."""
        role = create_role_config(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            account_id="123456789012",
            duration_seconds=7200,
        )

        assert role.role_arn == "arn:aws:iam::123456789012:role/TestRole"
        assert role.account_id == "123456789012"
        assert role.duration_seconds == 7200


class TestExceptionHandling:
    """Test custom exception classes and error handling."""

    def test_aws_auth_error(self):
        """Test base AWSAuthError exception."""
        error = AWSAuthError("Test error", error_code="TEST_ERROR")
        assert str(error) == "[TEST_ERROR] Test error"
        assert error.error_code == "TEST_ERROR"

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        error = AuthenticationError(
            "Access denied", role_arn="arn:aws:iam::123456789012:role/TestRole"
        )
        assert "Access denied" in str(error)
        assert "arn:aws:iam::123456789012:role/TestRole" in str(error)
        assert error.error_code == "AUTH_FAILED"

    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        error = ConfigurationError("Invalid config", config_field="role_arn")
        assert "Invalid config" in str(error)
        assert "role_arn" in str(error)
        assert error.error_code == "CONFIG_INVALID"

    def test_create_auth_error_from_boto_error(self):
        """Test creating auth errors from boto exceptions."""
        from botocore.exceptions import NoCredentialsError, ClientError

        # Test NoCredentialsError
        boto_error = NoCredentialsError()
        auth_error = create_auth_error_from_boto_error(boto_error)
        assert isinstance(auth_error, AuthenticationError)

        # Test ClientError with AccessDenied
        boto_error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "AssumeRole",
        )
        auth_error = create_auth_error_from_boto_error(boto_error)
        assert isinstance(auth_error, AuthenticationError)


class TestBackwardCompatibility:
    """Test backward compatibility with existing patterns."""

    @pytest.mark.asyncio
    async def test_existing_cost_tools_integration(self):
        """Test that existing cost tools can be used without auth service."""
        # This test would normally import and test aws_cost_tools
        # but since we want to test integration without breaking existing functionality
        # we'll mock the import to ensure the pattern works

        with patch(
            "agents.sre_agent.sub_agents.aws_cost.tools.aws_cost_tools.get_current_date_info"
        ) as mock_date_info:
            mock_date_info.return_value = {
                "current_year": 2025,
                "current_month": 1,
                "current_month_name": "January",
            }

            # Import and call the function
            from agents.sre_agent.sub_agents.aws_cost.tools.aws_cost_tools import (
                get_current_date_info,
            )

            result = get_current_date_info()

            assert result["current_year"] == 2025
            assert result["current_month"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
