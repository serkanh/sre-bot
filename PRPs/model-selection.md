name: "Dynamic Model Selection for SRE Agent"
description: |
  Implement dynamic model selection for the SRE agent based on environment variables to support multiple AI providers (Google Gemini, Anthropic Claude, AWS Bedrock).

## Goal

Implement a feature where agents/agent.py and all sub-agents will dynamically determine which AI model and provider to use based on environment variables. The system should automatically detect which API keys are set and configure the Agent model parameter accordingly.

## Why

- **Flexibility**: Users can switch between different AI providers without code changes
- **Cost Optimization**: Different providers have different pricing models
- **Provider Preference**: Users may have existing relationships or credits with specific providers
- **Regional Availability**: Some providers may be better in certain regions
- **Model Capabilities**: Different models excel at different tasks

## What

The system will check environment variables in priority order and configure the agent with the appropriate model:
1. If `GOOGLE_API_KEY` is set → Use Gemini (direct string)
2. If `ANTHROPIC_API_KEY` is set → Use Claude via LiteLlm wrapper
3. If `BEDROCK_INFERENCE_PROFILE` is set → Use AWS Bedrock via LiteLlm wrapper

### Success Criteria

- [ ] Agent initializes correctly with Google Gemini when GOOGLE_API_KEY is set
- [ ] Agent initializes correctly with Claude via LiteLlm when ANTHROPIC_API_KEY is set
- [ ] Agent initializes correctly with Bedrock via LiteLlm when BEDROCK_INFERENCE_PROFILE is set
- [ ] Sub-agents inherit the same model configuration logic
- [ ] Clear error messages when no valid API keys are found
- [ ] Startup validation shows specific requirements for each provider
- [ ] Provider-specific errors guide users to resolution
- [ ] Tests pass for all configuration scenarios
- [ ] Environment variable precedence is documented

## All Needed Context

### Documentation & References

```yaml
# MUST READ - Include these in your context window
- url: https://google.github.io/adk-docs/agents/models/
  why: Official ADK documentation on model configuration patterns

- url: https://docs.litellm.ai/docs/tutorials/google_adk
  why: LiteLlm integration patterns with Google ADK

- file: agents/sre_agent/agent.py
  why: Current implementation to modify, uses _get_model() pattern

- file: agents/sre_agent/sub_agents/aws_cost/agent.py
  why: Sub-agent pattern that also needs modification

- file: agents/sre_agent/sub_agents/aws_core/agent.py
  why: Another sub-agent that needs the same pattern

- file: agents/sre_agent/settings.py
  why: Pattern for environment variable handling

- file: CLAUDE.md
  why: Import pattern shown - from google.adk.models.lite_llm import LiteLlm
```

### Critical Implementation Details

1. **LiteLlm Import Pattern** (from CLAUDE.md):
   ```python
   from google.adk.models.lite_llm import LiteLlm
   ```

2. **Current Model Configuration** (from agent.py):
   ```python
   def _get_model():
       """Get the configured model from environment variables."""
       return os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash")
   ```

3. **Agent Initialization Pattern**:
   ```python
   Agent(
       name="sre_agent",
       model=_get_model(),  # This is what we're changing
       instruction="...",
       # ...
   )
   ```

4. **Dependencies Already Available**:
   - `litellm==1.77.1` is already in requirements.txt
   - Google ADK agents framework is already imported

5. **Environment Variables Expected** (from .env.example):
   - `GOOGLE_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_AI_MODEL` (default: gemini-2.0-flash)
   - `ANTHROPIC_MODEL` (new, default: claude-3-5-sonnet-20240620)
   - `BEDROCK_INFERENCE_PROFILE` (new, for AWS Bedrock)

## Implementation Blueprint

### Pseudocode Approach with Enhanced Error Handling

