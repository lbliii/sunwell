"""Telegram channel settings form handler."""

from chirp import Fragment

from sunwell.interface.chirp.schemas import TelegramForm
from sunwell.interface.chirp.services import ConfigService


def post(form: TelegramForm, config_svc: ConfigService) -> Fragment:
    """Update Telegram channel settings.

    Args:
        form: Telegram form data
        config_svc: Config service for persistence

    Returns:
        Success/error status message fragment
    """
    success = config_svc.update_telegram_config(
        enabled=form.enabled,
        token=form.token,
    )

    if success:
        return Fragment(
            "settings/_status.html",
            "telegram_status",
            success=True,
            message="Telegram settings saved. Restart Sunwell Studio for changes to take effect.",
        )
    return Fragment(
        "settings/_status.html",
        "telegram_status",
        success=False,
        message="Failed to save Telegram settings",
    )
