"""Tests for artifact lineage store (RFC-121)."""

from pathlib import Path

import pytest

from sunwell.lineage.models import compute_content_hash
from sunwell.lineage.store import LineageStore


class TestLineageStore:
    """Core store functionality tests."""

    def test_record_create(self, tmp_path: Path) -> None:
        """Test artifact creation records lineage."""
        store = LineageStore(tmp_path)

        lineage = store.record_create(
            path="src/auth.py",
            content="class Auth: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Auth module",
            model="claude-sonnet",
        )

        assert lineage.artifact_id is not None
        assert lineage.path == "src/auth.py"
        assert lineage.content_hash == compute_content_hash("class Auth: pass")
        assert lineage.created_by_goal == "goal-1"
        assert lineage.created_by_task == "task-1"
        assert lineage.created_reason == "Auth module"
        assert lineage.model == "claude-sonnet"
        assert lineage.human_edited is False

        # Retrieve by path
        retrieved = store.get_by_path("src/auth.py")
        assert retrieved is not None
        assert retrieved.artifact_id == lineage.artifact_id

    def test_record_create_no_goal(self, tmp_path: Path) -> None:
        """Test artifact creation without goal (external file)."""
        store = LineageStore(tmp_path)

        lineage = store.record_create(
            path="external.py",
            content="# external",
            goal_id=None,
            task_id=None,
            reason="Pre-existing file",
            model=None,
        )

        assert lineage.artifact_id is not None
        assert lineage.created_by_goal is None
        assert lineage.model is None

    def test_edit_history(self, tmp_path: Path) -> None:
        """Test edit recording creates history."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/auth.py",
            content="class Auth: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Auth module",
            model="claude-sonnet",
        )

        store.record_edit(
            path="src/auth.py",
            goal_id="goal-2",
            task_id="task-2",
            lines_added=10,
            lines_removed=5,
            source="sunwell",
            model="claude-sonnet",
            content="class Auth:\n    def login(self): pass",
        )

        lineage = store.get_by_path("src/auth.py")
        assert lineage is not None
        assert len(lineage.edits) == 1
        assert lineage.edits[0].lines_added == 10
        assert lineage.edits[0].lines_removed == 5
        assert lineage.edits[0].edit_type == "modify"
        assert lineage.edits[0].source == "sunwell"
        assert lineage.edits[0].goal_id == "goal-2"

    def test_multiple_edits(self, tmp_path: Path) -> None:
        """Test multiple edits accumulate in history."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/api.py",
            content="# api",
            goal_id="goal-1",
            task_id="task-1",
            reason="API module",
            model="claude-sonnet",
        )

        # First edit
        store.record_edit(
            path="src/api.py",
            goal_id="goal-2",
            task_id="task-2",
            lines_added=5,
            lines_removed=0,
            source="sunwell",
            model="claude-sonnet",
        )

        # Second edit
        store.record_edit(
            path="src/api.py",
            goal_id="goal-3",
            task_id="task-3",
            lines_added=3,
            lines_removed=2,
            source="human",
            model=None,
        )

        lineage = store.get_by_path("src/api.py")
        assert lineage is not None
        assert len(lineage.edits) == 2
        assert lineage.edits[0].goal_id == "goal-2"
        assert lineage.edits[1].goal_id == "goal-3"
        assert lineage.edits[1].source == "human"
        assert lineage.human_edited is True

    def test_rename_preserves_lineage(self, tmp_path: Path) -> None:
        """Test rename keeps artifact ID and adds rename edit."""
        store = LineageStore(tmp_path)
        original = store.record_create(
            path="src/old.py",
            content="class Old: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Initial",
            model="claude-sonnet",
        )

        store.record_rename(
            old_path="src/old.py",
            new_path="src/new.py",
            goal_id="goal-2",
        )

        # Old path should not resolve
        assert store.get_by_path("src/old.py") is None

        # New path should resolve to same artifact
        renamed = store.get_by_path("src/new.py")
        assert renamed is not None
        assert renamed.artifact_id == original.artifact_id
        assert renamed.path == "src/new.py"
        assert any(e.edit_type == "rename" for e in renamed.edits)

    def test_delete_soft_deletes(self, tmp_path: Path) -> None:
        """Test delete marks artifact as deleted but keeps history."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/temp.py",
            content="# temp",
            goal_id="goal-1",
            task_id="task-1",
            reason="Temporary",
            model="claude-sonnet",
        )

        store.record_delete(path="src/temp.py", goal_id="goal-2")

        # Should not resolve by path
        assert store.get_by_path("src/temp.py") is None

        # But should be in recently deleted
        deleted = store.get_recently_deleted(hours=1)
        assert len(deleted) == 1
        assert deleted[0].path == "src/temp.py"
        assert deleted[0].deleted_at is not None
        assert any(e.edit_type == "delete" for e in deleted[0].edits)

    def test_get_by_goal(self, tmp_path: Path) -> None:
        """Test querying artifacts by goal ID."""
        store = LineageStore(tmp_path)

        # Create artifacts for different goals
        store.record_create(
            path="src/a.py",
            content="# a",
            goal_id="goal-1",
            task_id="task-1",
            reason="File A",
            model="claude-sonnet",
        )
        store.record_create(
            path="src/b.py",
            content="# b",
            goal_id="goal-1",
            task_id="task-2",
            reason="File B",
            model="claude-sonnet",
        )
        store.record_create(
            path="src/c.py",
            content="# c",
            goal_id="goal-2",
            task_id="task-3",
            reason="File C",
            model="claude-sonnet",
        )

        goal1_artifacts = store.get_by_goal("goal-1")
        assert len(goal1_artifacts) == 2
        assert {a.path for a in goal1_artifacts} == {"src/a.py", "src/b.py"}

        goal2_artifacts = store.get_by_goal("goal-2")
        assert len(goal2_artifacts) == 1
        assert goal2_artifacts[0].path == "src/c.py"

    def test_get_by_goal_includes_edited(self, tmp_path: Path) -> None:
        """Test get_by_goal includes artifacts edited by the goal."""
        store = LineageStore(tmp_path)

        store.record_create(
            path="src/main.py",
            content="# main",
            goal_id="goal-1",
            task_id="task-1",
            reason="Main file",
            model="claude-sonnet",
        )

        # Edit by different goal
        store.record_edit(
            path="src/main.py",
            goal_id="goal-2",
            task_id="task-2",
            lines_added=5,
            lines_removed=0,
            source="sunwell",
            model="claude-sonnet",
        )

        goal2_artifacts = store.get_by_goal("goal-2")
        assert len(goal2_artifacts) == 1
        assert goal2_artifacts[0].path == "src/main.py"

    def test_persistence(self, tmp_path: Path) -> None:
        """Test lineage persists across store instances."""
        # Create store and add artifact
        store1 = LineageStore(tmp_path)
        lineage = store1.record_create(
            path="src/persist.py",
            content="# persist",
            goal_id="goal-1",
            task_id="task-1",
            reason="Persistence test",
            model="claude-sonnet",
        )

        # Create new store instance
        store2 = LineageStore(tmp_path)
        retrieved = store2.get_by_path("src/persist.py")

        assert retrieved is not None
        assert retrieved.artifact_id == lineage.artifact_id
        assert retrieved.created_reason == "Persistence test"


class TestRenameDetection:
    """Content-based rename detection tests."""

    def test_detect_move_by_content(self, tmp_path: Path) -> None:
        """Test moved file with same content reuses artifact ID."""
        store = LineageStore(tmp_path)
        content = "class Auth:\n    def login(self): pass"

        # Create file
        original = store.record_create(
            path="src/auth.py",
            content=content,
            goal_id="goal-1",
            task_id="task-1",
            reason="Auth module",
            model="claude-sonnet",
        )

        # Delete it
        store.record_delete(path="src/auth.py", goal_id="goal-2")

        # Create with same content at new path
        moved = store.record_create(
            path="src/auth/main.py",
            content=content,  # Same content
            goal_id="goal-3",
            task_id="task-3",
            reason="Moved auth module",
            model="claude-sonnet",
        )

        # Should reuse artifact ID
        assert moved.artifact_id == original.artifact_id

    def test_different_content_new_id(self, tmp_path: Path) -> None:
        """Test file with different content gets new artifact ID."""
        store = LineageStore(tmp_path)

        # Create and delete first file
        original = store.record_create(
            path="src/old.py",
            content="class Old: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Old file",
            model="claude-sonnet",
        )
        store.record_delete(path="src/old.py", goal_id="goal-2")

        # Create different file
        new = store.record_create(
            path="src/new.py",
            content="class New: pass",  # Different content
            goal_id="goal-3",
            task_id="task-3",
            reason="New file",
            model="claude-sonnet",
        )

        # Should have different artifact ID
        assert new.artifact_id != original.artifact_id


class TestDependencies:
    """Dependency tracking tests."""

    def test_update_imports(self, tmp_path: Path) -> None:
        """Test updating import list for an artifact."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/main.py",
            content="import utils",
            goal_id="goal-1",
            task_id="task-1",
            reason="Main",
            model="claude-sonnet",
        )

        store.update_imports("src/main.py", ["src/utils.py", "src/config.py"])

        lineage = store.get_by_path("src/main.py")
        assert lineage is not None
        assert set(lineage.imports) == {"src/utils.py", "src/config.py"}

    def test_add_imported_by(self, tmp_path: Path) -> None:
        """Test adding importer to imported_by list."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/utils.py",
            content="def helper(): pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Utils",
            model="claude-sonnet",
        )

        store.add_imported_by("src/utils.py", "src/main.py")
        store.add_imported_by("src/utils.py", "src/api.py")

        lineage = store.get_by_path("src/utils.py")
        assert lineage is not None
        assert set(lineage.imported_by) == {"src/main.py", "src/api.py"}

    def test_remove_imported_by(self, tmp_path: Path) -> None:
        """Test removing importer from imported_by list."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/utils.py",
            content="def helper(): pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Utils",
            model="claude-sonnet",
        )

        store.add_imported_by("src/utils.py", "src/main.py")
        store.add_imported_by("src/utils.py", "src/api.py")
        store.remove_imported_by("src/utils.py", "src/main.py")

        lineage = store.get_by_path("src/utils.py")
        assert lineage is not None
        assert list(lineage.imported_by) == ["src/api.py"]

    def test_get_dependents(self, tmp_path: Path) -> None:
        """Test getting files that depend on a given file."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/base.py",
            content="class Base: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Base class",
            model="claude-sonnet",
        )

        store.add_imported_by("src/base.py", "src/derived1.py")
        store.add_imported_by("src/base.py", "src/derived2.py")

        dependents = store.get_dependents("src/base.py")
        assert set(dependents) == {"src/derived1.py", "src/derived2.py"}

    def test_get_dependencies(self, tmp_path: Path) -> None:
        """Test getting files that a given file imports."""
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/main.py",
            content="import stuff",
            goal_id="goal-1",
            task_id="task-1",
            reason="Main",
            model="claude-sonnet",
        )

        store.update_imports("src/main.py", ["src/utils.py", "src/config.py"])

        dependencies = store.get_dependencies("src/main.py")
        assert set(dependencies) == {"src/utils.py", "src/config.py"}


class TestExternalFiles:
    """Tests for handling pre-existing files."""

    def test_edit_unknown_file_creates_external(self, tmp_path: Path) -> None:
        """Test editing unknown file creates external record."""
        store = LineageStore(tmp_path)

        # Edit file that wasn't created by Sunwell
        store.record_edit(
            path="external.py",
            goal_id="goal-1",
            task_id="task-1",
            lines_added=5,
            lines_removed=0,
            source="sunwell",
            model="claude-sonnet",
            content="# external file",
        )

        lineage = store.get_by_path("external.py")
        assert lineage is not None
        assert lineage.created_by_goal is None
        assert lineage.human_edited is True
        assert lineage.created_reason == "Pre-existing file (not created by Sunwell)"
        assert len(lineage.edits) == 1
