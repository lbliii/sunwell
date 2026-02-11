"""Settings page."""

from chirp import Page
from sunwell.interface.chirp.services import ConfigService


def get(config_svc: ConfigService) -> Page:
    """Render settings page.

    Shows configuration options for:
    - Model provider (Ollama, Anthropic, OpenAI)
    - API keys
    - Default project
    - Studio preferences
    - System paths
    """
    provider_config = config_svc.get_provider_config()
    embedding_config = config_svc.get_embedding_config()
    preferences = config_svc.get_preferences()

    settings = {
        "provider": provider_config["provider"],
        "ollama_base": provider_config["ollama"]["base_url"],
        "ollama_enabled": provider_config["ollama"]["enabled"],
        "default_model": provider_config["default_model"],
        "api_key_configured": provider_config["api_key_configured"],
        # Embedding config
        "embedding_prefer_local": embedding_config["prefer_local"],
        "embedding_model": embedding_config["ollama_model"],
        # Preferences
        "auto_archive": preferences["auto_archive"],
        "spawn_enabled": preferences["spawn_enabled"],
        "max_simulacrums": preferences["max_simulacrums"],
    }

    return Page(
        "settings/page.html",
        "content",
        current_page="settings",
        settings=settings,
        title="Settings",
    )
