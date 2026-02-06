"""Tests for WorktreeManager.

These tests require git to be installed and create temporary git repositories.
"""

import asyncio
import subprocess
import pytest
from pathlib import Path

from sunwell.agent.isolation.worktree import (
    WorktreeInfo,
    WorktreeManager,
    BRANCH_PREFIX,
)
from sunwell.agent.isolation.merge import MergeResult, MergeStrategy


def run_git(cwd: Path, args: list[str]) -> str:
    """Synchronous git command for test setup."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, ["init"])
    run_git(path, ["config", "user.email", "test@test.com"])
    run_git(path, ["config", "user.name", "Test"])

    # Create initial commit
    (path / "README.md").write_text("# Test Project")
    run_git(path, ["add", "README.md"])
    run_git(path, ["commit", "-m", "Initial commit"])


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    """Create a temporary git workspace."""
    workspace = tmp_path / "workspace"
    init_git_repo(workspace)
    return workspace


@pytest.fixture
def non_git_workspace(tmp_path: Path) -> Path:
    """Create a temporary non-git workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    return workspace


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_frozen(self) -> None:
        """WorktreeInfo should be frozen (immutable)."""
        from datetime import datetime

        info = WorktreeInfo(
            task_id="task-1",
            path=Path("/tmp/test"),
            branch="test-branch",
            created_at=datetime.now(),
            base_commit="abc123",
        )

        with pytest.raises(AttributeError):
            info.task_id = "other"


class TestWorktreeManager:
    """Tests for WorktreeManager."""

    @pytest.mark.asyncio
    async def test_is_git_repo_true(self, git_workspace: Path) -> None:
        """is_git_repo should return True for git repos."""
        manager = WorktreeManager(base_path=git_workspace)
        assert await manager.is_git_repo()

    @pytest.mark.asyncio
    async def test_is_git_repo_false(self, non_git_workspace: Path) -> None:
        """is_git_repo should return False for non-git directories."""
        manager = WorktreeManager(base_path=non_git_workspace)
        assert not await manager.is_git_repo()

    @pytest.mark.asyncio
    async def test_create_worktree(self, git_workspace: Path) -> None:
        """create_worktree should create isolated worktree."""
        manager = WorktreeManager(base_path=git_workspace)

        info = await manager.create_worktree("task-1")

        assert info.task_id == "task-1"
        assert info.path.exists()
        assert info.branch == f"{BRANCH_PREFIX}/task-1"
        from sunwell.knowledge.project.state import resolve_state_dir
        assert info.path == resolve_state_dir(git_workspace) / "worktrees" / "task-1"
        assert "task-1" in manager.worktrees

    @pytest.mark.asyncio
    async def test_create_worktree_duplicate_error(self, git_workspace: Path) -> None:
        """create_worktree should error on duplicate task_id."""
        manager = WorktreeManager(base_path=git_workspace)
        await manager.create_worktree("task-1")

        with pytest.raises(ValueError, match="already exists"):
            await manager.create_worktree("task-1")

    @pytest.mark.asyncio
    async def test_create_multiple_worktrees(self, git_workspace: Path) -> None:
        """Multiple worktrees should coexist."""
        manager = WorktreeManager(base_path=git_workspace)

        info1 = await manager.create_worktree("task-1")
        info2 = await manager.create_worktree("task-2")
        info3 = await manager.create_worktree("task-3")

        assert len(manager.worktrees) == 3
        assert info1.path != info2.path != info3.path
        assert info1.path.exists()
        assert info2.path.exists()
        assert info3.path.exists()

    @pytest.mark.asyncio
    async def test_worktree_isolation(self, git_workspace: Path) -> None:
        """Changes in worktrees should be isolated."""
        manager = WorktreeManager(base_path=git_workspace)

        info1 = await manager.create_worktree("task-1")
        info2 = await manager.create_worktree("task-2")

        # Write different files in each worktree
        (info1.path / "file1.py").write_text("x = 1")
        (info2.path / "file2.py").write_text("y = 2")

        # Files should not exist in other worktree
        assert not (info2.path / "file1.py").exists()
        assert not (info1.path / "file2.py").exists()

        # Files should not exist in main workspace
        assert not (git_workspace / "file1.py").exists()
        assert not (git_workspace / "file2.py").exists()

    @pytest.mark.asyncio
    async def test_get_modified_files(self, git_workspace: Path) -> None:
        """get_modified_files should list changes in worktree."""
        manager = WorktreeManager(base_path=git_workspace)
        info = await manager.create_worktree("task-1")

        # Create some files
        (info.path / "new_file.py").write_text("x = 1")
        (info.path / "src").mkdir()
        (info.path / "src" / "util.py").write_text("y = 2")

        files = await manager.get_modified_files("task-1")

        assert len(files) == 2
        assert "new_file.py" in files
        assert "src/util.py" in files

    @pytest.mark.asyncio
    async def test_commit_changes(self, git_workspace: Path) -> None:
        """commit_changes should commit worktree changes."""
        manager = WorktreeManager(base_path=git_workspace)
        info = await manager.create_worktree("task-1")

        (info.path / "test.py").write_text("x = 1")

        sha = await manager.commit_changes("task-1", "Add test.py")

        assert sha != ""
        assert len(sha) == 40  # Full SHA

    @pytest.mark.asyncio
    async def test_commit_changes_empty(self, git_workspace: Path) -> None:
        """commit_changes with no changes should return empty string."""
        manager = WorktreeManager(base_path=git_workspace)
        await manager.create_worktree("task-1")

        sha = await manager.commit_changes("task-1", "Empty commit")

        assert sha == ""

    @pytest.mark.asyncio
    async def test_merge_worktree_fast_forward(self, git_workspace: Path) -> None:
        """merge_worktree should fast-forward non-conflicting changes."""
        manager = WorktreeManager(base_path=git_workspace)
        info = await manager.create_worktree("task-1")

        # Create a file in worktree
        (info.path / "new_file.py").write_text("x = 1")

        result = await manager.merge_worktree("task-1", MergeStrategy.FAST_FORWARD)

        assert result.success
        assert result.strategy_used == MergeStrategy.FAST_FORWARD
        assert "new_file.py" in result.files_merged

        # File should now exist in main workspace
        assert (git_workspace / "new_file.py").exists()

    @pytest.mark.asyncio
    async def test_merge_worktree_no_changes(self, git_workspace: Path) -> None:
        """merge_worktree with no changes should succeed."""
        manager = WorktreeManager(base_path=git_workspace)
        await manager.create_worktree("task-1")

        result = await manager.merge_worktree("task-1")

        assert result.success
        assert len(result.files_merged) == 0

    @pytest.mark.asyncio
    async def test_cleanup_worktree(self, git_workspace: Path) -> None:
        """cleanup_worktree should remove worktree and branch."""
        manager = WorktreeManager(base_path=git_workspace)
        info = await manager.create_worktree("task-1")

        assert info.path.exists()
        assert "task-1" in manager.worktrees

        await manager.cleanup_worktree("task-1")

        assert not info.path.exists()
        assert "task-1" not in manager.worktrees

    @pytest.mark.asyncio
    async def test_cleanup_all(self, git_workspace: Path) -> None:
        """cleanup_all should remove all worktrees."""
        manager = WorktreeManager(base_path=git_workspace)

        info1 = await manager.create_worktree("task-1")
        info2 = await manager.create_worktree("task-2")

        await manager.cleanup_all()

        assert not info1.path.exists()
        assert not info2.path.exists()
        assert len(manager.worktrees) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, git_workspace: Path) -> None:
        """WorktreeManager as context manager should cleanup on exit."""
        async with WorktreeManager(base_path=git_workspace) as manager:
            info = await manager.create_worktree("task-1")
            path = info.path
            assert path.exists()

        # After context exit, worktree should be cleaned up
        assert not path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_missing_worktree_error(self, git_workspace: Path) -> None:
        """cleanup_worktree for non-existent task should raise."""
        manager = WorktreeManager(base_path=git_workspace)

        with pytest.raises(KeyError):
            await manager.cleanup_worktree("non-existent")


