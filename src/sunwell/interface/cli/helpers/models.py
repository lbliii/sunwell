"""Model creation utilities."""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


def create_model(provider: str, model_name: str) -> ModelProtocol:
    """Create model instance based on provider."""
    from sunwell.interface.cli.core.theme import console

    if provider == "mock":
        from sunwell.models import MockModel

        return MockModel()

    elif provider == "anthropic":
        from sunwell.models import AnthropicModel

        return AnthropicModel(
            model=model_name,
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    elif provider == "openai":
        from sunwell.models import OpenAIModel

        return OpenAIModel(
            model=model_name,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )

    elif provider == "ollama":
        from sunwell.foundation.config import get_config
        from sunwell.models import OllamaModel

        cfg = get_config()
        return OllamaModel(
            model=model_name,
            use_native_api=cfg.naaru.use_native_ollama_api,
        )

    else:
        console.print(f"[red]Unknown provider:[/red] {provider}")
        console.print("Available: anthropic, openai, ollama, mock")
        import sys

        sys.exit(1)


def resolve_model(
    provider_override: str | None = None,
    model_override: str | None = None,
) -> ModelProtocol:
    """Resolve model from CLI overrides or config defaults.

    Priority:
    1. CLI overrides (--provider, --model)
    2. Config defaults (model.default_provider, model.default_model)
    3. Provider-specific defaults (if provider specified but no model)
    4. Hardcoded fallbacks (ollama, llama3.1:8b)

    Args:
        provider_override: Provider from CLI --provider flag
        model_override: Model name from CLI --model flag

    Returns:
        Configured model instance
    """
    from sunwell.foundation.config import get_config

    cfg = get_config()

    # Priority 1: CLI overrides
    provider = provider_override or cfg.model.default_provider or "ollama"

    # Priority 2: Config model, then provider-specific defaults, then fallback
    if model_override:
        model_name = model_override
    elif cfg.model.default_model:
        model_name = cfg.model.default_model
    else:
        # Priority 3: Provider-specific defaults
        provider_defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "llama3.1:8b",
            "mock": "mock-model",
        }
        model_name = provider_defaults.get(provider, "llama3.1:8b")

    return create_model(provider, model_name)
