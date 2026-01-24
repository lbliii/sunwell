"""Tests for observability and debugging features.

Tests cover:
- Debug dump creation and sanitization
- Plan versioning (save_version, get_versions, diff)
- Session tracking (SessionTracker, SessionSummary)
"""

import json
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.naaru.persistence import (
    PlanDiff,
    PlanStore,
    PlanVersion,
    SavedExecution,
)
from sunwell.session import GoalSummary, SessionSummary, SessionTracker


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_graph() -> ArtifactGraph:
    """Create a sample artifact graph for testing."""
    graph = ArtifactGraph()
    graph.add(ArtifactSpec(id="A", description="Task A", contract="Contract A"))
    graph.add(ArtifactSpec(id="B", description="Task B", contract="Contract B"))
    graph.add(
        ArtifactSpec(
            id="C",
            description="Task C",
            contract="Contract C",
            requires=frozenset(["A", "B"]),
        )
    )
    return graph


@pytest.fixture
def temp_store(tmp_path: Path) -> PlanStore:
    """Create a PlanStore with temp directory."""
    return PlanStore(base_path=tmp_path / "plans")


@pytest.fixture
def temp_session_tracker(tmp_path: Path) -> SessionTracker:
    """Create a SessionTracker with temp directory."""
    return SessionTracker(base_path=tmp_path / "sessions")


# =============================================================================
# Plan Versioning Tests
# =============================================================================


class TestPlanVersion:
    """Tests for PlanVersion dataclass."""

    def test_plan_version_creation(self) -> None:
        """PlanVersion should be creatable with required fields."""
        version = PlanVersion(
            version=1,
            plan_id="abc123",
            goal="Build API",
            artifacts=("A", "B", "C"),
            tasks=("Task A", "Task B"),
            created_at=datetime.now(UTC),
            reason="Initial plan",
        )

        assert version.version == 1
        assert version.plan_id == "abc123"
        assert version.goal == "Build API"
        assert len(version.artifacts) == 3
        assert version.reason == "Initial plan"

    def test_plan_version_to_dict(self) -> None:
        """PlanVersion should serialize to dict."""
        version = PlanVersion(
            version=2,
            plan_id="def456",
            goal="Build UI",
            artifacts=("X", "Y"),
            tasks=("Task X",),
            created_at=datetime.now(UTC),
            reason="After resonance",
            score=0.85,
            added_artifacts=("Y",),
            removed_artifacts=(),
            modified_artifacts=(),
        )

        data = version.to_dict()

        assert data["version"] == 2
        assert data["plan_id"] == "def456"
        assert data["score"] == 0.85
        assert data["added_artifacts"] == ["Y"]
        assert "created_at" in data

    def test_plan_version_from_dict(self) -> None:
        """PlanVersion should deserialize from dict."""
        data = {
            "version": 3,
            "plan_id": "ghi789",
            "goal": "Build tests",
            "artifacts": ["T1", "T2"],
            "tasks": ["Test 1"],
            "created_at": "2026-01-24T10:00:00",
            "reason": "User edit",
            "score": 0.92,
            "added_artifacts": [],
            "removed_artifacts": ["T3"],
            "modified_artifacts": [],
        }

        version = PlanVersion.from_dict(data)

        assert version.version == 3
        assert version.plan_id == "ghi789"
        assert version.score == 0.92
        assert "T3" in version.removed_artifacts


class TestPlanDiff:
    """Tests for PlanDiff dataclass."""

    def test_plan_diff_creation(self) -> None:
        """PlanDiff should be creatable."""
        diff = PlanDiff(
            plan_id="abc123",
            v1=1,
            v2=2,
            added=("C", "D"),
            removed=("A",),
            modified=(),
        )

        assert diff.plan_id == "abc123"
        assert diff.v1 == 1
        assert diff.v2 == 2
        assert "C" in diff.added
        assert "A" in diff.removed

    def test_plan_diff_to_dict(self) -> None:
        """PlanDiff should serialize to dict."""
        diff = PlanDiff(
            plan_id="test",
            v1=1,
            v2=3,
            added=("X",),
            removed=("Y",),
            modified=("Z",),
        )

        data = diff.to_dict()

        assert data["v1"] == 1
        assert data["v2"] == 3
        assert data["added"] == ["X"]


