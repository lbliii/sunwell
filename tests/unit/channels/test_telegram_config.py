"""Tests for Telegram token resolution."""

import pytest

from sunwell.channels.telegram.config import (
    get_telegram_config_from_dict,
    resolve_telegram_token,
)


def test_resolve_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "  abc123  ")
    assert resolve_telegram_token({}) == "abc123"


def test_resolve_token_from_config() -> None:
    config = {"channels": {"telegram": {"token": "config-token"}}}
    assert resolve_telegram_token(config) == "config-token"


def test_resolve_token_env_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    config = {"channels": {"telegram": {"token": "config-token"}}}
    assert resolve_telegram_token(config) == "env-token"


def test_resolve_token_none_when_empty() -> None:
    assert resolve_telegram_token({}) is None
    assert resolve_telegram_token({"channels": {}}) is None


def test_get_telegram_config_from_dict() -> None:
    config = {"channels": {"telegram": {"enabled": True, "token": "secret123"}}}
    out = get_telegram_config_from_dict(config)
    assert out["enabled"] is True
    assert out["token_configured"] is True
    assert "secret" in out["token"] or "..." in out["token"]
