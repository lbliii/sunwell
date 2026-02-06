"""TaskDispatcher for routing tasks to parallel or sequential execution.

Central coordinator that decides execution strategy per task/group based on
TaskGraph analysis. Routes parallel groups to ParallelExecutor and sequential
tasks to the standard execution path.

This bridges the gap between:
- TaskGraph.get_parallelizable_groups() (identifies safe parallel groups)
- ParallelExecutor.execute_parallel_group() (executes with isolation)
- execute_task_with_tools() (sequential task execution)
"""

import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.coordination.parallel_executor import (
    ParallelExecutor,
    ParallelGroupResult,
    TaskResult,
)
from sunwell.agent.events import AgentEvent, EventType
from sunwell.agent.isolation import check_workspace_readiness, WorkspaceIsolationMode

if TYPE_CHECKING:
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.loop.config import LoopConfig
    from sunwell.planning.naaru.types import Task

logger = logging.getLogger(__name__)


# Type for sequential task executor callback
SequentialExecutor = Callable[
    ["Task", Any],  # (task, context) -> AsyncIterator[AgentEvent]
    Coroutine[Any, Any, AsyncIterator[AgentEvent]],
]


@dataclass(slots=True)
class DispatchResult:
    """Result of dispatching a TaskGraph for execution."""

    total_tasks: int
    """Total number of tasks in the graph."""

    parallel_tasks: int
    """Number of tasks executed in parallel."""

    sequential_tasks: int
    """Number of tasks executed sequentially."""

    parallel_groups: int
    """Number of parallel groups executed."""

    all_success: bool
    """True if all tasks completed successfully."""

    total_duration_ms: int
    """Total wall-clock time for all execution."""

    task_results: list[TaskResult] = field(default_factory=list)
    """Results for all tasks."""