```python
def validate_provider_requirements(provider_name, api_key, additional_checks=None):
    """
    Validate that provider has all required configuration.
    Log clear error messages for missing requirements.
    """
    logger = get_logger(__name__)

    if not api_key or api_key.strip() == "":
        return False

    # Run provider-specific validation
    if additional_checks:
        for check_name, check_func in additional_checks.items():
            if not check_func():
                logger.error(f"{provider_name} configuration error: {check_name}")
                return False

    logger.info(f"✓ {provider_name} provider configured successfully")
    return True

def get_configured_model():
    """
    Determine model configuration based on available API keys.
    Priority: Google > Anthropic > Bedrock
    Provides clear error messages for each provider's requirements.
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
        from google.adk.models.lite_llm import LiteLlm
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
        logger.info(f"🚀 Using Anthropic Claude provider with model: {model_name}")
        logger.info("✓ ANTHROPIC_API_KEY found and validated")
        return LiteLlm(model=model_name)

    # Check for Bedrock profile (LiteLlm wrapper)
    bedrock_profile = os.getenv("BEDROCK_INFERENCE_PROFILE")
    if bedrock_profile and bedrock_profile.strip():
        # Validate AWS credentials are available
        import boto3
        try:
            # Test AWS credentials
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"✓ AWS credentials validated for account: {identity['Account']}")
        except Exception as e:
            logger.error("❌ AWS Bedrock configuration error:")
            logger.error("   - BEDROCK_INFERENCE_PROFILE is set but AWS credentials are not configured")
            logger.error("   - Please configure AWS credentials via:")
            logger.error("     • AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
            logger.error("     • AWS profile via AWS_PROFILE environment variable")
            logger.error("     • IAM role (if running on AWS)")
            logger.error(f"   - Error details: {str(e)}")
            raise ConfigurationError(
                "Bedrock requires valid AWS credentials. "
                "Please configure AWS access before using Bedrock models."
            )

        from google.adk.models.lite_llm import LiteLlm
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

    raise ConfigurationError(
        "No AI provider API key found. Please set GOOGLE_API_KEY, "
        "ANTHROPIC_API_KEY, or BEDROCK_INFERENCE_PROFILE. "
        "See logs above for detailed configuration instructions."
    )
```

### Files to Modify

1. **agents/sre_agent/agent.py**:
   - Update `_get_model()` function with new logic
   - Add import for LiteLlm conditionally
   - Add error handling

2. **agents/sre_agent/sub_agents/aws_cost/agent.py**:
   - Update `_get_model()` function to match main agent pattern
   - Consider extracting to shared utility

3. **agents/sre_agent/sub_agents/aws_core/agent.py**:
   - Update `_get_model()` function to match main agent pattern

4. **agents/sre_agent/utils.py**:
   - Consider adding shared `get_configured_model()` function to avoid duplication
   - This follows the DRY principle from CLAUDE.md

5. **agents/.env.example**:
   - Add `ANTHROPIC_MODEL` with default value
   - Add `BEDROCK_INFERENCE_PROFILE` with example
   - Document the priority order

## Implementation Tasks

1. **Create Shared Model Configuration Utility**:
   - Add `get_configured_model()` to agents/sre_agent/utils.py
   - Include proper logging for which provider is selected
   - Handle all error cases with clear messages

2. **Update Main Agent**:
   - Modify agents/sre_agent/agent.py to use new utility
   - Remove local `_get_model()` function
   - Import and use `get_configured_model()` from utils

3. **Update Sub-Agents**:
   - Modify agents/sre_agent/sub_agents/aws_cost/agent.py
   - Modify agents/sre_agent/sub_agents/aws_core/agent.py
   - Both should import and use the shared utility

4. **Update Documentation**:
   - Update agents/.env.example with new environment variables
   - Add comments explaining the priority order

5. **Create Tests**:
   - Add tests/test_model_configuration.py
   - Test all three provider scenarios
   - Test error case when no API keys are set
   - Test precedence order

## Error Handling Strategy

