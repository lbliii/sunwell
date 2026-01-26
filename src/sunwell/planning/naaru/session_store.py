"""Global session storage for autonomous sessions.

Stores sessions at ~/.sunwell/sessions/{session_id}/ for persistence
across runs and projects. Enables:
- Session resume after interruption
- Session listing and management
- Cross-project session history
"""

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sunwell.planning.naaru.types import SessionState, SessionStatus

logger = logging.getLogger(__name__)

__all__ = [
    "SessionStore",
    "SessionSummary",
    "get_sessions_dir",
]


def get_sessions_dir() -> Path:
    """Get the global sessions directory.

    Returns:
        Path to ~/.sunwell/sessions/
    """
    sessions_dir = Path.home() / ".sunwell" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Lightweight session info for listing."""

    session_id: str
    """Session identifier."""

    status: SessionStatus
    """Current status."""

    goals: tuple[str, ...]
    """Session goals."""

    started_at: datetime
    """When the session started."""

    stopped_at: datetime | None
    """When the session stopped (if completed/failed)."""

    stop_reason: str | None
    """Why the session stopped."""

    opportunities_total: int
    """Total opportunities discovered."""

    opportunities_completed: int
    """Opportunities completed."""

    project_id: str | None
    """Associated project ID (if any)."""

    workspace_id: str | None
    """Associated workspace ID (if any)."""


class SessionStore:
    """Manages persistent session storage.

    Sessions are stored at:
        ~/.sunwell/sessions/{session_id}/
            state.json          - SessionState
            checkpoints/        - Periodic snapshots
                checkpoint_N.json
            runs/               - Links to run IDs

    Usage:
        >>> store = SessionStore()
        >>> store.save(session_state)
        >>> state = store.load("session_id")
        >>> summaries = store.list_sessions()
    """

    def __init__(self, sessions_dir: Path | None = None) -> None:
        """Initialize session store.

        Args:
            sessions_dir: Override sessions directory (for testing).
        """
        self._sessions_dir = sessions_dir or get_sessions_dir()

    def save(self, state: SessionState) -> Path:
        """Save session state to disk.

        Args:
            state: Session state to save.

        Returns:
            Path to the session directory.
        """
        session_dir = self._sessions_dir / state.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save state
        state_path = session_dir / "state.json"
        state.save(state_path)

        # Create checkpoint
        self._save_checkpoint(state, session_dir)

        return session_dir

    def load(self, session_id: str) -> SessionState | None:
        """Load session state from disk.

        Args:
            session_id: Session to load.

        Returns:
            SessionState or None if not found.
        """
        session_dir = self._sessions_dir / session_id

        if not session_dir.exists():
            return None

        state_path = session_dir / "state.json"
        if not state_path.exists():
            return None

        try:
            return SessionState.load(state_path)
        except Exception as e:
            logger.warning(f"Failed to load session {session_id}: {e}")
            return None

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session to delete.

        Returns:
            True if deleted, False if not found.
        """
        session_dir = self._sessions_dir / session_id

        if not session_dir.exists():
            return False

        try:
            shutil.rmtree(session_dir)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete session {session_id}: {e}")
            return False

    def list_sessions(
        self,
        status: SessionStatus | None = None,
        limit: int = 50,
    ) -> list[SessionSummary]:
        """List all sessions.

        Args:
            status: Optional filter by status.
            limit: Maximum sessions to return.

        Returns:
            List of session summaries, newest first.
        """
        summaries: list[SessionSummary] = []

        for session_dir in self._sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            state_path = session_dir / "state.json"
            if not state_path.exists():
                continue

            try:
                state = SessionState.load(state_path)

                if status is not None and state.status != status:
                    continue

                # Get associated project/workspace from metadata
                metadata = self._load_metadata(session_dir)

                summaries.append(
                    SessionSummary(
                        session_id=state.session_id,
                        status=state.status,
                        goals=state.config.goals,
                        started_at=state.started_at,
                        stopped_at=state.stopped_at,
                        stop_reason=state.stop_reason,
                        opportunities_total=len(state.opportunities) + len(state.completed),
                        opportunities_completed=len(state.completed),
                        project_id=metadata.get("project_id"),
                        workspace_id=metadata.get("workspace_id"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to read session {session_dir.name}: {e}")
                continue

        # Sort by started_at, newest first
        summaries.sort(key=lambda s: s.started_at, reverse=True)
        return summaries[:limit]

    def get_resumable_sessions(self) -> list[SessionSummary]:
        """Get sessions that can be resumed.

        Returns:
            Sessions with status PAUSED or RUNNING (interrupted).
        """
        all_sessions = self.list_sessions()
        return [
            s for s in all_sessions
            if s.status in (SessionStatus.PAUSED, SessionStatus.RUNNING)
        ]

    def update_status(self, session_id: str, status: SessionStatus, reason: str | None = None) -> bool:
        """Update session status without loading full state.

        Args:
            session_id: Session to update.
            status: New status.
            reason: Optional stop reason.

        Returns:
            True if updated, False if not found.
        """
        state = self.load(session_id)
        if not state:
            return False

        state.status = status
        if reason:
            state.stop_reason = reason
        if status in (SessionStatus.COMPLETED, SessionStatus.FAILED):
            state.stopped_at = datetime.now()

        self.save(state)
        return True

    def set_metadata(
        self,
        session_id: str,
        project_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        """Set session metadata.

        Args:
            session_id: Session to update.
            project_id: Associated project.
            workspace_id: Associated workspace container.
        """
        session_dir = self._sessions_dir / session_id
        metadata_path = session_dir / "metadata.json"

        metadata: dict = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text())
            except Exception:
                pass

        if project_id is not None:
            metadata["project_id"] = project_id
        if workspace_id is not None:
            metadata["workspace_id"] = workspace_id

        metadata_path.write_text(json.dumps(metadata, indent=2))

    def _load_metadata(self, session_dir: Path) -> dict:
        """Load session metadata."""
        metadata_path = session_dir / "metadata.json"
        if not metadata_path.exists():
            return {}

        try:
            return json.loads(metadata_path.read_text())
        except Exception:
            return {}

    def _save_checkpoint(self, state: SessionState, session_dir: Path) -> None:
        """Save a checkpoint of the session state."""
        checkpoints_dir = session_dir / "checkpoints"
        checkpoints_dir.mkdir(exist_ok=True)

        # Find next checkpoint number
        existing = list(checkpoints_dir.glob("checkpoint_*.json"))
        next_num = len(existing)

        checkpoint_path = checkpoints_dir / f"checkpoint_{next_num}.json"
        state.save(checkpoint_path)

        # Update state's checkpoint timestamp
        state.checkpoint_at = datetime.now()
