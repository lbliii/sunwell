"""Tests for sunwell.agent.recovery package.

Tests cover:
- RecoverySummary.total includes all artifact states (bug fix)
- RecoveryManager.list_pending counts all states
- RecoveryState properties
- Serialization round-trips
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.agent.recovery import (
    ArtifactStatus,
    RecoveryArtifact,
    RecoveryManager,
    RecoveryState,
    RecoverySummary,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_recovery_dir(tmp_path: Path) -> Path:
    """Create a temporary recovery directory."""
    recovery_dir = tmp_path / "recovery"
    recovery_dir.mkdir()
    return recovery_dir


@pytest.fixture
def sample_recovery_state() -> RecoveryState:
    """Create a sample recovery state with all artifact statuses."""
    return RecoveryState(
        goal="Test goal",
        goal_hash="abc123",
        run_id="run-1",
        artifacts={
            "a.py": RecoveryArtifact(
                path=Path("a.py"),
                content="# passed",
                status=ArtifactStatus.PASSED,
            ),
            "b.py": RecoveryArtifact(
                path=Path("b.py"),
                content="# failed",
                status=ArtifactStatus.FAILED,
                errors=("syntax error",),
            ),
            "c.py": RecoveryArtifact(
                path=Path("c.py"),
                content="# waiting",
                status=ArtifactStatus.WAITING,
            ),
            "d.py": RecoveryArtifact(
                path=Path("d.py"),
                content="# fixed",
                status=ArtifactStatus.FIXED,
            ),
            "e.py": RecoveryArtifact(
                path=Path("e.py"),
                content="# skipped",
                status=ArtifactStatus.SKIPPED,
            ),
        },
    )


# =============================================================================
# RecoverySummary Tests (Bug Fix Verification)
# =============================================================================


class TestRecoverySummaryTotal:
    """Tests for RecoverySummary.total property bug fix.

    Bug: total only summed passed + failed + waiting, missing fixed + skipped.
    Fix: Added fixed and skipped fields, updated total to include all 5 states.
    """

    def test_total_includes_all_five_states(self) -> None:
        """Verify total counts all artifact states."""
        summary = RecoverySummary(
            goal_hash="abc123",
            goal_preview="Test goal",
            run_id="run-1",
            passed=5,
            failed=3,
            waiting=2,
            fixed=4,
            skipped=1,
            created_at=datetime.now(),
        )

        assert summary.total == 15  # 5+3+2+4+1

    def test_total_with_zero_fixed_skipped(self) -> None:
        """Verify total works when fixed/skipped default to zero."""
        summary = RecoverySummary(
            goal_hash="abc123",
            goal_preview="Test goal",
            run_id="run-1",
            passed=5,
            failed=3,
            waiting=2,
            created_at=datetime.now(),
        )

        assert summary.fixed == 0
        assert summary.skipped == 0
        assert summary.total == 10  # 5+3+2+0+0

    def test_total_with_only_fixed(self) -> None:
        """Verify total works when only fixed artifacts exist."""
        summary = RecoverySummary(
            goal_hash="abc123",
            goal_preview="Test goal",
            run_id="run-1",
            passed=0,
            failed=0,
            waiting=0,
            fixed=5,
            skipped=0,
            created_at=datetime.now(),
        )

        assert summary.total == 5

    def test_total_with_only_skipped(self) -> None:
        """Verify total works when only skipped artifacts exist."""
        summary = RecoverySummary(
            goal_hash="abc123",
            goal_preview="Test goal",
            run_id="run-1",
            passed=0,
            failed=0,
            waiting=0,
            fixed=0,
            skipped=3,
            created_at=datetime.now(),
        )

        assert summary.total == 3


class TestRecoverySummaryDefaults:
    """Tests for RecoverySummary default values."""

    def test_fixed_defaults_to_zero(self) -> None:
        """fixed field should default to 0."""
        summary = RecoverySummary(
            goal_hash="x",
            goal_preview="y",
            run_id="z",
            passed=1,
            failed=1,
            waiting=1,
        )
        assert summary.fixed == 0

    def test_skipped_defaults_to_zero(self) -> None:
        """skipped field should default to 0."""
        summary = RecoverySummary(
            goal_hash="x",
            goal_preview="y",
            run_id="z",
            passed=1,
            failed=1,
            waiting=1,
        )
        assert summary.skipped == 0

    def test_created_at_defaults_to_now(self) -> None:
        """created_at should default to current time."""
        before = datetime.now()
        summary = RecoverySummary(
            goal_hash="x",
            goal_preview="y",
            run_id="z",
            passed=1,
            failed=1,
            waiting=1,
        )
        after = datetime.now()

        assert before <= summary.created_at <= after


# =============================================================================
# RecoveryManager Tests
# =============================================================================


class TestRecoveryManagerListPending:
    """Tests for RecoveryManager.list_pending() counting all states."""

    def test_counts_all_artifact_states(self, temp_recovery_dir: Path) -> None:
        """Verify list_pending counts fixed and skipped artifacts."""
        manager = RecoveryManager(temp_recovery_dir)

        # Create a recovery file with all status types
        recovery_file = temp_recovery_dir / "test123.json"
        recovery_file.write_text(
            json.dumps({
                "goal_hash": "test123",
                "goal": "Test goal",
                "run_id": "run-1",
                "artifacts": {
                    "a.py": {
                        "status": "passed",
                        "path": "a.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    },
                    "b.py": {
                        "status": "failed",
                        "path": "b.py",
                        "content": "",
                        "errors": ["error"],
                        "depends_on": [],
                    },
                    "c.py": {
                        "status": "waiting",
                        "path": "c.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    },
                    "d.py": {
                        "status": "fixed",
                        "path": "d.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    },
                    "e.py": {
                        "status": "skipped",
                        "path": "e.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    },
                },
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            })
        )

        summaries = manager.list_pending()
        assert len(summaries) == 1

        s = summaries[0]
        assert s.passed == 1
        assert s.failed == 1
        assert s.waiting == 1
        assert s.fixed == 1
        assert s.skipped == 1
        assert s.total == 5

    def test_counts_multiple_of_same_status(self, temp_recovery_dir: Path) -> None:
        """Verify counting works with multiple artifacts of same status."""
        manager = RecoveryManager(temp_recovery_dir)

        recovery_file = temp_recovery_dir / "multi.json"
        recovery_file.write_text(
            json.dumps({
                "goal_hash": "multi",
                "goal": "Multiple artifacts",
                "run_id": "run-2",
                "artifacts": {
                    f"file{i}.py": {
                        "status": "fixed",
                        "path": f"file{i}.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    }
                    for i in range(5)
                },
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            })
        )

        summaries = manager.list_pending()
        assert len(summaries) == 1
        assert summaries[0].fixed == 5
        assert summaries[0].total == 5

    def test_ignores_unknown_status(self, temp_recovery_dir: Path) -> None:
        """Verify unknown statuses are ignored in counting."""
        manager = RecoveryManager(temp_recovery_dir)

        recovery_file = temp_recovery_dir / "unknown.json"
        recovery_file.write_text(
            json.dumps({
                "goal_hash": "unknown",
                "goal": "Unknown status",
                "run_id": "run-3",
                "artifacts": {
                    "a.py": {
                        "status": "passed",
                        "path": "a.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    },
                    "b.py": {
                        "status": "unknown_status",
                        "path": "b.py",
                        "content": "",
                        "errors": [],
                        "depends_on": [],
                    },
                },
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            })
        )

        summaries = manager.list_pending()
        assert len(summaries) == 1
        # Only counts known statuses
        assert summaries[0].passed == 1
        assert summaries[0].total == 1


# =============================================================================
# RecoveryState Tests
# =============================================================================


class TestRecoveryStateProperties:
    """Tests for RecoveryState property methods."""

    def test_passed_artifacts(self, sample_recovery_state: RecoveryState) -> None:
        """passed_artifacts returns only PASSED status."""
        passed = sample_recovery_state.passed_artifacts
        assert len(passed) == 1
        assert all(a.status == ArtifactStatus.PASSED for a in passed)

    def test_failed_artifacts(self, sample_recovery_state: RecoveryState) -> None:
        """failed_artifacts returns only FAILED status."""
        failed = sample_recovery_state.failed_artifacts
        assert len(failed) == 1
        assert all(a.status == ArtifactStatus.FAILED for a in failed)

    def test_waiting_artifacts(self, sample_recovery_state: RecoveryState) -> None:
        """waiting_artifacts returns only WAITING status."""
        waiting = sample_recovery_state.waiting_artifacts
        assert len(waiting) == 1
        assert all(a.status == ArtifactStatus.WAITING for a in waiting)

    def test_fixed_artifacts(self, sample_recovery_state: RecoveryState) -> None:
        """fixed_artifacts returns only FIXED status."""
        fixed = sample_recovery_state.fixed_artifacts
        assert len(fixed) == 1
        assert all(a.status == ArtifactStatus.FIXED for a in fixed)

    def test_recovery_possible_with_passed(
        self, sample_recovery_state: RecoveryState
    ) -> None:
        """recovery_possible is True when any artifacts passed."""
        assert sample_recovery_state.recovery_possible is True

    def test_recovery_possible_no_passed(self) -> None:
        """recovery_possible is False when no artifacts passed."""
        state = RecoveryState(
            goal="No passed",
            goal_hash="xyz",
            run_id="run",
            artifacts={
                "a.py": RecoveryArtifact(
                    path=Path("a.py"),
                    content="",
                    status=ArtifactStatus.FAILED,
                ),
            },
        )
        assert state.recovery_possible is False

    def test_is_resolved_all_resolved(self) -> None:
        """is_resolved is True when all artifacts are in resolved state."""
        state = RecoveryState(
            goal="All resolved",
            goal_hash="res",
            run_id="run",
            artifacts={
                "a.py": RecoveryArtifact(
                    path=Path("a.py"),
                    content="",
                    status=ArtifactStatus.PASSED,
                ),
                "b.py": RecoveryArtifact(
                    path=Path("b.py"),
                    content="",
                    status=ArtifactStatus.FIXED,
                ),
                "c.py": RecoveryArtifact(
                    path=Path("c.py"),
                    content="",
                    status=ArtifactStatus.SKIPPED,
                ),
            },
        )
        assert state.is_resolved is True

    def test_is_resolved_with_failed(
        self, sample_recovery_state: RecoveryState
    ) -> None:
        """is_resolved is False when any artifact is failed/waiting."""
        assert sample_recovery_state.is_resolved is False

    def test_summary_format(self, sample_recovery_state: RecoveryState) -> None:
        """summary property produces readable string."""
        summary = sample_recovery_state.summary
        assert "✅" in summary
        assert "⚠️" in summary
        assert "⏸️" in summary


class TestRecoveryStateMutations:
    """Tests for RecoveryState mutation methods."""

    def test_mark_fixed(self, sample_recovery_state: RecoveryState) -> None:
        """mark_fixed updates artifact status and content."""
        sample_recovery_state.mark_fixed("b.py", "# new content")

        artifact = sample_recovery_state.artifacts["b.py"]
        assert artifact.status == ArtifactStatus.FIXED
        assert artifact.content == "# new content"
        assert artifact.errors == ()  # Errors cleared

    def test_mark_fixed_updates_timestamp(
        self, sample_recovery_state: RecoveryState
    ) -> None:
        """mark_fixed updates updated_at timestamp."""
        original_time = sample_recovery_state.updated_at
        sample_recovery_state.mark_fixed("b.py", "# new")
        assert sample_recovery_state.updated_at >= original_time

    def test_mark_skipped(self, sample_recovery_state: RecoveryState) -> None:
        """mark_skipped updates artifact status."""
        sample_recovery_state.mark_skipped("b.py")

        artifact = sample_recovery_state.artifacts["b.py"]
        assert artifact.status == ArtifactStatus.SKIPPED

    def test_mark_nonexistent_path_is_noop(
        self, sample_recovery_state: RecoveryState
    ) -> None:
        """mark_fixed/skipped on nonexistent path is a no-op."""
        original_artifacts = dict(sample_recovery_state.artifacts)

        sample_recovery_state.mark_fixed("nonexistent.py", "content")
        sample_recovery_state.mark_skipped("also_nonexistent.py")

        # No changes
        assert sample_recovery_state.artifacts == original_artifacts


# =============================================================================
# RecoveryArtifact Tests
# =============================================================================


class TestRecoveryArtifact:
    """Tests for RecoveryArtifact dataclass."""

    def test_needs_review_for_failed(self) -> None:
        """needs_review is True only for FAILED status."""
        failed = RecoveryArtifact(
            path=Path("f.py"), content="", status=ArtifactStatus.FAILED
        )
        passed = RecoveryArtifact(
            path=Path("p.py"), content="", status=ArtifactStatus.PASSED
        )

        assert failed.needs_review is True
        assert passed.needs_review is False

    def test_is_resolved_states(self) -> None:
        """is_resolved is True for PASSED, FIXED, SKIPPED."""
        for status in [ArtifactStatus.PASSED, ArtifactStatus.FIXED, ArtifactStatus.SKIPPED]:
            artifact = RecoveryArtifact(path=Path("x.py"), content="", status=status)
            assert artifact.is_resolved is True

        for status in [ArtifactStatus.FAILED, ArtifactStatus.WAITING]:
            artifact = RecoveryArtifact(path=Path("x.py"), content="", status=status)
            assert artifact.is_resolved is False

    def test_with_status(self) -> None:
        """with_status returns new artifact with updated status."""
        original = RecoveryArtifact(
            path=Path("x.py"),
            content="code",
            status=ArtifactStatus.FAILED,
            errors=("error",),
        )

        updated = original.with_status(ArtifactStatus.SKIPPED)

        # Original unchanged (frozen)
        assert original.status == ArtifactStatus.FAILED
        # New artifact has new status
        assert updated.status == ArtifactStatus.SKIPPED
        # Other fields preserved
        assert updated.content == "code"
        assert updated.errors == ("error",)

    def test_with_content(self) -> None:
        """with_content returns new artifact with updated content and FIXED status."""
        original = RecoveryArtifact(
            path=Path("x.py"),
            content="old",
            status=ArtifactStatus.FAILED,
            errors=("error",),
        )

        updated = original.with_content("new")

        assert original.content == "old"  # Unchanged
        assert updated.content == "new"
        assert updated.status == ArtifactStatus.FIXED
        assert updated.errors == ()  # Errors cleared


# =============================================================================
# Serialization Round-Trip Tests
# =============================================================================


class TestRecoveryManagerSerialization:
    """Tests for save/load round-trips."""

    def test_save_and_load_state(self, temp_recovery_dir: Path) -> None:
        """State survives save/load round-trip."""
        manager = RecoveryManager(temp_recovery_dir)

        original = RecoveryState(
            goal="Test save/load",
            goal_hash="saveload",
            run_id="run-save",
            artifacts={
                "a.py": RecoveryArtifact(
                    path=Path("a.py"),
                    content="# content",
                    status=ArtifactStatus.PASSED,
                ),
                "b.py": RecoveryArtifact(
                    path=Path("b.py"),
                    content="# failed",
                    status=ArtifactStatus.FAILED,
                    errors=("error1", "error2"),
                ),
            },
            failure_reason="test failure",
        )

        manager.save(original)
        loaded = manager.load("saveload")

        assert loaded is not None
        assert loaded.goal == original.goal
        assert loaded.goal_hash == original.goal_hash
        assert loaded.run_id == original.run_id
        assert loaded.failure_reason == original.failure_reason
        assert len(loaded.artifacts) == 2
        assert loaded.artifacts["a.py"].status == ArtifactStatus.PASSED
        assert loaded.artifacts["b.py"].errors == ("error1", "error2")

    def test_load_nonexistent_returns_none(self, temp_recovery_dir: Path) -> None:
        """Loading nonexistent state returns None."""
        manager = RecoveryManager(temp_recovery_dir)
        result = manager.load("nonexistent")
        assert result is None

    def test_mark_resolved_moves_to_archive(self, temp_recovery_dir: Path) -> None:
        """mark_resolved moves file to archive directory."""
        manager = RecoveryManager(temp_recovery_dir)

        state = RecoveryState(
            goal="To archive",
            goal_hash="archive",
            run_id="run-arch",
        )
        manager.save(state)

        # File exists in main dir
        assert (temp_recovery_dir / "archive.json").exists()

        manager.mark_resolved("archive")

        # File moved to archive
        assert not (temp_recovery_dir / "archive.json").exists()
        assert (temp_recovery_dir / "archive" / "archive.json").exists()

    def test_delete_removes_file(self, temp_recovery_dir: Path) -> None:
        """delete removes state file."""
        manager = RecoveryManager(temp_recovery_dir)

        state = RecoveryState(
            goal="To delete",
            goal_hash="todelete",
            run_id="run-del",
        )
        manager.save(state)

        assert (temp_recovery_dir / "todelete.json").exists()

        manager.delete("todelete")

        assert not (temp_recovery_dir / "todelete.json").exists()
