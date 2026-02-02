"""Tests for in-memory staging fallback."""

import pytest
import tempfile
from pathlib import Path

from sunwell.agent.isolation.fallback import (
    FallbackIsolation,
    StagedFile,
    StagingBuffer,
)
from sunwell.agent.isolation.merge import MergeStrategy


class TestStagedFile:
    """Tests for StagedFile dataclass."""

    def test_create_computes_checksum(self) -> None:
        """StagedFile.create should compute SHA-256 checksum."""
        content = "def hello(): pass"
        staged = StagedFile.create("test.py", content, "task-1")

        assert staged.path == "test.py"
        assert staged.content == content
        assert staged.task_id == "task-1"
        assert len(staged.checksum) == 64  # SHA-256 hex length
        assert staged.staged_at is not None

    def test_same_content_same_checksum(self) -> None:
        """Same content should produce same checksum."""
        content = "x = 1"
        s1 = StagedFile.create("a.py", content, "task-1")
        s2 = StagedFile.create("b.py", content, "task-2")
        assert s1.checksum == s2.checksum

    def test_different_content_different_checksum(self) -> None:
        """Different content should produce different checksum."""
        s1 = StagedFile.create("test.py", "x = 1", "task-1")
        s2 = StagedFile.create("test.py", "x = 2", "task-1")
        assert s1.checksum != s2.checksum


class TestStagingBuffer:
    """Tests for StagingBuffer."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace."""
        return tmp_path

    def test_stage_file(self, workspace: Path) -> None:
        """Staging a file should store it in the buffer."""
        buffer = StagingBuffer(workspace=workspace)
        staged = buffer.stage("test.py", "print('hello')", "task-1")

        assert staged.path == "test.py"
        assert buffer.file_count == 1
        assert "task-1" in buffer.task_ids

    def test_stage_same_task_update(self, workspace: Path) -> None:
        """Same task can re-stage a file (update)."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("test.py", "v1", "task-1")
        buffer.stage("test.py", "v2", "task-1")

        assert buffer.file_count == 1
        assert buffer.get_staged("test.py").content == "v2"

    def test_stage_different_task_conflict(self, workspace: Path) -> None:
        """Different task staging same path should raise."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("test.py", "content", "task-1")

        with pytest.raises(ValueError, match="Path conflict"):
            buffer.stage("test.py", "other", "task-2")

    def test_unstage(self, workspace: Path) -> None:
        """Unstaging should remove file from buffer."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("test.py", "content", "task-1")

        removed = buffer.unstage("test.py")
        assert removed is not None
        assert removed.path == "test.py"
        assert buffer.file_count == 0

    def test_unstage_missing(self, workspace: Path) -> None:
        """Unstaging non-existent file should return None."""
        buffer = StagingBuffer(workspace=workspace)
        assert buffer.unstage("missing.py") is None

    def test_get_staged(self, workspace: Path) -> None:
        """get_staged should return the file or None."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("test.py", "content", "task-1")

        assert buffer.get_staged("test.py") is not None
        assert buffer.get_staged("missing.py") is None

    def test_get_all_staged(self, workspace: Path) -> None:
        """get_all_staged should return a copy of all files."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("a.py", "a", "task-1")
        buffer.stage("b.py", "b", "task-2")

        all_staged = buffer.get_all_staged()
        assert len(all_staged) == 2
        assert "a.py" in all_staged
        assert "b.py" in all_staged

    def test_get_task_files(self, workspace: Path) -> None:
        """get_task_files should filter by task ID."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("a.py", "a", "task-1")
        buffer.stage("b.py", "b", "task-1")
        buffer.stage("c.py", "c", "task-2")

        task1_files = buffer.get_task_files("task-1")
        assert len(task1_files) == 2
        assert "a.py" in task1_files
        assert "b.py" in task1_files
        assert "c.py" not in task1_files

    def test_validate_good_content(self, workspace: Path) -> None:
        """Validation should pass for good content."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("test.py", "def hello(): pass", "task-1")

        issues = buffer.validate()
        assert len(issues) == 0

    def test_validate_bad_content(self, workspace: Path) -> None:
        """Validation should catch tool output contamination."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("good.py", "x = 1", "task-1")
        buffer.stage("bad.py", "✓ Wrote file.py (100 bytes)", "task-2")

        issues = buffer.validate()
        assert len(issues) == 1
        assert "bad.py" in issues

    def test_commit_writes_files(self, workspace: Path) -> None:
        """Commit should write all staged files to disk."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("src/test.py", "print('hello')", "task-1")
        buffer.stage("src/utils/helper.py", "x = 1", "task-2")

        count, paths = buffer.commit()

        assert count == 2
        assert (workspace / "src/test.py").exists()
        assert (workspace / "src/test.py").read_text() == "print('hello')"
        assert (workspace / "src/utils/helper.py").exists()
        assert buffer.file_count == 0  # Buffer cleared after commit

    def test_clear_all(self, workspace: Path) -> None:
        """clear() without task_id should clear all files."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("a.py", "a", "task-1")
        buffer.stage("b.py", "b", "task-2")

        count = buffer.clear()
        assert count == 2
        assert buffer.file_count == 0

    def test_clear_by_task(self, workspace: Path) -> None:
        """clear(task_id) should only clear that task's files."""
        buffer = StagingBuffer(workspace=workspace)
        buffer.stage("a.py", "a", "task-1")
        buffer.stage("b.py", "b", "task-2")

        count = buffer.clear("task-1")
        assert count == 1
        assert buffer.file_count == 1
        assert buffer.get_staged("b.py") is not None


