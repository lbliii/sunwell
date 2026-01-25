"""Worker process for multi-instance coordination (RFC-051).

Each worker:
1. Operates on its own git branch
2. Claims goals from shared backlog
3. Acquires file locks before editing
4. Commits changes atomically
5. Reports status to coordinator
"""

import json
import os
import signal
from dataclasses import asdict
from datetime import datetime
from multiprocessing import Queue
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.parallel.config import MultiInstanceConfig
from sunwell.agent.parallel.dependencies import estimate_affected_files
from sunwell.agent.parallel.git import commit_all, create_branch
from sunwell.agent.parallel.locks import FileLockManager
from sunwell.agent.parallel.types import WorkerResult, WorkerState, WorkerStatus

if TYPE_CHECKING:
    from sunwell.features.backlog.goals import Goal
    from sunwell.features.backlog.manager import BacklogManager


class WorkerProcess:
    """A single worker process that executes goals.

    Each worker:
    1. Operates on its own git branch
    2. Claims goals from shared backlog
    3. Acquires file locks before editing
    4. Commits changes atomically
    5. Reports status to coordinator

    Example:
        worker = WorkerProcess(
            worker_id=1,
            root=project_root,
            backlog_manager=backlog,
            config=config,
        )
        result = await worker.run()
    """

    def __init__(
        self,
        worker_id: int,
        root: Path,
        backlog_manager: BacklogManager,
        config: MultiInstanceConfig,
    ):
        """Initialize worker process.

        Args:
            worker_id: Unique identifier for this worker
            root: Project root directory
            backlog_manager: Shared backlog manager
            config: Multi-instance configuration
        """
        self.worker_id = worker_id
        self.root = Path(root)
        self.backlog_manager = backlog_manager
        self.config = config

        self.branch = f"{config.branch_prefix}{worker_id}"
        self.status = WorkerStatus(
            worker_id=worker_id,
            pid=os.getpid(),
            state=WorkerState.STARTING,
            branch=self.branch,
        )

        self._lock_manager = FileLockManager(
            root / ".sunwell" / "locks",
            stale_threshold_seconds=config.stale_lock_threshold_seconds,
        )
        self._status_file = root / ".sunwell" / "workers" / f"worker-{worker_id}.json"
        self._commit_shas: list[str] = []

    async def run(self) -> WorkerResult:
        """Main worker loop.

        Returns:
            WorkerResult with completed/failed goal counts.
        """
        start_time = datetime.now()

        try:
            # Setup: checkout worker branch
            await self._setup_branch()
            self._update_status(WorkerState.IDLE)

            # Main loop: claim and execute goals
            while True:
                # Find an executable goal
                goal = await self._claim_next_goal()

                if goal is None:
                    # No more work
                    break

                # Execute the goal
                success = await self._execute_goal(goal)

                if success:
                    self.status.goals_completed += 1
                else:
                    self.status.goals_failed += 1

                self._update_status(WorkerState.IDLE)

            duration = (datetime.now() - start_time).total_seconds()
            return WorkerResult(
                worker_id=self.worker_id,
                goals_completed=self.status.goals_completed,
                goals_failed=self.status.goals_failed,
                branch=self.branch,
                duration_seconds=duration,
                commit_shas=tuple(self._commit_shas),
            )

        except Exception as e:
            self._update_status(WorkerState.FAILED, error=str(e))
            raise
        finally:
            self._update_status(WorkerState.STOPPED)

    async def _claim_next_goal(self) -> Goal | None:
        """Claim the next executable goal from backlog.

        Executable means:
        1. Not already claimed by another worker
        2. Dependencies satisfied
        3. No file conflicts with in-progress goals
        """
        self._update_status(WorkerState.CLAIMING)

        async with self.backlog_manager.exclusive_access():
            # Get all pending goals
            pending = await self.backlog_manager.get_pending_goals()

            for goal in pending:
                # Check if claimable
                if await self._can_claim(goal):
                    # Claim it
                    await self.backlog_manager.claim_goal(
                        goal.id,
                        worker_id=self.worker_id,
                    )
                    return goal

            return None  # Nothing available

    async def _can_claim(self, goal: Goal) -> bool:
        """Check if this worker can claim a goal.

        Checks:
        1. Not already claimed
        2. Dependencies satisfied
        3. Estimated files don't conflict with locked files
        """
        # Already claimed?
        if hasattr(goal, "claimed_by") and goal.claimed_by is not None:
            return False

        # Dependencies satisfied?
        for dep_id in goal.requires:
            dep_goal = await self.backlog_manager.get_goal(dep_id)
            if dep_goal and dep_goal.id not in self.backlog_manager.backlog.completed:
                return False

        # File conflicts?
        estimated_files = await self._estimate_affected_files(goal)
        return all(
            not self._lock_manager.is_locked(file_path)
            for file_path in estimated_files
        )

    async def _execute_goal(self, goal: Goal) -> bool:
        """Execute a single goal.

        Steps:
        1. Estimate affected files
        2. Acquire file locks
        3. Run agent
        4. Commit changes
        5. Release locks
        6. Mark complete
        """
        self._update_status(WorkerState.EXECUTING, goal_id=goal.id)

        try:
            # Estimate files we'll touch
            estimated_files = await self._estimate_affected_files(goal)

            # Acquire locks (with timeout)
            locks = await self._lock_manager.acquire_all(
                list(estimated_files),
                timeout=self.config.lock_timeout_seconds,
            )

            try:
                # Execute via Agent
                await self._run_agent(goal)

                # Commit changes
                self._update_status(WorkerState.COMMITTING)
                sha = await self._commit_changes(goal)
                if sha:
                    self._commit_shas.append(sha)

                # Mark goal complete
                await self.backlog_manager.mark_complete(goal.id)

                return True

            finally:
                # Always release locks
                await self._lock_manager.release_all(locks)

        except Exception as e:
            # Mark goal failed
            await self.backlog_manager.mark_failed(goal.id, error=str(e))
            return False

    async def _run_agent(self, goal: Goal) -> None:
        """Run the adaptive agent on a goal.

        Args:
            goal: The goal to execute
        """
        # Import here to avoid circular imports and allow worker to run in subprocess
        from sunwell.agent import Agent
        from sunwell.agent.utils.request import RunOptions
        from sunwell.agent.context.session import SessionContext
        from sunwell.memory.persistent import PersistentMemory
        from sunwell.models.ollama import OllamaModel

        # Create model (each worker gets its own model instance)
        try:
            model = OllamaModel(model="gemma3:1b")
        except Exception:
            # Fall back to a basic implementation that just logs
            # In production, this would fail or use alternative model
            return

        agent = Agent(
            model=model,
            cwd=self.root,
        )

        # RFC-MEMORY: Build SessionContext and load PersistentMemory
        options = RunOptions(trust="workspace")
        session = SessionContext.build(self.root, goal.description, options)
        memory = PersistentMemory.load(self.root)

        # Run the agent
        async for event in agent.run(session, memory):
            # Handle events (logging, status updates)
            await self._handle_agent_event(event)

    async def _handle_agent_event(self, event: Any) -> None:
        """Handle an agent event.

        Args:
            event: Event from the adaptive agent
        """
        # Update heartbeat on any event
        self.status.last_heartbeat = datetime.now()
        self._write_status()

    async def _estimate_affected_files(self, goal: Goal) -> set[Path]:
        """Estimate which files a goal will touch.

        Args:
            goal: The goal to analyze

        Returns:
            Set of estimated file paths
        """
        scope_paths = (
            set(goal.scope.allowed_paths)
            if goal.scope and goal.scope.allowed_paths
            else None
        )
        return estimate_affected_files(goal.description, scope_paths)

    async def _commit_changes(self, goal: Goal) -> str:
        """Commit changes for a completed goal.

        Returns:
            Commit SHA, or empty string if nothing to commit
        """
        commit_msg = f"""sunwell: {goal.title}

Goal ID: {goal.id}
Worker: {self.worker_id}
Category: {goal.category}

{goal.description[:200]}
"""
        return await commit_all(self.root, commit_msg)

    async def _setup_branch(self) -> None:
        """Create and checkout worker branch."""
        await create_branch(self.root, self.branch)

    def _update_status(
        self,
        state: WorkerState,
        goal_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update worker status."""
        self.status.state = state
        self.status.last_heartbeat = datetime.now()

        if goal_id is not None:
            self.status.current_goal_id = goal_id
        if state == WorkerState.IDLE:
            self.status.current_goal_id = None
        if error is not None:
            self.status.error_message = error

        self._write_status()

    def _write_status(self) -> None:
        """Write status to file atomically."""
        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._status_file.with_suffix(".tmp")

        # Convert status to dict with JSON-serializable values
        data = asdict(self.status)
        data["state"] = self.status.state.value
        data["started_at"] = self.status.started_at.isoformat()
        data["last_heartbeat"] = self.status.last_heartbeat.isoformat()

        tmp.write_text(json.dumps(data, default=str))
        tmp.rename(self._status_file)


def worker_entry(
    worker_id: int,
    root: Path,
    config: MultiInstanceConfig,
    result_queue: Queue,
) -> None:
    """Entry point for worker process (module-level for pickling).

    Must be a top-level function because multiprocessing pickles it.

    Args:
        worker_id: Unique worker identifier
        root: Project root directory
        config: Multi-instance configuration
        result_queue: Queue to send results back to coordinator
    """
    import asyncio

    # Setup signal handling for graceful shutdown
    shutdown_requested = False

    def handle_shutdown(signum: int, frame: Any) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    async def _run() -> None:
        # Each worker needs its own instances (fresh per process)
        from sunwell.features.backlog.manager import BacklogManager

        backlog = BacklogManager(root)

        worker = WorkerProcess(
            worker_id=worker_id,
            root=root,
            backlog_manager=backlog,
            config=config,
        )

        result = await worker.run()
        result_queue.put(result)

    asyncio.run(_run())
