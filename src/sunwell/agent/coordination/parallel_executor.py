"""Parallel task execution via subagents with filesystem isolation.

Orchestrates parallel execution of tasks that have been identified as
parallelizable (via TaskGraph.get_parallelizable_groups()).

This module connects:
- TaskGraph (identifies parallelizable tasks)
- SubagentRegistry (tracks subagent lifecycle)
- ExecutionLanes (provides isolated execution queues)
- WorktreeManager (filesystem isolation via git worktrees)
- FallbackIsolation (in-memory staging for non-git workspaces)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.coordination.handoff import Handoff, HandoffCollector
from sunwell.agent.coordination.registry import (
    SubagentOutcome,
    SubagentRecord,
    get_registry,
)
from sunwell.agent.execution.lanes import ExecutionLane, get_lanes
from sunwell.agent.isolation import (
    FallbackIsolation,
    MergeResult,
    MergeStrategy,
    WorktreeManager,
    get_content_validator,
)

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

    handoffs: HandoffCollector = field(default_factory=HandoffCollector)
    """Collected handoffs from all workers in this group.

    Each worker produces a Handoff on completion that carries not just
    the outcome but findings, concerns, deviations, and suggestions.
    The parent planner uses these for dynamic replanning.
    """

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
    """Execute parallelizable task groups via subagents with filesystem isolation.

    Coordinates spawning subagents for parallel tasks and aggregating results.
    Uses git worktree isolation when available, falling back to in-memory staging.

    Usage:
        executor = ParallelExecutor(task_executor=my_executor)

        # Execute a parallel group with isolation
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
        self._content_validator = get_content_validator()

    async def execute_parallel_group(
        self,
        parent: SessionContext,
        group_name: str,
        tasks: list[Task],
        config: LoopConfig,
    ) -> ParallelGroupResult:
        """Execute a group of tasks in parallel via subagents with isolation.

        Spawns subagents for each task, executes them concurrently
        (up to max_concurrent_subagents) with filesystem isolation,
        and aggregates results after merging.

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
            "Starting parallel group '%s' with %d tasks (parent=%s, isolation=%s)",
            group_name,
            len(tasks),
            parent.session_id,
            "worktree" if config.enable_worktree_isolation else "fallback",
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

        # Set up isolation manager (worktree or fallback)
        worktree_manager: WorktreeManager | None = None
        fallback_manager: FallbackIsolation | None = None

        if config.enable_worktree_isolation:
            worktree_manager = WorktreeManager(base_path=parent.cwd)
            if not await worktree_manager.is_git_repo():
                logger.warning(
                    "Workspace is not a git repo, falling back to in-memory staging"
                )
                worktree_manager = None
                fallback_manager = FallbackIsolation(workspace=parent.cwd)
        else:
            fallback_manager = FallbackIsolation(workspace=parent.cwd)

        try:
            # Execute tasks concurrently with isolation
            results = await self._execute_concurrent_isolated(
                parent,
                task_map,
                config,
                worktree_manager,
            )

            # Wait for completion
            outcomes = await self._registry.await_all(
                records,
                timeout=config.subagent_timeout_seconds,
            )

            # Merge phase: merge worktrees back to main workspace
            if worktree_manager:
                merge_results = await self._merge_worktrees(
                    worktree_manager,
                    task_map,
                    config,
                )
                # Update results based on merge status
                for run_id, merge_result in merge_results.items():
                    if not merge_result.success and run_id in results:
                        results[run_id] = TaskResult(
                            task_id=results[run_id].task_id,
                            success=False,
                            error=f"Merge failed: {merge_result.error}",
                            artifacts=results[run_id].artifacts,
                            duration_ms=results[run_id].duration_ms,
                        )

            # Build result with handoffs
            task_results: list[TaskResult] = []
            handoff_collector = HandoffCollector()

            for run_id, (task, record) in task_map.items():
                outcome = outcomes.get(run_id, SubagentOutcome.ERROR)
                result = results.get(run_id)

                if result:
                    task_results.append(result)
                    # Create handoff from task result
                    handoff = Handoff.from_task_result(
                        task_id=task.id,
                        result=result,
                        worker_id=record.child_session_id,
                    )
                    handoff_collector.add(handoff)
                else:
                    # Task didn't produce a result
                    task_result = TaskResult(
                        task_id=task.id,
                        success=outcome == SubagentOutcome.OK,
                        error=f"Outcome: {outcome.value}" if outcome != SubagentOutcome.OK else None,
                    )
                    task_results.append(task_result)
                    # Create failure handoff
                    handoff = Handoff.failure(
                        task_id=task.id,
                        error=f"No result produced. Outcome: {outcome.value}",
                        worker_id=record.child_session_id,
                    )
                    handoff_collector.add(handoff)

        finally:
            # Cleanup worktrees
            if worktree_manager:
                await worktree_manager.cleanup_all()
            if fallback_manager:
                fallback_manager.cleanup()

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        group_result = ParallelGroupResult(
            group_name=group_name,
            task_results=task_results,
            total_duration_ms=duration_ms,
            handoffs=handoff_collector,
        )

        logger.info(
            "Completed parallel group '%s': %d/%d succeeded in %dms",
            group_name,
            group_result.success_count,
            len(tasks),
            duration_ms,
        )

        return group_result

    async def _merge_worktrees(
        self,
        manager: WorktreeManager,
        task_map: dict[str, tuple[Task, SubagentRecord]],
        config: LoopConfig,
    ) -> dict[str, MergeResult]:
        """Merge all worktrees back to main workspace sequentially.

        Args:
            manager: WorktreeManager with created worktrees
            task_map: Mapping of run_id to (task, record) tuples
            config: Loop configuration

        Returns:
            Dict mapping run_id to MergeResult
        """
        results: dict[str, MergeResult] = {}

        for run_id, (task, _) in task_map.items():
            try:
                # Validate content before merge if enabled
                if config.enable_content_validation:
                    modified_files = await manager.get_modified_files(task.id)
                    worktree_info = manager.worktrees.get(task.id)
                    if worktree_info and modified_files:
                        for file_path in modified_files:
                            full_path = worktree_info.path / file_path
                            if full_path.exists():
                                content = full_path.read_text(encoding="utf-8")
                                validation = self._content_validator.validate(
                                    content, file_path
                                )
                                if not validation.valid:
                                    results[run_id] = MergeResult(
                                        success=False,
                                        strategy_used=MergeStrategy.ABORT_ON_CONFLICT,
                                        files_merged=(),
                                        conflicts=(file_path,),
                                        error=validation.message,
                                    )
                                    continue

                # Merge the worktree
                merge_result = await manager.merge_worktree(
                    task.id,
                    MergeStrategy.FAST_FORWARD,
                )
                results[run_id] = merge_result

                if merge_result.success:
                    logger.debug(
                        "Merged worktree for task %s: %d files",
                        task.id,
                        len(merge_result.files_merged),
                    )
                else:
                    logger.warning(
                        "Failed to merge worktree for task %s: %s",
                        task.id,
                        merge_result.error,
                    )

            except Exception as e:
                logger.exception("Error merging worktree for task %s", task.id)
                results[run_id] = MergeResult(
                    success=False,
                    strategy_used=MergeStrategy.ABORT_ON_CONFLICT,
                    files_merged=(),
                    error=str(e),
                )

        return results

    async def _execute_concurrent_isolated(
        self,
        parent: SessionContext,
        task_map: dict[str, tuple[Task, SubagentRecord]],
        config: LoopConfig,
        worktree_manager: WorktreeManager | None = None,
    ) -> dict[str, TaskResult]:
        """Execute tasks concurrently with filesystem isolation.

        Args:
            parent: Parent session context
            task_map: Mapping of run_id to (task, record) tuples
            config: Loop configuration
            worktree_manager: Optional worktree manager for git isolation

        Returns:
            Dict mapping run_id to TaskResult

        Raises:
            ValueError: If no task executor is configured
        """
        if self._task_executor is None:
            raise ValueError(
                "ParallelExecutor requires a task_executor callback to execute tasks. "
                "Pass task_executor to ParallelExecutor.__init__() or use set_task_executor()."
            )

        from sunwell.agent.context.session import SessionContext

        results: dict[str, TaskResult] = {}
        worktree_paths: dict[str, Path] = {}

        # Create worktrees for all tasks first (if using worktree isolation)
        if worktree_manager:
            for run_id, (task, _) in task_map.items():
                try:
                    wt_info = await worktree_manager.create_worktree(task.id)
                    worktree_paths[run_id] = wt_info.path
                    logger.debug(
                        "Created worktree for task %s at %s",
                        task.id,
                        wt_info.path,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to create worktree for task %s: %s",
                        task.id,
                        e,
                    )
                    # Will fall back to shared workspace

        async def execute_one(run_id: str, task: Task, record: SubagentRecord) -> None:
            """Execute a single task in an isolated worktree."""
            # Mark as started
            self._registry.mark_started(run_id)

            try:
                # Get worktree path for this task (if created)
                worktree_path = worktree_paths.get(run_id)

                # Create child session with isolated worktree
                child_session = SessionContext.spawn_child(
                    parent,
                    task=task.description,
                    cleanup=config.subagent_cleanup,
                    worktree_path=worktree_path,
                )
                # Sync child session ID with record
                child_session.session_id = record.child_session_id

                # Execute task in isolated worktree
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

        Raises:
            ValueError: If no task executor is configured
        """
        if self._task_executor is None:
            raise ValueError(
                "ParallelExecutor requires a task_executor callback to execute tasks. "
                "Pass task_executor to ParallelExecutor.__init__() or use set_task_executor()."
            )

        from sunwell.agent.context.session import SessionContext

        start_time = datetime.now()
        task_results: list[TaskResult] = []

        for task in tasks:
            task_start = datetime.now()

            try:
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
# Anti-Fragile Worker Management
# =============================================================================

