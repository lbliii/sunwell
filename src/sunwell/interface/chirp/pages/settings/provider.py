"""Provider settings form handler."""

from chirp import Fragment

from sunwell.interface.chirp.schemas import ProviderForm
from sunwell.interface.chirp.services import ConfigService


def post(form: ProviderForm, config_svc: ConfigService) -> Fragment:
    """Update provider settings.

    Args:
        form: Provider form data
        config_svc: Config service for persistence

    Returns:
        Success/error status message fragment
    """
    # Validate provider
    valid_providers = ["ollama", "anthropic", "openai"]
    if form.provider not in valid_providers:
        return Fragment(
            "settings/_status.html",
            "provider_status",
            success=False,
            message=f"Invalid provider: {form.provider}",
        )

    # Update config
    success = config_svc.update_provider_config(
        provider=form.provider,
        # TODO: Add more fields as needed
    )

    if success:
        return Fragment(
            "settings/_status.html",
            "provider_status",
            success=True,
            message=f"Provider settings saved: {form.provider}",
        )
    else:
        return Fragment(
            "settings/_status.html",
            "provider_status",
            success=False,
            message="Failed to save provider settings",
        )
