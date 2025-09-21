"""
AWS Core Tools - General AWS operations using the authentication service.

Provides common AWS operations across multiple services using role-based
authentication for cross-account access.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any
from datetime import datetime

from ....aws_auth import get_auth_service
from ....utils import get_logger

# Thread pool for running blocking boto3 operations
_thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="aws_core")

# Initialize a logger using shared utility
logger = get_logger(__name__)


async def _run_in_executor(func, *args, **kwargs):
    """Run a blocking function in a thread pool executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_thread_pool, lambda: func(*args, **kwargs))


async def get_caller_identity(role_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get AWS caller identity information using STS.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.

    Returns:
        Dict containing caller identity information including account, user ID, and ARN

    Raises:
        AWSAuthError: If authentication fails
    """
    try:
        auth_service = get_auth_service()
        sts_client = await auth_service.get_client("sts", role_name=role_name)

        response = await _run_in_executor(sts_client.get_caller_identity)

        return {
            "status": "success",
            "account": response.get("Account"),
            "user_id": response.get("UserId"),
            "arn": response.get("Arn"),
            "role_name": role_name or "default",
        }

    except Exception as e:
        logger.error(f"Failed to get caller identity: {e}")
        return {
            "status": "error",
            "message": f"Failed to get caller identity: {str(e)}",
            "role_name": role_name or "default",
        }


async def list_s3_buckets(role_name: Optional[str] = None) -> Dict[str, Any]:
    """
    List S3 buckets in the account.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.

    Returns:
        Dict containing list of S3 buckets

    Raises:
        AWSAuthError: If authentication fails
    """
    try:
        auth_service = get_auth_service()
        s3_client = await auth_service.get_client("s3", role_name=role_name)

        response = await _run_in_executor(s3_client.list_buckets)

        buckets = []
        for bucket in response.get("Buckets", []):
            buckets.append(
                {
                    "name": bucket["Name"],
                    "creation_date": bucket["CreationDate"].isoformat(),
                }
            )

        return {
            "status": "success",
            "buckets": buckets,
            "count": len(buckets),
            "role_name": role_name or "default",
        }

    except Exception as e:
        logger.error(f"Failed to list S3 buckets: {e}")
        return {
            "status": "error",
            "message": f"Failed to list S3 buckets: {str(e)}",
            "role_name": role_name or "default",
        }


async def list_ec2_instances(
    role_name: Optional[str] = None,
    region: Optional[str] = None,
    instance_states: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    List EC2 instances in the account.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.
        region: Optional AWS region. If None, uses default region.
        instance_states: Optional list of instance states to filter by (e.g., ['running', 'stopped'])

    Returns:
        Dict containing list of EC2 instances

    Raises:
        AWSAuthError: If authentication fails
    """
    try:
        auth_service = get_auth_service()
        ec2_client = await auth_service.get_client(
            "ec2", role_name=role_name, region=region
        )

        filters = []
        if instance_states:
            filters.append({"Name": "instance-state-name", "Values": instance_states})

        params = {}
        if filters:
            params["Filters"] = filters

        response = await _run_in_executor(ec2_client.describe_instances, **params)

        instances = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                # Extract instance name from tags
                instance_name = "N/A"
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        instance_name = tag["Value"]
                        break

                instances.append(
                    {
                        "instance_id": instance["InstanceId"],
                        "instance_type": instance["InstanceType"],
                        "state": instance["State"]["Name"],
                        "name": instance_name,
                        "launch_time": instance["LaunchTime"].isoformat(),
                        "private_ip": instance.get("PrivateIpAddress", "N/A"),
                        "public_ip": instance.get("PublicIpAddress", "N/A"),
                        "vpc_id": instance.get("VpcId", "N/A"),
                        "subnet_id": instance.get("SubnetId", "N/A"),
                    }
                )

        return {
            "status": "success",
            "instances": instances,
            "count": len(instances),
            "region": region or "default",
            "role_name": role_name or "default",
            "filtered_states": instance_states,
        }

    except Exception as e:
        logger.error(f"Failed to list EC2 instances: {e}")
        return {
            "status": "error",
            "message": f"Failed to list EC2 instances: {str(e)}",
            "region": region or "default",
            "role_name": role_name or "default",
        }


async def list_rds_instances(
    role_name: Optional[str] = None, region: Optional[str] = None
) -> Dict[str, Any]:
    """
    List RDS database instances in the account.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.
        region: Optional AWS region. If None, uses default region.

    Returns:
        Dict containing list of RDS instances

    Raises:
        AWSAuthError: If authentication fails
    """
    try:
        auth_service = get_auth_service()
        rds_client = await auth_service.get_client(
            "rds", role_name=role_name, region=region
        )

        response = await _run_in_executor(rds_client.describe_db_instances)

        instances = []
        for instance in response.get("DBInstances", []):
            instances.append(
                {
                    "identifier": instance["DBInstanceIdentifier"],
                    "engine": instance["Engine"],
                    "engine_version": instance["EngineVersion"],
                    "instance_class": instance["DBInstanceClass"],
                    "status": instance["DBInstanceStatus"],
                    "allocated_storage": instance["AllocatedStorage"],
                    "storage_type": instance.get("StorageType", "N/A"),
                    "multi_az": instance["MultiAZ"],
                    "endpoint": instance.get("Endpoint", {}).get("Address", "N/A"),
                    "port": instance.get("Endpoint", {}).get("Port", "N/A"),
                    "vpc_id": instance.get("DBSubnetGroup", {}).get("VpcId", "N/A"),
                    "creation_time": instance["InstanceCreateTime"].isoformat(),
                }
            )

        return {
            "status": "success",
            "instances": instances,
            "count": len(instances),
            "region": region or "default",
            "role_name": role_name or "default",
        }

    except Exception as e:
        logger.error(f"Failed to list RDS instances: {e}")
        return {
            "status": "error",
            "message": f"Failed to list RDS instances: {str(e)}",
            "region": region or "default",
            "role_name": role_name or "default",
        }


async def get_aws_regions(
    role_name: Optional[str] = None, service: str = "ec2"
) -> Dict[str, Any]:
    """
    Get list of available AWS regions for a service.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.
        service: AWS service to get regions for (default: ec2)

    Returns:
        Dict containing list of regions

    Raises:
        AWSAuthError: If authentication fails
    """
    try:
        auth_service = get_auth_service()
        client = await auth_service.get_client(service, role_name=role_name)

        if service == "ec2":
            response = await _run_in_executor(client.describe_regions)
            regions = [region["RegionName"] for region in response.get("Regions", [])]
        else:
            # For other services, use boto3 session to get regions
            import boto3

            session = boto3.Session()
            regions = session.get_available_regions(service)

        return {
            "status": "success",
            "regions": sorted(regions),
            "count": len(regions),
            "service": service,
            "role_name": role_name or "default",
        }

    except Exception as e:
        logger.error(f"Failed to get AWS regions: {e}")
        return {
            "status": "error",
            "message": f"Failed to get AWS regions: {str(e)}",
            "service": service,
            "role_name": role_name or "default",
        }


async def get_account_summary(role_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get AWS account summary with basic information across services.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.

    Returns:
        Dict containing account summary information

    Raises:
        AWSAuthError: If authentication fails
    """
    try:
        summary = {}

        # Get caller identity
        identity = await get_caller_identity(role_name)
        if identity.get("status") == "success":
            summary["identity"] = {
                "account_id": identity.get("account"),
                "user_id": identity.get("user_id"),
                "arn": identity.get("arn"),
            }

        # Get S3 bucket count
        s3_result = await list_s3_buckets(role_name)
        if s3_result.get("status") == "success":
            summary["s3"] = {"bucket_count": s3_result.get("count", 0)}

        # Get EC2 instance count by state
        ec2_result = await list_ec2_instances(role_name)
        if ec2_result.get("status") == "success":
            instances = ec2_result.get("instances", [])
            state_counts = {}
            for instance in instances:
                state = instance.get("state", "unknown")
                state_counts[state] = state_counts.get(state, 0) + 1

            summary["ec2"] = {
                "total_instances": len(instances),
                "instances_by_state": state_counts,
            }

        # Get RDS instance count
        rds_result = await list_rds_instances(role_name)
        if rds_result.get("status") == "success":
            instances = rds_result.get("instances", [])
            engine_counts = {}
            for instance in instances:
                engine = instance.get("engine", "unknown")
                engine_counts[engine] = engine_counts.get(engine, 0) + 1

            summary["rds"] = {
                "total_instances": len(instances),
                "instances_by_engine": engine_counts,
            }

        return {
            "status": "success",
            "summary": summary,
            "role_name": role_name or "default",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get account summary: {e}")
        return {
            "status": "error",
            "message": f"Failed to get account summary: {str(e)}",
            "role_name": role_name or "default",
        }


async def test_aws_connectivity(role_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Test AWS connectivity and permissions across multiple services.

    Args:
        role_name: Optional role name to assume. If None, uses default credentials.

    Returns:
        Dict containing connectivity test results

    Raises:
        AWSAuthError: If authentication fails
    """
    test_results = {
        "role_name": role_name or "default",
        "timestamp": datetime.utcnow().isoformat(),
        "tests": {},
    }

    # Test STS (basic connectivity)
    try:
        identity = await get_caller_identity(role_name)
        test_results["tests"]["sts"] = {
            "status": identity.get("status", "error"),
            "message": "Successfully retrieved caller identity"
            if identity.get("status") == "success"
            else identity.get("message", "Unknown error"),
            "account_id": identity.get("account"),
        }
    except Exception as e:
        test_results["tests"]["sts"] = {
            "status": "error",
            "message": f"STS test failed: {str(e)}",
        }

    # Test S3 (list permissions)
    try:
        s3_result = await list_s3_buckets(role_name)
        test_results["tests"]["s3"] = {
            "status": s3_result.get("status", "error"),
            "message": f"Found {s3_result.get('count', 0)} buckets"
            if s3_result.get("status") == "success"
            else s3_result.get("message", "Unknown error"),
        }
    except Exception as e:
        test_results["tests"]["s3"] = {
            "status": "error",
            "message": f"S3 test failed: {str(e)}",
        }

    # Test EC2 (describe permissions)
    try:
        ec2_result = await list_ec2_instances(role_name)
        test_results["tests"]["ec2"] = {
            "status": ec2_result.get("status", "error"),
            "message": f"Found {ec2_result.get('count', 0)} instances"
            if ec2_result.get("status") == "success"
            else ec2_result.get("message", "Unknown error"),
        }
    except Exception as e:
        test_results["tests"]["ec2"] = {
            "status": "error",
            "message": f"EC2 test failed: {str(e)}",
        }

    # Calculate overall status
    success_count = sum(
        1 for test in test_results["tests"].values() if test["status"] == "success"
    )
    total_count = len(test_results["tests"])

    test_results["overall_status"] = (
        "success"
        if success_count == total_count
        else "partial"
        if success_count > 0
        else "error"
    )
    test_results["success_rate"] = f"{success_count}/{total_count}"

    return test_results


# Export all functions
__all__ = [
    "get_caller_identity",
    "list_s3_buckets",
    "list_ec2_instances",
    "list_rds_instances",
    "get_aws_regions",
    "get_account_summary",
    "test_aws_connectivity",
]
