"""Plan persistence and incremental execution for RFC-040.

This package provides modular persistence support:
- hashing: Content hashing utilities
- types: ExecutionStatus, ArtifactCompletion
- saved_execution: SavedExecution class
- plan_version: PlanVersion, PlanDiff classes
- store: PlanStore class
- trace: TraceLogger class
- resume: resume_execution function
- utils: Utility functions
"""

# Re-export all public APIs
from sunwell.planning.naaru.persistence.hashing import hash_content, hash_file, hash_goal
from sunwell.planning.naaru.persistence.plan_version import PlanDiff, PlanVersion
from sunwell.planning.naaru.persistence.resume import resume_execution
from sunwell.planning.naaru.persistence.saved_execution import PERSISTENCE_VERSION, SavedExecution
from sunwell.planning.naaru.persistence.store import DEFAULT_PLANS_DIR, PlanStore
from sunwell.planning.naaru.persistence.trace import TraceLogger
from sunwell.planning.naaru.persistence.types import ArtifactCompletion, ExecutionStatus
from sunwell.planning.naaru.persistence.utils import get_latest_execution, save_execution

__all__ = [
    # Types
    "ExecutionStatus",
    "ArtifactCompletion",
    "SavedExecution",
    "PlanVersion",
    "PlanDiff",
    # Classes
    "PlanStore",
    "TraceLogger",
    # Functions
    "hash_goal",
    "hash_content",
    "hash_file",
    "resume_execution",
    "get_latest_execution",
    "save_execution",
    # Constants
    "PERSISTENCE_VERSION",
    "DEFAULT_PLANS_DIR",
]
