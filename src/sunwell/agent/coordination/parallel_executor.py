"""Parallel task execution via subagents.

Orchestrates parallel execution of tasks that have been identified as
parallelizable (via TaskGraph.get_parallelizable_groups()).

This module connects:
- TaskGraph (identifies parallelizable tasks)
- SubagentRegistry (tracks subagent lifecycle)
- ExecutionLanes (provides isolated execution queues)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from sunwell.agent.coordination.registry import (
    SubagentOutcome,
    SubagentRecord,
    get_registry,
)
from sunwell.agent.execution.lanes import ExecutionLane, get_lanes

if TYPE_CHECKING:
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.loop.config import LoopConfig
    from sunwell.planning.naaru.types import Task

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TaskResult:
    """Result of executing a task."""

    task_id: str
    """ID of the task."""

    success: bool
    """Whether the task completed successfully."""

    output: str | None = None
    """Output or result description."""

    error: str | None = None
    """Error message if failed."""

    artifacts: list[str] = field(default_factory=list)
    """Paths of artifacts created."""

    duration_ms: int = 0
    """Execution time in milliseconds."""


@dataclass(slots=True)
class ParallelGroupResult:
    """Result of executing a parallel group."""

    group_name: str
    """Name of the parallel group."""

    task_results: list[TaskResult]
    """Results for each task in the group."""

    total_duration_ms: int = 0
    """Total wall-clock time for the group."""

    @property
    def all_success(self) -> bool:
        """True if all tasks succeeded."""
        return all(r.success for r in self.task_results)

    @property
    def success_count(self) -> int:
        """Number of successful tasks."""
        return sum(1 for r in self.task_results if r.success)

    @property
    def failure_count(self) -> int:
        """Number of failed tasks."""
        return sum(1 for r in self.task_results if not r.success)


# Type for task executor callback
TaskExecutor = "Callable[[SessionContext, Task], Awaitable[TaskResult]]"


class ParallelExecutor:
    """Execute parallelizable task groups via subagents.

    Coordinates spawning subagents for parallel tasks and aggregating results.

    Usage:
        executor = ParallelExecutor(task_executor=my_executor)

        # Execute a parallel group
        result = await executor.execute_parallel_group(
            parent=session,
            group_name="implementations",
            tasks=[task1, task2, task3],
            config=config,
        )

        if result.all_success:
            print(f"All {len(result.task_results)} tasks completed!")
    """

    def __init__(
        self,
        task_executor: TaskExecutor | None = None,
    ) -> None:
        """Initialize the parallel executor.

        Args:
            task_executor: Callback to execute individual tasks.
                Signature: (session: SessionContext, task: Task) -> TaskResult
                If None, tasks are marked as completed without execution.
        """
        self._task_executor = task_executor
        self._registry = get_registry()
        self._lanes = get_lanes()

    async def execute_parallel_group(
        self,
        parent: SessionContext,
        group_name: str,
        tasks: list[Task],
        config: LoopConfig,
    ) -> ParallelGroupResult:
        """Execute a group of tasks in parallel via subagents.

        Spawns subagents for each task, executes them concurrently
        (up to max_concurrent_subagents), and aggregates results.

        Args:
            parent: Parent session context
            group_name: Name of the parallel group
            tasks: Tasks to execute in parallel
            config: Loop configuration with subagent settings

        Returns:
            ParallelGroupResult with all task results
        """
        start_time = datetime.now()
        logger.info(
            "Starting parallel group '%s' with %d tasks (parent=%s)",
            group_name,
            len(tasks),
            parent.session_id,
        )

        # Register subagents
        try:
            records = self._registry.spawn_parallel(parent, tasks, config)
        except ValueError as e:
            # Not enough slots - fall back to sequential
            logger.warning(
                "Cannot parallelize group '%s': %s. Executing sequentially.",
                group_name,
                str(e),
            )
            return await self._execute_sequential(parent, group_name, tasks, config)

        # Create task-to-record mapping
        task_map: dict[str, tuple[Task, SubagentRecord]] = {}
        for task, record in zip(tasks, records, strict=True):
            task_map[record.run_id] = (task, record)

        # Execute tasks concurrently
        results = await self._execute_concurrent(parent, task_map, config)

        # Wait for completion
        outcomes = await self._registry.await_all(
            records,
            timeout=config.subagent_timeout_seconds,
        )

        # Build result
        task_results: list[TaskResult] = []
        for run_id, (task, record) in task_map.items():
            outcome = outcomes.get(run_id, SubagentOutcome.ERROR)
            result = results.get(run_id)

            if result:
                task_results.append(result)
            else:
                # Task didn't produce a result
                task_results.append(TaskResult(
                    task_id=task.id,
                    success=outcome == SubagentOutcome.OK,
                    error=f"Outcome: {outcome.value}" if outcome != SubagentOutcome.OK else None,
                ))

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        group_result = ParallelGroupResult(
            group_name=group_name,
            task_results=task_results,
            total_duration_ms=duration_ms,
        )

        logger.info(
            "Completed parallel group '%s': %d/%d succeeded in %dms",
            group_name,
            group_result.success_count,
            len(tasks),
            duration_ms,
        )

        return group_result

    async def _execute_concurrent(
        self,
        parent: SessionContext,
        task_map: dict[str, tuple[Task, SubagentRecord]],
        config: LoopConfig,
    ) -> dict[str, TaskResult]:
        """Execute tasks concurrently using execution lanes.

        Args:
            parent: Parent session context
            task_map: Mapping of run_id to (task, record) tuples
            config: Loop configuration

        Returns:
            Dict mapping run_id to TaskResult
        """
        from sunwell.agent.context.session import SessionContext

        results: dict[str, TaskResult] = {}

        async def execute_one(run_id: str, task: Task, record: SubagentRecord) -> None:
            """Execute a single task in the subagent lane."""
            # Mark as started
            self._registry.mark_started(run_id)

            try:
                if self._task_executor is None:
                    # No executor - mock success
                    result = TaskResult(
                        task_id=task.id,
                        success=True,
                        output="Task completed (no executor)",
                    )
                else:
                    # Create child session
                    child_session = SessionContext.spawn_child(
                        parent,
                        task=task.description,
                        cleanup=config.subagent_cleanup,
                    )
                    # Sync child session ID with record
                    child_session.session_id = record.child_session_id

                    # Execute task
                    result = await self._task_executor(child_session, task)

                results[run_id] = result

                # Mark complete
                outcome = SubagentOutcome.OK if result.success else SubagentOutcome.ERROR
                self._registry.mark_complete(
                    run_id,
                    outcome,
                    error_message=result.error,
                )

            except Exception as e:
                logger.exception("Task %s failed with exception", task.id)
                results[run_id] = TaskResult(
                    task_id=task.id,
                    success=False,
                    error=str(e),
                )
                self._registry.mark_complete(
                    run_id,
                    SubagentOutcome.ERROR,
                    error_message=str(e),
                )

        # Enqueue all tasks in the subagent lane
        tasks_to_run = []
        for run_id, (task, record) in task_map.items():
            async def task_wrapper(
                rid: str = run_id,
                t: Task = task,
                r: SubagentRecord = record,
            ) -> None:
                await execute_one(rid, t, r)

            tasks_to_run.append(
                self._lanes.enqueue(
                    ExecutionLane.SUBAGENT,
                    task_wrapper,
                    label=f"subagent:{task.id}",
                )
            )

        # Wait for all to complete
        await asyncio.gather(*tasks_to_run, return_exceptions=True)

        return results

    async def _execute_sequential(
        self,
        parent: SessionContext,
        group_name: str,
        tasks: list[Task],
        config: LoopConfig,
    ) -> ParallelGroupResult:
        """Fallback: execute tasks sequentially when parallelization fails.

        Args:
            parent: Parent session context
            group_name: Name of the parallel group
            tasks: Tasks to execute
            config: Loop configuration

        Returns:
            ParallelGroupResult
        """
        from sunwell.agent.context.session import SessionContext

        start_time = datetime.now()
        task_results: list[TaskResult] = []

        for task in tasks:
            task_start = datetime.now()

            try:
                if self._task_executor is None:
                    result = TaskResult(
                        task_id=task.id,
                        success=True,
                        output="Task completed (no executor)",
                    )
                else:
                    child_session = SessionContext.spawn_child(
                        parent,
                        task=task.description,
                        cleanup=config.subagent_cleanup,
                    )
                    result = await self._task_executor(child_session, task)

                result.duration_ms = int(
                    (datetime.now() - task_start).total_seconds() * 1000
                )
                task_results.append(result)

            except Exception as e:
                logger.exception("Sequential task %s failed", task.id)
                task_results.append(TaskResult(
                    task_id=task.id,
                    success=False,
                    error=str(e),
                    duration_ms=int(
                        (datetime.now() - task_start).total_seconds() * 1000
                    ),
                ))

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return ParallelGroupResult(
            group_name=group_name,
            task_results=task_results,
            total_duration_ms=duration_ms,
        )


# =============================================================================
# Module-Level Helper
# =============================================================================

_global_executor: ParallelExecutor | None = None


def get_parallel_executor() -> ParallelExecutor:
    """Get the global ParallelExecutor instance.

    Note: Call set_task_executor() to configure actual task execution.
    """
    global _global_executor
    if _global_executor is None:
        _global_executor = ParallelExecutor()
    return _global_executor


def set_task_executor(executor: TaskExecutor) -> None:
    """Set the task executor for the global ParallelExecutor."""
    global _global_executor
    if _global_executor is None:
        _global_executor = ParallelExecutor(task_executor=executor)
    else:
        _global_executor._task_executor = executor


def reset_executor_for_tests() -> None:
    """Reset the global executor (for testing only)."""
    global _global_executor
    _global_executor = None
