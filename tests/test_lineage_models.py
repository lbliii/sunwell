"""Tests for artifact lineage models (RFC-121)."""

from datetime import UTC, datetime

import pytest

from sunwell.lineage.models import (
    ArtifactEdit,
    ArtifactLineage,
    compute_content_hash,
    generate_artifact_id,
)


class TestArtifactEdit:
    """Tests for ArtifactEdit dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        timestamp = datetime.now(UTC)
        edit = ArtifactEdit(
            edit_id="edit-1",
            artifact_id="artifact-1",
            goal_id="goal-1",
            task_id="task-1",
            lines_added=10,
            lines_removed=5,
            edit_type="modify",
            source="sunwell",
            model="claude-sonnet",
            timestamp=timestamp,
            session_id="session-1",
            commit_hash="abc123",
            content_hash="def456",
        )

        data = edit.to_dict()

        assert data["edit_id"] == "edit-1"
        assert data["artifact_id"] == "artifact-1"
        assert data["goal_id"] == "goal-1"
        assert data["lines_added"] == 10
        assert data["lines_removed"] == 5
        assert data["edit_type"] == "modify"
        assert data["source"] == "sunwell"
        assert data["model"] == "claude-sonnet"
        assert data["timestamp"] == timestamp.isoformat()
        assert data["commit_hash"] == "abc123"

    def test_from_dict(self) -> None:
        """Test deserialization from dict."""
        timestamp = datetime.now(UTC)
        data = {
            "edit_id": "edit-2",
            "artifact_id": "artifact-2",
            "goal_id": "goal-2",
            "task_id": "task-2",
            "lines_added": 20,
            "lines_removed": 10,
            "edit_type": "create",
            "source": "human",
            "model": None,
            "timestamp": timestamp.isoformat(),
            "session_id": None,
            "commit_hash": None,
            "content_hash": "hash123",
        }

        edit = ArtifactEdit.from_dict(data)

        assert edit.edit_id == "edit-2"
        assert edit.artifact_id == "artifact-2"
        assert edit.lines_added == 20
        assert edit.edit_type == "create"
        assert edit.source == "human"
        assert edit.model is None
        assert edit.timestamp == timestamp

    def test_roundtrip(self) -> None:
        """Test to_dict -> from_dict roundtrip."""
        original = ArtifactEdit(
            edit_id="edit-rt",
            artifact_id="artifact-rt",
            goal_id="goal-rt",
            task_id="task-rt",
            lines_added=100,
            lines_removed=50,
            edit_type="rename",
            source="external",
            model="gpt-4",
            timestamp=datetime.now(UTC),
            session_id="session-rt",
            commit_hash="commit123",
            content_hash="content456",
        )

        restored = ArtifactEdit.from_dict(original.to_dict())

        assert restored.edit_id == original.edit_id
        assert restored.artifact_id == original.artifact_id
        assert restored.lines_added == original.lines_added
        assert restored.edit_type == original.edit_type
        assert restored.source == original.source


class TestArtifactLineage:
    """Tests for ArtifactLineage dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        created = datetime.now(UTC)
        lineage = ArtifactLineage(
            artifact_id="artifact-1:abc123",
            path="src/main.py",
            content_hash="hash123",
            created_by_goal="goal-1",
            created_by_task="task-1",
            created_at=created,
            created_reason="Main module",
            model="claude-sonnet",
            human_edited=False,
            edits=(),
            imports=("src/utils.py",),
            imported_by=("src/app.py",),
            deleted_at=None,
        )

        data = lineage.to_dict()

        assert data["artifact_id"] == "artifact-1:abc123"
        assert data["path"] == "src/main.py"
        assert data["content_hash"] == "hash123"
        assert data["created_by_goal"] == "goal-1"
        assert data["created_at"] == created.isoformat()
        assert data["model"] == "claude-sonnet"
        assert data["human_edited"] is False
        assert data["imports"] == ["src/utils.py"]
        assert data["imported_by"] == ["src/app.py"]
        assert data["deleted_at"] is None

    def test_from_dict(self) -> None:
        """Test deserialization from dict."""
        created = datetime.now(UTC)
        data = {
            "artifact_id": "artifact-2:def456",
            "path": "src/auth.py",
            "content_hash": "hash456",
            "created_by_goal": None,
            "created_by_task": None,
            "created_at": created.isoformat(),
            "created_reason": "External file",
            "model": None,
            "human_edited": True,
            "edits": [],
            "imports": [],
            "imported_by": [],
            "deleted_at": None,
        }

        lineage = ArtifactLineage.from_dict(data)

        assert lineage.artifact_id == "artifact-2:def456"
        assert lineage.path == "src/auth.py"
        assert lineage.created_by_goal is None
        assert lineage.human_edited is True
        assert lineage.edits == ()
        assert lineage.imports == ()

    def test_roundtrip_with_edits(self) -> None:
        """Test roundtrip with edits included."""
        created = datetime.now(UTC)
        edit_ts = datetime.now(UTC)

        edit = ArtifactEdit(
            edit_id="e1",
            artifact_id="a1:hash",
            goal_id="g1",
            task_id="t1",
            lines_added=5,
            lines_removed=2,
            edit_type="modify",
            source="sunwell",
            model="claude",
            timestamp=edit_ts,
            session_id="s1",
            commit_hash=None,
            content_hash="newhash",
        )

        original = ArtifactLineage(
            artifact_id="a1:hash",
            path="src/file.py",
            content_hash="oldhash",
            created_by_goal="g0",
            created_by_task="t0",
            created_at=created,
            created_reason="Test",
            model="claude",
            human_edited=False,
            edits=(edit,),
            imports=("src/dep.py",),
            imported_by=(),
            deleted_at=None,
        )

        restored = ArtifactLineage.from_dict(original.to_dict())

        assert restored.artifact_id == original.artifact_id
        assert len(restored.edits) == 1
        assert restored.edits[0].edit_id == "e1"
        assert restored.edits[0].lines_added == 5
        assert tuple(restored.imports) == ("src/dep.py",)

    def test_with_edit(self) -> None:
        """Test with_edit creates new lineage with edit appended."""
        lineage = ArtifactLineage(
            artifact_id="a1:hash",
            path="src/file.py",
            content_hash="hash1",
            created_by_goal="g1",
            created_by_task="t1",
            created_at=datetime.now(UTC),
            created_reason="Test",
            model="claude",
            human_edited=False,
            edits=(),
            imports=(),
            imported_by=(),
            deleted_at=None,
        )

        edit = ArtifactEdit(
            edit_id="e1",
            artifact_id="a1:hash",
            goal_id="g2",
            task_id="t2",
            lines_added=10,
            lines_removed=0,
            edit_type="modify",
            source="sunwell",
            model="claude",
            timestamp=datetime.now(UTC),
            session_id=None,
            commit_hash=None,
            content_hash="hash2",
        )

        updated = lineage.with_edit(edit)

        # Original unchanged
        assert len(lineage.edits) == 0
        assert lineage.content_hash == "hash1"

        # Updated has edit and new hash
        assert len(updated.edits) == 1
        assert updated.edits[0].edit_id == "e1"
        assert updated.content_hash == "hash2"

    def test_with_edit_human_marks_human_edited(self) -> None:
        """Test with_edit from human source marks human_edited."""
        lineage = ArtifactLineage(
            artifact_id="a1:hash",
            path="src/file.py",
            content_hash="hash1",
            created_by_goal="g1",
            created_by_task="t1",
            created_at=datetime.now(UTC),
            created_reason="Test",
            model="claude",
            human_edited=False,
            edits=(),
            imports=(),
            imported_by=(),
            deleted_at=None,
        )

        human_edit = ArtifactEdit(
            edit_id="e1",
            artifact_id="a1:hash",
            goal_id=None,
            task_id=None,
            lines_added=5,
            lines_removed=0,
            edit_type="modify",
            source="human",
            model=None,
            timestamp=datetime.now(UTC),
            session_id=None,
            commit_hash=None,
            content_hash="hash2",
        )

        updated = lineage.with_edit(human_edit)

        assert lineage.human_edited is False
        assert updated.human_edited is True

    def test_with_path(self) -> None:
        """Test with_path creates new lineage with updated path."""
        lineage = ArtifactLineage(
            artifact_id="a1:hash",
            path="src/old.py",
            content_hash="hash1",
            created_by_goal="g1",
            created_by_task="t1",
            created_at=datetime.now(UTC),
            created_reason="Test",
            model="claude",
            human_edited=False,
            edits=(),
            imports=(),
            imported_by=(),
            deleted_at=None,
        )

        updated = lineage.with_path("src/new.py")

        assert lineage.path == "src/old.py"
        assert updated.path == "src/new.py"
        assert updated.artifact_id == lineage.artifact_id

    def test_with_deleted(self) -> None:
        """Test with_deleted marks artifact as deleted."""
        lineage = ArtifactLineage(
            artifact_id="a1:hash",
            path="src/temp.py",
            content_hash="hash1",
            created_by_goal="g1",
            created_by_task="t1",
            created_at=datetime.now(UTC),
            created_reason="Test",
            model="claude",
            human_edited=False,
            edits=(),
            imports=(),
            imported_by=(),
            deleted_at=None,
        )

        deleted_at = datetime.now(UTC)
        updated = lineage.with_deleted(deleted_at)

        assert lineage.deleted_at is None
        assert updated.deleted_at == deleted_at

    def test_with_imports(self) -> None:
        """Test with_imports updates dependency info."""
        lineage = ArtifactLineage(
            artifact_id="a1:hash",
            path="src/main.py",
            content_hash="hash1",
            created_by_goal="g1",
            created_by_task="t1",
            created_at=datetime.now(UTC),
            created_reason="Test",
            model="claude",
            human_edited=False,
            edits=(),
            imports=(),
            imported_by=(),
            deleted_at=None,
        )

        updated = lineage.with_imports(
            imports=("src/utils.py", "src/config.py"),
            imported_by=("src/app.py",),
        )

        assert lineage.imports == ()
        assert lineage.imported_by == ()
        assert updated.imports == ("src/utils.py", "src/config.py")
        assert updated.imported_by == ("src/app.py",)