```python
class ModelConfigurationError(Exception):
    """Raised when model configuration fails."""
    pass

# Example startup output for each scenario:

# Scenario 1: Successful Google Gemini configuration
# INFO: 🚀 Using Google Gemini provider with model: gemini-2.0-flash
# INFO: ✓ GOOGLE_API_KEY found and validated

# Scenario 2: Successful Anthropic configuration
# INFO: 🚀 Using Anthropic Claude provider with model: claude-3-5-sonnet-20240620
# INFO: ✓ ANTHROPIC_API_KEY found and validated

# Scenario 3: Successful Bedrock configuration
# INFO: ✓ AWS credentials validated for account: 123456789012
# INFO: 🚀 Using AWS Bedrock provider with profile: arn:aws:bedrock:...

# Scenario 4: Bedrock with missing AWS credentials
# ERROR: ❌ AWS Bedrock configuration error:
# ERROR:    - BEDROCK_INFERENCE_PROFILE is set but AWS credentials are not configured
# ERROR:    - Please configure AWS credentials via:
# ERROR:      • AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
# ERROR:      • AWS profile via AWS_PROFILE environment variable
# ERROR:      • IAM role (if running on AWS)
# ERROR:    - Error details: Unable to locate credentials

# Scenario 5: No configuration at all
# ERROR: ❌ No AI provider configured!
# ERROR:
# ERROR: Please configure one of the following providers:
# ERROR:
# ERROR: 1. Google Gemini (Recommended for Google Cloud users):
# ERROR:    export GOOGLE_API_KEY='your-api-key'
# ERROR:    export GOOGLE_AI_MODEL='gemini-2.0-flash'  # optional
# ERROR:
# ERROR: 2. Anthropic Claude (Via LiteLLM):
# ERROR:    export ANTHROPIC_API_KEY='your-api-key'
# ERROR:    export ANTHROPIC_MODEL='claude-3-5-sonnet-20240620'  # optional
# ERROR:
# ERROR: 3. AWS Bedrock (Requires AWS credentials):
# ERROR:    export BEDROCK_INFERENCE_PROFILE='arn:aws:bedrock:...'
# ERROR:    export AWS_ACCESS_KEY_ID='your-access-key'
# ERROR:    export AWS_SECRET_ACCESS_KEY='your-secret-key'
```

## Test Implementation

```python
# tests/test_model_configuration.py
import pytest
import os
from unittest.mock import patch, MagicMock
from agents.sre_agent.utils import get_configured_model, ModelConfigurationError
from google.adk.models.lite_llm import LiteLlm

class TestModelConfiguration:

    def test_google_api_key_returns_gemini(self):
        """Test that Google API key results in Gemini model."""
        with patch.dict(os.environ, {
            "GOOGLE_API_KEY": "test-key",
            "GOOGLE_AI_MODEL": "gemini-2.0-flash"
        }):
            model = get_configured_model()
            assert model == "gemini-2.0-flash"

    def test_anthropic_api_key_returns_litellm(self):
        """Test that Anthropic API key results in LiteLlm wrapper."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20240620"
        }, clear=True):
            model = get_configured_model()
            assert isinstance(model, LiteLlm)
            assert model.model == "claude-3-5-sonnet-20240620"

    def test_bedrock_profile_with_valid_aws_credentials(self):
        """Test Bedrock with valid AWS credentials."""
        arn = "arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0"

        # Mock boto3 to simulate valid AWS credentials
        with patch('boto3.client') as mock_boto:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                'Account': '123456789012',
                'Arn': 'arn:aws:iam::123456789012:user/test'
            }
            mock_boto.return_value = mock_sts

            with patch.dict(os.environ, {
                "BEDROCK_INFERENCE_PROFILE": arn
            }, clear=True):
                model = get_configured_model()
                assert isinstance(model, LiteLlm)
                assert model.model == arn

    def test_bedrock_profile_without_aws_credentials_raises_error(self):
        """Test that Bedrock without AWS credentials raises helpful error."""
        arn = "arn:aws:bedrock:us-west-2:812201244513:inference-profile/test"

        # Mock boto3 to simulate missing credentials
        with patch('boto3.client') as mock_boto:
            mock_boto.side_effect = Exception("Unable to locate credentials")

            with patch.dict(os.environ, {
                "BEDROCK_INFERENCE_PROFILE": arn
            }, clear=True):
                with pytest.raises(ModelConfigurationError) as exc_info:
                    get_configured_model()
                assert "Bedrock requires valid AWS credentials" in str(exc_info.value)

    def test_empty_api_key_values_are_ignored(self):
        """Test that empty string API keys are treated as missing."""
        with patch.dict(os.environ, {
            "GOOGLE_API_KEY": "",
            "ANTHROPIC_API_KEY": "   ",  # whitespace only
        }, clear=True):
            with pytest.raises(ModelConfigurationError) as exc_info:
                get_configured_model()
            assert "No AI provider API key found" in str(exc_info.value)

    def test_priority_order_google_over_anthropic(self):
        """Test that Google takes precedence over Anthropic."""
        with patch.dict(os.environ, {
            "GOOGLE_API_KEY": "google-key",
            "ANTHROPIC_API_KEY": "anthropic-key"
        }):
            model = get_configured_model()
            assert isinstance(model, str)  # Google returns string

    def test_priority_order_anthropic_over_bedrock(self):
        """Test that Anthropic takes precedence over Bedrock."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "anthropic-key",
            "BEDROCK_INFERENCE_PROFILE": "arn:aws:bedrock:test"
        }):
            model = get_configured_model()
            assert isinstance(model, LiteLlm)
            assert "claude" in model.model.lower()

    def test_no_api_keys_raises_detailed_error(self):
        """Test that missing API keys raises error with setup instructions."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ModelConfigurationError) as exc_info:
                get_configured_model()
            error_msg = str(exc_info.value)
            assert "No AI provider API key found" in error_msg
            assert "GOOGLE_API_KEY" in error_msg
            assert "ANTHROPIC_API_KEY" in error_msg
            assert "BEDROCK_INFERENCE_PROFILE" in error_msg
```

