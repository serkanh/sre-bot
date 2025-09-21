# AWS Role-Based Authentication System PRP

name: "AWS Role-Based Authentication System PRP"
description: |

## Goal

Build a shared AWS authentication service that enables role-based access for single or multiple AWS systems, allowing SRE bot agents to assume remote roles and execute AWS API queries across accounts. The system should be simple to configure with just role ARN and account ID, and reusable across all agents.

## Why

- **Multi-Account Support**: Enable SRE operations across multiple AWS accounts with proper isolation and security
- **Security Best Practices**: Implement AWS STS role assumption instead of long-term credentials
- **Operational Efficiency**: Centralized authentication service reduces duplication across agents
- **Audit Trail**: Role session names and CloudTrail integration for security monitoring
- **Scalability**: Foundation for expanding SRE capabilities across AWS organizations

## What

A centralized AWS authentication module that:

- Assumes IAM roles in target AWS accounts using STS
- Provides authenticated boto3 clients for AWS service interactions
- Supports both single and multi-account configurations
- Maintains backward compatibility with existing default credential patterns
- Includes comprehensive error handling and retry logic
- Integrates seamlessly with existing agent architecture

### Success Criteria

- [ ] Can assume roles in remote AWS accounts using role ARN + account ID
- [ ] Returns properly authenticated boto3 clients for any AWS service
- [ ] Existing AWS cost agent continues to work without changes
- [ ] Configuration via environment variables and/or config files
- [ ] Comprehensive error handling for authentication failures
- [ ] Unit tests covering all authentication scenarios
- [ ] Documentation and examples for other agents to integrate

## All Needed Context

### Documentation & References

```yaml
# MUST READ - Include these in your context window
- url: https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html
  why: Official AWS STS AssumeRole API reference for proper implementation

- url: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html
  why: Boto3 STS client documentation with code examples

- url: https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html
  why: AWS cross-account role assumption patterns and security considerations

- file: agents/sre_agent/sub_agents/aws_cost/tools/aws_cost_tools.py
  why: Current AWS client creation pattern to maintain compatibility

- file: agents/sre_agent/sub_agents/aws_cost/agent.py
  why: Existing agent structure and tool integration patterns

- file: agents/sre_agent/utils.py
  why: Shared utility patterns for logging and configuration

- file: agents/sre_agent/agent.py
  why: Main agent architecture and sub-agent integration pattern

- file: docker-compose.yml
  why: Current AWS credential mounting and environment configuration

- file: .env.example
  why: Environment variable patterns and AWS configuration
```

### Current Codebase Tree

```bash
.
├── PRPs
│   └── templates
│       └── prp_base.md
├── agents
│   └── sre_agent
│       ├── sub_agents
│       │   └── aws_cost
│       │       ├── tools
│       │       │   └── aws_cost_tools.py
│       │       ├── prompts
│       │       └── agent.py
│       ├── Dockerfile-agent
│       ├── agent.py
│       ├── serve.py
│       ├── settings.py
│       └── utils.py
├── slack_bot
├── CLAUDE.md
├── docker-compose.yml
└── requirements-dev.txt
```

### Desired Codebase Tree (Files to Add)

```bash
agents/sre_agent/
├── aws_auth/                           # New shared AWS authentication module
│   ├── __init__.py                     # Export main auth functions
│   ├── auth_service.py                 # Core authentication logic
│   ├── config.py                       # Configuration management
│   └── exceptions.py                   # Custom exceptions
├── sub_agents/
│   ├── aws_core/                       # New general AWS operations agent
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   └── aws_core_tools.py       # General AWS tools using auth service
│   │   ├── prompts/
│   │   │   └── aws_core_agent_system_prompt.md
│   │   ├── __init__.py
│   │   └── agent.py                    # AWS core operations agent
│   └── aws_cost/                       # Updated to use auth service
│       └── tools/
│           └── aws_cost_tools.py       # Modified to use new auth service
└── tests/                              # New test directory
    ├── __init__.py
    ├── test_aws_auth.py                # Unit tests for auth service
    └── test_aws_core_tools.py          # Integration tests
```

### Known Gotchas & Critical Patterns