class TestFallbackIsolation:
    """Tests for FallbackIsolation manager."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace."""
        return tmp_path

    def test_stage_file(self, workspace: Path) -> None:
        """stage_file should add to internal buffer."""
        manager = FallbackIsolation(workspace=workspace)
        staged = manager.stage_file("task-1", "test.py", "content")

        assert staged.task_id == "task-1"
        assert staged.path == "test.py"

    def test_get_task_workspace_returns_shared(self, workspace: Path) -> None:
        """get_task_workspace should return shared workspace (no isolation)."""
        manager = FallbackIsolation(workspace=workspace)

        assert manager.get_task_workspace("task-1") == workspace
        assert manager.get_task_workspace("task-2") == workspace

    @pytest.mark.asyncio
    async def test_merge_task_writes_files(self, workspace: Path) -> None:
        """merge_task should validate and commit files."""
        manager = FallbackIsolation(workspace=workspace)
        manager.stage_file("task-1", "test.py", "def hello(): pass")

        result = await manager.merge_task("task-1")

        assert result.success
        assert "test.py" in result.files_merged
        assert (workspace / "test.py").exists()

    @pytest.mark.asyncio
    async def test_merge_task_validates_content(self, workspace: Path) -> None:
        """merge_task should reject invalid content."""
        manager = FallbackIsolation(workspace=workspace)
        manager.stage_file("task-1", "test.py", "✓ Wrote something")

        result = await manager.merge_task("task-1")

        assert not result.success
        assert "test.py" in result.conflicts
        assert not (workspace / "test.py").exists()

    @pytest.mark.asyncio
    async def test_merge_task_empty(self, workspace: Path) -> None:
        """merge_task with no files should succeed."""
        manager = FallbackIsolation(workspace=workspace)
        result = await manager.merge_task("task-1")

        assert result.success
        assert len(result.files_merged) == 0

    def test_cleanup(self, workspace: Path) -> None:
        """cleanup should clear staged files."""
        manager = FallbackIsolation(workspace=workspace)
        manager.stage_file("task-1", "a.py", "a")
        manager.stage_file("task-2", "b.py", "b")

        manager.cleanup("task-1")
        assert manager._buffer.file_count == 1

        manager.cleanup()
        assert manager._buffer.file_count == 0