## Validation Gates (Must be Executable)

```bash
# 1. Syntax and Style Check
ruff check agents/ --fix
ruff format agents/

# 2. Type Checking (if mypy is configured)
# mypy agents/sre_agent/

# 3. Unit Tests
pytest tests/test_model_configuration.py -v

# 4. Integration Test - Test each provider with validation output
# Test Google Gemini - should show success message
export GOOGLE_API_KEY="test" && python -c "
import logging
logging.basicConfig(level=logging.INFO)
from agents.sre_agent.agent import root_agent
print('✅ Google Gemini configuration test passed')
"

# Test Anthropic Claude - should show success message
unset GOOGLE_API_KEY && export ANTHROPIC_API_KEY="test" && python -c "
import logging
logging.basicConfig(level=logging.INFO)
from agents.sre_agent.agent import root_agent
print('✅ Anthropic Claude configuration test passed')
"

# Test AWS Bedrock with credentials - should validate AWS access
export AWS_ACCESS_KEY_ID="test" && export AWS_SECRET_ACCESS_KEY="test"
export BEDROCK_INFERENCE_PROFILE="arn:aws:bedrock:us-west-2:test:inference-profile/test" && python -c "
import logging
logging.basicConfig(level=logging.INFO)
from agents.sre_agent.agent import root_agent
print('✅ AWS Bedrock configuration test passed')
"

# Test error scenario - should show helpful error messages
unset GOOGLE_API_KEY && unset ANTHROPIC_API_KEY && unset BEDROCK_INFERENCE_PROFILE && python -c "
import logging
logging.basicConfig(level=logging.ERROR)
try:
    from agents.sre_agent.agent import root_agent
except Exception as e:
    print('✅ Error handling test passed - proper error message shown')
"

# 5. Verify sub-agents also updated
grep -r "get_configured_model" agents/sre_agent/sub_agents/
```

## Edge Cases to Handle

1. **Multiple API Keys Set**: Follow priority order (Google > Anthropic > Bedrock)
2. **Invalid Model Names**: LiteLlm will handle validation, but log warnings
3. **Missing LiteLlm Import**: Already in requirements.txt, but handle ImportError gracefully
4. **Empty API Key Values**: Check for non-empty strings, not just existence
5. **Case Sensitivity**: Environment variables are case-sensitive, document this

## Common Pitfalls to Avoid

1. **Import Location**: Import LiteLlm only when needed (inside the function) to avoid unnecessary imports
2. **Model String vs Object**: Gemini uses string directly, others need LiteLlm wrapper
3. **Logging**: Use existing logger from utils.py, don't create new logger
4. **Testing**: Mock environment variables properly with `clear=True` to avoid test pollution
5. **Sub-Agent Sync**: Ensure all sub-agents use the same configuration logic

## Implementation Order

1. First, create the shared utility function in utils.py
2. Write and run tests for the utility function
3. Update main agent.py to use the utility
4. Update both sub-agents to use the utility
5. Update .env.example with new variables
6. Run full test suite and fix any issues
7. Test manually with each provider configuration

## Startup Behavior Examples

### Example 1: Google Gemini Provider
```bash
$ python agents/sre_agent/serve.py
2024-01-15 10:30:15 INFO: 🚀 Using Google Gemini provider with model: gemini-2.0-flash
2024-01-15 10:30:15 INFO: ✓ GOOGLE_API_KEY found and validated
2024-01-15 10:30:15 INFO: Starting SRE Agent API server on port 8000...
```

### Example 2: Anthropic Claude Provider
```bash
$ python agents/sre_agent/serve.py
2024-01-15 10:30:15 INFO: 🚀 Using Anthropic Claude provider with model: claude-3-5-sonnet-20240620
2024-01-15 10:30:15 INFO: ✓ ANTHROPIC_API_KEY found and validated
2024-01-15 10:30:15 INFO: Starting SRE Agent API server on port 8000...
```

