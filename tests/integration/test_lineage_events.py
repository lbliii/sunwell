"""Integration tests for lineage event tracking (RFC-121)."""

from pathlib import Path

import pytest

from sunwell.memory.lineage import (
    HumanEditDetector,
    LineageEventListener,
    LineageStore,
    create_lineage_listener,
)
from sunwell.tools.handlers.file import FileHandlers


class TestLineageEventListener:
    """Test LineageEventListener integration."""

    def test_on_file_created(self, tmp_path: Path) -> None:
        """Test file creation events are recorded."""
        store = LineageStore(tmp_path)
        listener = LineageEventListener(store)

        listener.on_file_created(
            path="src/new.py",
            content="class New: pass",
            goal_id="goal-1",
            task_id="task-1",
            model="claude-sonnet",
            reason="Test file",
        )

        lineage = store.get_by_path("src/new.py")
        assert lineage is not None
        assert lineage.created_by_goal == "goal-1"
        assert lineage.created_reason == "Test file"
        assert lineage.model == "claude-sonnet"

    def test_on_file_modified(self, tmp_path: Path) -> None:
        """Test file modification events are recorded."""
        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)
        detector.start_session("session-1")
        listener = LineageEventListener(store, human_detector=detector)

        # Create file first
        listener.on_file_created(
            path="src/main.py",
            content="# main",
            goal_id="goal-1",
            task_id="task-1",
            model="claude-sonnet",
        )

        # Modify it
        listener.on_file_modified(
            path="src/main.py",
            content="# main\ndef main(): pass",
            goal_id="goal-2",
            task_id="task-2",
            model="claude-sonnet",
            lines_added=2,
            lines_removed=0,
        )

        lineage = store.get_by_path("src/main.py")
        assert lineage is not None
        assert len(lineage.edits) == 1
        assert lineage.edits[0].source == "sunwell"
        assert lineage.edits[0].lines_added == 2

    def test_on_file_modified_human_source(self, tmp_path: Path) -> None:
        """Test modifications without session are marked as human."""
        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)
        # No active session
        listener = LineageEventListener(store, human_detector=detector)

        # Create file first (as sunwell for setup)
        store.record_create(
            path="src/config.py",
            content="# config",
            goal_id="goal-1",
            task_id="task-1",
            reason="Config file",
            model="claude-sonnet",
        )

        # Modify without attribution (human edit)
        listener.on_file_modified(
            path="src/config.py",
            content="# config modified",
            goal_id=None,
            task_id=None,
            model=None,
            lines_added=1,
            lines_removed=0,
        )

        lineage = store.get_by_path("src/config.py")
        assert lineage is not None
        assert len(lineage.edits) == 1
        assert lineage.edits[0].source == "human"
        assert lineage.human_edited is True

    def test_on_file_deleted(self, tmp_path: Path) -> None:
        """Test file deletion events are recorded."""
        store = LineageStore(tmp_path)
        listener = LineageEventListener(store)

        # Create file
        listener.on_file_created(
            path="src/temp.py",
            content="# temp",
            goal_id="goal-1",
            task_id="task-1",
            model="claude-sonnet",
        )

        # Delete it
        listener.on_file_deleted(
            path="src/temp.py",
            goal_id="goal-2",
        )

        # Should not be retrievable by path
        assert store.get_by_path("src/temp.py") is None

        # Should be in recently deleted
        deleted = store.get_recently_deleted(hours=1)
        assert len(deleted) == 1
        assert any(e.edit_type == "delete" for e in deleted[0].edits)

    def test_on_file_renamed(self, tmp_path: Path) -> None:
        """Test file rename events preserve lineage."""
        store = LineageStore(tmp_path)
        listener = LineageEventListener(store)

        # Create file
        listener.on_file_created(
            path="src/old.py",
            content="class Old: pass",
            goal_id="goal-1",
            task_id="task-1",
            model="claude-sonnet",
        )

        original = store.get_by_path("src/old.py")
        assert original is not None
        original_id = original.artifact_id

        # Rename it
        listener.on_file_renamed(
            old_path="src/old.py",
            new_path="src/new.py",
            goal_id="goal-2",
        )

        # Old path should not resolve
        assert store.get_by_path("src/old.py") is None

        # New path should have same artifact ID
        renamed = store.get_by_path("src/new.py")
        assert renamed is not None
        assert renamed.artifact_id == original_id
        assert any(e.edit_type == "rename" for e in renamed.edits)