# Maximum retries per task before sending to dead letter queue
MAX_TASK_RETRIES = 2

# Maximum tasks in dead letter queue before alerting
DEAD_LETTER_ALERT_THRESHOLD = 10


@dataclass(slots=True)
class DeadLetterEntry:
    """A task that has repeatedly failed and been shelved.

    Dead letter entries preserve full context so the planner can
    review them later, re-decompose, or try a different approach.
    """

    task_id: str
    """ID of the failed task."""

    task_description: str
    """Description of what was attempted."""

    attempts: int
    """Number of times this task was attempted."""

    errors: list[str]
    """Error messages from each attempt."""

    last_handoff: Handoff | None = None
    """Last handoff produced (may contain useful findings)."""

    shelved_at: datetime = field(default_factory=datetime.now)
    """When this entry was added to the dead letter queue."""


@dataclass(slots=True)
class RetryContext:
    """Context for retrying a failed task with lessons learned.

    When a worker fails, the retry gets a clean context plus a summary
    of what went wrong, so it can try a different approach.
    """

    task_id: str
    """ID of the task being retried."""

    attempt: int
    """Which attempt this is (1-indexed)."""

    previous_errors: list[str]
    """Error messages from previous attempts."""

    lessons: list[str]
    """Lessons extracted from previous failures."""

    def to_prompt_context(self) -> str:
        """Format retry context for injection into worker prompt."""
        lines = [
            f"## Retry Context (attempt {self.attempt})",
            "",
            "Previous attempts at this task failed. Learn from these failures:",
            "",
        ]

        if self.previous_errors:
            lines.append("### Previous Errors")
            for i, error in enumerate(self.previous_errors, 1):
                lines.append(f"{i}. {error}")
            lines.append("")

        if self.lessons:
            lines.append("### Lessons Learned")
            for lesson in self.lessons:
                lines.append(f"- {lesson}")
            lines.append("")

        lines.append(
            "Try a different approach than what failed before. "
            "Consider the errors above and adjust your strategy."
        )

        return "\n".join(lines)


