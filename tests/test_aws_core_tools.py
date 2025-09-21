"""
Integration tests for AWS Core Tools.

Tests the integration between AWS core tools and the authentication service,
ensuring proper role-based access and error handling.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools import (
    get_caller_identity,
    list_s3_buckets,
    list_ec2_instances,
    list_rds_instances,
    get_aws_regions,
    get_account_summary,
    test_aws_connectivity,
)
from agents.sre_agent.aws_auth import AWSAuthService, AWSAuthConfig, RoleConfig


class TestAWSCoreToolsIntegration:
    """Test AWS Core Tools integration with authentication service."""

    @pytest.mark.asyncio
    async def test_get_caller_identity_default_credentials(self):
        """Test get_caller_identity with default credentials."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_sts_client = Mock()
            mock_service.get_client = AsyncMock(return_value=mock_sts_client)

            mock_response = {
                "Account": "123456789012",
                "UserId": "test-user-id",
                "Arn": "arn:aws:iam::123456789012:user/test-user",
            }

            with patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools._run_in_executor"
            ) as mock_executor:
                mock_executor.return_value = mock_response

                result = await get_caller_identity()

                assert result["status"] == "success"
                assert result["account"] == "123456789012"
                assert result["user_id"] == "test-user-id"
                assert result["role_name"] == "default"

                mock_service.get_client.assert_called_once_with("sts", role_name=None)

    @pytest.mark.asyncio
    async def test_get_caller_identity_with_role(self):
        """Test get_caller_identity with assumed role."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_sts_client = Mock()
            mock_service.get_client = AsyncMock(return_value=mock_sts_client)

            mock_response = {
                "Account": "987654321098",
                "UserId": "AIDACKCEVSQ6C2EXAMPLE",
                "Arn": "arn:aws:sts::987654321098:assumed-role/TestRole/session-name",
            }

            with patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools._run_in_executor"
            ) as mock_executor:
                mock_executor.return_value = mock_response

                result = await get_caller_identity(role_name="test-role")

                assert result["status"] == "success"
                assert result["account"] == "987654321098"
                assert result["role_name"] == "test-role"

                mock_service.get_client.assert_called_once_with(
                    "sts", role_name="test-role"
                )

    @pytest.mark.asyncio
    async def test_list_s3_buckets_success(self):
        """Test list_s3_buckets with successful response."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_s3_client = Mock()
            mock_service.get_client = AsyncMock(return_value=mock_s3_client)

            mock_response = {
                "Buckets": [
                    {"Name": "bucket1", "CreationDate": datetime.now(timezone.utc)},
                    {"Name": "bucket2", "CreationDate": datetime.now(timezone.utc)},
                ]
            }

            with patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools._run_in_executor"
            ) as mock_executor:
                mock_executor.return_value = mock_response

                result = await list_s3_buckets(role_name="test-role")

                assert result["status"] == "success"
                assert result["count"] == 2
                assert len(result["buckets"]) == 2
                assert result["buckets"][0]["name"] == "bucket1"

                mock_service.get_client.assert_called_once_with(
                    "s3", role_name="test-role"
                )

    @pytest.mark.asyncio
    async def test_list_ec2_instances_with_filters(self):
        """Test list_ec2_instances with state filters."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_ec2_client = Mock()
            mock_service.get_client = AsyncMock(return_value=mock_ec2_client)

            mock_response = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-1234567890abcdef0",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "running"},
                                "LaunchTime": datetime.now(timezone.utc),
                                "PrivateIpAddress": "10.0.1.10",
                                "PublicIpAddress": "1.2.3.4",
                                "VpcId": "vpc-12345678",
                                "SubnetId": "subnet-12345678",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }

            with patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools._run_in_executor"
            ) as mock_executor:
                mock_executor.return_value = mock_response

                result = await list_ec2_instances(
                    role_name="test-role",
                    region="us-west-2",
                    instance_states=["running"],
                )

                assert result["status"] == "success"
                assert result["count"] == 1
                assert result["region"] == "us-west-2"
                assert result["instances"][0]["instance_id"] == "i-1234567890abcdef0"
                assert result["instances"][0]["name"] == "test-instance"

                mock_service.get_client.assert_called_once_with(
                    "ec2", role_name="test-role", region="us-west-2"
                )

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in AWS core tools."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            # Simulate authentication error
            mock_service.get_client = AsyncMock(
                side_effect=Exception("Authentication failed")
            )

            result = await get_caller_identity(role_name="invalid-role")

            assert result["status"] == "error"
            assert "Authentication failed" in result["message"]
            assert result["role_name"] == "invalid-role"

    @pytest.mark.asyncio
    async def test_get_account_summary_integration(self):
        """Test get_account_summary that calls multiple other functions."""
        # Mock all the individual functions that get_account_summary calls
        with (
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.get_caller_identity"
            ) as mock_identity,
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.list_s3_buckets"
            ) as mock_s3,
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.list_ec2_instances"
            ) as mock_ec2,
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.list_rds_instances"
            ) as mock_rds,
        ):
            # Setup mock responses
            mock_identity.return_value = {
                "status": "success",
                "account": "123456789012",
                "user_id": "test-user",
                "arn": "arn:aws:iam::123456789012:user/test",
            }

            mock_s3.return_value = {"status": "success", "count": 5}

            mock_ec2.return_value = {
                "status": "success",
                "instances": [
                    {"state": "running"},
                    {"state": "running"},
                    {"state": "stopped"},
                ],
            }

            mock_rds.return_value = {
                "status": "success",
                "instances": [{"engine": "mysql"}, {"engine": "postgres"}],
            }

            result = await get_account_summary(role_name="test-role")

            assert result["status"] == "success"
            assert result["role_name"] == "test-role"
            assert "summary" in result
            assert result["summary"]["identity"]["account_id"] == "123456789012"
            assert result["summary"]["s3"]["bucket_count"] == 5
            assert result["summary"]["ec2"]["total_instances"] == 3
            assert result["summary"]["ec2"]["instances_by_state"]["running"] == 2
            assert result["summary"]["ec2"]["instances_by_state"]["stopped"] == 1
            assert result["summary"]["rds"]["total_instances"] == 2

    @pytest.mark.asyncio
    async def test_connectivity_test_integration(self):
        """Test test_aws_connectivity that tests multiple services."""
        # Mock all the services for connectivity testing
        with (
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.get_caller_identity"
            ) as mock_identity,
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.list_s3_buckets"
            ) as mock_s3,
            patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools.list_ec2_instances"
            ) as mock_ec2,
        ):
            # Setup mixed success/failure responses
            mock_identity.return_value = {
                "status": "success",
                "account": "123456789012",
            }
            mock_s3.return_value = {"status": "success", "count": 3}
            mock_ec2.return_value = {"status": "error", "message": "Access denied"}

            result = await test_aws_connectivity(role_name="test-role")

            assert result["role_name"] == "test-role"
            assert "tests" in result
            assert result["tests"]["sts"]["status"] == "success"
            assert result["tests"]["s3"]["status"] == "success"
            assert result["tests"]["ec2"]["status"] == "error"
            assert (
                result["overall_status"] == "partial"
            )  # Some tests passed, some failed
            assert result["success_rate"] == "2/3"

    @pytest.mark.asyncio
    async def test_aws_regions_functionality(self):
        """Test get_aws_regions with different services."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_ec2_client = Mock()
            mock_service.get_client = AsyncMock(return_value=mock_ec2_client)

            mock_response = {
                "Regions": [
                    {"RegionName": "us-east-1"},
                    {"RegionName": "us-west-2"},
                    {"RegionName": "eu-west-1"},
                ]
            }

            with patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools._run_in_executor"
            ) as mock_executor:
                mock_executor.return_value = mock_response

                result = await get_aws_regions(role_name="test-role", service="ec2")

                assert result["status"] == "success"
                assert result["count"] == 3
                assert "us-east-1" in result["regions"]
                assert "us-west-2" in result["regions"]
                assert result["service"] == "ec2"

                mock_service.get_client.assert_called_once_with(
                    "ec2", role_name="test-role"
                )


class TestToolsWithoutAuthService:
    """Test AWS core tools fallback behavior without auth service."""

    @pytest.mark.asyncio
    async def test_fallback_to_default_credentials(self):
        """Test that tools work with default credentials when no role is specified."""
        with patch("agents.sre_agent.aws_auth.get_auth_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_sts_client = Mock()
            mock_service.get_client = AsyncMock(return_value=mock_sts_client)

            mock_response = {
                "Account": "123456789012",
                "UserId": "test-user-id",
                "Arn": "arn:aws:iam::123456789012:user/test-user",
            }

            with patch(
                "agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools._run_in_executor"
            ) as mock_executor:
                mock_executor.return_value = mock_response

                # Call without role_name (should use default credentials)
                result = await get_caller_identity()

                assert result["status"] == "success"
                assert result["role_name"] == "default"

                # Verify called with None for role_name
                mock_service.get_client.assert_called_once_with("sts", role_name=None)


# Mark all tests as async
pytestmark = pytest.mark.asyncio


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
