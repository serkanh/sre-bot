# AWS Authentication Service

A centralized AWS authentication service for the SRE Bot that enables role-based access across multiple AWS accounts using AWS STS (Security Token Service).

## Features

- **Role-Based Authentication**: Assume IAM roles in target AWS accounts using STS
- **Multi-Account Support**: Manage access to multiple AWS accounts with separate role configurations
- **Credential Caching**: Automatic caching of temporary credentials with expiration handling
- **Backward Compatibility**: Maintains compatibility with existing default credential patterns
- **Comprehensive Error Handling**: Detailed error messages and troubleshooting guidance
- **Security Best Practices**: Session names with timestamps for audit trails, configurable session durations

## Quick Start

### Simple Usage (Default Credentials)

```python
from agents.sre_agent.aws_auth import create_client

# Use default AWS credentials
s3_client = await create_client('s3')
```

### Role-Based Authentication

```python
from agents.sre_agent.aws_auth import AWSAuthConfig, RoleConfig, create_client

# Configure a role
config = AWSAuthConfig()
config.add_role('production', RoleConfig(
    role_arn='arn:aws:iam::123456789012:role/SRERole',
    account_id='123456789012'
))

# Use role-based authentication
ec2_client = await create_client('ec2', role_name='production')
```

### Environment-Based Configuration

Set environment variables for automatic configuration:

```bash
# Simple single role setup
export AWS_AUTH_DEFAULT_ROLE_ARN=arn:aws:iam::123456789012:role/SRERole
export AWS_AUTH_DEFAULT_ACCOUNT_ID=123456789012

# Complex multi-role setup (JSON format)
export AWS_AUTH_ROLES='{"prod": {"role_arn": "arn:aws:iam::111111111111:role/SRERole", "account_id": "111111111111"}, "staging": {"role_arn": "arn:aws:iam::222222222222:role/SRERole", "account_id": "222222222222"}}'
```

## API Reference

### Core Classes

#### `AWSAuthService`

Main authentication service class that handles role assumption and client creation.

```python
from agents.sre_agent.aws_auth import AWSAuthService, AWSAuthConfig

config = AWSAuthConfig.from_env()
auth_service = AWSAuthService(config)

# Get authenticated client
client = await auth_service.get_client('s3', role_name='production')

# Test credentials
identity = await auth_service.test_credentials('production')
```

#### `AWSAuthConfig`

Configuration class for AWS authentication settings.

```python
from agents.sre_agent.aws_auth import AWSAuthConfig, RoleConfig

config = AWSAuthConfig(
    default_region='us-west-2',
    enable_caching=True,
    cache_ttl_seconds=3600,
    roles={
        'prod': RoleConfig(
            role_arn='arn:aws:iam::123456789012:role/ProdRole',
            account_id='123456789012',
            duration_seconds=7200
        )
    }
)
```

#### `RoleConfig`

Configuration for individual AWS roles.

```python
from agents.sre_agent.aws_auth import RoleConfig

role = RoleConfig(
    role_arn='arn:aws:iam::123456789012:role/MyRole',
    account_id='123456789012',
    role_session_name='MySession',
    duration_seconds=3600,
    external_id='optional-external-id'
)
```

### Convenience Functions

#### `create_client(service, role_name=None, region=None, **kwargs)`

Create authenticated AWS client (most commonly used function).

```python
# Default credentials
s3 = await create_client('s3')

# With role
ec2 = await create_client('ec2', role_name='production', region='us-west-2')
```

#### `test_auth(role_name=None)`

Test AWS authentication and get caller identity.

```python
# Test default credentials
identity = await test_auth()

# Test specific role
identity = await test_auth('production')
```

#### `get_authenticated_client(service, role_name=None, region=None, **kwargs)`

Alternative name for `create_client` (same functionality).

## Environment Variables

### Basic Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_AUTH_DEFAULT_REGION` | Default AWS region | `us-east-1` |
| `AWS_AUTH_DEFAULT_PROFILE` | Default AWS profile | None |
| `AWS_AUTH_ENABLE_CACHING` | Enable credential caching | `true` |
| `AWS_AUTH_CACHE_TTL` | Cache TTL in seconds | `3000` |

### Single Role Configuration

| Variable | Description |
|----------|-------------|
| `AWS_AUTH_DEFAULT_ROLE_ARN` | ARN of the default role |
| `AWS_AUTH_DEFAULT_ACCOUNT_ID` | AWS account ID (12 digits) |
| `AWS_AUTH_DEFAULT_ROLE_NAME` | Name for the default role |
| `AWS_AUTH_DEFAULT_SESSION_NAME` | Session name for role assumption |
| `AWS_AUTH_DEFAULT_DURATION` | Session duration in seconds |
| `AWS_AUTH_DEFAULT_EXTERNAL_ID` | External ID for third-party access |

### Multi-Role Configuration

Use `AWS_AUTH_ROLES` with JSON format:

```bash
export AWS_AUTH_ROLES='{
  "production": {
    "role_arn": "arn:aws:iam::111111111111:role/ProdRole",
    "account_id": "111111111111",
    "duration_seconds": 7200
  },
  "staging": {
    "role_arn": "arn:aws:iam::222222222222:role/StagingRole",
    "account_id": "222222222222",
    "external_id": "staging-external-id"
  }
}'
```

## Integration with Existing Tools

### AWS Cost Tools

The authentication service is integrated with existing AWS cost tools while maintaining backward compatibility:

```python
# Configure cost tools to use role-based authentication
from agents.sre_agent.sub_agents.aws_cost.tools.aws_cost_tools import configure_aws_auth
from agents.sre_agent.aws_auth import get_auth_service

auth_service = get_auth_service()
configure_aws_auth(auth_service, role_name='production')

# Now cost tools will use the specified role
cost_data = await get_monthly_cost(2025, 9)
```

### AWS Core Tools

AWS core tools automatically use the authentication service:

```python
from agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools import get_caller_identity

# Uses default credentials
identity = await get_caller_identity()

# Uses specific role
identity = await get_caller_identity(role_name='production')
```

## Error Handling

The service provides comprehensive error handling with specific exception types:

```python
from agents.sre_agent.aws_auth import create_client
from agents.sre_agent.aws_auth.exceptions import (
    AuthenticationError,
    RoleNotFoundError,
    AssumeRoleError
)

try:
    client = await create_client('s3', role_name='invalid-role')
except RoleNotFoundError:
    print("Role configuration not found")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except AssumeRoleError as e:
    print(f"Role assumption failed: {e}")
```

## Security Considerations

### Session Names
- Unique session names with timestamps for audit trails
- Session names appear in AWS CloudTrail logs
- Format: `{role_session_name}_{timestamp}`

### Credential Caching
- Temporary credentials cached with expiration checks
- 5-minute buffer before expiration for safety
- Configurable cache TTL (default: 50 minutes)

### External IDs
- Support for external IDs in role trust policies
- Useful for third-party access scenarios

### Duration Limits
- Configurable session duration (900 seconds to 12 hours)
- Respects AWS STS limits and role maximum session duration

## Troubleshooting

### Common Issues

**Role Not Found Error**
```
RoleNotFoundError: Role configuration not found: production
```
- Check that the role is configured in `AWS_AUTH_ROLES` or added to the config
- Verify the role name spelling

**Access Denied**
```
AssumeRoleError: Access denied - check IAM permissions and trust relationships
```
- Verify the IAM role trust policy allows assumption from your account
- Check that your AWS credentials have `sts:AssumeRole` permission
- Ensure the role ARN is correct

**Invalid Role ARN**
```
ValidationError: role_arn must be a valid IAM role ARN starting with arn:aws:iam::
```
- Check the role ARN format: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`
- Ensure the account ID is 12 digits

**Credentials Expired**
```
CredentialExpiredError: AWS credentials have expired
```
- The service automatically refreshes expired credentials
- Check if your base AWS credentials are valid
- Verify role session duration limits

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export LOG_LEVEL=DEBUG
```

This will show detailed information about:
- Role assumption attempts
- Credential caching behavior
- Client creation process
- Error details

### Testing Connectivity

Use the connectivity test function to verify setup:

```python
from agents.sre_agent.sub_agents.aws_core.tools.aws_core_tools import test_aws_connectivity

# Test default credentials
result = await test_aws_connectivity()

# Test specific role
result = await test_aws_connectivity(role_name='production')
```

## Migration Guide

### From Default Credentials

If you're currently using default AWS credentials:

1. **No changes required** - the service maintains backward compatibility
2. **Optional**: Add role configurations for cross-account access
3. **Optional**: Configure environment variables for specific roles

### Adding Role-Based Authentication

1. **Configure roles** via environment variables or config objects
2. **Update tool usage** to specify `role_name` parameter where needed
3. **Test connectivity** using `test_aws_connectivity()` function

### Example Migration

Before:
```python
import boto3
s3_client = boto3.client('s3')
```

After:
```python
from agents.sre_agent.aws_auth import create_client
s3_client = await create_client('s3')  # Same behavior

# Add cross-account access
prod_s3_client = await create_client('s3', role_name='production')
```

## Best Practices

1. **Use Role-Based Authentication**: Prefer IAM roles over long-term access keys
2. **Least Privilege**: Configure roles with minimal required permissions
3. **Session Duration**: Use appropriate session durations (shorter for high-privilege operations)
4. **External IDs**: Use external IDs for third-party integrations
5. **Monitoring**: Monitor role usage through AWS CloudTrail
6. **Testing**: Regularly test role configurations and permissions
7. **Caching**: Enable credential caching for better performance
8. **Error Handling**: Handle authentication errors gracefully with user-friendly messages

For more examples and advanced usage, see the test files in `/tests/test_aws_auth.py` and `/tests/test_aws_core_tools.py`.