class DeadLetterQueue:
    """Queue for tasks that have repeatedly failed.

    Tasks are not silently dropped -- they're shelved with full context
    so the planner can review, re-decompose, or try later.

    This enables anti-fragility: individual worker failures don't halt
    the system, and no knowledge is lost.
    """

    def __init__(self) -> None:
        self._entries: list[DeadLetterEntry] = []

    def add(
        self,
        task_id: str,
        task_description: str,
        attempts: int,
        errors: list[str],
        last_handoff: Handoff | None = None,
    ) -> DeadLetterEntry:
        """Add a failed task to the dead letter queue.

        Args:
            task_id: ID of the failed task
            task_description: Description of what was attempted
            attempts: Number of attempts made
            errors: Error messages from each attempt
            last_handoff: Last handoff produced (if any)

        Returns:
            The created DeadLetterEntry
        """
        entry = DeadLetterEntry(
            task_id=task_id,
            task_description=task_description,
            attempts=attempts,
            errors=errors,
            last_handoff=last_handoff,
        )
        self._entries.append(entry)

        if len(self._entries) >= DEAD_LETTER_ALERT_THRESHOLD:
            logger.warning(
                "Dead letter queue has %d entries (threshold: %d). "
                "Consider reviewing failed tasks.",
                len(self._entries),
                DEAD_LETTER_ALERT_THRESHOLD,
            )

        return entry

    @property
    def entries(self) -> list[DeadLetterEntry]:
        """All dead letter entries."""
        return list(self._entries)

    @property
    def count(self) -> int:
        """Number of entries in the queue."""
        return len(self._entries)

    def get_for_replanning(self) -> list[dict]:
        """Get dead letter entries formatted for planner review.

        Returns entries with enough context for the planner to decide
        whether to re-decompose, retry with different approach, or skip.

        Returns:
            List of dicts with task info and failure context
        """
        return [
            {
                "task_id": e.task_id,
                "description": e.task_description,
                "attempts": e.attempts,
                "errors": e.errors,
                "has_findings": e.last_handoff is not None and bool(e.last_handoff.findings),
                "shelved_at": e.shelved_at.isoformat(),
            }
            for e in self._entries
        ]

    def clear(self) -> int:
        """Clear the dead letter queue.

        Returns:
            Number of entries cleared
        """
        count = len(self._entries)
        self._entries.clear()
        return count


