"""Tests for CLI helpers — provider/model selection (RFC-Cloud-Model-Parity).

Tests the `create_model()` and `resolve_model()` functions that centralize
model instantiation across all CLI commands.
"""

from unittest.mock import MagicMock, patch

import pytest


def get_model_name(model) -> str:
    """Extract model name from any model type."""
    # MockModel has model_id property but no model attribute
    if hasattr(model, "model"):
        return model.model
    return model.model_id


class TestCreateModel:
    """Tests for create_model() helper."""

    def test_create_model_mock(self) -> None:
        """create_model('mock', ...) returns MockModel."""
        from sunwell.interface.cli.helpers import create_model
        from sunwell.models.adapters.mock import MockModel

        model = create_model("mock", "mock")
        assert isinstance(model, MockModel)

    def test_create_model_ollama(self) -> None:
        """create_model('ollama', 'gemma3:4b') returns OllamaModel."""
        from sunwell.interface.cli.helpers import create_model
        from sunwell.models.ollama import OllamaModel

        model = create_model("ollama", "gemma3:4b")
        assert isinstance(model, OllamaModel)
        assert model.model == "gemma3:4b"

    def test_create_model_openai(self) -> None:
        """create_model('openai', 'gpt-4o') returns OpenAIModel."""
        from sunwell.interface.cli.helpers import create_model
        from sunwell.models.openai import OpenAIModel

        model = create_model("openai", "gpt-4o")
        assert isinstance(model, OpenAIModel)
        assert model.model == "gpt-4o"

    def test_create_model_anthropic(self) -> None:
        """create_model('anthropic', 'claude-sonnet-4-20250514') returns AnthropicModel."""
        from sunwell.interface.cli.helpers import create_model
        from sunwell.models.anthropic import AnthropicModel

        model = create_model("anthropic", "claude-sonnet-4-20250514")
        assert isinstance(model, AnthropicModel)
        assert model.model == "claude-sonnet-4-20250514"

    def test_create_model_unknown_provider_exits(self) -> None:
        """create_model with unknown provider exits with error."""
        from sunwell.interface.cli.helpers import create_model

        with pytest.raises(SystemExit):
            create_model("unknown_provider", "some-model")


class TestResolveModel:
    """Tests for resolve_model() helper."""

    def test_resolve_model_cli_override_takes_precedence(self) -> None:
        """CLI override takes precedence over config defaults."""
        from sunwell.interface.cli.helpers import resolve_model
        from sunwell.models.anthropic import AnthropicModel

        # Even if config says ollama, CLI override wins
        model = resolve_model(
            provider_override="anthropic",
            model_override="claude-sonnet-4-20250514",
        )
        assert isinstance(model, AnthropicModel)
        assert model.model == "claude-sonnet-4-20250514"

    def test_resolve_model_uses_config_defaults(self) -> None:
        """resolve_model() with no args uses config.model.default_provider."""
        from sunwell.interface.cli.helpers import resolve_model
        from sunwell.models.openai import OpenAIModel

        # Mock config to return openai as default
        mock_config = MagicMock()
        mock_config.model.default_provider = "openai"
        mock_config.model.default_model = "gpt-4o"

        # Patch at the source module where get_config is defined
        with patch("sunwell.config.get_config", return_value=mock_config):
            model = resolve_model()

        assert isinstance(model, OpenAIModel)
        assert model.model == "gpt-4o"

    def test_resolve_model_provider_only_override(self) -> None:
        """Provider override uses provider-specific default model when config model is None."""
        from sunwell.interface.cli.helpers import resolve_model
        from sunwell.models.anthropic import AnthropicModel

        # Mock config with no default model
        mock_config = MagicMock()
        mock_config.model.default_provider = "ollama"
        mock_config.model.default_model = None

        # Override provider but not model — should use anthropic's default
        with patch("sunwell.config.get_config", return_value=mock_config):
            model = resolve_model(provider_override="anthropic")

        assert isinstance(model, AnthropicModel)
        assert model.model == "claude-sonnet-4-20250514"

    def test_resolve_model_model_only_override(self) -> None:
        """Model override with config provider uses specified model."""
        from sunwell.interface.cli.helpers import resolve_model
        from sunwell.models.openai import OpenAIModel

        # Mock config to return openai as default provider
        mock_config = MagicMock()
        mock_config.model.default_provider = "openai"
        mock_config.model.default_model = None  # No default model

        with patch("sunwell.config.get_config", return_value=mock_config):
            model = resolve_model(model_override="gpt-4-turbo")

        assert isinstance(model, OpenAIModel)
        assert model.model == "gpt-4-turbo"

    def test_resolve_model_fallback_to_ollama(self) -> None:
        """With no config and no override, fallback to ollama."""
        from sunwell.interface.cli.helpers import resolve_model
        from sunwell.models.ollama import OllamaModel

        # Mock config that has no model settings
        mock_config = MagicMock()
        mock_config.model.default_provider = None
        mock_config.model.default_model = None

        with patch("sunwell.config.get_config", return_value=mock_config):
            model = resolve_model()

        assert isinstance(model, OllamaModel)
        assert model.model == "gemma3:4b"


class TestProviderDefaults:
    """Tests for provider-specific default models."""

    @pytest.mark.parametrize(
        "provider,expected_model",
        [
            ("openai", "gpt-4o"),
            ("anthropic", "claude-sonnet-4-20250514"),
            ("ollama", "gemma3:4b"),
            ("mock", "mock-model"),  # MockModel returns "mock-model" from model_id
        ],
    )
    def test_provider_default_models(self, provider: str, expected_model: str) -> None:
        """Each provider has a sensible default model when config is empty."""
        from sunwell.interface.cli.helpers import resolve_model

        # Mock config with no defaults
        mock_config = MagicMock()
        mock_config.model.default_provider = None
        mock_config.model.default_model = None

        with patch("sunwell.config.get_config", return_value=mock_config):
            model = resolve_model(provider_override=provider)

        assert get_model_name(model) == expected_model
