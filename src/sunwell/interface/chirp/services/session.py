"""Background session management service for Chirp interface."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SessionService:
    """Service for background session management."""

    def __init__(self, workspace: Path | None = None):
        """Initialize session service.

        Args:
            workspace: Workspace path (defaults to current directory)
        """
        from sunwell.agent.background.manager import BackgroundManager

        self.workspace = workspace or Path.cwd()
        self.manager = BackgroundManager(self.workspace)

    def list_sessions(
        self,
        status_filter: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List background sessions.

        Args:
            status_filter: Optional status to filter by (pending, running, completed, etc.)
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts
        """
        from sunwell.agent.background.session import SessionStatus

        sessions = self.manager.list_sessions()

        # Filter by status if requested
        if status_filter:
            try:
                status_enum = SessionStatus(status_filter)
                sessions = [s for s in sessions if s.status == status_enum]
            except ValueError:
                pass  # Invalid status, return all

        # Convert to dicts
        result = []
        for session in sessions[:limit]:
            result.append({
                "id": session.session_id,
                "goal": session.goal,
                "status": session.status.value,
                "started_at": session.started_at.timestamp() if session.started_at else None,
                "completed_at": session.completed_at.timestamp() if session.completed_at else None,
                "tasks_completed": session.tasks_completed,
                "files_changed": len(session.files_changed),
                "duration": session.duration_seconds,
                "error": session.error,
                "result_summary": session.result_summary,
            })

        return result

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get single session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session dict or None if not found
        """
        session = self.manager.get_session(session_id)
        if not session:
            return None

        return {
            "id": session.session_id,
            "goal": session.goal,
            "status": session.status.value,
            "started_at": session.started_at.timestamp() if session.started_at else None,
            "completed_at": session.completed_at.timestamp() if session.completed_at else None,
            "tasks_completed": session.tasks_completed,
            "files_changed": session.files_changed,
            "duration": session.duration_seconds,
            "error": session.error,
            "result_summary": session.result_summary,
        }

    def get_running_count(self) -> int:
        """Get number of currently running sessions."""
        return self.manager.get_running_count()
