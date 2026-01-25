"""Parallel execution for RFC-016 Autonomous Mode.

With Python 3.13+ free-threading (no-GIL), we can run multiple workers
in true parallel, each processing opportunities concurrently.

This is particularly effective for:
- Documentation improvements (mostly I/O bound)
- Independent error pattern additions
- Test file generation
- Code analysis tasks

Example:
    >>> runner = ParallelAutonomousRunner(
    ...     config=config,
    ...     num_workers=8,  # 8 parallel threads!
    ... )
    >>> await runner.start()
"""


import asyncio
import json
import queue
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sunwell.mirror import MirrorHandler
from sunwell.naaru.discovery import OpportunityDiscoverer
from sunwell.naaru.signals import SignalHandler, StopReason, format_stop_reason
from sunwell.naaru.types import (
    Opportunity,
    SessionConfig,
    SessionState,
    SessionStatus,
)


@dataclass(slots=True)
class WorkerStats:
    """Stats for a single worker."""
    worker_id: int
    tasks_completed: int = 0
    tasks_failed: int = 0
    proposals_created: int = 0
    total_time_ms: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "worker_id": self.worker_id,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "proposals_created": self.proposals_created,
            "avg_time_ms": self.total_time_ms // max(1, self.tasks_completed),
        }


@dataclass(slots=True)
class ParallelSessionState(SessionState):
    """Extended state for parallel execution."""

    num_workers: int = 1
    worker_stats: list[WorkerStats] = field(default_factory=list)

    def to_dict(self) -> dict[str, int | list[dict[str, int]]]:
        base = super().to_dict()
        base["num_workers"] = self.num_workers
        base["worker_stats"] = [w.to_dict() for w in self.worker_stats]
        return base


