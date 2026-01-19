"""Simulacrum manager subpackage.

RFC-025: Extracted from manager.py into modular subpackage.
"""

from sunwell.simulacrum.manager.manager import SimulacrumManager
from sunwell.simulacrum.manager.policy import SpawnPolicy, LifecyclePolicy
from sunwell.simulacrum.manager.metadata import (
    SimulacrumMetadata,
    PendingDomain,
    ArchiveMetadata,
)
from sunwell.simulacrum.manager.tools import (
    SimulacrumToolHandler,
    SIMULACRUM_TOOLS,
)

__all__ = [
    "SimulacrumManager",
    "SpawnPolicy",
    "LifecyclePolicy",
    "SimulacrumMetadata",
    "PendingDomain",
    "ArchiveMetadata",
    "SimulacrumToolHandler",
    "SIMULACRUM_TOOLS",
]
