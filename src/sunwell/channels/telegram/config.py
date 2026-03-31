"""Telegram channel token resolution.

Priority: TELEGRAM_BOT_TOKEN env -> config file (channels.telegram.token)
-> config file (channels.telegram.token_file) for path to file.
"""

import os
from pathlib import Path
from typing import Any


def resolve_telegram_token(config_dict: dict[str, Any]) -> str | None:
    """Resolve Telegram bot token from env and config.

    Priority:
    1. TELEGRAM_BOT_TOKEN environment variable
    2. channels.telegram.token in config
    3. channels.telegram.token_file path to file containing token

    Returns:
        Token string or None if not configured
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token and token.strip():
        return token.strip()

    channels = config_dict.get("channels", {})
    tg = channels.get("telegram", {})
    if not isinstance(tg, dict):
        return None

    token = tg.get("token")
    if token and isinstance(token, str) and token.strip():
        return token.strip()

    token_file = tg.get("token_file")
    if token_file and isinstance(token_file, str):
        path = Path(token_file).expanduser()
        if path.exists():
            try:
                return path.read_text().strip()
            except OSError:
                pass

    return None


def get_telegram_config_from_dict(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract Telegram channel config for Settings UI."""
    token = resolve_telegram_token(config_dict)
    channels = config_dict.get("channels", {})
    tg = channels.get("telegram", {}) or {}
    if not isinstance(tg, dict):
        tg = {}

    return {
        "enabled": tg.get("enabled", False),
        "token_configured": token is not None and len(token or "") > 0,
        "token": (token[:8] + "..." if token and len(token) > 8 else "") or "",
    }
