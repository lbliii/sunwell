"""Preferences form handler."""

from dataclasses import dataclass

from chirp import Fragment
from sunwell.interface.chirp.services import ConfigService


@dataclass(frozen=True, slots=True)
class PreferencesForm:
    """Studio preferences form."""

    theme: str = "dark"
    auto_save: bool = False
    show_token_counts: bool = False


def post(form: PreferencesForm, config_svc: ConfigService) -> Fragment:
    """Update studio preferences.

    Args:
        form: Preferences form data
        config_svc: Config service for persistence

    Returns:
        Success/error status message fragment
    """
    # Validate theme
    valid_themes = ["dark", "light", "auto"]
    if form.theme not in valid_themes:
        return Fragment(
            "settings/_status.html",
            "preferences_status",
            success=False,
            message=f"Invalid theme: {form.theme}",
        )

    # Update preferences
    preferences = {
        "theme": form.theme,
        "auto_save": form.auto_save,
        "show_token_counts": form.show_token_counts,
    }

    success = config_svc.update_preferences(preferences)

    if success:
        return Fragment(
            "settings/_status.html",
            "preferences_status",
            success=True,
            message="Preferences saved successfully",
        )
    else:
        return Fragment(
            "settings/_status.html",
            "preferences_status",
            success=False,
            message="Failed to save preferences",
        )
