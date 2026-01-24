"""Run state management for HTTP server (RFC-113, RFC-119).

Tracks active agent runs with:
- Event buffering for reconnection
- Cancellation support
- Thread-safe access
- Source tracking for CLI/Studio visibility (RFC-119)
"""

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class RunState:
    """State for a single agent run."""

    run_id: str
    goal: str
    workspace: str | None = None
    project_id: str | None = None  # RFC-117: Explicit project binding
    lens: str | None = None
    provider: str | None = None
    model: str | None = None
    trust: str = "workspace"
    timeout: int = 300

    status: str = "pending"  # pending | running | complete | cancelled | error
    events: list[dict[str, Any]] = field(default_factory=list)
    _cancel_flag: bool = field(default=False, repr=False)

    # RFC-119: Origin and timing for unified visibility
    source: str = "studio"  # "cli" | "studio" | "api"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # RFC: Architecture Proposal - New execution path
    use_v2: bool = False
    """Use SessionContext + PersistentMemory architecture."""

    @property
    def is_cancelled(self) -> bool:
        """Check if run has been cancelled."""
        return self._cancel_flag

    def cancel(self) -> None:
        """Signal cancellation."""
        self._cancel_flag = True
        self.status = "cancelled"
        self.completed_at = datetime.now(UTC)

    def complete(self, status: str = "complete") -> None:
        """Mark run as finished."""
        self.status = status
        self.completed_at = datetime.now(UTC)


class RunManager:
    """Thread-safe manager for active runs.

    Manages run lifecycle:
    - Create new runs
    - Track active runs by ID
    - Cleanup completed runs
    """

    def __init__(self, max_runs: int = 100) -> None:
        """Initialize run manager.

        Args:
            max_runs: Maximum concurrent runs to track (prevents memory leak).
        """
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()
        self._max_runs = max_runs

    def create_run(
        self,
        goal: str,
        *,
        workspace: str | None = None,
        project_id: str | None = None,
        lens: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        trust: str = "workspace",
        timeout: int = 300,
        source: str = "studio",
        use_v2: bool = False,
    ) -> RunState:
        """Create a new run.

        Args:
            goal: The goal to execute.
            workspace: Optional workspace path.
            project_id: Optional project ID from registry (RFC-117).
            lens: Optional lens name.
            provider: Optional model provider.
            model: Optional model name.
            trust: Tool trust level.
            timeout: Execution timeout in seconds.
            source: Origin of the run ("cli", "studio", "api").
            use_v2: Use SessionContext + PersistentMemory architecture.

        Returns:
            New RunState with unique run_id.
        """
        run_id = str(uuid4())
        run = RunState(
            run_id=run_id,
            goal=goal,
            workspace=workspace,
            project_id=project_id,
            lens=lens,
            provider=provider,
            model=model,
            trust=trust,
            timeout=timeout,
            source=source,
            use_v2=use_v2,
        )

        with self._lock:
            # Cleanup old completed runs if at capacity
            if len(self._runs) >= self._max_runs:
                self._cleanup_completed()

            self._runs[run_id] = run

        return run

    def get_run(self, run_id: str) -> RunState | None:
        """Get run by ID.

        Args:
            run_id: The run ID.

        Returns:
            RunState or None if not found.
        """
        return self._runs.get(run_id)

    def list_runs(self) -> list[RunState]:
        """List all active runs.

        Returns:
            List of RunState objects.
        """
        return list(self._runs.values())

    def _cleanup_completed(self) -> None:
        """Remove completed runs to free memory.

        Called when at capacity. Removes oldest completed runs first.
        """
        completed = [
            run_id
            for run_id, run in self._runs.items()
            if run.status in ("complete", "error", "cancelled")
        ]

        # Remove up to half of completed runs
        for run_id in completed[: len(completed) // 2 + 1]:
            del self._runs[run_id]