```python
# CRITICAL: Current aws_cost_tools.py uses global client pattern
_cost_explorer = None  # Global variable pattern to preserve

# CRITICAL: Docker mounts ~/.aws as read-only
volumes:
  - ${HOME}/.aws:/root/.aws:ro

# CRITICAL: Current error handling pattern in aws_cost_tools.py
try:
    _cost_explorer = boto3.client("ce")
except (NoCredentialsError, ProfileNotFound) as e:
    logger.error(f"AWS credentials not configured: {e}")
    # Must maintain this error handling pattern

# CRITICAL: ADK agent pattern for tool imports
from .tools.aws_cost_tools import (get_cost_for_period, ...)
# Tools are imported as functions, not classes

# CRITICAL: Thread pool executor pattern for async operations
async def _run_in_executor(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_thread_pool, lambda: func(*args, **kwargs))

# CRITICAL: Environment variable patterns from .env.example
AWS_PROFILE=your_aws_profile
AWS_REGION=us-east-1
```

## Implementation Blueprint

### Data Models and Structure

```python
# Configuration management with Pydantic for validation
from pydantic import BaseModel, Field
from typing import Dict, Optional, List

class RoleConfig(BaseModel):
    """Configuration for a single AWS role."""
    role_arn: str = Field(..., description="ARN of the role to assume")
    account_id: str = Field(..., description="AWS account ID")
    role_session_name: str = Field(default="SREBotSession", description="Session name for role assumption")
    duration_seconds: int = Field(default=3600, ge=900, le=43200, description="Session duration in seconds")
    external_id: Optional[str] = Field(None, description="External ID for third-party access")

class AWSAuthConfig(BaseModel):
    """Main configuration for AWS authentication."""
    default_region: str = Field(default="us-east-1", description="Default AWS region")
    default_profile: Optional[str] = Field(None, description="Default AWS profile")
    roles: Dict[str, RoleConfig] = Field(default_factory=dict, description="Named role configurations")
    enable_role_chaining: bool = Field(default=False, description="Allow role chaining")

class AWSCredentials(BaseModel):
    """Temporary AWS credentials from STS."""
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str
    region: str
```

### List of Tasks (Implementation Order)

```yaml
Task 1: Create AWS Auth Configuration Module
CREATE agents/sre_agent/aws_auth/config.py:
  - IMPLEMENT Pydantic models for role configuration
  - ADD environment variable loading with validation
  - ADD config file support (JSON/YAML) for complex setups
  - INCLUDE default profile fallback mechanism

Task 2: Create AWS Auth Service Core
CREATE agents/sre_agent/aws_auth/auth_service.py:
  - IMPLEMENT STS role assumption with retry logic
  - ADD session management and credential caching
  - ADD boto3 client factory with assumed role credentials
  - INCLUDE comprehensive error handling and logging

Task 3: Create Custom Exceptions
CREATE agents/sre_agent/aws_auth/exceptions.py:
  - DEFINE custom exceptions for authentication failures
  - ADD error codes for different failure scenarios
  - INCLUDE helpful error messages for troubleshooting

Task 4: Create Auth Module Exports
CREATE agents/sre_agent/aws_auth/__init__.py:
  - EXPORT main authentication functions
  - ADD convenience functions for common operations
  - INCLUDE version information and compatibility

Task 5: Update AWS Cost Tools Integration
MODIFY agents/sre_agent/sub_agents/aws_cost/tools/aws_cost_tools.py:
  - PRESERVE existing global client pattern
  - ADD optional role-based authentication
  - MAINTAIN backward compatibility with default credentials
  - KEEP all existing function signatures unchanged

Task 6: Create General AWS Core Agent
CREATE agents/sre_agent/sub_agents/aws_core/:
  - MIRROR structure from aws_cost agent
  - IMPLEMENT general AWS operations tools
  - ADD system prompt for AWS core operations
  - INTEGRATE with new auth service

Task 7: Update Main Agent Integration
MODIFY agents/sre_agent/agent.py:
  - ADD import for new aws_core agent
  - INCLUDE aws_core agent in sub_agents list
  - UPDATE instruction with delegation patterns

Task 8: Create Comprehensive Tests
CREATE tests/test_aws_auth.py:
  - IMPLEMENT unit tests for all auth scenarios
  - ADD mock tests for STS calls
  - INCLUDE error handling test cases
  - ADD integration tests with real AWS (optional)

Task 9: Update Environment Configuration
MODIFY .env.example:
  - ADD new AWS auth environment variables
  - INCLUDE role configuration examples
  - UPDATE documentation comments

Task 10: Create Documentation and Examples
CREATE agents/sre_agent/aws_auth/README.md:
  - ADD usage examples for other agents
  - INCLUDE configuration guide
  - ADD troubleshooting section
```