class TestHumanEditDetector:
    """Test HumanEditDetector."""

    def test_classify_sunwell_with_session(self, tmp_path: Path) -> None:
        """Test sunwell classification with active session and attribution."""
        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)

        detector.start_session("session-1")
        source = detector.classify_edit("path.py", goal_id="g1", model="claude")
        assert source == "sunwell"

    def test_classify_human_without_session(self, tmp_path: Path) -> None:
        """Test human classification without active session."""
        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)

        # No session started
        source = detector.classify_edit("path.py", goal_id=None, model=None)
        assert source == "human"

    def test_classify_external_partial_attribution(self, tmp_path: Path) -> None:
        """Test external classification with session but missing attribution."""
        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)

        detector.start_session("session-1")
        # Has session but missing goal or model
        source = detector.classify_edit("path.py", goal_id="g1", model=None)
        assert source == "external"

    def test_detect_untracked_changes(self, tmp_path: Path) -> None:
        """Test detecting files modified outside Sunwell."""
        # Create actual file on disk
        (tmp_path / "src").mkdir()
        test_file = tmp_path / "src" / "tracked.py"
        test_file.write_text("# original")

        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)

        # Record in lineage
        store.record_create(
            path="src/tracked.py",
            content="# original",
            goal_id="goal-1",
            task_id="task-1",
            reason="Test",
            model="claude-sonnet",
        )

        # Modify file outside Sunwell
        test_file.write_text("# modified externally")

        # Detect changes
        untracked = detector.detect_untracked_changes(tmp_path)
        assert len(untracked) == 1
        assert untracked[0]["path"] == "src/tracked.py"

    def test_session_lifecycle(self, tmp_path: Path) -> None:
        """Test session start/end affects classification."""
        store = LineageStore(tmp_path)
        detector = HumanEditDetector(store)

        # Before session
        assert detector.classify_edit("p", goal_id="g", model="m") == "human"

        # During session
        detector.start_session("s1")
        assert detector.classify_edit("p", goal_id="g", model="m") == "sunwell"
        assert detector.active_session_id == "s1"

        # After session
        detector.end_session()
        assert detector.classify_edit("p", goal_id="g", model="m") == "human"
        assert detector.active_session_id is None


class TestFileHandlersLineageIntegration:
    """Test FileHandlers emit lineage events."""

    @pytest.fixture
    def handlers(self, tmp_path: Path) -> FileHandlers:
        """Create FileHandlers with workspace."""
        return FileHandlers(workspace=tmp_path)

    @pytest.mark.asyncio
    async def test_write_file_emits_created(self, tmp_path: Path, handlers: FileHandlers) -> None:
        """Test write_file emits file_created for new files."""
        events: list[tuple] = []

        def capture_event(event_type: str, path: str, content: str, added: int, removed: int) -> None:
            events.append((event_type, path, content, added, removed))

        handlers.set_file_event_callback(capture_event)

        await handlers.write_file({"path": "new.py", "content": "# new file\n"})

        assert len(events) == 1
        assert events[0][0] == "file_created"
        assert events[0][1] == "new.py"
        assert events[0][3] == 2  # lines_added

    @pytest.mark.asyncio
    async def test_write_file_emits_modified(self, tmp_path: Path, handlers: FileHandlers) -> None:
        """Test write_file emits file_modified for existing files."""
        # Create file first
        (tmp_path / "existing.py").write_text("# old")

        events: list[tuple] = []

        def capture_event(event_type: str, path: str, content: str, added: int, removed: int) -> None:
            events.append((event_type, path, content, added, removed))

        handlers.set_file_event_callback(capture_event)

        await handlers.write_file({"path": "existing.py", "content": "# new\n# more"})

        assert len(events) == 1
        assert events[0][0] == "file_modified"
        assert events[0][1] == "existing.py"

    @pytest.mark.asyncio
    async def test_edit_file_emits_modified(self, tmp_path: Path, handlers: FileHandlers) -> None:
        """Test edit_file emits file_modified."""
        # Create file
        (tmp_path / "edit.py").write_text("# line 1\n# line 2\n")

        events: list[tuple] = []

        def capture_event(event_type: str, path: str, content: str, added: int, removed: int) -> None:
            events.append((event_type, path, content, added, removed))

        handlers.set_file_event_callback(capture_event)

        await handlers.edit_file({
            "path": "edit.py",
            "old_content": "# line 2",
            "new_content": "# modified line 2\n# added line",
        })

        assert len(events) == 1
        assert events[0][0] == "file_modified"
        assert events[0][1] == "edit.py"


class TestCreateLineageListener:
    """Test factory function."""

    def test_create_lineage_listener(self, tmp_path: Path) -> None:
        """Test factory creates configured listener."""
        listener = create_lineage_listener(tmp_path)

        assert listener.store is not None
        assert listener.human_detector is not None

        # Should be functional
        listener.on_file_created(
            path="test.py",
            content="# test",
            goal_id="g1",
            task_id="t1",
            model="claude",
        )

        lineage = listener.store.get_by_path("test.py")
        assert lineage is not None
