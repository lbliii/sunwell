"""Workspace lifecycle management (RFC-141).

Deletion, edit, and cleanup operations for workspaces with proper cascade behavior.
"""

import logging
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class DeletionMode(Enum):
    """Workspace deletion mode."""

    UNREGISTER = "unregister"
    """Remove from registry, keep all files."""

    PURGE = "purge"
    """Remove from registry and delete .sunwell/ directory."""

    FULL = "full"
    """Remove from registry and delete entire workspace directory."""


@dataclass(frozen=True, slots=True)
class DeleteResult:
    """Result of a workspace deletion operation."""

    success: bool
    """Whether the operation completed successfully."""

    mode: DeletionMode
    """The deletion mode used."""

    workspace_id: str
    """The workspace ID that was deleted."""

    workspace_path: Path
    """The workspace path that was targeted."""

    deleted_items: tuple[str, ...]
    """List of items that were deleted."""

    failed_items: tuple[str, ...]
    """List of items that failed to delete."""

    runs_deleted: int
    """Number of runs deleted (if delete_runs=True)."""

    runs_orphaned: int
    """Number of runs marked as orphaned."""

    was_current: bool
    """Whether this was the current workspace."""

    error: str | None = None
    """Error message if operation failed."""


@dataclass(frozen=True, slots=True)
class PurgeResult:
    """Result of a workspace purge operation."""

    success: bool
    """Whether the operation completed successfully."""

    workspace_id: str
    """The workspace ID that was purged."""

    workspace_path: Path
    """The workspace path that was targeted."""

    deleted_dirs: tuple[str, ...]
    """List of directories that were deleted."""

    deleted_files: tuple[str, ...]
    """List of files that were deleted."""

    failed_items: tuple[str, ...]
    """List of items that failed to delete."""

    runs_deleted: int
    """Number of runs deleted."""

    was_current: bool
    """Whether this was the current workspace."""

    error: str | None = None
    """Error message if operation failed."""


@dataclass(frozen=True, slots=True)
class RenameResult:
    """Result of a workspace rename operation."""

    success: bool
    """Whether the operation completed successfully."""

    old_id: str
    """The original workspace ID."""

    new_id: str
    """The new workspace ID."""

    runs_updated: int
    """Number of runs updated with new ID."""

    error: str | None = None
    """Error message if operation failed."""


