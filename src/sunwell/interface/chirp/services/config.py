"""Configuration service for Chirp interface."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sunwell.channels.telegram.config import (
    get_telegram_config_from_dict,
    resolve_telegram_token,
)
from sunwell.foundation.config import SunwellConfig, get_config, reset_config

logger = logging.getLogger(__name__)


def _api_key_configured_for_provider(provider: str) -> bool:
    """Whether the environment has credentials for the given provider."""
    if provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    return True


@dataclass
class ConfigService:
    """Service for accessing and modifying Sunwell configuration."""

    def _get_config_path(self) -> Path:
        """Get path to user config file.

        Returns:
            Path to .sunwell/config.yaml (project) or ~/.sunwell/config.yaml (user)
        """
        # Prefer project-local config
        project_config = Path(".sunwell/config.yaml")
        if project_config.exists():
            return project_config

        # Fall back to user-global config
        user_config = Path.home() / ".sunwell" / "config.yaml"
        user_config.parent.mkdir(parents=True, exist_ok=True)
        return user_config

    def _load_config_dict(self) -> dict[str, Any]:
        """Load current config file as dict.

        Returns:
            Config dict (empty if file doesn't exist)
        """
        config_path = self._get_config_path()
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", config_path, e)
            return {}

    def _save_config_dict(self, config_dict: dict[str, Any]) -> bool:
        """Save config dict to YAML file.

        Args:
            config_dict: Config dictionary to save

        Returns:
            True if successful
        """
        config_path = self._get_config_path()

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)

            # Reset cached config so next get_config() reloads
            reset_config()

            logger.info("Saved config to %s", config_path)
            return True
        except Exception as e:
            logger.error("Failed to save config to %s: %s", config_path, e)
            return False

    def get_config(self) -> SunwellConfig:
        """Get current configuration."""
        return get_config()

    def get_provider_config(self) -> dict[str, Any]:
        """Get provider configuration for Settings page.

        Returns:
            Dict with provider settings (model, api_key, etc.)
        """
        config = get_config()
        provider = config.model.default_provider
        default_model = config.model.default_model
        return {
            "default_model": default_model,
            "provider": provider,
            "api_key_configured": _api_key_configured_for_provider(provider),
            "ollama": {
                "base_url": config.ollama.base_url
                if hasattr(config, "ollama")
                else "http://localhost:11434",
                "enabled": True,
            },
        }

    def get_embedding_config(self) -> dict[str, Any]:
        """Get embedding configuration."""
        config = get_config()

        if hasattr(config, "embedding"):
            return {
                "prefer_local": config.embedding.prefer_local,
                "ollama_model": config.embedding.ollama_model,
                "fallback_to_hash": config.embedding.fallback_to_hash,
            }

        return {
            "prefer_local": True,
            "ollama_model": "all-minilm",
            "fallback_to_hash": True,
        }

    def get_preferences(self) -> dict[str, Any]:
        """Get user preferences."""
        config = get_config()

        # Access config attributes (dataclasses), not dict keys
        auto_archive = True
        spawn_enabled = True
        max_simulacrums = 20

        if hasattr(config, "simulacrum") and config.simulacrum:
            if hasattr(config.simulacrum, "lifecycle") and config.simulacrum.lifecycle:
                auto_archive = getattr(config.simulacrum.lifecycle, "auto_archive", True)
            if hasattr(config.simulacrum, "spawn") and config.simulacrum.spawn:
                spawn_enabled = getattr(config.simulacrum.spawn, "enabled", True)
                max_simulacrums = getattr(config.simulacrum.spawn, "max_simulacrums", 20)

        return {
            "auto_archive": auto_archive,
            "spawn_enabled": spawn_enabled,
            "max_simulacrums": max_simulacrums,
        }

    def update_provider_config(
        self,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        ollama_base: str | None = None,
    ) -> bool:
        """Update provider configuration.

        Cloud API keys are not written to YAML (use environment variables or a
        future keyring integration). Passing ``api_key`` logs intent only.

        Args:
            provider: Provider name (ollama, anthropic, openai)
            api_key: Optional API key to set
            model: Optional default model
            ollama_base: Optional Ollama base URL

        Returns:
            True if successful
        """
        config_dict = self._load_config_dict()

        # Ensure model section exists
        if "model" not in config_dict:
            config_dict["model"] = {}

        # Update provider
        config_dict["model"]["default_provider"] = provider

        # Update model if provided
        if model:
            config_dict["model"]["default_model"] = model

        # Update Ollama config if provided
        if ollama_base:
            if "ollama" not in config_dict:
                config_dict["ollama"] = {}
            config_dict["ollama"]["base_url"] = ollama_base

        if api_key:
            logger.info(
                "API key update requested for provider %s — set %s in the environment "
                "or shell profile; keys are not persisted to config.yaml",
                provider,
                "ANTHROPIC_API_KEY"
                if provider == "anthropic"
                else ("OPENAI_API_KEY" if provider == "openai" else "N/A"),
            )

        return self._save_config_dict(config_dict)

    def get_telegram_config(self) -> dict[str, Any]:
        """Get Telegram channel config for Settings page."""
        config_dict = self._load_config_dict()
        return get_telegram_config_from_dict(config_dict)

    def get_telegram_token_for_runtime(self) -> str | None:
        """Resolve Telegram token for runtime (start bot). Returns None if disabled."""
        config_dict = self._load_config_dict()
        channels = config_dict.get("channels", {})
        tg = channels.get("telegram", {}) or {}
        if not isinstance(tg, dict) or not tg.get("enabled", False):
            return None
        return resolve_telegram_token(config_dict)

    def update_telegram_config(
        self,
        enabled: bool,
        token: str = "",
    ) -> bool:
        """Update Telegram channel config.

        Args:
            enabled: Enable/disable the channel
            token: Bot token (empty string clears stored token)

        Returns:
            True if successful
        """
        config_dict = self._load_config_dict()
        if "channels" not in config_dict:
            config_dict["channels"] = {}
        if "telegram" not in config_dict["channels"]:
            config_dict["channels"]["telegram"] = {}

        config_dict["channels"]["telegram"]["enabled"] = enabled
        if token.strip():
            config_dict["channels"]["telegram"]["token"] = token.strip()
        else:
            config_dict["channels"]["telegram"].pop("token", None)

        return self._save_config_dict(config_dict)

    def update_preferences(self, preferences: dict[str, Any]) -> bool:
        """Update user preferences.

        Args:
            preferences: Dict of preference key-value pairs (theme, auto_save, etc.)

        Returns:
            True if successful
        """
        config_dict = self._load_config_dict()

        # Map UI preferences to config structure
        # Theme, auto_save, show_token_counts go to root or appropriate sections

        # Simulacrum preferences
        if (
            "auto_archive" in preferences
            or "spawn_enabled" in preferences
            or "max_simulacrums" in preferences
        ):
            if "simulacrum" not in config_dict:
                config_dict["simulacrum"] = {}

            if "auto_archive" in preferences:
                if "lifecycle" not in config_dict["simulacrum"]:
                    config_dict["simulacrum"]["lifecycle"] = {}
                config_dict["simulacrum"]["lifecycle"]["auto_archive"] = preferences["auto_archive"]

            if "spawn_enabled" in preferences:
                if "spawn" not in config_dict["simulacrum"]:
                    config_dict["simulacrum"]["spawn"] = {}
                config_dict["simulacrum"]["spawn"]["enabled"] = preferences["spawn_enabled"]

            if "max_simulacrums" in preferences:
                if "spawn" not in config_dict["simulacrum"]:
                    config_dict["simulacrum"]["spawn"] = {}
                config_dict["simulacrum"]["spawn"]["max_simulacrums"] = preferences[
                    "max_simulacrums"
                ]

        # Note: theme, auto_save, show_token_counts are UI-only preferences
        # They don't map to Sunwell core config, so we'd need a separate
        # studio config file for these. For now, acknowledge but don't persist.
        if (
            "theme" in preferences
            or "auto_save" in preferences
            or "show_token_counts" in preferences
        ):
            logger.info(
                "UI preferences (theme, auto_save, show_token_counts) not persisted yet; "
                "need studio config"
            )

        return self._save_config_dict(config_dict)
