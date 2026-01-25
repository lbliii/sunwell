"""Recovery & Review system for handling execution failures (RFC-125).

When Sunwell can't automatically fix errors, this module preserves all
progress and provides a review interface — like GitHub's merge conflict UI.

Example:
    >>> from sunwell.recovery import RecoveryManager, RecoveryState
    >>>
    >>> # On failure, state is automatically saved
    >>> manager = RecoveryManager(Path(".sunwell/recovery"))
    >>>
    >>> # List pending recoveries
    >>> for summary in manager.list_pending():
    ...     print(f"{summary.goal[:50]}... - {summary.passed}/{summary.total} passed")
    >>>
    >>> # Load and review
    >>> state = manager.load(goal_hash)
    >>> for artifact in state.failed_artifacts:
    ...     print(f"  ⚠️ {artifact.path}: {artifact.errors[0]}")
    >>>
    >>> # Resume with agent
    >>> async for event in agent.resume_from_recovery(state):
    ...     print(event)
"""

from sunwell.agent.recovery.context import build_healing_context
from sunwell.agent.recovery.manager import RecoveryManager
from sunwell.agent.recovery.recovery_helpers import (
    execute_with_convergence_recovery,
    resume_from_recovery,
)
from sunwell.agent.recovery.types import (
    ArtifactStatus,
    RecoveryArtifact,
    RecoveryState,
    RecoverySummary,
)

__all__ = [
    "ArtifactStatus",
    "RecoveryArtifact",
    "RecoveryManager",
    "RecoveryState",
    "RecoverySummary",
    "build_healing_context",
    "execute_with_convergence_recovery",
    "resume_from_recovery",
]
