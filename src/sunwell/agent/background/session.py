"""Background session for async task execution.

Represents a task running in the background with status tracking
and result storage.

Thread Safety:
    Uses threading.Lock for thread-safe status updates.
"""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Status of a background session."""

    PENDING = "pending"
    """Session created but not yet started."""

    RUNNING = "running"
    """Session is actively executing."""

    COMPLETED = "completed"
    """Session finished successfully."""

    FAILED = "failed"
    """Session failed with error."""

    WAITING = "waiting"
    """Session is waiting for user input (checkpoint)."""

    CANCELLED = "cancelled"
    """Session was cancelled by user."""


@dataclass
class BackgroundSession:
    """A task running in the background.

    Tracks execution status, results, and provides methods for
    status updates and result retrieval.

    Attributes:
        session_id: Unique session identifier
        goal: The goal being executed
        workspace: Workspace path
        status: Current execution status
        started_at: When execution started
        completed_at: When execution completed (if done)
        result_summary: Summary of results (if complete)
        error: Error message (if failed)
        tasks_completed: Number of tasks completed
        files_changed: List of files modified
    """

    session_id: str
    goal: str
    workspace: Path
    status: SessionStatus = SessionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_summary: str | None = None
    error: str | None = None
    tasks_completed: int = 0
    files_changed: list[str] = field(default_factory=list)
    estimated_duration_seconds: int | None = None

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Thread safety lock."""

    _task: asyncio.Task | None = field(default=None, init=False, repr=False)
    """The asyncio task running this session."""

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace)

    @property
    def is_running(self) -> bool:
        """True if session is currently running."""
        return self.status == SessionStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        """True if session has finished (success or failure)."""
        return self.status in (
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED,
        )

    @property
    def duration_seconds(self) -> float | None:
        """Duration in seconds if completed, None if still running."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    def update_status(self, status: SessionStatus) -> None:
        """Update session status (thread-safe)."""
        with self._lock:
            self.status = status
            if status == SessionStatus.RUNNING and self.started_at is None:
                self.started_at = datetime.now(timezone.utc)
            elif status in (
                SessionStatus.COMPLETED,
                SessionStatus.FAILED,
                SessionStatus.CANCELLED,
            ):
                self.completed_at = datetime.now(timezone.utc)

    def set_result(self, summary: str, tasks: int, files: list[str]) -> None:
        """Set successful completion result."""
        with self._lock:
            self.result_summary = summary
            self.tasks_completed = tasks
            self.files_changed = files

    def set_error(self, error: str) -> None:
        """Set failure error message."""
        with self._lock:
            self.error = error

    def cancel(self) -> bool:
        """Request cancellation of running session.

        Returns:
            True if cancellation was requested, False if already complete
        """
        if self.is_complete:
            return False

        with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
            self.status = SessionStatus.CANCELLED
            self.completed_at = datetime.now(timezone.utc)
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "workspace": str(self.workspace),
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_summary": self.result_summary,
            "error": self.error,
            "tasks_completed": self.tasks_completed,
            "files_changed": self.files_changed,
            "estimated_duration_seconds": self.estimated_duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackgroundSession":
        """Deserialize from dictionary."""
        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])

        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        return cls(
            session_id=data["session_id"],
            goal=data["goal"],
            workspace=Path(data["workspace"]),
            status=SessionStatus(data.get("status", "pending")),
            started_at=started_at,
            completed_at=completed_at,
            result_summary=data.get("result_summary"),
            error=data.get("error"),
            tasks_completed=data.get("tasks_completed", 0),
            files_changed=data.get("files_changed", []),
            estimated_duration_seconds=data.get("estimated_duration_seconds"),
        )

    async def run(
        self,
        model: ModelProtocol,
        tool_executor: ToolExecutor,
        memory: PersistentMemory | None = None,
        on_complete: Any | None = None,
        precomputed_plan: Any | None = None,  # PlanResult for RFC: Plan-Based Duration Estimation
    ) -> None:
        """Execute the goal in the background.

        Args:
            model: LLM for generation
            tool_executor: Tool executor for file operations
            memory: Optional persistent memory
            on_complete: Optional callback when complete (async callable)
            precomputed_plan: Optional PlanResult to skip re-planning (RFC)
        """
        from sunwell.agent import Agent
        from sunwell.agent.context.session import SessionContext
        from sunwell.agent.events import EventType
        from sunwell.memory import PersistentMemory

        self.update_status(SessionStatus.RUNNING)
        logger.info("Background session %s started: %s", self.session_id, self.goal[:50])

        try:
            # Create agent
            agent = Agent(
                model=model,
                tool_executor=tool_executor,
                cwd=self.workspace,
            )

            # Create session context
            session = SessionContext.build(self.workspace, self.goal, None)

            # Load memory if not provided
            if memory is None:
                memory = PersistentMemory.load(self.workspace)

            # Run agent and collect results
            tasks_completed = 0
            files_changed: list[str] = []

            # RFC: Plan-Based Duration Estimation - pass precomputed plan if available
            async for event in agent.run(session, memory, precomputed_plan=precomputed_plan):
                if event.type == EventType.TASK_COMPLETE:
                    tasks_completed += 1
                elif event.type == EventType.COMPLETE:
                    files_changed = event.data.get("files_changed", [])

            # Set successful result
            self.set_result(
                summary=f"Completed {tasks_completed} tasks",
                tasks=tasks_completed,
                files=files_changed,
            )
            self.update_status(SessionStatus.COMPLETED)
            logger.info(
                "Background session %s completed: %d tasks",
                self.session_id,
                tasks_completed,
            )

            # Call completion callback
            if on_complete:
                try:
                    if asyncio.iscoroutinefunction(on_complete):
                        await on_complete(self)
                    else:
                        on_complete(self)
                except Exception as e:
                    logger.warning("Completion callback failed: %s", e)

        except asyncio.CancelledError:
            self.update_status(SessionStatus.CANCELLED)
            logger.info("Background session %s cancelled", self.session_id)
            raise

        except Exception as e:
            self.set_error(str(e))
            self.update_status(SessionStatus.FAILED)
            logger.exception("Background session %s failed", self.session_id)

            # Still call completion callback on failure
            if on_complete:
                try:
                    if asyncio.iscoroutinefunction(on_complete):
                        await on_complete(self)
                    else:
                        on_complete(self)
                except Exception as cb_e:
                    logger.warning("Completion callback failed: %s", cb_e)
