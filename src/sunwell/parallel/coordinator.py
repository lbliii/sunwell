"""Coordinator for multi-instance execution (RFC-051).

Orchestrates multiple worker processes:
1. Spawns worker processes
2. Monitors worker health
3. Handles worker failures
4. Merges worker branches
5. Reports results
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from multiprocessing import Process, Queue
from pathlib import Path

from sunwell.parallel.config import MultiInstanceConfig
from sunwell.parallel.git import (
    abort_rebase,
    checkout_branch,
    delete_branch,
    get_branch_first_commit_time,
    get_current_branch,
    is_working_dir_clean,
    merge_ff_only,
    rebase_branch,
)
from sunwell.parallel.types import MergeResult, WorkerResult
from sunwell.parallel.worker import worker_entry

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorResult:
    """Result of multi-instance execution."""

    total_goals: int = 0
    """Total goals processed."""

    completed: int = 0
    """Goals completed successfully."""

    failed: int = 0
    """Goals that failed."""

    skipped: int = 0
    """Goals that were skipped."""

    duration_seconds: float = 0.0
    """Total execution time."""

    workers_used: int = 0
    """Number of workers that participated."""

    merged_branches: list[str] = field(default_factory=list)
    """Branches that were successfully merged."""

    conflict_branches: list[str] = field(default_factory=list)
    """Branches with merge conflicts."""

    errors: list[str] = field(default_factory=list)
    """Error messages encountered."""


class Coordinator:
    """Orchestrates multiple worker processes.

    Responsibilities:
    1. Spawn worker processes
    2. Monitor worker health
    3. Handle worker failures
    4. Merge worker branches
    5. Report results

    Example:
        coordinator = Coordinator(
            root=project_root,
            backlog_manager=backlog,
            config=MultiInstanceConfig(num_workers=4),
        )
        result = await coordinator.execute()
    """

    def __init__(
        self,
        root: Path,
        config: MultiInstanceConfig | None = None,
    ):
        """Initialize coordinator.

        Args:
            root: Project root directory
            config: Multi-instance configuration
        """
        self.root = Path(root)
        self.config = config or MultiInstanceConfig()

        self._workers: dict[int, Process] = {}
        self._result_queue: Queue = Queue()
        self._base_branch: str = ""

    async def execute(self) -> CoordinatorResult:
        """Run multi-instance execution.

        Returns:
            CoordinatorResult with execution summary.
        """
        start_time = datetime.now()

        try:
            # Phase 1: Setup
            await self._setup()

            # Phase 2: Spawn and monitor workers
            await self._run_workers()

            # Phase 3: Collect results
            worker_results = self._collect_results()

            # Phase 4: Merge branches
            merge_result = await self._merge_branches(worker_results)

            # Phase 5: Cleanup
            if self.config.cleanup_branches:
                await self._cleanup_branches(worker_results)

            return CoordinatorResult(
                total_goals=sum(
                    r.goals_completed + r.goals_failed for r in worker_results
                ),
                completed=sum(r.goals_completed for r in worker_results),
                failed=sum(r.goals_failed for r in worker_results),
                skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                workers_used=len(worker_results),
                merged_branches=merge_result.merged,
                conflict_branches=merge_result.conflicts,
                errors=[],
            )

        except Exception as e:
            return CoordinatorResult(
                total_goals=0,
                completed=0,
                failed=0,
                skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                workers_used=0,
                merged_branches=[],
                conflict_branches=[],
                errors=[str(e)],
            )
        finally:
            await self._terminate_all_workers()

    async def _setup(self) -> None:
        """Setup for multi-instance execution."""
        # Record base branch
        self._base_branch = await get_current_branch(self.root)

        # Ensure clean working directory
        if not await is_working_dir_clean(self.root):
            raise RuntimeError(
                "Working directory not clean. Commit or stash changes first."
            )

        # Create directories
        (self.root / ".sunwell" / "locks").mkdir(parents=True, exist_ok=True)
        (self.root / ".sunwell" / "workers").mkdir(parents=True, exist_ok=True)
        (self.root / ".sunwell" / "resources").mkdir(parents=True, exist_ok=True)

    async def _run_workers(self) -> None:
        """Spawn and monitor worker processes."""
        # Spawn workers
        for worker_id in range(1, self.config.num_workers + 1):
            process = Process(
                target=worker_entry,
                args=(
                    worker_id,
                    self.root,
                    self.config,
                    self._result_queue,
                ),
            )
            process.start()
            self._workers[worker_id] = process

        # Monitor until all complete
        await self._monitor_workers()

    async def _monitor_workers(self) -> None:
        """Monitor worker processes until all complete.

        Handles:
        - Stuck worker detection (heartbeat timeout)
        - Crashed worker recovery (unclaim goals)
        - Graceful termination
        """
        import asyncio

        while any(p.is_alive() for p in self._workers.values()):
            # Check for stuck or crashed workers
            for worker_id, process in list(self._workers.items()):
                status_file = (
                    self.root / ".sunwell" / "workers" / f"worker-{worker_id}.json"
                )

                # Check if process crashed
                if not process.is_alive():
                    exit_code = process.exitcode
                    if exit_code != 0:
                        logger.warning(
                            f"Worker {worker_id} crashed with exit code {exit_code}"
                        )
                        await self._recover_crashed_worker(worker_id)
                    continue

                # Check heartbeat for stuck detection
                if status_file.exists():
                    try:
                        status = json.loads(status_file.read_text())
                        last_heartbeat = datetime.fromisoformat(
                            status["last_heartbeat"]
                        )

                        # Worker stuck?
                        stuck_threshold = self.config.heartbeat_interval_seconds * 12
                        if (
                            datetime.now() - last_heartbeat
                        ).total_seconds() > stuck_threshold:
                            logger.warning(f"Worker {worker_id} appears stuck")
                            await self._handle_stuck_worker(worker_id, process)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        pass

            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    async def _recover_crashed_worker(self, worker_id: int) -> None:
        """Recover from a crashed worker.

        Releases any goals claimed by the worker so they can be
        picked up by other workers.

        Args:
            worker_id: The crashed worker's ID
        """
        from sunwell.backlog.manager import BacklogManager

        try:
            backlog = BacklogManager(self.root)
            async with backlog.exclusive_access():
                # Find and unclaim any goals claimed by this worker
                for goal in backlog.backlog.goals.values():
                    if goal.claimed_by == worker_id:
                        await backlog.unclaim_goal(goal.id)
                        logger.info(f"Unclaimed goal {goal.id} from crashed worker {worker_id}")
        except Exception as e:
            logger.error(f"Failed to recover crashed worker {worker_id}: {e}")

    async def _handle_stuck_worker(self, worker_id: int, process: Process) -> None:
        """Handle a stuck worker.

        Attempts graceful termination, then forces kill if needed.

        Args:
            worker_id: The stuck worker's ID
            process: The worker's process object
        """
        logger.warning(f"Terminating stuck worker {worker_id}")

        # Try graceful termination first
        process.terminate()
        process.join(timeout=5)

        if process.is_alive():
            # Force kill
            logger.warning(f"Force killing worker {worker_id}")
            process.kill()
            process.join(timeout=2)

        # Recover any claimed goals
        await self._recover_crashed_worker(worker_id)

    def _collect_results(self) -> list[WorkerResult]:
        """Collect results from all workers."""
        results = []
        while not self._result_queue.empty():
            results.append(self._result_queue.get())
        return results

    async def _merge_branches(
        self, worker_results: list[WorkerResult]
    ) -> MergeResult:
        """Merge worker branches back to base.

        Strategy:
        1. Sort branches by first commit timestamp (deterministic order)
        2. For each branch, rebase it onto current base, then fast-forward base
        3. If conflict, mark for human review and skip
        4. Base accumulates all clean merges
        """
        merged = []
        conflicts = []

        # Ensure we're on base branch
        await checkout_branch(self.root, self._base_branch)

        # Sort by first commit time for deterministic ordering
        branches_with_times: list[tuple[str, str]] = []
        for result in worker_results:
            if result.goals_completed > 0:
                try:
                    start_time = await get_branch_first_commit_time(
                        self.root, result.branch, self._base_branch
                    )
                    if start_time:
                        branches_with_times.append((result.branch, start_time))
                except subprocess.CalledProcessError:
                    # Branch has no commits, skip
                    pass

        branches = [b for b, _ in sorted(branches_with_times, key=lambda x: x[1])]

        for branch in branches:
            try:
                # Rebase worker branch onto current base (updates worker branch)
                await checkout_branch(self.root, branch)
                await rebase_branch(self.root, self._base_branch)

                # Fast-forward base to include worker's changes
                await checkout_branch(self.root, self._base_branch)
                await merge_ff_only(self.root, branch)

                merged.append(branch)
            except subprocess.CalledProcessError:
                # Conflict detected during rebase
                await abort_rebase(self.root)
                await checkout_branch(self.root, self._base_branch)
                conflicts.append(branch)
                logger.warning(f"Merge conflict in {branch}, marked for review")

        return MergeResult(merged=merged, conflicts=conflicts)

    async def _cleanup_branches(self, worker_results: list[WorkerResult]) -> None:
        """Delete worker branches."""
        for result in worker_results:
            await delete_branch(self.root, result.branch, force=True)

    async def _terminate_all_workers(self) -> None:
        """Terminate all worker processes."""
        for process in self._workers.values():
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()

    async def get_worker_statuses(self) -> list[dict]:
        """Get current status of all workers.

        Returns:
            List of worker status dictionaries
        """
        statuses = []
        workers_dir = self.root / ".sunwell" / "workers"

        if not workers_dir.exists():
            return statuses

        for status_file in workers_dir.glob("worker-*.json"):
            try:
                status = json.loads(status_file.read_text())
                statuses.append(status)
            except (json.JSONDecodeError, ValueError):
                pass

        return sorted(statuses, key=lambda s: s.get("worker_id", 0))

    def is_running(self) -> bool:
        """Check if any workers are currently running.

        Returns:
            True if at least one worker is alive
        """
        return any(p.is_alive() for p in self._workers.values())