### Per Task Pseudocode

```python
# Task 2: AWS Auth Service Core Implementation
class AWSAuthService:
    def __init__(self, config: AWSAuthConfig):
        self.config = config
        self._credential_cache = {}  # Role ARN -> (credentials, expiry)
        self._sts_client = None

    async def get_client(self, service: str, role_name: Optional[str] = None, region: Optional[str] = None):
        """Get authenticated boto3 client for any AWS service."""
        # PATTERN: Check credential cache first
        if role_name and not self._credentials_valid(role_name):
            await self._refresh_credentials(role_name)

        # PATTERN: Use assumed role credentials or default
        if role_name:
            credentials = self._credential_cache[role_name]
            return boto3.client(
                service,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                aws_session_token=credentials.session_token,
                region_name=region or self.config.default_region
            )
        else:
            # FALLBACK: Default credentials (existing behavior)
            return boto3.client(service, region_name=region or self.config.default_region)

    async def _assume_role(self, role_config: RoleConfig) -> AWSCredentials:
        """Assume AWS role and return temporary credentials."""
        # CRITICAL: Use thread executor for blocking boto3 calls
        sts_client = self._get_sts_client()

        params = {
            'RoleArn': role_config.role_arn,
            'RoleSessionName': f"{role_config.role_session_name}_{int(time.time())}",
            'DurationSeconds': role_config.duration_seconds
        }

        if role_config.external_id:
            params['ExternalId'] = role_config.external_id

        # PATTERN: Async execution with comprehensive error handling
        try:
            response = await self._run_in_executor(
                sts_client.assume_role, **params
            )
            return AWSCredentials(**response['Credentials'], region=self.config.default_region)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                raise AuthenticationError(f"Access denied assuming role {role_config.role_arn}")
            elif error_code == 'InvalidParameterValue':
                raise ConfigurationError(f"Invalid role configuration: {e}")
            else:
                raise AWSAuthError(f"Failed to assume role: {e}")
```

### Integration Points

```yaml
ENVIRONMENT_VARIABLES:
  - add to: .env.example
  - pattern: |
      # AWS Role-Based Authentication
      AWS_AUTH_DEFAULT_ROLE=my-sre-role
      AWS_AUTH_ROLES='{"prod": {"role_arn": "arn:aws:iam::123456789012:role/SRERole", "account_id": "123456789012"}}'
      AWS_AUTH_ENABLE_CACHING=true

DOCKER_CONFIGURATION:
  - modify: docker-compose.yml
  - pattern: "Add new environment variables to both sre-bot-web and sre-bot-api services"

AGENT_INTEGRATION:
  - modify: agents/sre_agent/agent.py
  - pattern: |
      from .sub_agents.aws_core.agent import create_aws_core_agent
      # Add to sub_agents list: aws_core_agent = create_aws_core_agent()

BACKWARDS_COMPATIBILITY:
  - preserve: agents/sre_agent/sub_agents/aws_cost/tools/aws_cost_tools.py
  - pattern: "Existing global _cost_explorer client continues to work with default credentials"
```

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
ruff check agents/sre_agent/aws_auth/ --fix
ruff format agents/sre_agent/aws_auth/
mypy agents/sre_agent/aws_auth/

# Expected: No errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests

```python
# CREATE tests/test_aws_auth.py with comprehensive test cases:

import pytest
from unittest.mock import Mock, patch, AsyncMock
from agents.sre_agent.aws_auth import AWSAuthService, AWSAuthConfig, RoleConfig

@pytest.mark.asyncio
async def test_get_client_default_credentials():
    """Test default credential behavior (backward compatibility)."""
    config = AWSAuthConfig()
    auth_service = AWSAuthService(config)

    with patch('boto3.client') as mock_client:
        client = await auth_service.get_client('s3')
        mock_client.assert_called_once_with('s3', region_name='us-east-1')

@pytest.mark.asyncio
async def test_assume_role_success():
    """Test successful role assumption."""
    role_config = RoleConfig(
        role_arn="arn:aws:iam::123456789012:role/TestRole",
        account_id="123456789012"
    )
    config = AWSAuthConfig(roles={"test": role_config})
    auth_service = AWSAuthService(config)

    with patch.object(auth_service, '_run_in_executor') as mock_executor:
        mock_executor.return_value = {
            'Credentials': {
                'AccessKeyId': 'test_key',
                'SecretAccessKey': 'test_secret',
                'SessionToken': 'test_token',
                'Expiration': '2025-01-01T00:00:00Z'
            }
        }

        client = await auth_service.get_client('ec2', role_name='test')
        assert client is not None

@pytest.mark.asyncio
async def test_authentication_error_handling():
    """Test proper error handling for authentication failures."""
    from botocore.exceptions import ClientError

    role_config = RoleConfig(
        role_arn="arn:aws:iam::123456789012:role/InvalidRole",
        account_id="123456789012"
    )
    config = AWSAuthConfig(roles={"invalid": role_config})
    auth_service = AWSAuthService(config)

    with patch.object(auth_service, '_run_in_executor') as mock_executor:
        mock_executor.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'AssumeRole'
        )

        with pytest.raises(AuthenticationError):
            await auth_service.get_client('s3', role_name='invalid')
```

```bash
# Run and iterate until passing:
pytest tests/test_aws_auth.py -v
# If failing: Read error, understand root cause, fix code, re-run
```

### Level 3: Integration Test

```bash
# Test existing AWS cost functionality still works
python -c "
from agents.sre_agent.sub_agents.aws_cost.tools.aws_cost_tools import get_current_date_info
print('Backward compatibility test:', get_current_date_info())
"

# Test new auth service with environment variables
export AWS_AUTH_DEFAULT_ROLE=test
python -c "
from agents.sre_agent.aws_auth import AWSAuthService, AWSAuthConfig
import asyncio

async def test():
    config = AWSAuthConfig()
    service = AWSAuthService(config)
    # This should work with default credentials
    client = await service.get_client('sts')
    print('Auth service test: SUCCESS')

asyncio.run(test())
"
```

## Final Validation Checklist

- [ ] All tests pass: `pytest tests/ -v`
- [ ] No linting errors: `ruff check agents/sre_agent/`
- [ ] No type errors: `mypy agents/sre_agent/`
- [ ] Backward compatibility: existing aws_cost agent works unchanged
- [ ] Environment configuration: new variables documented in .env.example
- [ ] Integration test: can create clients with both default and assumed role credentials
- [ ] Error cases handled gracefully with informative messages
- [ ] Documentation complete with usage examples

---

## Security Considerations

- **Credential Caching**: Temporary credentials cached with expiration checks
- **Session Names**: Unique session names for audit trail (includes timestamp)
- **Error Disclosure**: Error messages don't expose sensitive information
- **External ID**: Support for external ID in role trust policies
- **Duration Limits**: Configurable session duration with AWS limits enforcement
- **Role Chaining**: Optional support for role chaining scenarios

## Anti-Patterns to Avoid

- ❌ Don't break existing AWS cost agent functionality
- ❌ Don't hardcode role ARNs or account IDs in code
- ❌ Don't store long-term credentials in the application
- ❌ Don't ignore STS credential expiration
- ❌ Don't use overly broad IAM permissions
- ❌ Don't assume roles without proper error handling
- ❌ Don't log sensitive credential information

---

## Confidence Score: 9/10

This PRP provides comprehensive context for one-pass implementation success through:

- ✅ Complete current codebase analysis and patterns
- ✅ AWS STS best practices and security patterns from official documentation
- ✅ Detailed implementation blueprint with specific file locations
- ✅ Comprehensive testing strategy with real test cases
- ✅ Backward compatibility preservation
- ✅ Clear integration points and configuration patterns
- ✅ Executable validation gates

The only uncertainty (score reduction) is potential complexity in credential caching implementation, but the provided patterns and documentation should handle this effectively.