@dataclass(slots=True)
class ParallelAutonomousRunner:
    """Parallel runner using multiple worker threads.

    With free-threading enabled, each worker runs in true parallel,
    allowing Sunwell to work on multiple improvements simultaneously.

    Example:
        >>> config = SessionConfig(goals=["documentation", "testing"])
        >>> runner = ParallelAutonomousRunner(
        ...     config=config,
        ...     workspace=Path("."),
        ...     num_workers=8,
        ... )
        >>> await runner.start()
    """

    config: SessionConfig
    workspace: Path
    num_workers: int = 4
    storage_path: Path = None
    on_event: Callable[[str, str, int], None] | None = None

    # Internal state
    state: ParallelSessionState = field(init=False)
    _work_queue: queue.Queue = field(init=False)
    _results_queue: queue.Queue = field(init=False)
    _stop_event: threading.Event = field(init=False)
    _lock: threading.Lock = field(init=False)
    _executor: ThreadPoolExecutor = field(init=False)
    signals: SignalHandler = field(init=False)

    def __post_init__(self) -> None:
        if self.storage_path is None:
            self.storage_path = self.workspace / ".sunwell" / "autonomous"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._work_queue = queue.Queue()
        self._results_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    async def start(self) -> ParallelSessionState:
        """Start parallel autonomous execution."""
        # Initialize state
        self.state = ParallelSessionState(
            session_id=f"parallel_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
            config=self.config,
            status=SessionStatus.RUNNING,
            started_at=datetime.now(),
            num_workers=self.num_workers,
            worker_stats=[WorkerStats(i) for i in range(self.num_workers)],
        )

        # Setup signals
        self.signals = SignalHandler(
            session_id=self.state.session_id,
            storage_path=self.storage_path,
            on_stop=lambda r: self._request_stop(r),
        )
        self.signals.setup()

        try:
            await self.signals.start_file_watcher()
            self._display_banner()
            await self._run_parallel()
        except Exception as e:
            self.state.status = SessionStatus.FAILED
            self.state.stop_reason = str(e)
            self._emit("error", f"Fatal: {e}")
        finally:
            self.signals.teardown()
            await self._finalize()

        return self.state

    async def _run_parallel(self) -> None:
        """Run with parallel workers."""
        # Discovery phase
        self._emit("phase", "🔍 Discovering opportunities...")

        discoverer = OpportunityDiscoverer(
            mirror=MirrorHandler(self.workspace, self.storage_path / "mirror"),
            workspace=self.workspace,
        )
        opportunities = await discoverer.discover(self.config.goals)

        if not opportunities:
            self._emit("idle", "No opportunities found")
            return

        self._emit("discovery", f"Found {len(opportunities)} opportunities")

        # Group by category for better parallelism
        by_category = self._group_by_category(opportunities)
        self._display_categories(by_category)

        # Queue all work
        for opp in opportunities:
            self._work_queue.put(opp)

        self._emit("phase", f"🚀 Starting {self.num_workers} parallel workers...")

        # Start worker threads
        self._executor = ThreadPoolExecutor(
            max_workers=self.num_workers,
            thread_name_prefix="sunwell_worker",
        )

        # Submit workers
        futures = []
        for worker_id in range(self.num_workers):
            future = self._executor.submit(self._worker_loop, worker_id)
            futures.append(future)

        # Process results while workers run
        await self._process_results()

        # Wait for workers to finish
        self._stop_event.set()
        self._executor.shutdown(wait=True)

        self._emit("phase", "✅ All workers finished")

    def _worker_loop(self, worker_id: int) -> None:
        """Worker thread main loop."""
        # Each worker gets its own mirror handler
        mirror = MirrorHandler(
            workspace=self.workspace,
            storage_path=self.storage_path / f"mirror_w{worker_id}",
        )

        while not self._stop_event.is_set():
            try:
                # Get work with timeout (allows checking stop event)
                opp = self._work_queue.get(timeout=0.5)
            except queue.Empty:
                if self._work_queue.empty():
                    break
                continue

            # Process the opportunity
            start = datetime.now()
            result = self._process_opportunity(worker_id, mirror, opp)
            elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)

            # Record result
            result["elapsed_ms"] = elapsed_ms
            result["worker_id"] = worker_id
            self._results_queue.put(result)

            # Update worker stats
            with self._lock:
                stats = self.state.worker_stats[worker_id]
                stats.tasks_completed += 1
                stats.total_time_ms += elapsed_ms
                if result.get("proposal_id"):
                    stats.proposals_created += 1
                if result.get("error"):
                    stats.tasks_failed += 1

    def _process_opportunity(
        self,
        worker_id: int,
        mirror: MirrorHandler,
        opp: Opportunity,
    ) -> dict[str, str | int]:
        """Process a single opportunity (runs in worker thread)."""
        import asyncio

        # Map category to scope
        scope_map = {
            "error_handling": "validator",
            "testing": "validator",
            "performance": "workflow",
            "documentation": "heuristic",
            "code_quality": "heuristic",
            "security": "validator",
            "other": "heuristic",
        }
        scope = scope_map.get(opp.category.value, "heuristic")

        # Run async handler in sync context
        async def create_proposal() -> str:
            return await mirror.handle("propose_improvement", {
                "scope": scope,
                "problem": opp.description,
                "evidence": [
                    f"Worker: {worker_id}",
                    f"Target: {opp.target_module}",
                    f"Category: {opp.category.value}",
                ],
                "diff": f"# {opp.description}\n# Worker {worker_id}",
            })

        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(create_proposal())
            finally:
                loop.close()

            data = json.loads(result)

            if "error" in data:
                return {
                    "opportunity_id": opp.id,
                    "error": data["error"],
                    "status": "rejected",
                }

            return {
                "opportunity_id": opp.id,
                "proposal_id": data.get("proposal_id"),
                "status": "created",
            }

        except Exception as e:
            return {
                "opportunity_id": opp.id,
                "error": str(e),
                "status": "failed",
            }

    async def _process_results(self) -> None:
        """Process results from workers."""
        processed = 0
        total = self._work_queue.qsize() + processed

        while not self._stop_event.is_set() or not self._results_queue.empty():
            try:
                result = self._results_queue.get(timeout=0.1)
            except queue.Empty:
                # Check if all work is done
                if self._work_queue.empty() and self._results_queue.empty():
                    # Give workers a moment to finish
                    await asyncio.sleep(0.5)
                    if self._results_queue.empty():
                        break
                continue

            processed += 1
            worker_id = result.get("worker_id", "?")

            if result["status"] == "created":
                self.state.proposals_created += 1
                self._emit(
                    "created",
                    f"[W{worker_id}] ✅ {result['proposal_id']}",
                    worker_id,
                )
            elif result["status"] == "rejected":
                self.state.proposals_rejected += 1
                self._emit(
                    "rejected",
                    f"[W{worker_id}] ❌ {result.get('error', 'unknown')[:40]}",
                    worker_id,
                )
            else:
                self._emit(
                    "failed",
                    f"[W{worker_id}] ⚠️ {result.get('error', 'unknown')[:40]}",
                    worker_id,
                )

            # Progress update every 5 results
            if processed % 5 == 0:
                self._emit("progress", f"Progress: {processed}/{total}")

            # Check for stop
            if self.signals.stop_requested:
                self._stop_event.set()
                break

    def _request_stop(self, reason: StopReason) -> None:
        """Handle stop request."""
        self._stop_event.set()
        self._emit("stop", f"Stop requested: {format_stop_reason(reason)}")

    def _group_by_category(
        self,
        opportunities: list[Opportunity],
    ) -> dict[str, list[Opportunity]]:
        """Group opportunities by category."""
        groups: dict[str, list[Opportunity]] = {}
        for opp in opportunities:
            cat = opp.category.value
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(opp)
        return groups

    def _emit(self, event: str, message: str, worker_id: int = -1) -> None:
        """Emit event."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

        if self.on_event:
            self.on_event(event, message, worker_id)

    def _display_banner(self) -> None:
        """Display startup banner."""
        print()
        print("╔" + "═" * 78 + "╗")
        print("║" + " 🚀 PARALLEL AUTONOMOUS MODE".ljust(78) + "║")
        print("╠" + "═" * 78 + "╣")
        print(f"║  Session:     {self.state.session_id}".ljust(79) + "║")
        print(f"║  Workers:     {self.num_workers} parallel threads".ljust(79) + "║")
        print(f"║  Goals:       {', '.join(self.config.goals)[:55]}".ljust(79) + "║")
        print("║" + " " * 78 + "║")
        print("║  With free-threading, all workers run in TRUE PARALLEL!".ljust(79) + "║")
        print("╚" + "═" * 78 + "╝")
        print()

    def _display_categories(self, by_category: dict[str, list[Opportunity]]) -> None:
        """Display opportunity categories."""
        print("\n📊 Opportunities by Category:")
        for cat, opps in sorted(by_category.items(), key=lambda x: -len(x[1])):
            print(f"   • {cat}: {len(opps)} items")
        print()

    async def _finalize(self) -> None:
        """Finalize session."""
        self.state.stopped_at = datetime.now()
        self.state.status = SessionStatus.COMPLETED
        self.state.total_runtime_seconds = (
            self.state.stopped_at - self.state.started_at
        ).total_seconds()

        # Save state
        path = self.storage_path / f"{self.state.session_id}.json"
        with open(path, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2, default=str)

        self._display_summary()

    def _display_summary(self) -> None:
        """Display summary with worker stats."""
        print()
        print("╔" + "═" * 78 + "╗")
        print("║" + " 📊 PARALLEL SESSION SUMMARY".ljust(78) + "║")
        print("╠" + "═" * 78 + "╣")
        print(f"║  Runtime:     {self.state.total_runtime_seconds:.1f}s".ljust(79) + "║")
        print(f"║  Workers:     {self.num_workers}".ljust(79) + "║")
        print(f"║  Proposals:   {self.state.proposals_created} created".ljust(79) + "║")
        print("║" + " " * 78 + "║")
        print("║  Worker Performance:".ljust(79) + "║")

        for stats in self.state.worker_stats:
            avg_ms = stats.total_time_ms // max(1, stats.tasks_completed)
            print(f"║    W{stats.worker_id}: {stats.tasks_completed} tasks, {stats.proposals_created} proposals, {avg_ms}ms avg".ljust(79) + "║")

        # Calculate speedup
        total_work_time = sum(s.total_time_ms for s in self.state.worker_stats)
        wall_time = int(self.state.total_runtime_seconds * 1000)
        if wall_time > 0:
            speedup = total_work_time / wall_time
            print("║" + " " * 78 + "║")
            print(f"║  ⚡ Parallel speedup: {speedup:.1f}x".ljust(79) + "║")

        print("╚" + "═" * 78 + "╝")
        print()
