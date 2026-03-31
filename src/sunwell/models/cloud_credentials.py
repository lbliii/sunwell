"""Validate environment for cloud LLM providers before adapter construction."""

import os

from sunwell.foundation.errors import ErrorCode, SunwellError


def require_cloud_provider_env(provider: str) -> None:
    """Raise SunwellError if a cloud provider is selected but its API key is missing.

    Ollama and mock do not require keys. Call from CLI ``create_model`` and registry
    factories so misconfiguration fails at resolution time instead of first generate().
    """
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SunwellError(
            code=ErrorCode.CONFIG_ENV_MISSING,
            context={
                "var": "ANTHROPIC_API_KEY",
                "provider": "anthropic",
                "flag": "provider ollama",
            },
        )
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise SunwellError(
            code=ErrorCode.CONFIG_ENV_MISSING,
            context={
                "var": "OPENAI_API_KEY",
                "provider": "openai",
                "flag": "provider ollama",
            },
        )
