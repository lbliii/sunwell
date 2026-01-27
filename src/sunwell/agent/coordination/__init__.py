"""Coordination — Multi-agent coordination infrastructure.

This module provides infrastructure for coordinating multiple agent instances
working on related tasks (subagents, parallel work, etc.).

Components:
- SubagentRegistry: Track spawned subagents and their lifecycle
- SubagentRecord: Data model for subagent state
- ParallelExecutor: Execute parallelizable task groups via subagents
- TaskResult: Result of executing a single task
- ParallelGroupResult: Result of executing a parallel group

Based on patterns from moltbot's subagent-registry.ts but adapted for
sunwell's async/Python patterns.
"""

from sunwell.agent.coordination.parallel_executor import (
    ParallelExecutor,
    ParallelGroupResult,
    TaskResult,
    get_parallel_executor,
    set_task_executor,
)
from sunwell.agent.coordination.registry import (
    SubagentOutcome,
    SubagentRecord,
    SubagentRegistry,
    get_registry,
)

__all__ = [
    # Registry
    "SubagentRecord",
    "SubagentRegistry",
    "SubagentOutcome",
    "get_registry",
    # Parallel Execution
    "ParallelExecutor",
    "TaskResult",
    "ParallelGroupResult",
    "get_parallel_executor",
    "set_task_executor",
]