class TestPlanStoreVersioning:
    """Tests for PlanStore versioning methods."""

    def test_save_version(self, temp_store: PlanStore, sample_graph: ArtifactGraph) -> None:
        """save_version should create version file."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)

        version = temp_store.save_version(execution, "Initial plan")

        assert version.version == 1
        assert version.reason == "Initial plan"
        assert len(version.artifacts) == 3  # A, B, C

        # Verify file exists
        version_path = temp_store.base_path / execution.goal_hash / "v1.json"
        assert version_path.exists()

    def test_save_multiple_versions(
        self, temp_store: PlanStore, sample_graph: ArtifactGraph
    ) -> None:
        """save_version should increment version numbers."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)

        v1 = temp_store.save_version(execution, "Initial")
        v2 = temp_store.save_version(execution, "Resonance round 1")
        v3 = temp_store.save_version(execution, "User edit")

        assert v1.version == 1
        assert v2.version == 2
        assert v3.version == 3

    def test_get_versions(self, temp_store: PlanStore, sample_graph: ArtifactGraph) -> None:
        """get_versions should return all versions for a plan."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)

        temp_store.save_version(execution, "v1")
        temp_store.save_version(execution, "v2")
        temp_store.save_version(execution, "v3")

        versions = temp_store.get_versions(execution.goal_hash)

        assert len(versions) == 3
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3

    def test_get_versions_empty(self, temp_store: PlanStore) -> None:
        """get_versions should return empty list for non-existent plan."""
        versions = temp_store.get_versions("nonexistent")
        assert versions == []

    def test_get_version(self, temp_store: PlanStore, sample_graph: ArtifactGraph) -> None:
        """get_version should return specific version."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)

        temp_store.save_version(execution, "First")
        temp_store.save_version(execution, "Second")

        v2 = temp_store.get_version(execution.goal_hash, 2)

        assert v2 is not None
        assert v2.version == 2
        assert v2.reason == "Second"

    def test_get_version_not_found(
        self, temp_store: PlanStore, sample_graph: ArtifactGraph
    ) -> None:
        """get_version should return None for non-existent version."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)
        temp_store.save_version(execution, "v1")

        result = temp_store.get_version(execution.goal_hash, 99)

        assert result is None

    def test_diff(self, temp_store: PlanStore) -> None:
        """diff should compute changes between versions."""
        # Create two versions with different artifacts
        graph1 = ArtifactGraph()
        graph1.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph1.add(ArtifactSpec(id="B", description="B", contract="B"))

        graph2 = ArtifactGraph()
        graph2.add(ArtifactSpec(id="B", description="B", contract="B"))
        graph2.add(ArtifactSpec(id="C", description="C", contract="C"))

        exec1 = SavedExecution(goal="Test", graph=graph1)
        exec2 = SavedExecution(goal="Test", graph=graph2)

        temp_store.save_version(exec1, "v1")
        temp_store.save_version(exec2, "v2")

        diff = temp_store.diff(exec1.goal_hash, 1, 2)

        assert diff is not None
        assert "C" in diff.added
        assert "A" in diff.removed

    def test_diff_not_found(self, temp_store: PlanStore) -> None:
        """diff should return None when versions don't exist."""
        diff = temp_store.diff("nonexistent", 1, 2)
        assert diff is None

    def test_clean_old_prunes_versions(
        self, temp_store: PlanStore, sample_graph: ArtifactGraph
    ) -> None:
        """clean_old should prune old versions beyond max_versions."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)

        # Create 15 versions
        for i in range(15):
            temp_store.save_version(execution, f"Version {i+1}")

        # Clean with max_versions=5
        deleted = temp_store.clean_old(max_age_hours=9999, max_versions=5)

        # Should have deleted 10 old versions
        assert deleted == 10

        # Should have 5 versions remaining
        versions = temp_store.get_versions(execution.goal_hash)
        assert len(versions) == 5

    def test_delete_removes_versions(
        self, temp_store: PlanStore, sample_graph: ArtifactGraph
    ) -> None:
        """delete should remove version directory."""
        execution = SavedExecution(goal="Build API", graph=sample_graph)
        temp_store.save(execution)
        temp_store.save_version(execution, "v1")
        temp_store.save_version(execution, "v2")

        version_dir = temp_store.base_path / execution.goal_hash
        assert version_dir.exists()

        temp_store.delete(execution.goal_hash)

        assert not version_dir.exists()


# =============================================================================
# Session Tracking Tests
# =============================================================================


class TestGoalSummary:
    """Tests for GoalSummary dataclass."""

    def test_goal_summary_creation(self) -> None:
        """GoalSummary should be creatable."""
        summary = GoalSummary(
            goal_id="g1",
            goal="Add OAuth",
            status="completed",
            source="cli",
            started_at=datetime.now(UTC),
            duration_seconds=120.0,
            tasks_completed=3,
            tasks_failed=0,
            files_touched=("oauth.py", "tests.py"),
        )

        assert summary.goal_id == "g1"
        assert summary.status == "completed"
        assert len(summary.files_touched) == 2

    def test_goal_summary_to_dict(self) -> None:
        """GoalSummary should serialize to dict."""
        summary = GoalSummary(
            goal_id="g2",
            goal="Fix bug",
            status="failed",
            source="studio",
            started_at=datetime.now(UTC),
            duration_seconds=60.0,
            tasks_completed=1,
            tasks_failed=2,
            files_touched=("bug.py",),
        )

        data = summary.to_dict()

        assert data["goal_id"] == "g2"
        assert data["status"] == "failed"
        assert data["files_touched"] == ["bug.py"]

    def test_goal_summary_from_dict(self) -> None:
        """GoalSummary should deserialize from dict."""
        data = {
            "goal_id": "g3",
            "goal": "Refactor",
            "status": "completed",
            "source": "api",
            "started_at": "2026-01-24T10:00:00",
            "duration_seconds": 180.0,
            "tasks_completed": 5,
            "tasks_failed": 0,
            "files_touched": ["a.py", "b.py"],
        }

        summary = GoalSummary.from_dict(data)

        assert summary.goal_id == "g3"
        assert summary.duration_seconds == 180.0


class TestSessionTracker:
    """Tests for SessionTracker."""

    def test_session_tracker_creation(self, tmp_path: Path) -> None:
        """SessionTracker should be creatable."""
        tracker = SessionTracker(base_path=tmp_path / "sessions")

        assert tracker.session_id is not None
        assert tracker.started_at is not None

    def test_record_goal_complete(self, temp_session_tracker: SessionTracker) -> None:
        """record_goal_complete should add goal to tracker."""
        summary = temp_session_tracker.record_goal_complete(
            goal_id="g1",
            goal="Add OAuth",
            status="completed",
            source="cli",
            duration_seconds=120.0,
            tasks_completed=3,
            tasks_failed=0,
            files=["oauth.py", "tests.py"],
        )

        assert summary.goal_id == "g1"
        assert summary.status == "completed"

        # Should be reflected in session summary
        session = temp_session_tracker.get_summary()
        assert session.goals_completed == 1

    def test_record_multiple_goals(self, temp_session_tracker: SessionTracker) -> None:
        """SessionTracker should track multiple goals."""
        temp_session_tracker.record_goal_complete(
            goal_id="g1", goal="Goal 1", status="completed",
            source="cli", duration_seconds=60.0,
            tasks_completed=2, tasks_failed=0, files=["a.py"],
        )
        temp_session_tracker.record_goal_complete(
            goal_id="g2", goal="Goal 2", status="failed",
            source="studio", duration_seconds=30.0,
            tasks_completed=0, tasks_failed=1, files=["b.py"],
        )
        temp_session_tracker.record_goal_complete(
            goal_id="g3", goal="Goal 3", status="completed",
            source="cli", duration_seconds=90.0,
            tasks_completed=3, tasks_failed=0, files=["c.py"],
        )

        summary = temp_session_tracker.get_summary()

        assert summary.goals_started == 3
        assert summary.goals_completed == 2
        assert summary.goals_failed == 1
        assert summary.source == "mixed"  # Both cli and studio

    def test_record_lines_changed(self, temp_session_tracker: SessionTracker) -> None:
        """record_lines_changed should update counters."""
        temp_session_tracker.record_lines_changed(added=100, removed=20)
        temp_session_tracker.record_lines_changed(added=50, removed=10)

        summary = temp_session_tracker.get_summary()

        assert summary.lines_added == 150
        assert summary.lines_removed == 30

    def test_record_learning(self, temp_session_tracker: SessionTracker) -> None:
        """record_learning should increment counter."""
        temp_session_tracker.record_learning()
        temp_session_tracker.record_learning()

        summary = temp_session_tracker.get_summary()

        assert summary.learnings_added == 2

    def test_compute_top_files(self, temp_session_tracker: SessionTracker) -> None:
        """get_summary should compute top files correctly."""
        # Touch same file multiple times
        for i in range(5):
            temp_session_tracker.record_goal_complete(
                goal_id=f"g{i}", goal=f"Goal {i}", status="completed",
                source="cli", duration_seconds=10.0,
                tasks_completed=1, tasks_failed=0,
                files=["common.py", f"unique{i}.py"],
            )

        summary = temp_session_tracker.get_summary()

        # common.py should be first with 5 edits
        assert summary.top_files[0] == ("common.py", 5)

    def test_save_and_load(self, tmp_path: Path) -> None:
        """SessionTracker should save and load state."""
        tracker = SessionTracker(base_path=tmp_path / "sessions")
        tracker.record_goal_complete(
            goal_id="g1", goal="Test goal", status="completed",
            source="cli", duration_seconds=100.0,
            tasks_completed=2, tasks_failed=0, files=["test.py"],
        )
        tracker.record_learning()

        # Save
        path = tracker.save()
        assert path.exists()

        # Load
        loaded = SessionTracker.load(path)
        summary = loaded.get_summary()

        assert summary.goals_completed == 1
        assert summary.learnings_added == 1

    def test_list_recent(self, tmp_path: Path) -> None:
        """list_recent should return session files."""
        sessions_dir = tmp_path / "sessions"

        # Create multiple sessions
        for i in range(3):
            tracker = SessionTracker(base_path=sessions_dir)
            tracker.record_goal_complete(
                goal_id=f"g{i}", goal=f"Goal {i}", status="completed",
                source="cli", duration_seconds=10.0,
                tasks_completed=1, tasks_failed=0, files=[],
            )
            tracker.save()

        recent = SessionTracker.list_recent(base_path=sessions_dir, limit=10)

        assert len(recent) == 3


class TestSessionSummary:
    """Tests for SessionSummary dataclass."""

    def test_session_summary_to_dict(self) -> None:
        """SessionSummary should serialize to dict."""
        summary = SessionSummary(
            session_id="sess123",
            started_at=datetime.now(UTC),
            source="cli",
            goals_started=5,
            goals_completed=4,
            goals_failed=1,
            files_modified=10,
            lines_added=500,
            lines_removed=100,
        )

        data = summary.to_dict()

        assert data["session_id"] == "sess123"
        assert data["goals_completed"] == 4
        assert data["lines_added"] == 500

    def test_session_summary_from_dict(self) -> None:
        """SessionSummary should deserialize from dict."""
        data = {
            "session_id": "sess456",
            "started_at": "2026-01-24T10:00:00",
            "ended_at": None,
            "source": "studio",
            "goals_started": 3,
            "goals_completed": 3,
            "goals_failed": 0,
            "files_created": 2,
            "files_modified": 5,
            "files_deleted": 0,
            "lines_added": 200,
            "lines_removed": 50,
            "learnings_added": 1,
            "dead_ends_recorded": 0,
            "total_duration_seconds": 3600.0,
            "planning_seconds": 720.0,
            "execution_seconds": 2880.0,
            "waiting_seconds": 0.0,
            "top_files": [("main.py", 3)],
            "goals": [],
        }

        summary = SessionSummary.from_dict(data)

        assert summary.session_id == "sess456"
        assert summary.goals_completed == 3


# =============================================================================
# Debug Dump Tests
# =============================================================================


class TestDebugDumpSanitization:
    """Tests for debug dump sanitization."""

    def test_sanitize_api_keys(self) -> None:
        """Sanitization should remove API keys."""
        from sunwell.cli.debug_cmd import _sanitize

        content = """
        ANTHROPIC_API_KEY=sk-ant-api123secret456
        OPENAI_API_KEY=sk-proj-xyz789
        some_config: value
        """

        sanitized, found = _sanitize(content)

        assert "sk-ant-api123secret456" not in sanitized
        assert "sk-proj-xyz789" not in sanitized
        assert "[REDACTED]" in sanitized
        assert "some_config: value" in sanitized
        assert len(found) > 0

    def test_sanitize_bearer_tokens(self) -> None:
        """Sanitization should remove Bearer tokens."""
        from sunwell.cli.debug_cmd import _sanitize

        content = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'

        sanitized, found = _sanitize(content)

        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
        assert "Bearer token" in found

    def test_sanitize_passwords(self) -> None:
        """Sanitization should remove passwords."""
        from sunwell.cli.debug_cmd import _sanitize

        content = """
        password: supersecret123
        secret_key: myapisecret
        """

        sanitized, found = _sanitize(content)

        assert "supersecret123" not in sanitized
        assert "myapisecret" not in sanitized

    def test_sanitize_preserves_normal_content(self) -> None:
        """Sanitization should preserve non-sensitive content."""
        from sunwell.cli.debug_cmd import _sanitize

        content = """
        name: my-project
        version: 1.0.0
        description: A test project
        """

        sanitized, found = _sanitize(content)

        assert "name: my-project" in sanitized
        assert "version: 1.0.0" in sanitized
        assert len(found) == 0


class TestDebugDumpHelpers:
    """Tests for debug dump helper functions."""

    def test_read_jsonl(self, tmp_path: Path) -> None:
        """_read_jsonl should read JSONL with limit."""
        from sunwell.cli.debug_cmd import _read_jsonl

        jsonl_file = tmp_path / "events.jsonl"
        events = [{"event": f"event_{i}", "ts": "2026-01-24T10:00:00"} for i in range(10)]
        jsonl_file.write_text("\n".join(json.dumps(e) for e in events))

        # Read with limit
        result = _read_jsonl(jsonl_file, limit=5)

        assert len(result) == 5
        assert result[0]["event"] == "event_0"

    def test_read_jsonl_handles_invalid_lines(self, tmp_path: Path) -> None:
        """_read_jsonl should skip invalid JSON lines."""
        from sunwell.cli.debug_cmd import _read_jsonl

        jsonl_file = tmp_path / "events.jsonl"
        content = """{"event": "valid"}
        invalid json line
        {"event": "also_valid"}"""
        jsonl_file.write_text(content)

        result = _read_jsonl(jsonl_file, limit=10)

        assert len(result) == 2

    def test_collect_meta(self, tmp_path: Path) -> None:
        """_collect_meta should write system metadata."""
        from sunwell.cli.debug_cmd import _collect_meta

        meta_path = tmp_path / "meta.json"
        _collect_meta(meta_path)

        assert meta_path.exists()

        data = json.loads(meta_path.read_text())

        assert "sunwell_version" in data
        assert "python_version" in data
        assert "platform" in data
        assert "collected_at" in data
