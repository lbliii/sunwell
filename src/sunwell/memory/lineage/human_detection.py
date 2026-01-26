"""Human edit detection for lineage tracking (RFC-121).

Detects edits made by humans (not Sunwell) using session-based tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.lineage.models import compute_content_hash

if TYPE_CHECKING:
    from sunwell.memory.lineage.store import LineageStore
    from sunwell.memory.session.tracker import SessionTracker


class HumanEditDetector:
    """Detects edits made by humans (not Sunwell).

    Detection strategies:
    1. Session-based: Edits outside active Sunwell session = human
    2. Attribution-based: Edits without goal_id or model = human

    Example:
        >>> detector = HumanEditDetector(store, session_tracker)
        >>> detector.start_session("session-123")
        >>> source = detector.classify_edit("path", goal_id="g1", model="claude")
        >>> print(source)  # "sunwell"
        >>> detector.end_session()
        >>> source = detector.classify_edit("path", goal_id=None, model=None)
        >>> print(source)  # "human"
    """

    def __init__(
        self,
        store: LineageStore,
        session_tracker: SessionTracker | None = None,
    ) -> None:
        """Initialize detector.

        Args:
            store: LineageStore for accessing artifact state
            session_tracker: SessionTracker for session awareness
        """
        self.store = store
        self.session_tracker = session_tracker
        self._active_session_id: str | None = None

    def start_session(self, session_id: str) -> None:
        """Mark start of Sunwell session.

        Args:
            session_id: Session identifier
        """
        self._active_session_id = session_id

    def end_session(self) -> None:
        """Mark end of Sunwell session."""
        self._active_session_id = None

    @property
    def active_session_id(self) -> str | None:
        """Get active session ID."""
        return self._active_session_id

    def classify_edit(
        self,
        path: str,
        goal_id: str | None,
        model: str | None,
    ) -> str:
        """Classify edit source.

        Args:
            path: File path being edited
            goal_id: Goal ID (if any)
            model: Model name (if any)

        Returns:
            "sunwell": Edit from active Sunwell session with attribution
            "human": Edit from user (no session or missing attribution)
            "external": Edit from unknown source (has session but missing attribution)
        """
        # Active session with full attribution = Sunwell
        if self._active_session_id and goal_id and model:
            return "sunwell"

        # No active session = human edit
        if self._active_session_id is None:
            return "human"

        # Active session but missing attribution = external tool
        return "external"

    def detect_untracked_changes(self, project_root: Path) -> list[dict]:
        """Detect files modified outside Sunwell.

        Compares stored content_hash with current file content.

        Args:
            project_root: Project root directory

        Returns:
            List of dicts with path, artifact_id, last_known_hash, current_hash
        """
        untracked = []

        # Get all tracked paths from store index
        for path in list(self.store._index.keys()):
            full_path = project_root / path
            if not full_path.exists():
                continue

            lineage = self.store.get_by_path(path)
            if not lineage:
                continue

            try:
                current_content = full_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            current_hash = compute_content_hash(current_content)

            # Get last known hash (from last edit or creation)
            last_known_hash = lineage.content_hash
            if lineage.edits:
                last_edit_hash = lineage.edits[-1].content_hash
                if last_edit_hash:
                    last_known_hash = last_edit_hash

            if current_hash != last_known_hash:
                untracked.append({
                    "path": path,
                    "artifact_id": lineage.artifact_id,
                    "last_known_hash": last_known_hash,
                    "current_hash": current_hash,
                })

        return untracked

    def sync_untracked(
        self,
        project_root: Path,
        mark_as_human: bool = True,
    ) -> list[str]:
        """Sync untracked changes by recording them as human edits.

        Args:
            project_root: Project root directory
            mark_as_human: Whether to mark changes as human edits

        Returns:
            List of paths that were synced
        """
        untracked = self.detect_untracked_changes(project_root)
        synced = []

        for change in untracked:
            path = change["path"]
            full_path = project_root / path

            if not full_path.exists():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            # Get current lineage to compute line changes
            lineage = self.store.get_by_path(path)
            if not lineage:
                continue

            # Estimate line changes (approximate)
            new_lines = content.count("\n") + 1

            # Record as human edit
            if mark_as_human:
                self.store.record_edit(
                    path=path,
                    goal_id=None,
                    task_id=None,
                    lines_added=new_lines,  # Approximate
                    lines_removed=0,  # Can't know without old content
                    source="human",
                    model=None,
                    session_id=None,
                    content=content,
                )

            synced.append(path)

        return synced