@dataclass(frozen=True, slots=True)
class MoveResult:
    """Result of a workspace move operation."""

    success: bool
    """Whether the operation completed successfully."""

    workspace_id: str
    """The workspace ID."""

    old_path: Path
    """The original workspace path."""

    new_path: Path
    """The new workspace path."""

    error: str | None = None
    """Error message if operation failed."""


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Result of orphaned data cleanup."""

    dry_run: bool
    """Whether this was a dry run (no actual deletions)."""

    orphaned_runs: tuple[str, ...]
    """Run IDs that are orphaned (workspace deleted/missing)."""

    invalid_registrations: tuple[str, ...]
    """Workspace IDs in registry with missing paths."""

    cleaned_runs: int
    """Number of runs cleaned up."""

    cleaned_registrations: int
    """Number of invalid registrations removed."""


@dataclass(slots=True)
class WorkspaceLifecycle:
    """Handles workspace lifecycle operations.

    Provides deletion, edit, and cleanup with proper cascade behavior.
    """

    _sunwell_dir: Path = field(default_factory=lambda: Path.home() / ".sunwell")

    def get_runs_dir(self) -> Path:
        """Get the global runs directory."""
        return self._sunwell_dir / "runs"

    def get_sunwell_data_dir(self, workspace_path: Path) -> Path:
        """Get the .sunwell directory for a workspace."""
        return workspace_path / ".sunwell"

    def list_workspace_runs(self, workspace_id: str) -> list[str]:
        """List all run IDs for a workspace.

        Args:
            workspace_id: The workspace ID to find runs for.

        Returns:
            List of run IDs belonging to this workspace.
        """
        import json

        runs_dir = self.get_runs_dir()
        if not runs_dir.exists():
            return []

        run_ids: list[str] = []
        for run_file in runs_dir.glob("*.json"):
            try:
                data = json.loads(run_file.read_text())
                if data.get("project_id") == workspace_id:
                    run_ids.append(data.get("run_id", run_file.stem))
            except (json.JSONDecodeError, OSError):
                continue

        return run_ids

    def delete_runs(self, run_ids: list[str]) -> int:
        """Delete runs by ID.

        Args:
            run_ids: List of run IDs to delete.

        Returns:
            Number of runs deleted.
        """
        runs_dir = self.get_runs_dir()
        deleted = 0

        for run_id in run_ids:
            run_file = runs_dir / f"{run_id}.json"
            if run_file.exists():
                try:
                    run_file.unlink()
                    deleted += 1
                except OSError as e:
                    logger.warning(f"Failed to delete run {run_id}: {e}")

        return deleted

    def mark_runs_orphaned(self, run_ids: list[str]) -> int:
        """Mark runs as orphaned (workspace deleted).

        Args:
            run_ids: List of run IDs to mark.

        Returns:
            Number of runs marked.
        """
        import json

        runs_dir = self.get_runs_dir()
        marked = 0

        for run_id in run_ids:
            run_file = runs_dir / f"{run_id}.json"
            if run_file.exists():
                try:
                    data = json.loads(run_file.read_text())
                    data["workspace_deleted"] = True
                    run_file.write_text(json.dumps(data, indent=2))
                    marked += 1
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to mark run {run_id} as orphaned: {e}")

        return marked

    def update_runs_workspace_id(self, old_id: str, new_id: str) -> int:
        """Update workspace ID in all matching runs.

        Args:
            old_id: The old workspace ID.
            new_id: The new workspace ID.

        Returns:
            Number of runs updated.
        """
        import json

        runs_dir = self.get_runs_dir()
        if not runs_dir.exists():
            return 0

        updated = 0
        for run_file in runs_dir.glob("*.json"):
            try:
                data = json.loads(run_file.read_text())
                if data.get("project_id") == old_id:
                    data["project_id"] = new_id
                    run_file.write_text(json.dumps(data, indent=2))
                    updated += 1
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to update run {run_file.stem}: {e}")

        return updated

    def delete_sunwell_data(self, workspace_path: Path) -> tuple[list[str], list[str]]:
        """Delete the .sunwell directory for a workspace.

        Args:
            workspace_path: The workspace root path.

        Returns:
            Tuple of (deleted_items, failed_items).
        """
        sunwell_dir = self.get_sunwell_data_dir(workspace_path)
        if not sunwell_dir.exists():
            return ([], [])

        deleted: list[str] = []
        failed: list[str] = []

        # Track what we're about to delete for reporting
        items_to_delete = [
            "project.toml",
            "lineage/",
            "intelligence/",
            "memory/",
            "team/",
            "backlog/",
            "recovery/",
        ]

        for item in items_to_delete:
            item_path = sunwell_dir / item.rstrip("/")
            if item_path.exists():
                try:
                    if item_path.is_dir():
                        shutil.rmtree(item_path)
                    else:
                        item_path.unlink()
                    deleted.append(f".sunwell/{item}")
                except OSError as e:
                    logger.warning(f"Failed to delete {item_path}: {e}")
                    failed.append(f".sunwell/{item}")

        # Try to remove the .sunwell dir itself if empty
        try:
            if sunwell_dir.exists() and not any(sunwell_dir.iterdir()):
                sunwell_dir.rmdir()
                deleted.append(".sunwell/")
        except OSError:
            pass  # Not empty or permission issue

        return (deleted, failed)

    def delete_workspace_directory(self, workspace_path: Path) -> tuple[list[str], list[str]]:
        """Delete the entire workspace directory.

        Args:
            workspace_path: The workspace root path.

        Returns:
            Tuple of (deleted_items, failed_items).
        """
        if not workspace_path.exists():
            return ([], [])

        deleted: list[str] = []
        failed: list[str] = []

        try:
            shutil.rmtree(workspace_path)
            deleted.append(str(workspace_path))
        except OSError as e:
            logger.error(f"Failed to delete workspace directory {workspace_path}: {e}")
            failed.append(str(workspace_path))

        return (deleted, failed)

    def find_orphaned_runs(self, registered_workspace_ids: set[str]) -> list[str]:
        """Find runs that reference non-existent workspaces.

        Args:
            registered_workspace_ids: Set of valid workspace IDs.

        Returns:
            List of orphaned run IDs.
        """
        import json

        runs_dir = self.get_runs_dir()
        if not runs_dir.exists():
            return []

        orphaned: list[str] = []
        for run_file in runs_dir.glob("*.json"):
            try:
                data = json.loads(run_file.read_text())
                project_id = data.get("project_id")
                # Skip if already marked as orphaned
                if data.get("workspace_deleted"):
                    continue
                # Check if workspace exists
                if project_id and project_id not in registered_workspace_ids:
                    orphaned.append(data.get("run_id", run_file.stem))
            except (json.JSONDecodeError, OSError):
                continue

        return orphaned

    def find_invalid_registrations(
        self, registry_entries: dict[str, dict]
    ) -> list[str]:
        """Find registry entries with missing workspace paths.

        Args:
            registry_entries: Registry entries dict (id -> entry).

        Returns:
            List of workspace IDs with invalid paths.
        """
        invalid: list[str] = []
        for workspace_id, entry in registry_entries.items():
            root = entry.get("root")
            if root and not Path(root).exists():
                invalid.append(workspace_id)
        return invalid


def has_nested_workspaces(workspace_path: Path, registry_entries: dict[str, dict]) -> list[str]:
    """Check if workspace contains nested workspaces.

    Args:
        workspace_path: The workspace to check.
        registry_entries: Registry entries dict.

    Returns:
        List of nested workspace IDs found within this workspace.
    """
    workspace_path = workspace_path.resolve()
    nested: list[str] = []

    for workspace_id, entry in registry_entries.items():
        root = entry.get("root")
        if not root:
            continue
        entry_path = Path(root).resolve()
        # Check if entry_path is inside workspace_path (but not the same)
        try:
            if entry_path != workspace_path and entry_path.is_relative_to(workspace_path):
                nested.append(workspace_id)
        except ValueError:
            # is_relative_to raises ValueError if not relative
            continue

    return nested
