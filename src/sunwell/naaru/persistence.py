"""Plan persistence and incremental execution for RFC-040.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from `sunwell.naaru.persistence` (the package) instead.

This module re-exports everything from the modular persistence package.
The actual implementations are in:
- `sunwell.naaru.persistence.hashing` - Hash functions
- `sunwell.naaru.persistence.types` - ExecutionStatus, ArtifactCompletion
- `sunwell.naaru.persistence.saved_execution` - SavedExecution class
- `sunwell.naaru.persistence.plan_version` - PlanVersion, PlanDiff classes
- `sunwell.naaru.persistence.store` - PlanStore class
- `sunwell.naaru.persistence.trace` - TraceLogger class
- `sunwell.naaru.persistence.resume` - resume_execution function
- `sunwell.naaru.persistence.utils` - Utility functions

Migration guide:
    # Old (still works)
    from sunwell.naaru.persistence import PlanStore

    # New (same import, but now from package)
    from sunwell.naaru.persistence import PlanStore
"""

# Re-export everything from the modular persistence package for backward compatibility
from sunwell.naaru.persistence import (
    DEFAULT_PLANS_DIR,
    ArtifactCompletion,
    ExecutionStatus,
    PlanDiff,
    PlanStore,
    PlanVersion,
    PERSISTENCE_VERSION,
    SavedExecution,
    TraceLogger,
    get_latest_execution,
    hash_content,
    hash_file,
    hash_goal,
    resume_execution,
    save_execution,
)

__all__ = [
    "DEFAULT_PLANS_DIR",
    "ArtifactCompletion",
    "ExecutionStatus",
    "PlanDiff",
    "PlanStore",
    "PlanVersion",
    "PERSISTENCE_VERSION",
    "SavedExecution",
    "TraceLogger",
    "get_latest_execution",
    "hash_content",
    "hash_file",
    "hash_goal",
    "resume_execution",
    "save_execution",
]