class TestHelperFunctions:
    """Tests for module helper functions."""

    def test_compute_content_hash_deterministic(self) -> None:
        """Test content hash is deterministic."""
        content = "class Foo: pass"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_compute_content_hash_different_content(self) -> None:
        """Test different content produces different hash."""
        hash1 = compute_content_hash("class Foo: pass")
        hash2 = compute_content_hash("class Bar: pass")
        assert hash1 != hash2

    def test_compute_content_hash_empty(self) -> None:
        """Test empty content produces valid hash."""
        hash_val = compute_content_hash("")
        assert len(hash_val) == 64

    def test_generate_artifact_id_format(self) -> None:
        """Test artifact ID format is uuid:hash_prefix."""
        artifact_id = generate_artifact_id("path.py", "content")
        parts = artifact_id.split(":")
        assert len(parts) == 2
        # UUID part should have 4 hyphens (5 sections)
        assert len(parts[0].split("-")) == 5
        # Hash prefix should be 12 chars
        assert len(parts[1]) == 12

    def test_generate_artifact_id_unique(self) -> None:
        """Test artifact IDs are unique even for same content."""
        id1 = generate_artifact_id("path.py", "content")
        id2 = generate_artifact_id("path.py", "content")
        # IDs should be different (different UUIDs)
        assert id1 != id2
        # But hash prefixes should be same (same content)
        assert id1.split(":")[1] == id2.split(":")[1]


