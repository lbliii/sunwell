"""Settings page."""

from sunwell.interface.chirp.services import ConfigService


def get(config_svc: ConfigService) -> dict:
    """Render settings page."""
    provider_config = config_svc.get_provider_config()
    embedding_config = config_svc.get_embedding_config()
    preferences = config_svc.get_preferences()
    telegram_config = config_svc.get_telegram_config()

    settings = {
        "provider": provider_config["provider"],
        "ollama_base": provider_config["ollama"]["base_url"],
        "ollama_enabled": provider_config["ollama"]["enabled"],
        "ollama_model": embedding_config["ollama_model"],
        "default_model": provider_config["default_model"],
        "api_key_configured": provider_config["api_key_configured"],
        "anthropic_api_key": "",
        "openai_api_key": "",
        "embedding_prefer_local": embedding_config["prefer_local"],
        "embedding_model": embedding_config["ollama_model"],
        "theme": "dark",
        "auto_save": False,
        "show_token_counts": False,
        "auto_archive": preferences["auto_archive"],
        "spawn_enabled": preferences["spawn_enabled"],
        "max_simulacrums": preferences["max_simulacrums"],
        "telegram_enabled": telegram_config["enabled"],
        "telegram_token_configured": telegram_config["token_configured"],
        "telegram_token_preview": telegram_config["token"],
    }

    return {
        "settings": settings,
        "page_title": "Settings - Sunwell Studio",
        "breadcrumb_label": "Settings",
    }
