"""Background session manager.

Manages background sessions including spawning, tracking, and cleanup.

Thread Safety:
    Uses threading.Lock for thread-safe session management.
"""

import asyncio
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.background.session import BackgroundSession, SessionStatus

if TYPE_CHECKING:
    from sunwell.interface.cli.notifications import Notifier
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor

logger = logging.getLogger(__name__)

# Maximum background sessions to retain
MAX_SESSIONS = 20

# Session retention period (7 days in seconds)
SESSION_RETENTION_SECONDS = 7 * 24 * 60 * 60


@dataclass
class BackgroundManager:
    """Manages background task sessions.

    Handles session creation, status tracking, persistence, and cleanup.

    Thread-safe for concurrent access.

    Example:
        >>> manager = BackgroundManager(workspace)
        >>> session = await manager.spawn(goal, model, tool_executor)
        >>> print(session.session_id)
        >>> 
        >>> # Later
        >>> status = manager.get_session(session.session_id)
    """

    workspace: Path
    """Workspace root directory."""

    notifier: Notifier | None = None
    """Optional notifier for completion notifications."""

    _sessions: dict[str, BackgroundSession] = field(default_factory=dict, init=False)
    """In-memory session cache."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Thread safety lock."""

    _loaded: bool = field(default=False, init=False)
    """Whether sessions have been loaded from disk."""

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace)

    @property
    def _sessions_dir(self) -> Path:
        """Directory for session storage."""
        return self.workspace / ".sunwell" / "background"

    @property
    def _index_path(self) -> Path:
        """Path to session index file."""
        return self._sessions_dir / "sessions.json"

    def _ensure_loaded(self) -> None:
        """Load sessions from disk if not already loaded."""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            if self._index_path.exists():
                try:
                    with open(self._index_path) as f:
                        data = json.load(f)

                    for session_data in data.get("sessions", []):
                        session = BackgroundSession.from_dict(session_data)
                        self._sessions[session.session_id] = session

                    logger.debug(
                        "Loaded %d background sessions from index",
                        len(self._sessions),
                    )
                except Exception as e:
                    logger.warning("Failed to load background sessions: %s", e)

            self._loaded = True

    def _save_index(self) -> None:
        """Save session index to disk."""
        try:
            self._sessions_dir.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "sessions": [s.to_dict() for s in self._sessions.values()],
            }

            with open(self._index_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save background sessions: %s", e)

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"bg-{uuid.uuid4().hex[:8]}"

    def _cleanup_old_sessions(self) -> None:
        """Remove old sessions exceeding retention limits."""
        now = datetime.now(timezone.utc)

        # Sort by start time (newest first)
        sorted_sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.started_at or now,
            reverse=True,
        )

        to_remove: list[str] = []

        for i, session in enumerate(sorted_sessions):
            # Keep first MAX_SESSIONS
            if i >= MAX_SESSIONS:
                to_remove.append(session.session_id)
                continue

            # Don't remove running sessions
            if session.status == SessionStatus.RUNNING:
                continue

            # Check age for completed sessions
            if session.completed_at:
                age_seconds = (now - session.completed_at).total_seconds()
                if age_seconds > SESSION_RETENTION_SECONDS:
                    to_remove.append(session.session_id)

        for session_id in to_remove:
            del self._sessions[session_id]
            logger.debug("Removed old background session: %s", session_id)

    async def _on_session_complete(self, session: BackgroundSession) -> None:
        """Called when a background session completes."""
        # Save updated session state
        with self._lock:
            self._save_index()

        # Send notification
        if self.notifier is not None:
            try:
                if session.status == SessionStatus.COMPLETED:
                    await self.notifier.send_complete(
                        title="Sunwell: Background Task Complete",
                        message=session.result_summary or f"Completed: {session.goal[:50]}",
                    )
                elif session.status == SessionStatus.FAILED:
                    await self.notifier.send_error(
                        title="Sunwell: Background Task Failed",
                        message=session.error or f"Failed: {session.goal[:50]}",
                    )
            except Exception as e:
                logger.warning("Failed to send completion notification: %s", e)

    async def spawn(
        self,
        goal: str,
        model: ModelProtocol,
        tool_executor: ToolExecutor,
        memory: PersistentMemory | None = None,
        estimated_duration: int | None = None,
    ) -> BackgroundSession:
        """Spawn a new background session.

        Args:
            goal: The goal to execute
            model: LLM for generation
            tool_executor: Tool executor for file operations
            memory: Optional persistent memory
            estimated_duration: Estimated duration in seconds

        Returns:
            The created BackgroundSession
        """
        self._ensure_loaded()

        session_id = self._generate_session_id()
        session = BackgroundSession(
            session_id=session_id,
            goal=goal,
            workspace=self.workspace,
            estimated_duration_seconds=estimated_duration,
        )

        # Add to tracking
        with self._lock:
            self._sessions[session_id] = session
            self._cleanup_old_sessions()
            self._save_index()

        # Start background task
        task = asyncio.create_task(
            session.run(
                model=model,
                tool_executor=tool_executor,
                memory=memory,
                on_complete=self._on_session_complete,
            )
        )
        session._task = task

        logger.info("Spawned background session: %s", session_id)
        return session

    def get_session(self, session_id: str) -> BackgroundSession | None:
        """Get a specific background session.

        Args:
            session_id: ID of session to retrieve

        Returns:
            BackgroundSession if found, None otherwise
        """
        self._ensure_loaded()
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        running_only: bool = False,
        limit: int = 10,
    ) -> list[BackgroundSession]:
        """List background sessions.

        Args:
            running_only: If True, only return running sessions
            limit: Maximum number of sessions to return

        Returns:
            List of sessions, newest first
        """
        self._ensure_loaded()

        with self._lock:
            sessions = list(self._sessions.values())

        if running_only:
            sessions = [s for s in sessions if s.status == SessionStatus.RUNNING]

        # Sort by start time (newest first)
        sessions.sort(
            key=lambda s: s.started_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        return sessions[:limit]

    def cancel_session(self, session_id: str) -> bool:
        """Cancel a running background session.

        Args:
            session_id: ID of session to cancel

        Returns:
            True if cancelled, False if not found or already complete
        """
        session = self.get_session(session_id)
        if session is None:
            return False

        result = session.cancel()

        if result:
            with self._lock:
                self._save_index()
            logger.info("Cancelled background session: %s", session_id)

        return result

    def get_running_count(self) -> int:
        """Get number of currently running sessions."""
        self._ensure_loaded()

        with self._lock:
            return sum(
                1 for s in self._sessions.values()
                if s.status == SessionStatus.RUNNING
            )

    def clear(self) -> None:
        """Clear all sessions (for testing)."""
        with self._lock:
            # Cancel any running sessions
            for session in self._sessions.values():
                if session.status == SessionStatus.RUNNING:
                    session.cancel()

            self._sessions.clear()
            if self._index_path.exists():
                self._index_path.unlink()
            self._loaded = True
