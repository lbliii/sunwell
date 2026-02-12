"""Form schemas and validation for Chirp interface.

All form dataclasses are defined here for reuse across page handlers.
"""

from sunwell.interface.chirp.schemas.backlog import NewGoalForm
from sunwell.interface.chirp.schemas.project import NewProjectForm
from sunwell.interface.chirp.schemas.settings import APIKeysForm, PreferencesForm, ProviderForm
from sunwell.interface.chirp.schemas.writer import NewDocumentForm

__all__ = [
    # Project schemas
    "NewProjectForm",
    # Backlog schemas
    "NewGoalForm",
    # Writer schemas
    "NewDocumentForm",
    # Settings schemas
    "ProviderForm",
    "PreferencesForm",
    "APIKeysForm",
]
