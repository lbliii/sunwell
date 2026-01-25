"""Multi-Instance Coordination — Parallel Autonomous Agents (RFC-051).

Enables multiple Sunwell agent instances to work in parallel on the same
codebase, dividing work intelligently and avoiding conflicts.

Core Components:
- Coordinator: Spawns workers, monitors health, merges results
- WorkerProcess: Claims goals, executes, commits to isolated branch
- FileLockManager: Prevents concurrent file access
- GoalDependencyGraph: Detects conflicts, enables parallel scheduling
- ResourceGovernor: Manages LLM rate limits, memory

Example:
    # Start parallel execution with 4 workers
    sunwell workers start --workers 4

    # Or programmatically
    from sunwell.parallel import Coordinator, MultiInstanceConfig

    config = MultiInstanceConfig(num_workers=4)
    coordinator = Coordinator(root=project_path, config=config)
    result = await coordinator.execute()
"""

from sunwell.agent.parallel.config import MultiInstanceConfig
from sunwell.agent.parallel.coordinator import Coordinator, CoordinatorResult
from sunwell.agent.parallel.dependencies import GoalDependencyGraph, estimate_affected_files
from sunwell.agent.parallel.locks import FileLock, FileLockManager
from sunwell.agent.parallel.resources import ResourceGovernor, ResourceLimits
from sunwell.agent.parallel.types import MergeResult, WorkerResult, WorkerState, WorkerStatus
from sunwell.agent.parallel.worker import WorkerProcess, worker_entry

__all__ = [
    # Types
    "WorkerState",
    "WorkerStatus",
    "WorkerResult",
    "MergeResult",
    # Config
    "MultiInstanceConfig",
    "ResourceLimits",
    # Components
    "Coordinator",
    "CoordinatorResult",
    "WorkerProcess",
    "FileLockManager",
    "FileLock",
    "GoalDependencyGraph",
    "ResourceGovernor",
    # Utilities
    "estimate_affected_files",
    # Entry points
    "worker_entry",
]
