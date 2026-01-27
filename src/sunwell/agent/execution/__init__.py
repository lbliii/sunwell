"""Task execution and specialist handling."""

from sunwell.agent.core.task_graph import sanitize_code_content
from sunwell.agent.execution.context import BacklogContext
from sunwell.agent.execution.emitter import StdoutEmitter
from sunwell.agent.execution.executor import (
    determine_specialist_role,
    execute_task_streaming_fallback,
    execute_task_with_tools,
    execute_with_convergence,
    select_lens_for_task,
    should_spawn_specialist,
    validate_gate,
)
from sunwell.agent.execution.fixer import FixResult, FixStage
from sunwell.agent.execution.lanes import (
    ExecutionLanes,
    LaneState,
    QueueEntry,
    get_lanes,
)
from sunwell.agent.execution.manager import ExecutionManager
from sunwell.agent.execution.specialist import execute_via_specialist, get_context_snapshot

__all__ = [
    "BacklogContext",
    "determine_specialist_role",
    "execute_task_streaming_fallback",
    "execute_task_with_tools",
    "execute_with_convergence",
    "sanitize_code_content",
    "select_lens_for_task",
    "should_spawn_specialist",
    "validate_gate",
    "execute_via_specialist",
    "get_context_snapshot",
    "FixStage",
    "FixResult",
    "ExecutionManager",
    "StdoutEmitter",
    # Execution Lanes (Phase 2)
    "ExecutionLanes",
    "LaneState",
    "QueueEntry",
    "get_lanes",
]
