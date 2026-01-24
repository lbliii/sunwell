"""Event listener for lineage tracking (RFC-121).

Listens to file events and updates LineageStore automatically.
Integrates with RFC-119 EventBus for real-time Studio updates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sunwell.lineage.human_detection import HumanEditDetector
from sunwell.lineage.store import LineageStore

if TYPE_CHECKING:
    from sunwell.server.events import BusEvent, EventBus


class LineageEventListener:
    """Listens to agent events and updates lineage.

    Integrates with RFC-119 EventBus to capture file operations.
    Can also be called directly from tool handlers for synchronous updates.

    Example:
        >>> listener = LineageEventListener(store, event_bus, human_detector)
        >>> await listener.start()
        >>>
        >>> # Or call directly from tool handler:
        >>> listener.on_file_created(
        ...     path="src/new.py",
        ...     content="class New: pass",
        ...     goal_id="goal-1",
        ...     task_id="task-1",
        ...     model="claude-sonnet",
        ... )
    """

    # Event types we handle
    FILE_EVENTS = frozenset([
        "file_created",
        "file_modified",
        "file_deleted",
        "file_renamed",
    ])

    def __init__(
        self,
        store: LineageStore,
        event_bus: EventBus | None = None,
        human_detector: HumanEditDetector | None = None,
    ) -> None:
        """Initialize listener.

        Args:
            store: LineageStore to record events
            event_bus: Optional EventBus for WebSocket broadcast
            human_detector: Optional HumanEditDetector for source classification
        """
        self.store = store
        self.event_bus = event_bus
        self.human_detector = human_detector or HumanEditDetector(store)
        self._subscribed = False

    async def start(self) -> None:
        """Start listening for events on the EventBus."""
        if self._subscribed or not self.event_bus:
            return
        # EventBus integration would go here
        # For now, we use direct method calls from tool handlers
        self._subscribed = True

    async def stop(self) -> None:
        """Stop listening for events."""
        self._subscribed = False

    async def handle_event(self, event: BusEvent) -> None:
        """Route event to appropriate handler.

        Args:
            event: BusEvent from the EventBus
        """
        if event.type not in self.FILE_EVENTS:
            return

        match event.type:
            case "file_created":
                await self._on_file_created(event)
            case "file_modified":
                await self._on_file_modified(event)
            case "file_deleted":
                await self._on_file_deleted(event)
            case "file_renamed":
                await self._on_file_renamed(event)

    # ─────────────────────────────────────────────────────────────────
    # Event Handlers (from EventBus)
    # ─────────────────────────────────────────────────────────────────

    async def _on_file_created(self, event: BusEvent) -> None:
        """Handle file creation event from EventBus."""
        data = event.data
        self.on_file_created(
            path=data["path"],
            content=data.get("content", ""),
            goal_id=data.get("goal_id"),
            task_id=data.get("task_id"),
            model=data.get("model"),
            session_id=data.get("session_id"),
            reason=data.get("reason", "Created by Sunwell"),
        )

    async def _on_file_modified(self, event: BusEvent) -> None:
        """Handle file modification event from EventBus."""
        data = event.data
        self.on_file_modified(
            path=data["path"],
            content=data.get("content"),
            goal_id=data.get("goal_id"),
            task_id=data.get("task_id"),
            model=data.get("model"),
            session_id=data.get("session_id"),
            lines_added=data.get("lines_added", 0),
            lines_removed=data.get("lines_removed", 0),
        )

    async def _on_file_deleted(self, event: BusEvent) -> None:
        """Handle file deletion event from EventBus."""
        data = event.data
        self.on_file_deleted(
            path=data["path"],
            goal_id=data.get("goal_id"),
            session_id=data.get("session_id"),
        )

    async def _on_file_renamed(self, event: BusEvent) -> None:
        """Handle file rename event from EventBus."""
        data = event.data
        self.on_file_renamed(
            old_path=data["old_path"],
            new_path=data["new_path"],
            goal_id=data.get("goal_id"),
            session_id=data.get("session_id"),
        )

    # ─────────────────────────────────────────────────────────────────
    # Direct Method Calls (from tool handlers)
    # ─────────────────────────────────────────────────────────────────

    def on_file_created(
        self,
        path: str,
        content: str,
        goal_id: str | None = None,
        task_id: str | None = None,
        model: str | None = None,
        session_id: str | None = None,
        reason: str = "Created by Sunwell",
    ) -> None:
        """Record file creation.

        Args:
            path: File path relative to project root
            content: File content
            goal_id: Goal that triggered creation
            task_id: Task that triggered creation
            model: Model that generated the content
            session_id: Session ID
            reason: Why this file was created
        """
        self.store.record_create(
            path=path,
            content=content,
            goal_id=goal_id,
            task_id=task_id,
            reason=reason,
            model=model,
            session_id=session_id,
        )

    def on_file_modified(
        self,
        path: str,
        content: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        model: str | None = None,
        session_id: str | None = None,
        lines_added: int = 0,
        lines_removed: int = 0,
    ) -> None:
        """Record file modification.

        Args:
            path: File path
            content: New file content (for hash update)
            goal_id: Goal that triggered edit
            task_id: Task that triggered edit
            model: Model that made the edit
            session_id: Session ID
            lines_added: Lines added
            lines_removed: Lines removed
        """
        source = self.human_detector.classify_edit(
            path=path,
            goal_id=goal_id,
            model=model,
        )

        self.store.record_edit(
            path=path,
            goal_id=goal_id,
            task_id=task_id,
            lines_added=lines_added,
            lines_removed=lines_removed,
            source=source,
            model=model,
            session_id=session_id,
            content=content,
        )

    def on_file_deleted(
        self,
        path: str,
        goal_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Record file deletion.

        Args:
            path: File path
            goal_id: Goal that triggered deletion
            session_id: Session ID
        """
        self.store.record_delete(
            path=path,
            goal_id=goal_id,
            session_id=session_id,
        )

    def on_file_renamed(
        self,
        old_path: str,
        new_path: str,
        goal_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Record file rename.

        Args:
            old_path: Original path
            new_path: New path
            goal_id: Goal that triggered rename
            session_id: Session ID
        """
        self.store.record_rename(
            old_path=old_path,
            new_path=new_path,
            goal_id=goal_id,
            session_id=session_id,
        )


# ─────────────────────────────────────────────────────────────────
# Factory for easy setup
# ─────────────────────────────────────────────────────────────────


def create_lineage_listener(
    project_root: Any,
    event_bus: EventBus | None = None,
    session_tracker: Any = None,
) -> LineageEventListener:
    """Create a fully configured LineageEventListener.

    Args:
        project_root: Project root path
        event_bus: Optional EventBus for WebSocket broadcast
        session_tracker: Optional SessionTracker

    Returns:
        Configured LineageEventListener
    """
    from pathlib import Path

    root = Path(project_root)
    store = LineageStore(root)
    human_detector = HumanEditDetector(store, session_tracker)

    return LineageEventListener(
        store=store,
        event_bus=event_bus,
        human_detector=human_detector,
    )
