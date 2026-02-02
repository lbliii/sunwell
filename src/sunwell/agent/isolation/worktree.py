"""Git worktree management for parallel task isolation.

Manages the lifecycle of git worktrees for parallel task execution:
- Create isolated worktrees for each parallel task
- Merge changes back to main workspace
- Clean up worktrees after completion

This provides isolation-by-construction: parallel tasks cannot conflict
because they operate on separate filesystem copies.
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.isolation.merge import MergeResult, MergeStrategy

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Worktree directory within .sunwell
WORKTREE_DIR = ".sunwell/worktrees"

# Branch prefix for parallel task branches
BRANCH_PREFIX = "sunwell/parallel"


@dataclass(frozen=True, slots=True)
class WorktreeInfo:
    """Information about a created worktree."""

    task_id: str
    """ID of the task this worktree is for."""

    path: Path
    """Absolute path to the worktree directory."""

    branch: str
    """Git branch name for this worktree."""

    created_at: datetime
    """When the worktree was created."""

    base_commit: str
    """Commit SHA the worktree was created from."""


@dataclass(slots=True)
class WorktreeManager:
    """Manages git worktree lifecycle for parallel task isolation.

    Creates isolated worktrees for parallel tasks, allowing each task
    to write files without conflicting with others. Changes are merged
    back to the main workspace after validation.

    Usage:
        manager = WorktreeManager(workspace_path)

        # Create worktrees for parallel tasks
        wt1 = await manager.create_worktree("task-1")
        wt2 = await manager.create_worktree("task-2")

        # Tasks execute in their isolated worktrees...

        # Merge changes back
        result1 = await manager.merge_worktree("task-1", MergeStrategy.FAST_FORWARD)
        result2 = await manager.merge_worktree("task-2", MergeStrategy.THREE_WAY)

        # Cleanup
        await manager.cleanup_all()
    """

    base_path: Path
    """Main workspace path (must be a git repository)."""

    worktrees: dict[str, WorktreeInfo] = field(default_factory=dict)
    """task_id -> worktree info mapping."""

    _base_branch: str | None = field(default=None, repr=False)
    """Cached name of the base branch."""

    _base_commit: str | None = field(default=None, repr=False)
    """Cached commit SHA of the base branch."""

    async def _run_git(self, args: list[str], cwd: Path | None = None) -> str:
        """Run a git command asynchronously.

        Args:
            args: Git command arguments
            cwd: Working directory (defaults to base_path)

        Returns:
            Command stdout as string

        Raises:
            subprocess.CalledProcessError: If git command fails
        """
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd or self.base_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode,
                ["git", *args],
                stdout,
                stderr,
            )

        return stdout.decode()

    async def _ensure_initialized(self) -> None:
        """Ensure base branch and commit are cached."""
        if self._base_branch is None:
            result = await self._run_git(["branch", "--show-current"])
            self._base_branch = result.strip() or "HEAD"

        if self._base_commit is None:
            result = await self._run_git(["rev-parse", "HEAD"])
            self._base_commit = result.strip()

    def _worktree_path(self, task_id: str) -> Path:
        """Get the path for a task's worktree."""
        return self.base_path / WORKTREE_DIR / task_id

    def _branch_name(self, task_id: str) -> str:
        """Get the branch name for a task."""
        return f"{BRANCH_PREFIX}/{task_id}"

    async def is_git_repo(self) -> bool:
        """Check if the workspace is a git repository."""
        try:
            await self._run_git(["rev-parse", "--git-dir"])
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    async def create_worktree(self, task_id: str) -> WorktreeInfo:
        """Create an isolated worktree for a task.

        Creates a new git worktree at .sunwell/worktrees/{task_id}/
        with a new branch sunwell/parallel/{task_id}.

        Args:
            task_id: Unique identifier for the task

        Returns:
            WorktreeInfo with path and branch details

        Raises:
            ValueError: If worktree already exists for this task
            subprocess.CalledProcessError: If git command fails
        """
        if task_id in self.worktrees:
            raise ValueError(f"Worktree already exists for task: {task_id}")

        await self._ensure_initialized()

        worktree_path = self._worktree_path(task_id)
        branch_name = self._branch_name(task_id)

        # Ensure parent directory exists
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "Creating worktree for task %s at %s (branch: %s)",
            task_id,
            worktree_path,
            branch_name,
        )

        # Create worktree with new branch
        # Use --no-checkout to speed up creation, then checkout
        # This is faster for large repos
        try:
            await self._run_git([
                "worktree", "add",
                "-b", branch_name,
                str(worktree_path),
                self._base_commit or "HEAD",
            ])
        except subprocess.CalledProcessError as e:
            # Branch might already exist from a previous run
            if b"already exists" in e.stderr:
                # Delete the branch and retry
                try:
                    await self._run_git(["branch", "-D", branch_name])
                except subprocess.CalledProcessError:
                    pass
                await self._run_git([
                    "worktree", "add",
                    "-b", branch_name,
                    str(worktree_path),
                    self._base_commit or "HEAD",
                ])
            else:
                raise

        info = WorktreeInfo(
            task_id=task_id,
            path=worktree_path,
            branch=branch_name,
            created_at=datetime.now(),
            base_commit=self._base_commit or "",
        )

        self.worktrees[task_id] = info

        logger.info(
            "Created worktree for task %s at %s",
            task_id,
            worktree_path,
        )

        return info

    async def get_modified_files(self, task_id: str) -> list[str]:
        """Get list of files modified in a worktree.

        Args:
            task_id: Task identifier

        Returns:
            List of modified file paths (relative to worktree root)

        Raises:
            KeyError: If no worktree exists for this task
        """
        if task_id not in self.worktrees:
            raise KeyError(f"No worktree for task: {task_id}")

        info = self.worktrees[task_id]

        # Get status of modified files
        result = await self._run_git(
            ["status", "--porcelain", "-uall"],
            cwd=info.path,
        )

        files = []
        for line in result.strip().split("\n"):
            if line:
                # Format: "XY filename" or "XY old -> new" for renames
                parts = line[3:].split(" -> ")
                files.append(parts[-1])

        return files

    async def commit_changes(self, task_id: str, message: str) -> str:
        """Commit all changes in a worktree.

        Args:
            task_id: Task identifier
            message: Commit message

        Returns:
            Commit SHA, or empty string if nothing to commit

        Raises:
            KeyError: If no worktree exists for this task
        """
        if task_id not in self.worktrees:
            raise KeyError(f"No worktree for task: {task_id}")

        info = self.worktrees[task_id]

        # Stage all changes
        await self._run_git(["add", "-A"], cwd=info.path)

        # Check if anything to commit
        status = await self._run_git(
            ["status", "--porcelain"],
            cwd=info.path,
        )
        if not status.strip():
            return ""

        # Commit
        await self._run_git(
            ["commit", "-m", message],
            cwd=info.path,
        )

        # Get commit SHA
        sha = await self._run_git(
            ["rev-parse", "HEAD"],
            cwd=info.path,
        )

        return sha.strip()

    async def merge_worktree(
        self,
        task_id: str,
        strategy: MergeStrategy = MergeStrategy.FAST_FORWARD,
    ) -> MergeResult:
        """Merge worktree changes back to main workspace.

        Args:
            task_id: Task identifier
            strategy: Merge strategy to use

        Returns:
            MergeResult with success status and details

        Raises:
            KeyError: If no worktree exists for this task
        """
        if task_id not in self.worktrees:
            raise KeyError(f"No worktree for task: {task_id}")

        info = self.worktrees[task_id]

        # Get list of modified files before merge
        modified_files = await self.get_modified_files(task_id)

        if not modified_files:
            return MergeResult(
                success=True,
                strategy_used=strategy,
                files_merged=(),
            )

        # Commit any uncommitted changes
        await self.commit_changes(task_id, f"[sunwell] Task {task_id} changes")

        logger.debug(
            "Merging worktree %s with strategy %s (%d files)",
            task_id,
            strategy.value,
            len(modified_files),
        )

        try:
            if strategy == MergeStrategy.FAST_FORWARD:
                await self._run_git(["merge", "--ff-only", info.branch])
            elif strategy == MergeStrategy.THREE_WAY:
                await self._run_git([
                    "merge",
                    "--no-edit",
                    "-m", f"Merge {task_id} changes",
                    info.branch,
                ])
            elif strategy == MergeStrategy.ABORT_ON_CONFLICT:
                # Try fast-forward first, then 3-way
                try:
                    await self._run_git(["merge", "--ff-only", info.branch])
                except subprocess.CalledProcessError:
                    await self._run_git([
                        "merge",
                        "--no-commit",
                        info.branch,
                    ])
                    # Check for conflicts
                    status = await self._run_git(["status", "--porcelain"])
                    if "UU" in status or "AA" in status or "DD" in status:
                        # Abort the merge
                        await self._run_git(["merge", "--abort"])
                        raise subprocess.CalledProcessError(
                            1, ["merge"], b"", b"Conflicts detected"
                        )
                    # Commit the merge
                    await self._run_git([
                        "commit",
                        "-m", f"Merge {task_id} changes",
                    ])

            logger.info(
                "Merged worktree %s: %d files",
                task_id,
                len(modified_files),
            )

            return MergeResult(
                success=True,
                strategy_used=strategy,
                files_merged=tuple(modified_files),
            )

        except subprocess.CalledProcessError as e:
            # Merge failed - likely conflicts
            logger.warning(
                "Merge failed for worktree %s: %s",
                task_id,
                e.stderr.decode() if e.stderr else str(e),
            )

            # Try to abort to clean up
            try:
                await self._run_git(["merge", "--abort"])
            except subprocess.CalledProcessError:
                pass

            return MergeResult(
                success=False,
                strategy_used=strategy,
                files_merged=(),
                conflicts=tuple(modified_files),
                error=e.stderr.decode() if e.stderr else str(e),
            )

    async def cleanup_worktree(self, task_id: str) -> None:
        """Remove a worktree and its branch.

        Args:
            task_id: Task identifier

        Raises:
            KeyError: If no worktree exists for this task
        """
        if task_id not in self.worktrees:
            raise KeyError(f"No worktree for task: {task_id}")

        info = self.worktrees[task_id]

        logger.debug("Cleaning up worktree for task %s", task_id)

        # Remove the worktree
        try:
            await self._run_git(["worktree", "remove", "--force", str(info.path)])
        except subprocess.CalledProcessError:
            # May fail if directory doesn't exist
            pass

        # Delete the branch
        try:
            await self._run_git(["branch", "-D", info.branch])
        except subprocess.CalledProcessError:
            # May fail if branch doesn't exist
            pass

        del self.worktrees[task_id]

        logger.info("Cleaned up worktree for task %s", task_id)

    async def cleanup_all(self) -> None:
        """Remove all managed worktrees."""
        task_ids = list(self.worktrees.keys())
        for task_id in task_ids:
            try:
                await self.cleanup_worktree(task_id)
            except Exception as e:
                logger.warning("Failed to cleanup worktree %s: %s", task_id, e)

    async def __aenter__(self) -> "WorktreeManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup all worktrees."""
        await self.cleanup_all()
