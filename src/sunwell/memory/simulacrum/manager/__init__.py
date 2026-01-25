"""Simulacrum manager subpackage.

RFC-025: Extracted from manager.py into modular subpackage.
"""

from sunwell.memory.simulacrum.manager.manager import SimulacrumManager
from sunwell.memory.simulacrum.manager.metadata import (
    ArchiveMetadata,
    PendingDomain,
    SimulacrumMetadata,
)
from sunwell.memory.simulacrum.manager.policy import LifecyclePolicy, SpawnPolicy
from sunwell.memory.simulacrum.manager.tools import (
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