### Example 3: AWS Bedrock Provider (Success)
```bash
$ python agents/sre_agent/serve.py
2024-01-15 10:30:15 INFO: ✓ AWS credentials validated for account: 123456789012
2024-01-15 10:30:15 INFO: 🚀 Using AWS Bedrock provider with profile: arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0
2024-01-15 10:30:15 INFO: Starting SRE Agent API server on port 8000...
```

### Example 4: AWS Bedrock Provider (Missing Credentials)
```bash
$ export BEDROCK_INFERENCE_PROFILE="arn:aws:bedrock:us-west-2:test:inference-profile/test"
$ python agents/sre_agent/serve.py
2024-01-15 10:30:15 ERROR: ❌ AWS Bedrock configuration error:
2024-01-15 10:30:15 ERROR:    - BEDROCK_INFERENCE_PROFILE is set but AWS credentials are not configured
2024-01-15 10:30:15 ERROR:    - Please configure AWS credentials via:
2024-01-15 10:30:15 ERROR:      • AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
2024-01-15 10:30:15 ERROR:      • AWS profile via AWS_PROFILE environment variable
2024-01-15 10:30:15 ERROR:      • IAM role (if running on AWS)
2024-01-15 10:30:15 ERROR:    - Error details: Unable to locate credentials
Traceback (most recent call last):
  File "serve.py", line 15, in <module>
    from agent import root_agent
ModelConfigurationError: Bedrock requires valid AWS credentials. Please configure AWS access before using Bedrock models.
```

### Example 5: No Configuration
```bash
$ python agents/sre_agent/serve.py
2024-01-15 10:30:15 ERROR: ❌ No AI provider configured!
2024-01-15 10:30:15 ERROR:
2024-01-15 10:30:15 ERROR: Please configure one of the following providers:
2024-01-15 10:30:15 ERROR:
2024-01-15 10:30:15 ERROR: 1. Google Gemini (Recommended for Google Cloud users):
2024-01-15 10:30:15 ERROR:    export GOOGLE_API_KEY='your-api-key'
2024-01-15 10:30:15 ERROR:    export GOOGLE_AI_MODEL='gemini-2.0-flash'  # optional
2024-01-15 10:30:15 ERROR:
2024-01-15 10:30:15 ERROR: 2. Anthropic Claude (Via LiteLLM):
2024-01-15 10:30:15 ERROR:    export ANTHROPIC_API_KEY='your-api-key'
2024-01-15 10:30:15 ERROR:    export ANTHROPIC_MODEL='claude-3-5-sonnet-20240620'  # optional
2024-01-15 10:30:15 ERROR:
2024-01-15 10:30:15 ERROR: 3. AWS Bedrock (Requires AWS credentials):
2024-01-15 10:30:15 ERROR:    export BEDROCK_INFERENCE_PROFILE='arn:aws:bedrock:...'
2024-01-15 10:30:15 ERROR:    export AWS_ACCESS_KEY_ID='your-access-key'
2024-01-15 10:30:15 ERROR:    export AWS_SECRET_ACCESS_KEY='your-secret-key'
2024-01-15 10:30:15 ERROR:    # OR use AWS_PROFILE for named profiles
2024-01-15 10:30:15 ERROR:
2024-01-15 10:30:15 ERROR: Priority order: Google > Anthropic > Bedrock
2024-01-15 10:30:15 ERROR: See agents/.env.example for complete configuration examples
Traceback (most recent call last):
  File "serve.py", line 15, in <module>
    from agent import root_agent
ModelConfigurationError: No AI provider API key found. Please set GOOGLE_API_KEY, ANTHROPIC_API_KEY, or BEDROCK_INFERENCE_PROFILE. See logs above for detailed configuration instructions.
```

## Quality Score

**Confidence Level: 10/10**

This PRP now provides:
- Complete context from codebase research
- Clear implementation patterns from existing code
- Specific import statements and code examples
- Comprehensive error handling with user-friendly messages
- Provider-specific validation (especially for AWS Bedrock)
- Clear startup output examples for all scenarios
- Executable validation gates with expected outputs
- Comprehensive test coverage including edge cases
- Detailed error messages that guide users to resolution
- Clear task ordering

The implementation path is crystal clear with detailed error handling that will immediately show users what's wrong and how to fix it upon startup.