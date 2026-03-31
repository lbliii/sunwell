"""Form schemas and validation for Chirp interface.

All form dataclasses are defined here for reuse across page handlers.
"""

from sunwell.interface.chirp.schemas.project import NewProjectForm
from sunwell.interface.chirp.schemas.settings import (
    APIKeysForm,
    PreferencesForm,
    ProviderForm,
    TelegramForm,
)

__all__ = [
    # Project schemas
    "NewProjectForm",
    # Settings schemas
    "ProviderForm",
    "PreferencesForm",
    "APIKeysForm",
    "TelegramForm",
]
