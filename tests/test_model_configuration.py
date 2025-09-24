"""
Comprehensive tests for model configuration functionality.

Tests all three provider scenarios (Google, Anthropic, Bedrock),
error handling, priority order, and edge cases.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from agents.sre_agent.utils import get_configured_model, ModelConfigurationError


class TestModelConfiguration:
    """Test model configuration logic for all providers."""

    def test_google_api_key_returns_gemini(self):
        """Test that Google API key results in Gemini model."""
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "test-key", "GOOGLE_AI_MODEL": "gemini-2.0-flash"},
        ):
            model = get_configured_model()
            assert model == "gemini-2.0-flash"

    def test_google_api_key_uses_default_model(self):
        """Test that Google API key uses default model when GOOGLE_AI_MODEL not set."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=True):
            model = get_configured_model()
            assert model == "gemini-2.0-flash"  # Default value

    def test_anthropic_api_key_returns_litellm(self):
        """Test that Anthropic API key results in LiteLlm wrapper."""
        with patch("google.adk.models.lite_llm.LiteLlm") as mock_litellm:
            mock_instance = MagicMock()
            mock_litellm.return_value = mock_instance
            mock_instance.model = "claude-3-5-sonnet-20240620"

            with patch.dict(
                os.environ,
                {
                    "ANTHROPIC_API_KEY": "test-key",
                    "ANTHROPIC_MODEL": "claude-3-5-sonnet-20240620",
                },
                clear=True,
            ):
                model = get_configured_model()
                assert model == mock_instance
                mock_litellm.assert_called_once_with(model="claude-3-5-sonnet-20240620")

    def test_anthropic_api_key_uses_default_model(self):
        """Test that Anthropic API key uses default model when ANTHROPIC_MODEL not set."""
        with patch("google.adk.models.lite_llm.LiteLlm") as mock_litellm:
            mock_instance = MagicMock()
            mock_litellm.return_value = mock_instance

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
                model = get_configured_model()
                assert model == mock_instance
                mock_litellm.assert_called_once_with(
                    model="claude-3-5-sonnet-20240620"
                )  # Default

    def test_bedrock_profile_with_valid_aws_credentials(self):
        """Test Bedrock with valid AWS credentials."""
        arn = "arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0"

        # Mock boto3 to simulate valid AWS credentials
        with patch("boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_boto.return_value = mock_sts

            with patch("google.adk.models.lite_llm.LiteLlm") as mock_litellm:
                mock_instance = MagicMock()
                mock_instance.model = arn
                mock_litellm.return_value = mock_instance

                with patch.dict(
                    os.environ, {"BEDROCK_INFERENCE_PROFILE": arn}, clear=True
                ):
                    model = get_configured_model()
                    assert model == mock_instance
                    # LiteLLM requires bedrock/ prefix for Bedrock models
                    mock_litellm.assert_called_once_with(model=f"bedrock/{arn}")

    def test_bedrock_profile_without_aws_credentials_raises_error(self):
        """Test that Bedrock without AWS credentials raises helpful error."""
        arn = "arn:aws:bedrock:us-west-2:812201244513:inference-profile/test"

        # Mock boto3 to simulate missing credentials
        with patch("boto3.client") as mock_boto:
            mock_boto.side_effect = Exception("Unable to locate credentials")

            with patch.dict(os.environ, {"BEDROCK_INFERENCE_PROFILE": arn}, clear=True):
                with pytest.raises(ModelConfigurationError) as exc_info:
                    get_configured_model()
                assert "Bedrock requires valid AWS credentials" in str(exc_info.value)

    def test_bedrock_missing_boto3_raises_error(self):
        """Test that Bedrock without boto3 raises helpful error."""
        arn = "arn:aws:bedrock:us-west-2:812201244513:inference-profile/test"

        # Mock boto3 import to fail
        with patch.dict("sys.modules", {"boto3": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'boto3'"),
            ):
                with patch.dict(
                    os.environ, {"BEDROCK_INFERENCE_PROFILE": arn}, clear=True
                ):
                    with pytest.raises(ModelConfigurationError) as exc_info:
                        get_configured_model()
                    assert "boto3" in str(exc_info.value)

    def test_empty_api_key_values_are_ignored(self):
        """Test that empty string API keys are treated as missing."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "",
                "ANTHROPIC_API_KEY": "   ",  # whitespace only
            },
            clear=True,
        ):
            with pytest.raises(ModelConfigurationError) as exc_info:
                get_configured_model()
            assert "No AI provider API key found" in str(exc_info.value)

    def test_priority_order_google_over_anthropic(self):
        """Test that Google takes precedence over Anthropic."""
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "google-key", "ANTHROPIC_API_KEY": "anthropic-key"},
        ):
            model = get_configured_model()
            assert isinstance(model, str)  # Google returns string

    def test_priority_order_google_over_bedrock(self):
        """Test that Google takes precedence over Bedrock."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "google-key",
                "BEDROCK_INFERENCE_PROFILE": "arn:aws:bedrock:test",
            },
        ):
            model = get_configured_model()
            assert isinstance(model, str)  # Google returns string

    def test_priority_order_anthropic_over_bedrock(self):
        """Test that Anthropic takes precedence over Bedrock."""
        with patch("google.adk.models.lite_llm.LiteLlm") as mock_litellm:
            mock_instance = MagicMock()
            mock_instance.model = "claude-3-5-sonnet-20240620"
            mock_litellm.return_value = mock_instance

            with patch.dict(
                os.environ,
                {
                    "ANTHROPIC_API_KEY": "anthropic-key",
                    "BEDROCK_INFERENCE_PROFILE": "arn:aws:bedrock:test",
                },
                clear=True,
            ):
                model = get_configured_model()
                assert model == mock_instance
                # Should call LiteLlm with Claude model, not Bedrock
                mock_litellm.assert_called_once_with(model="claude-3-5-sonnet-20240620")

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

    def test_anthropic_litellm_import_error_raises_helpful_error(self):
        """Test that LiteLlm import error for Anthropic raises helpful error."""
        with patch(
            "google.adk.models.lite_llm.LiteLlm",
            side_effect=ImportError("No module named 'google.adk.models.lite_llm'"),
        ):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
                with pytest.raises(ModelConfigurationError) as exc_info:
                    get_configured_model()
                assert "LiteLlm is required for Anthropic Claude" in str(exc_info.value)

    def test_bedrock_litellm_import_error_raises_helpful_error(self):
        """Test that LiteLlm import error for Bedrock raises helpful error."""
        # Mock successful AWS credentials check
        with patch("boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_boto.return_value = mock_sts

            # Mock LiteLlm import failure
            with patch(
                "google.adk.models.lite_llm.LiteLlm",
                side_effect=ImportError("No module named 'google.adk.models.lite_llm'"),
            ):
                with patch.dict(
                    os.environ,
                    {"BEDROCK_INFERENCE_PROFILE": "arn:aws:bedrock:test"},
                    clear=True,
                ):
                    with pytest.raises(ModelConfigurationError) as exc_info:
                        get_configured_model()
                    assert "LiteLlm is required for AWS Bedrock" in str(exc_info.value)

    def test_case_sensitivity_of_environment_variables(self):
        """Test that environment variables are case-sensitive."""
        with patch.dict(
            os.environ,
            {
                "google_api_key": "test-key",  # lowercase
                "Google_API_Key": "test-key",  # mixed case
            },
            clear=True,
        ):
            with pytest.raises(ModelConfigurationError) as exc_info:
                get_configured_model()
            assert "No AI provider API key found" in str(exc_info.value)

        # Test correct case works
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "test-key"  # correct case
            },
            clear=True,
        ):
            model = get_configured_model()
            assert model == "gemini-2.0-flash"

    def test_all_providers_set_uses_google_priority(self):
        """Test that when all providers are set, Google is used (highest priority)."""
        with patch("boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_boto.return_value = mock_sts

            with patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "google-key",
                    "ANTHROPIC_API_KEY": "anthropic-key",
                    "BEDROCK_INFERENCE_PROFILE": "arn:aws:bedrock:test",
                },
            ):
                model = get_configured_model()
                # Should return Google's string model, not LiteLlm wrapper
                assert isinstance(model, str)
                assert model == "gemini-2.0-flash"