class TaskDispatcher:
    """Route tasks to parallel or sequential execution based on TaskGraph analysis.

    The dispatcher queries TaskGraph.get_parallelizable_groups() to identify
    groups of tasks that can safely run in parallel, then:
    - Routes parallel groups to ParallelExecutor with filesystem isolation
    - Routes sequential tasks to the standard execute_task_with_tools() path

    Usage:
        dispatcher = TaskDispatcher(
            workspace=Path.cwd(),
            session=session_context,
            config=loop_config,
        )

        async for event in dispatcher.execute_graph(task_graph, execute_fn):
            handle_event(event)
    """

    def __init__(
        self,
        workspace: Path,
        session: "SessionContext",
        config: "LoopConfig",
        parallel_executor: ParallelExecutor | None = None,
    ) -> None:
        """Initialize the task dispatcher.

        Args:
            workspace: Working directory
            session: Parent session context for spawning subagents
            config: Loop configuration with parallel settings
            parallel_executor: Optional custom ParallelExecutor instance
        """
        self.workspace = workspace
        self.session = session
        self.config = config

        # Create or use provided parallel executor
        self._parallel_executor = parallel_executor or ParallelExecutor()

        # Check workspace readiness for isolation
        self._workspace_readiness = check_workspace_readiness(workspace)

    async def execute_graph(
        self,
        graph: "TaskGraph",
        sequential_fn: Callable[["Task"], AsyncIterator[AgentEvent]],
    ) -> AsyncIterator[AgentEvent]:
        """Execute task graph with automatic parallel/sequential routing.

        Analyzes the TaskGraph to find parallelizable groups, then executes:
        1. Parallel groups via ParallelExecutor with filesystem isolation
        2. Sequential tasks via the provided sequential_fn

        Args:
            graph: TaskGraph with tasks and parallel_group assignments
            sequential_fn: Async generator function for sequential task execution
                Signature: (task: Task) -> AsyncIterator[AgentEvent]

        Yields:
            AgentEvent for each step of execution (progress, completion, errors)
        """
        from sunwell.agent.core.task_graph import TaskGraph

        start_time = datetime.now()

        # Get parallelizable groups and sequential tasks
        parallel_groups = graph.get_parallelizable_groups()
        sequential_tasks = graph.get_sequential_tasks()

        total_tasks = len(graph.tasks)
        parallel_task_count = sum(len(tasks) for tasks in parallel_groups.values())
        sequential_task_count = len(sequential_tasks)

        logger.info(
            "TaskDispatcher: %d total tasks (%d parallel in %d groups, %d sequential)",
            total_tasks,
            parallel_task_count,
            len(parallel_groups),
            sequential_task_count,
        )

        # Emit dispatch start event
        yield AgentEvent(
            type=EventType.PARALLEL_DISPATCH_START,
            data={
                "total_tasks": total_tasks,
                "parallel_groups": len(parallel_groups),
                "parallel_tasks": parallel_task_count,
                "sequential_tasks": sequential_task_count,
                "isolation_mode": self._workspace_readiness.isolation_mode.value,
            },
        )

        # Check if parallel execution is enabled and useful
        can_parallelize = (
            self.config.enable_parallel_tasks
            and len(parallel_groups) > 0
            and parallel_task_count > 0
        )

        if can_parallelize and not self._workspace_readiness.is_git_repo:
            # Warn about fallback isolation
            if self._workspace_readiness.warning:
                yield AgentEvent(
                    type=EventType.ISOLATION_WARNING,
                    data={
                        "message": self._workspace_readiness.warning,
                        "isolation_mode": WorkspaceIsolationMode.STAGING.value,
                    },
                )

        all_results: list[TaskResult] = []
        all_success = True

        # Track which tasks have been executed
        executed_task_ids: set[str] = set()

        # Execute in waves: parallel groups first, then remaining sequential
        # This respects the natural dependency ordering

        # Phase 1: Execute parallel groups
        for group_name, tasks in parallel_groups.items():
            if not can_parallelize:
                # Parallel disabled - execute these sequentially too
                for task in tasks:
                    if task.id in executed_task_ids:
                        continue
                    async for event in self._execute_sequential_task(
                        task, sequential_fn, len(all_results), total_tasks
                    ):
                        yield event
                        if event.type == EventType.TASK_COMPLETE:
                            data = event.data
                            all_results.append(TaskResult(
                                task_id=task.id,
                                success=data.get("success", True),
                                output=data.get("result_text"),
                                error=data.get("error"),
                            ))
                            executed_task_ids.add(task.id)
                continue

            # Emit parallel group start
            yield AgentEvent(
                type=EventType.PARALLEL_GROUP_START,
                data={
                    "group_name": group_name,
                    "task_count": len(tasks),
                    "task_ids": [t.id for t in tasks],
                },
            )

            # Execute parallel group
            try:
                group_result = await self._parallel_executor.execute_parallel_group(
                    parent=self.session,
                    group_name=group_name,
                    tasks=tasks,
                    config=self.config,
                )

                # Record results
                all_results.extend(group_result.task_results)
                for result in group_result.task_results:
                    executed_task_ids.add(result.task_id)
                    if not result.success:
                        all_success = False

                # Emit parallel group complete
                yield AgentEvent(
                    type=EventType.PARALLEL_GROUP_COMPLETE,
                    data={
                        "group_name": group_name,
                        "success_count": group_result.success_count,
                        "failure_count": group_result.failure_count,
                        "duration_ms": group_result.total_duration_ms,
                    },
                )

            except Exception as e:
                logger.exception("Parallel group '%s' failed", group_name)
                all_success = False
                yield AgentEvent(
                    type=EventType.ERROR,
                    data={
                        "error": f"Parallel group '{group_name}' failed: {e}",
                        "group_name": group_name,
                    },
                )
                # Fall back to sequential for this group's tasks
                for task in tasks:
                    if task.id in executed_task_ids:
                        continue
                    async for event in self._execute_sequential_task(
                        task, sequential_fn, len(all_results), total_tasks
                    ):
                        yield event
                        if event.type == EventType.TASK_COMPLETE:
                            data = event.data
                            all_results.append(TaskResult(
                                task_id=task.id,
                                success=data.get("success", True),
                                output=data.get("result_text"),
                                error=data.get("error"),
                            ))
                            executed_task_ids.add(task.id)

        # Phase 2: Execute remaining sequential tasks
        for task in sequential_tasks:
            if task.id in executed_task_ids:
                continue

            async for event in self._execute_sequential_task(
                task, sequential_fn, len(all_results), total_tasks
            ):
                yield event
                if event.type == EventType.TASK_COMPLETE:
                    data = event.data
                    success = data.get("success", True)
                    all_results.append(TaskResult(
                        task_id=task.id,
                        success=success,
                        output=data.get("result_text"),
                        error=data.get("error"),
                    ))
                    executed_task_ids.add(task.id)
                    if not success:
                        all_success = False

        # Calculate total duration
        end_time = datetime.now()
        total_duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Emit dispatch complete
        yield AgentEvent(
            type=EventType.PARALLEL_DISPATCH_COMPLETE,
            data={
                "total_tasks": total_tasks,
                "executed_tasks": len(executed_task_ids),
                "parallel_groups_executed": len(parallel_groups) if can_parallelize else 0,
                "all_success": all_success,
                "duration_ms": total_duration_ms,
            },
        )

    async def _execute_sequential_task(
        self,
        task: "Task",
        sequential_fn: Callable[["Task"], AsyncIterator[AgentEvent]],
        current_index: int,
        total_tasks: int,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a single task sequentially.

        Args:
            task: Task to execute
            sequential_fn: Async generator function for execution
            current_index: Current task index (for progress)
            total_tasks: Total number of tasks (for progress)

        Yields:
            AgentEvent from task execution
        """
        # Emit task start
        yield AgentEvent(
            type=EventType.TASK_START,
            data={
                "task_id": task.id,
                "description": task.description,
                "task_index": current_index,
                "total_tasks": total_tasks,
                "parallel": False,
            },
        )

        try:
            # Execute via provided function
            async for event in sequential_fn(task):
                yield event

        except Exception as e:
            logger.exception("Sequential task %s failed", task.id)
            yield AgentEvent(
                type=EventType.TASK_COMPLETE,
                data={
                    "task_id": task.id,
                    "success": False,
                    "error": str(e),
                },
            )


def should_use_parallel_dispatch(
    graph: "TaskGraph",
    config: "LoopConfig",
) -> bool:
    """Check if parallel dispatch would be beneficial for this TaskGraph.

    Use this to decide whether to use TaskDispatcher vs simple sequential.

    Args:
        graph: TaskGraph to analyze
        config: Loop configuration

    Returns:
        True if parallel dispatch would execute tasks concurrently
    """
    if not config.enable_parallel_tasks:
        return False

    parallel_groups = graph.get_parallelizable_groups()
    total_parallel_tasks = sum(len(tasks) for tasks in parallel_groups.values())

    # Worth parallelizing if we have at least one group with 2+ tasks
    return any(len(tasks) >= 2 for tasks in parallel_groups.values())