class TestMergeStrategy:
    """Tests for different merge strategies."""

    @pytest.mark.asyncio
    async def test_three_way_merge(self, git_workspace: Path) -> None:
        """THREE_WAY strategy should handle more complex merges."""
        manager = WorktreeManager(base_path=git_workspace)
        info = await manager.create_worktree("task-1")

        # Create file in worktree
        (info.path / "feature.py").write_text("def feature(): pass")

        result = await manager.merge_worktree("task-1", MergeStrategy.THREE_WAY)

        assert result.success
        assert result.strategy_used == MergeStrategy.THREE_WAY

    @pytest.mark.asyncio
    async def test_abort_on_conflict_no_conflict(self, git_workspace: Path) -> None:
        """ABORT_ON_CONFLICT with no conflicts should succeed."""
        manager = WorktreeManager(base_path=git_workspace)
        info = await manager.create_worktree("task-1")

        (info.path / "safe.py").write_text("x = 1")

        result = await manager.merge_worktree("task-1", MergeStrategy.ABORT_ON_CONFLICT)

        assert result.success

    @pytest.mark.asyncio
    async def test_merge_multiple_sequential(self, git_workspace: Path) -> None:
        """Multiple worktrees should merge sequentially.

        After the first merge, subsequent worktrees need THREE_WAY merge
        since their base is now behind HEAD.
        """
        manager = WorktreeManager(base_path=git_workspace)

        info1 = await manager.create_worktree("task-1")
        info2 = await manager.create_worktree("task-2")

        # Each creates different files
        (info1.path / "file1.py").write_text("x = 1")
        (info2.path / "file2.py").write_text("y = 2")

        # Merge first worktree - can use fast-forward
        result1 = await manager.merge_worktree("task-1", MergeStrategy.FAST_FORWARD)
        assert result1.success

        # Merge second worktree - needs THREE_WAY since base is now behind
        result2 = await manager.merge_worktree("task-2", MergeStrategy.THREE_WAY)
        assert result2.success

        # Both files should exist in main workspace
        assert (git_workspace / "file1.py").exists()
        assert (git_workspace / "file2.py").exists()
