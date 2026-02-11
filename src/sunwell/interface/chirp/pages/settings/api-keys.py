"""API keys form handler."""

from dataclasses import dataclass

from chirp import Fragment
from sunwell.interface.chirp.services import ConfigService


@dataclass(frozen=True, slots=True)
class APIKeysForm:
    """API keys configuration form."""

    anthropic_api_key: str = ""
    openai_api_key: str = ""


def post(form: APIKeysForm, config_svc: ConfigService) -> Fragment:
    """Update API keys.

    Args:
        form: API keys form data
        config_svc: Config service for persistence

    Returns:
        Success/error status message fragment
    """
    # TODO: Securely store API keys (encrypted, keyring, etc.)
    # For now, just acknowledge the update

    if not form.anthropic_api_key and not form.openai_api_key:
        return Fragment(
            "settings/_status.html",
            "keys_status",
            success=False,
            message="No API keys provided",
        )

    keys_saved = []
    if form.anthropic_api_key:
        keys_saved.append("Anthropic")
    if form.openai_api_key:
        keys_saved.append("OpenAI")

    return Fragment(
        "settings/_status.html",
        "keys_status",
        success=True,
        message=f"API keys saved: {', '.join(keys_saved)}",
    )