def build_retry_context(
    task_id: str,
    attempt: int,
    previous_errors: list[str],
    previous_handoffs: list[Handoff] | None = None,
) -> RetryContext:
    """Build retry context from previous failure information.

    Extracts lessons from previous handoffs (findings, concerns)
    and error messages to help the retry succeed.

    Args:
        task_id: ID of the task being retried
        attempt: Which attempt this is (1-indexed)
        previous_errors: Error messages from previous attempts
        previous_handoffs: Handoffs from previous attempts (if any)

    Returns:
        RetryContext with extracted lessons
    """
    lessons: list[str] = []

    # Extract lessons from previous handoffs
    if previous_handoffs:
        for handoff in previous_handoffs:
            for finding in handoff.findings:
                lessons.append(f"Finding: {finding.description}")
            for concern in handoff.concerns:
                lessons.append(f"Concern: {concern}")
            for deviation in handoff.deviations:
                lessons.append(
                    f"Previous approach '{deviation.original_plan}' "
                    f"was changed to '{deviation.actual_approach}' "
                    f"because: {deviation.reason}"
                )

    # Extract lessons from error patterns
    error_set = set(previous_errors)
    if any("timeout" in e.lower() for e in error_set):
        lessons.append("Previous attempts timed out -- try a simpler approach")
    if any("merge" in e.lower() for e in error_set):
        lessons.append("Previous attempts had merge conflicts -- minimize file changes")
    if any("syntax" in e.lower() or "parse" in e.lower() for e in error_set):
        lessons.append("Previous attempts had syntax errors -- validate output carefully")

    return RetryContext(
        task_id=task_id,
        attempt=attempt,
        previous_errors=previous_errors,
        lessons=lessons,
    )


# =============================================================================
# Module-Level Helper
# =============================================================================

# Global dead letter queue
_dead_letter_queue: DeadLetterQueue | None = None


def get_dead_letter_queue() -> DeadLetterQueue:
    """Get the global dead letter queue."""
    global _dead_letter_queue
    if _dead_letter_queue is None:
        _dead_letter_queue = DeadLetterQueue()
    return _dead_letter_queue


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
    """Reset the global executor and dead letter queue (for testing only)."""
    global _global_executor, _dead_letter_queue
    _global_executor = None
    _dead_letter_queue = None
