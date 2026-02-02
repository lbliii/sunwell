"""In-memory staging fallback for non-git workspaces.

Provides a simpler isolation mechanism for workspaces that aren't git repositories.
Files are staged in memory and written atomically after validation.

This is the fallback when git worktrees aren't available.
"""

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sunwell.agent.isolation.merge import MergeResult, MergeStrategy
from sunwell.agent.isolation.validators import (
    ContentSanityValidator,
    ValidationResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StagedFile:
    """A file staged for writing.

    Attributes:
        path: Relative path from workspace root
        content: File content to write
        task_id: ID of the task that staged this file
        checksum: SHA-256 hash of content (for dedup)
        staged_at: When the file was staged
    """

    path: str
    """Relative path from workspace root."""

    content: str
    """File content to write."""

    task_id: str
    """ID of the task that staged this file."""

    checksum: str
    """SHA-256 hash of content (for dedup)."""

    staged_at: datetime
    """When the file was staged."""

    @classmethod
    def create(cls, path: str, content: str, task_id: str) -> "StagedFile":
        """Create a staged file with computed checksum."""
        checksum = hashlib.sha256(content.encode()).hexdigest()
        return cls(
            path=path,
            content=content,
            task_id=task_id,
            checksum=checksum,
            staged_at=datetime.now(),
        )


@dataclass(slots=True)
class StagingBuffer:
    """Thread-safe buffer for staging files before commit.

    Collects files from parallel tasks and allows validation and
    atomic commit. This is the fallback isolation mechanism for
    non-git workspaces.

    Usage:
        buffer = StagingBuffer(workspace_path)

        # Stage files from parallel tasks
        buffer.stage("src/utils.py", content, "task-1")
        buffer.stage("src/models.py", content, "task-2")

        # Validate all staged files
        issues = buffer.validate()
        if not issues:
            # Commit all files atomically
            buffer.commit()
        else:
            # Handle validation issues
            buffer.clear()
    """

    workspace: Path
    """Workspace root path."""

    _files: dict[str, StagedFile] = field(default_factory=dict)
    """path -> StagedFile mapping."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for thread-safe access."""

    _validator: ContentSanityValidator = field(
        default_factory=ContentSanityValidator
    )
    """Content validator for staged files."""

    def stage(self, path: str, content: str, task_id: str) -> StagedFile:
        """Stage a file for writing.

        Args:
            path: Relative path from workspace root
            content: File content
            task_id: ID of the task staging this file

        Returns:
            The staged file

        Raises:
            ValueError: If a different task already staged this path
        """
        staged = StagedFile.create(path, content, task_id)

        with self._lock:
            if path in self._files:
                existing = self._files[path]
                if existing.task_id != task_id:
                    raise ValueError(
                        f"Path conflict: {path} already staged by task "
                        f"{existing.task_id}, attempted by {task_id}"
                    )
                # Same task re-staging - allow (might be an update)

            self._files[path] = staged

        logger.debug(
            "Staged file %s from task %s (%d bytes)",
            path,
            task_id,
            len(content),
        )

        return staged

    def unstage(self, path: str) -> StagedFile | None:
        """Remove a file from staging.

        Args:
            path: Relative path to unstage

        Returns:
            The removed StagedFile, or None if not found
        """
        with self._lock:
            return self._files.pop(path, None)

    def get_staged(self, path: str) -> StagedFile | None:
        """Get a staged file by path.

        Args:
            path: Relative path to look up

        Returns:
            The StagedFile, or None if not found
        """
        with self._lock:
            return self._files.get(path)

    def get_all_staged(self) -> dict[str, StagedFile]:
        """Get all staged files.

        Returns:
            Copy of the staged files dict
        """
        with self._lock:
            return dict(self._files)

    def get_task_files(self, task_id: str) -> dict[str, StagedFile]:
        """Get all files staged by a specific task.

        Args:
            task_id: Task identifier

        Returns:
            Dict of path -> StagedFile for this task
        """
        with self._lock:
            return {
                path: staged
                for path, staged in self._files.items()
                if staged.task_id == task_id
            }

    def validate(self) -> dict[str, ValidationResult]:
        """Validate all staged files.

        Returns:
            Dict of path -> ValidationResult for files that failed validation
        """
        with self._lock:
            files = dict(self._files)

        issues: dict[str, ValidationResult] = {}
        for path, staged in files.items():
            result = self._validator.validate(staged.content, path)
            if not result.valid:
                issues[path] = result

        return issues

    def commit(self) -> tuple[int, list[str]]:
        """Write all staged files to disk.

        Writes files atomically - if any write fails, the operation
        is aborted and already-written files are left in place.

        Returns:
            Tuple of (files_written, paths of files written)

        Raises:
            OSError: If any file write fails
        """
        with self._lock:
            files = dict(self._files)

        written: list[str] = []

        for path, staged in files.items():
            full_path = self.workspace / path

            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            full_path.write_text(staged.content, encoding="utf-8")
            written.append(path)

            logger.debug(
                "Committed file %s (%d bytes)",
                path,
                len(staged.content),
            )

        # Clear the buffer after successful commit
        with self._lock:
            for path in written:
                self._files.pop(path, None)

        logger.info("Committed %d staged files", len(written))

        return len(written), written

    def clear(self, task_id: str | None = None) -> int:
        """Clear staged files.

        Args:
            task_id: If provided, only clear files from this task.
                    If None, clear all files.

        Returns:
            Number of files cleared
        """
        with self._lock:
            if task_id is None:
                count = len(self._files)
                self._files.clear()
            else:
                to_remove = [
                    path
                    for path, staged in self._files.items()
                    if staged.task_id == task_id
                ]
                for path in to_remove:
                    del self._files[path]
                count = len(to_remove)

        return count

    @property
    def file_count(self) -> int:
        """Number of files currently staged."""
        with self._lock:
            return len(self._files)

    @property
    def task_ids(self) -> set[str]:
        """Set of task IDs with staged files."""
        with self._lock:
            return {staged.task_id for staged in self._files.values()}


@dataclass(slots=True)
class FallbackIsolation:
    """Fallback isolation manager using in-memory staging.

    Provides a similar interface to WorktreeManager but uses in-memory
    staging instead of git worktrees. Each task gets its own "virtual"
    workspace view through the staging buffer.

    Usage:
        manager = FallbackIsolation(workspace_path)

        # Tasks stage files (no isolation - shared buffer)
        manager.stage_file("task-1", "src/utils.py", content)
        manager.stage_file("task-2", "src/models.py", content)

        # Validate and commit
        result = await manager.merge_task("task-1")
        result = await manager.merge_task("task-2")

        # Cleanup
        manager.cleanup()
    """

    workspace: Path
    """Workspace root path."""

    _buffer: StagingBuffer = field(init=False)
    """Internal staging buffer."""

    def __post_init__(self) -> None:
        """Initialize the staging buffer."""
        self._buffer = StagingBuffer(workspace=self.workspace)

    def stage_file(self, task_id: str, path: str, content: str) -> StagedFile:
        """Stage a file for a task.

        Args:
            task_id: Task identifier
            path: Relative file path
            content: File content

        Returns:
            The staged file
        """
        return self._buffer.stage(path, content, task_id)

    def get_task_workspace(self, task_id: str) -> Path:
        """Get the workspace path for a task.

        In the fallback mode, all tasks share the same workspace.
        This method exists for interface compatibility with WorktreeManager.

        Args:
            task_id: Task identifier

        Returns:
            The shared workspace path
        """
        return self.workspace

    async def merge_task(
        self,
        task_id: str,
        strategy: MergeStrategy = MergeStrategy.FAST_FORWARD,
    ) -> MergeResult:
        """Validate and commit files for a task.

        Args:
            task_id: Task identifier
            strategy: Merge strategy (ignored in fallback mode)

        Returns:
            MergeResult with commit details
        """
        task_files = self._buffer.get_task_files(task_id)

        if not task_files:
            return MergeResult(
                success=True,
                strategy_used=strategy,
                files_merged=(),
            )

        # Validate content
        issues: dict[str, ValidationResult] = {}
        for path, staged in task_files.items():
            result = self._buffer._validator.validate(staged.content, path)
            if not result.valid:
                issues[path] = result

        if issues:
            logger.warning(
                "Validation failed for task %s: %d issues",
                task_id,
                len(issues),
            )
            return MergeResult(
                success=False,
                strategy_used=strategy,
                files_merged=(),
                conflicts=tuple(issues.keys()),
                error="; ".join(
                    f"{path}: {result.message}"
                    for path, result in issues.items()
                ),
            )

        # Write files
        written: list[str] = []
        for path, staged in task_files.items():
            full_path = self.workspace / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(staged.content, encoding="utf-8")
            written.append(path)
            self._buffer.unstage(path)

        logger.info(
            "Committed %d files for task %s",
            len(written),
            task_id,
        )

        return MergeResult(
            success=True,
            strategy_used=strategy,
            files_merged=tuple(written),
        )

    def cleanup(self, task_id: str | None = None) -> None:
        """Clear staged files.

        Args:
            task_id: If provided, only clear files from this task
        """
        self._buffer.clear(task_id)
