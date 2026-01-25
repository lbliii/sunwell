"""Simulacrum manager subpackage.

RFC-025: Extracted from manager.py into modular subpackage.
"""

from sunwell.simulacrum.manager.manager import SimulacrumManager
from sunwell.simulacrum.manager.metadata import (
    ArchiveMetadata,
    PendingDomain,
    SimulacrumMetadata,
)
from sunwell.simulacrum.manager.policy import LifecyclePolicy, SpawnPolicy
from sunwell.simulacrum.manager.tools import (
    SIMULACRUM_TOOLS,
    SimulacrumToolHandler,
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