class TestIdentityResolver:
    """Tests for ArtifactIdentityResolver."""

    def test_resolve_new_file(self, tmp_path) -> None:
        """Test new file gets new artifact ID."""
        from sunwell.lineage.identity import ArtifactIdentityResolver
        from sunwell.lineage.store import LineageStore

        store = LineageStore(tmp_path)
        resolver = ArtifactIdentityResolver(store)

        artifact_id = resolver.resolve_create("new.py", "# new content")

        assert ":" in artifact_id
        # Should be a new UUID
        assert len(artifact_id.split(":")[0].split("-")) == 5

    def test_resolve_reuses_deleted_on_content_match(self, tmp_path) -> None:
        """Test resolver reuses ID when content matches deleted artifact."""
        from sunwell.lineage.identity import ArtifactIdentityResolver
        from sunwell.lineage.store import LineageStore

        store = LineageStore(tmp_path)
        resolver = ArtifactIdentityResolver(store)

        content = "class Reusable: pass"

        # Create and delete
        lineage = store.record_create(
            path="old.py",
            content=content,
            goal_id="g1",
            task_id="t1",
            reason="Test",
            model="claude",
        )
        original_id = lineage.artifact_id

        store.record_delete("old.py", goal_id="g2")

        # Resolve for new file with same content
        resolved_id = resolver.resolve_create("new.py", content)

        assert resolved_id == original_id

    def test_resolve_new_id_for_different_content(self, tmp_path) -> None:
        """Test resolver creates new ID when content differs."""
        from sunwell.lineage.identity import ArtifactIdentityResolver
        from sunwell.lineage.store import LineageStore

        store = LineageStore(tmp_path)
        resolver = ArtifactIdentityResolver(store)

        # Create and delete
        lineage = store.record_create(
            path="old.py",
            content="class Old: pass",
            goal_id="g1",
            task_id="t1",
            reason="Test",
            model="claude",
        )
        original_id = lineage.artifact_id

        store.record_delete("old.py", goal_id="g2")

        # Resolve for new file with different content
        resolved_id = resolver.resolve_create("new.py", "class New: pass")

        assert resolved_id != original_id
