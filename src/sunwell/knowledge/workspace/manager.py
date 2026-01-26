"""Workspace management for RFC-140 and RFC-141.

Unified workspace discovery, switching, status tracking, and lifecycle management.
"""

import fcntl
import json
import logging
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.knowledge.project import ProjectRegistry, create_project_from_workspace
from sunwell.knowledge.project.types import Project
from sunwell.knowledge.project.validation import ProjectValidationError, validate_workspace
from sunwell.knowledge.workspace.resolver import PROJECT_MARKERS, default_workspace_root

if TYPE_CHECKING:
    from sunwell.knowledge.workspace.lifecycle import (
        CleanupResult,
        DeleteResult,
        MoveResult,
        PurgeResult,
        RenameResult,
    )

logger = logging.getLogger(__name__)

# Constants
MAX_PATH_LENGTH = 260 if sys.platform == "win32" else 4096
MAX_DISCOVERY_DEPTH = 2
MAX_DISCOVERY_TIME = 5.0  # seconds


class WorkspaceStatus(Enum):
    """Workspace health status."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True, slots=True)
class WorkspaceInfo:
    """Information about a workspace."""

    id: str
    """Workspace identifier (project ID if registered, else derived from path)."""

    name: str
    """Human-readable name."""

    path: Path
    """Absolute path to workspace root."""

    is_registered: bool
    """Whether this workspace is registered in the project registry."""

    is_current: bool
    """Whether this is the current workspace."""

    status: WorkspaceStatus
    """Workspace health status."""

    workspace_type: str
    """Type of workspace (manifest, registered, discovered)."""

    last_used: str | None = None
    """Last used timestamp (ISO format)."""

    project: Project | None = None
    """Project instance if registered."""


def _get_current_workspace_path() -> Path:
    """Get path to current workspace state file."""
    return Path.home() / ".sunwell" / "current_workspace.json"


def _load_current_workspace() -> dict | None:
    """Load current workspace state."""
    path = _get_current_workspace_path()
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)

        # Validate workspace path still exists
        workspace_path = Path(data.get("workspace_path", ""))
        if workspace_path and not workspace_path.exists():
            # Clear invalid state
            _clear_current_workspace()
            return None

        return data
    except (json.JSONDecodeError, OSError, KeyError):
        # Corrupted or invalid JSON, clear it
        _clear_current_workspace()
        return None


def _clear_current_workspace() -> None:
    """Clear current workspace state file."""
    path = _get_current_workspace_path()
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass  # Non-critical


def _save_current_workspace(workspace_id: str, workspace_path: Path) -> None:
    """Save current workspace state with atomic write and file locking.
    
    Uses tempfile + rename pattern for atomic writes and file locking
    to prevent race conditions. Works on both Unix and Windows.
    """
    path = _get_current_workspace_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "workspace_id": workspace_id,
        "workspace_path": str(workspace_path.resolve()),
        "switched_at": datetime.now().isoformat(),
    }

    try:
        content = json.dumps(data, indent=2)

        # Atomic write: write to temp file, then rename
        # This prevents partial writes if process is interrupted
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)

        # Use file locking on Unix systems (fcntl not available on Windows)
        if sys.platform != "win32":
            try:
                with temp_path.open("r+") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    # File already written, just hold lock during rename
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except (OSError, AttributeError):
                # Fallback if locking fails (e.g., NFS)
                pass

        # Atomic rename (works on all platforms)
        # On Windows, this will fail if file is locked, which is acceptable
        temp_path.replace(path)
    except OSError:
        # Clean up temp file on error
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        # Non-critical, fail silently


class WorkspaceManager:
    """Unified workspace management.

    Provides discovery, switching, and status tracking for workspaces.
    """

    def __init__(self) -> None:
        """Initialize workspace manager."""
        self._registry = ProjectRegistry()

    def discover_workspaces(self, root: Path | None = None) -> list[WorkspaceInfo]:
        """Discover workspaces by scanning filesystem.

        Scans common locations and project markers to find workspaces.
        Merges with registered projects and deduplicates.

        Projects found in ~/Sunwell/projects/ are auto-registered (they're Sunwell
        projects, not external workspaces). Only external directories are shown
        as "discovered" workspaces.

        Args:
            root: Root directory to scan (defaults to common locations)

        Returns:
            List of discovered workspace info
        """
        import time

        start_time = time.time()
        current_workspace = self.get_current()
        current_path = current_workspace.path if current_workspace else None

        # Validate root if provided
        if root is not None:
            root = Path(root).resolve()
            if not root.is_dir():
                raise ValueError(f"Root must be a directory: {root}")

        # Get the Sunwell projects directory (projects here should be registered, not discovered)
        sunwell_projects_root = default_workspace_root().resolve()

        # Auto-register any unregistered Sunwell projects in ~/Sunwell/projects/
        self._auto_register_sunwell_projects(sunwell_projects_root)

        # Get registered projects (now includes auto-registered ones)
        registered_projects = self._registry.list_projects()
        # Use canonical paths (resolve symlinks) for deduplication
        registered_paths: set[Path] = {
            p.root.resolve().resolve() for p in registered_projects
        }

        # Scan locations if root not specified
        # NOTE: Do NOT scan ~/Sunwell/projects/ for "discovered" workspaces —
        # those are Sunwell projects and should be registered, not discovered.
        if root is None:
            scan_roots = [
                Path.home() / "Projects",
                Path.home() / "Code",
                Path.home() / "workspace",
                Path.home() / "workspaces",
                Path.home() / "Developer",
                Path.home() / "dev",
            ]
        else:
            scan_roots = [root]

        discovered_paths: set[Path] = set()

        # Scan each root location with depth limit
        for scan_root in scan_roots:
            if not scan_root.exists():
                continue

            # Check timeout
            if time.time() - start_time > MAX_DISCOVERY_TIME:
                break

            # Skip if scan_root is inside an already discovered workspace (nested workspace)
            # This prevents discovering workspaces inside other workspaces
            scan_root_canonical = scan_root.resolve().resolve()
            is_nested = any(
                scan_root_canonical.is_relative_to(p) or scan_root_canonical == p
                for p in registered_paths
            )
            if is_nested:
                continue

            # Skip if this is inside ~/Sunwell/ (not external)
            if scan_root_canonical.is_relative_to(sunwell_projects_root.parent):
                continue

            # Scan direct children only (depth 1)
            try:
                for item in scan_root.iterdir():
                    # Check timeout during iteration
                    if time.time() - start_time > MAX_DISCOVERY_TIME:
                        break

                    if not item.is_dir():
                        continue

                    # Skip nested workspaces (workspace inside another workspace)
                    item_canonical = item.resolve().resolve()
                    is_nested_workspace = any(
                        item_canonical.is_relative_to(p) or p.is_relative_to(item_canonical)
                        for p in registered_paths | discovered_paths
                    )
                    if is_nested_workspace:
                        continue

                    # Skip if inside ~/Sunwell/ (those are projects, not external workspaces)
                    if item_canonical.is_relative_to(sunwell_projects_root.parent):
                        continue

                    # Check for project markers
                    if self._has_project_markers(item):
                        # Resolve to canonical path for deduplication
                        canonical_path = item.resolve().resolve()
                        discovered_paths.add(canonical_path)
            except (OSError, PermissionError):
                # Log permission errors but continue
                # Could be enhanced to return warnings
                continue

        # Merge registered and discovered (deduplicate by canonical path)
        all_paths = registered_paths | discovered_paths

        # Build workspace info list
        workspaces: list[WorkspaceInfo] = []

        for path in all_paths:
            # Ensure canonical path
            canonical_path = path.resolve().resolve()

            # Check if registered
            project = self._registry.find_by_root(canonical_path)
            is_registered = project is not None

            # Get or derive ID and name
            if project:
                workspace_id = project.id
                workspace_name = project.name
                workspace_type = project.workspace_type.value
                last_used = self._registry.projects.get(project.id, {}).get("last_used")
            else:
                workspace_id = sanitize_workspace_id(canonical_path.name)
                workspace_name = canonical_path.name
                workspace_type = "discovered"
                last_used = None

            # Check status
            status = self._check_status(canonical_path)

            # Check if current (compare canonical paths)
            is_current = (
                current_path is not None
                and canonical_path.resolve() == current_path.resolve().resolve()
            )

            workspaces.append(
                WorkspaceInfo(
                    id=workspace_id,
                    name=workspace_name,
                    path=canonical_path,
                    is_registered=is_registered,
                    is_current=is_current,
                    status=status,
                    workspace_type=workspace_type,
                    last_used=last_used,
                    project=project,
                )
            )

        # Sort by: current first, then registered, then by last_used
        workspaces.sort(
            key=lambda w: (
                not w.is_current,
                not w.is_registered,
                w.last_used or "",
            ),
            reverse=True,
        )

        return workspaces

    def _auto_register_sunwell_projects(self, sunwell_projects_root: Path) -> None:
        """Auto-register any valid Sunwell projects found in ~/Sunwell/projects/.

        These are Sunwell projects (have .sunwell/ or are in the projects dir),
        not external workspaces. They should be registered, not discovered.

        Args:
            sunwell_projects_root: Path to ~/Sunwell/projects/
        """
        if not sunwell_projects_root.exists():
            return

        try:
            for item in sunwell_projects_root.iterdir():
                if not item.is_dir():
                    continue

                # Skip if already registered
                canonical_path = item.resolve().resolve()
                if self._registry.find_by_root(canonical_path):
                    continue

                # Check if it looks like a valid project (has .sunwell/ or project markers)
                if not self._has_project_markers(item):
                    continue

                # Auto-register this project
                try:
                    project = create_project_from_workspace(canonical_path)
                    self._registry.register(project)
                    logger.info(f"Auto-registered Sunwell project: {project.id}")
                except Exception as e:
                    logger.debug(f"Could not auto-register {item.name}: {e}")
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not scan {sunwell_projects_root}: {e}")

    def get_current(self) -> WorkspaceInfo | None:
        """Get current workspace.

        Returns:
            Current workspace info or None if not set
        """
        state = _load_current_workspace()
        if not state:
            # Fallback to default project
            default_project = self._registry.get_default()
            if default_project:
                return self._workspace_info_from_project(default_project, is_current=True)
            return None

        workspace_path = Path(state["workspace_path"])
        workspace_id = state.get("workspace_id")

        # Validate path exists (already checked in _load_current_workspace, but double-check)
        if not workspace_path.exists():
            _clear_current_workspace()
            return None

        # Resolve to canonical path (handles symlinks consistently)
        workspace_path = workspace_path.resolve().resolve()  # Double resolve for symlinks

        # Try to find in registry
        project = self._registry.find_by_root(workspace_path)
        if project:
            return self._workspace_info_from_project(project, is_current=True)

        # Not registered, create info from path
        status = self._check_status(workspace_path)
        return WorkspaceInfo(
            id=workspace_id or sanitize_workspace_id(workspace_path.name),
            name=workspace_path.name,
            path=workspace_path,
            is_registered=False,
            is_current=True,
            status=status,
            workspace_type="discovered",
        )

    def switch_workspace(self, workspace_id: str | Path) -> WorkspaceInfo:
        """Switch to a workspace.

        Args:
            workspace_id: Workspace ID or path

        Returns:
            Workspace info for the switched workspace

        Raises:
            ValueError: If workspace not found or invalid
            PermissionError: If workspace is not accessible
        """
        # Validate path length if it's a path
        if isinstance(workspace_id, (str, Path)):
            path_str = str(workspace_id)
            if len(path_str) > MAX_PATH_LENGTH:
                raise ValueError(
                    f"Path too long: {len(path_str)} > {MAX_PATH_LENGTH} characters"
                )

        # Try as ID first
        project = self._registry.get(workspace_id) if isinstance(workspace_id, str) else None

        if project:
            workspace_path = project.root.resolve().resolve()  # Canonical path
            actual_id = project.id
        elif isinstance(workspace_id, Path):
            workspace_path = workspace_id.resolve().resolve()  # Canonical path
            project = self._registry.find_by_root(workspace_path)
            if project:
                actual_id = project.id
            else:
                actual_id = sanitize_workspace_id(workspace_path.name)
        else:
            # Try to find by path in discovered workspaces
            workspaces = self.discover_workspaces()
            matching = [
                w
                for w in workspaces
                if w.id == workspace_id or str(w.path) == workspace_id
            ]
            if not matching:
                raise ValueError(f"Workspace not found: {workspace_id}")

            workspace_info = matching[0]
            workspace_path = workspace_info.path.resolve().resolve()  # Canonical
            actual_id = workspace_info.id
            project = workspace_info.project

        # Validate workspace exists
        if not workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace_path}")

        # Check permissions
        if not workspace_path.is_dir():
            raise ValueError(f"Workspace path is not a directory: {workspace_path}")

        try:
            # Check read permission
            list(workspace_path.iterdir())
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied accessing workspace: {workspace_path}"
            ) from e

        # Validate workspace
        try:
            validate_workspace(workspace_path)
        except ProjectValidationError as e:
            raise ValueError(f"Invalid workspace: {e}") from e

        # Save current workspace (with locking)
        _save_current_workspace(actual_id, workspace_path)

        # Update last used if registered
        if project:
            self._registry.update_last_used(project.id)

        # Return workspace info
        if project:
            return self._workspace_info_from_project(project, is_current=True)

        status = self._check_status(workspace_path)
        return WorkspaceInfo(
            id=actual_id,
            name=workspace_path.name,
            path=workspace_path,
            is_registered=False,
            is_current=True,
            status=status,
            workspace_type="discovered",
        )

    def get_status(self, path: Path) -> WorkspaceStatus:
        """Get workspace status.

        Args:
            path: Workspace path

        Returns:
            Workspace status
        """
        return self._check_status(path)

    def register_discovered(self, path: Path) -> Project:
        """Register a discovered workspace.

        Creates a project from the workspace path and registers it.

        Args:
            path: Workspace path to register

        Returns:
            Registered Project instance

        Raises:
            ValueError: If path is invalid or already registered
            PermissionError: If path is not accessible
        """
        # Validate path length
        path_str = str(path)
        if len(path_str) > MAX_PATH_LENGTH:
            raise ValueError(
                f"Path too long: {len(path_str)} > {MAX_PATH_LENGTH} characters"
            )

        # Resolve to canonical path
        path = path.resolve().resolve()

        # Check if already registered
        existing = self._registry.find_by_root(path)
        if existing:
            raise ValueError(f"Workspace already registered as: {existing.id}")

        # Validate workspace exists and is accessible
        if not path.exists():
            raise ValueError(f"Workspace path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Workspace path is not a directory: {path}")

        try:
            list(path.iterdir())
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied accessing workspace: {path}"
            ) from e

        # Validate workspace
        try:
            validate_workspace(path)
        except ProjectValidationError as e:
            raise ValueError(f"Invalid workspace: {e}") from e

        # Create project from workspace
        project = create_project_from_workspace(path)

        # Register it
        self._registry.register(project)

        return project

    def _has_project_markers(self, path: Path) -> bool:
        """Check if path has project markers.

        Args:
            path: Path to check

        Returns:
            True if markers found
        """
        for marker in PROJECT_MARKERS:
            if (path / marker).exists():
                return True
        return False

    def _check_status(self, path: Path) -> WorkspaceStatus:
        """Check workspace status.

        Args:
            path: Workspace path

        Returns:
            Workspace status
        """
        try:
            # Validate path length
            path_str = str(path)
            if len(path_str) > MAX_PATH_LENGTH:
                return WorkspaceStatus.INVALID

            if not path.exists():
                return WorkspaceStatus.NOT_FOUND

            # Check if accessible
            try:
                list(path.iterdir())
            except PermissionError:
                return WorkspaceStatus.INVALID

            validate_workspace(path)
            return WorkspaceStatus.VALID
        except ProjectValidationError:
            return WorkspaceStatus.INVALID
        except Exception:
            # Catch-all for other errors (OSError, etc.)
            return WorkspaceStatus.INVALID

    def _workspace_info_from_project(self, project: Project, is_current: bool = False) -> WorkspaceInfo:
        """Create WorkspaceInfo from Project.

        Args:
            project: Project instance
            is_current: Whether this is the current workspace

        Returns:
            WorkspaceInfo instance
        """
        status = self._check_status(project.root)
        last_used = self._registry.projects.get(project.id, {}).get("last_used")

        return WorkspaceInfo(
            id=project.id,
            name=project.name,
            path=project.root.resolve().resolve(),  # Canonical path
            is_registered=True,
            is_current=is_current,
            status=status,
            workspace_type=project.workspace_type.value,
            last_used=last_used,
            project=project,
        )

    # ═══════════════════════════════════════════════════════════════
    # LIFECYCLE OPERATIONS (RFC-141)
    # ═══════════════════════════════════════════════════════════════

    def unregister(self, workspace_id: str) -> DeleteResult:
        """Unregister a workspace from the registry.

        Removes the workspace from the registry but keeps all files intact.
        This is the least destructive deletion mode.

        Args:
            workspace_id: The workspace ID to unregister.

        Returns:
            DeleteResult with operation outcome.

        Raises:
            ValueError: If workspace not found.
        """
        from sunwell.knowledge.workspace.lifecycle import DeleteResult, DeletionMode

        # Find workspace
        project = self._registry.get(workspace_id)
        if not project:
            raise ValueError(f"Workspace not registered: {workspace_id}")

        workspace_path = project.root.resolve()

        # Check if current workspace
        current = self.get_current()
        was_current = current is not None and current.id == workspace_id

        # Clear current workspace if this is it
        if was_current:
            _clear_current_workspace()

        # Unregister from registry
        self._registry.unregister(workspace_id)

        return DeleteResult(
            success=True,
            mode=DeletionMode.UNREGISTER,
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            deleted_items=("registry_entry",),
            failed_items=(),
            runs_deleted=0,
            runs_orphaned=0,
            was_current=was_current,
        )

    def purge(
        self,
        workspace_id: str,
        *,
        delete_runs: bool = False,
        force: bool = False,
    ) -> PurgeResult:
        """Purge Sunwell data from a workspace.

        Removes the workspace from the registry and deletes the .sunwell/
        directory, but keeps the source code and other files intact.

        Args:
            workspace_id: The workspace ID to purge.
            delete_runs: Whether to delete associated runs (default: False).
            force: Whether to force deletion even if runs are active.

        Returns:
            PurgeResult with operation outcome.

        Raises:
            ValueError: If workspace not found.
            RuntimeError: If active runs exist and force=False.
        """
        from sunwell.knowledge.workspace.lifecycle import (
            PurgeResult,
            WorkspaceLifecycle,
        )

        # Find workspace
        project = self._registry.get(workspace_id)
        if not project:
            raise ValueError(f"Workspace not registered: {workspace_id}")

        workspace_path = project.root.resolve()

        # Check for active runs
        if not force:
            active_runs = self.has_active_runs(workspace_id)
            if active_runs:
                raise RuntimeError(
                    f"Workspace has active runs: {active_runs}. "
                    "Use force=True to proceed."
                )

        # Check if current workspace
        current = self.get_current()
        was_current = current is not None and current.id == workspace_id

        # Clear current workspace if this is it
        if was_current:
            _clear_current_workspace()

        # Initialize lifecycle handler
        lifecycle = WorkspaceLifecycle()

        # Handle runs
        runs_deleted = 0
        if delete_runs:
            run_ids = lifecycle.list_workspace_runs(workspace_id)
            runs_deleted = lifecycle.delete_runs(run_ids)
        else:
            # Mark runs as orphaned
            run_ids = lifecycle.list_workspace_runs(workspace_id)
            lifecycle.mark_runs_orphaned(run_ids)

        # Delete .sunwell/ directory
        deleted_items, failed_items = lifecycle.delete_sunwell_data(workspace_path)

        # Unregister from registry
        self._registry.unregister(workspace_id)

        # Separate dirs and files for reporting
        deleted_dirs = tuple(d for d in deleted_items if d.endswith("/"))
        deleted_files = tuple(f for f in deleted_items if not f.endswith("/"))

        return PurgeResult(
            success=len(failed_items) == 0,
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            deleted_dirs=deleted_dirs,
            deleted_files=deleted_files,
            failed_items=tuple(failed_items),
            runs_deleted=runs_deleted,
            was_current=was_current,
            error=f"Failed to delete: {failed_items}" if failed_items else None,
        )

    def delete(
        self,
        workspace_id: str,
        *,
        delete_runs: bool = False,
        force: bool = False,
    ) -> DeleteResult:
        """Fully delete a workspace.

        Removes the workspace from the registry and deletes the entire
        workspace directory including all source code.

        WARNING: This is destructive and cannot be undone.

        Args:
            workspace_id: The workspace ID to delete.
            delete_runs: Whether to delete associated runs (default: False).
            force: Whether to force deletion even if runs are active.

        Returns:
            DeleteResult with operation outcome.

        Raises:
            ValueError: If workspace not found or has nested workspaces.
            RuntimeError: If active runs exist and force=False.
        """
        from sunwell.knowledge.workspace.lifecycle import (
            DeleteResult,
            DeletionMode,
            WorkspaceLifecycle,
            has_nested_workspaces,
        )

        # Find workspace
        project = self._registry.get(workspace_id)
        if not project:
            raise ValueError(f"Workspace not registered: {workspace_id}")

        workspace_path = project.root.resolve()

        # Check for nested workspaces
        nested = has_nested_workspaces(workspace_path, self._registry.projects)
        if nested:
            raise ValueError(
                f"Workspace contains nested workspaces: {nested}. "
                "Delete or unregister nested workspaces first."
            )

        # Check for active runs
        if not force:
            active_runs = self.has_active_runs(workspace_id)
            if active_runs:
                raise RuntimeError(
                    f"Workspace has active runs: {active_runs}. "
                    "Use force=True to proceed."
                )

        # Check if current workspace
        current = self.get_current()
        was_current = current is not None and current.id == workspace_id

        # Clear current workspace if this is it
        if was_current:
            _clear_current_workspace()

        # Initialize lifecycle handler
        lifecycle = WorkspaceLifecycle()

        # Handle runs
        runs_deleted = 0
        runs_orphaned = 0
        run_ids = lifecycle.list_workspace_runs(workspace_id)
        if delete_runs:
            runs_deleted = lifecycle.delete_runs(run_ids)
        else:
            runs_orphaned = lifecycle.mark_runs_orphaned(run_ids)

        # Delete workspace directory
        deleted_items, failed_items = lifecycle.delete_workspace_directory(workspace_path)

        # Unregister from registry (even if deletion failed)
        self._registry.unregister(workspace_id)

        return DeleteResult(
            success=len(failed_items) == 0,
            mode=DeletionMode.FULL,
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            deleted_items=tuple(deleted_items),
            failed_items=tuple(failed_items),
            runs_deleted=runs_deleted,
            runs_orphaned=runs_orphaned,
            was_current=was_current,
            error=f"Failed to delete: {failed_items}" if failed_items else None,
        )

    def rename(
        self,
        workspace_id: str,
        new_id: str,
        new_name: str | None = None,
    ) -> RenameResult:
        """Rename a workspace.

        Changes the workspace ID and optionally the display name.
        Updates all references including runs.

        Args:
            workspace_id: The current workspace ID.
            new_id: The new workspace ID.
            new_name: The new display name (defaults to new_id).

        Returns:
            RenameResult with operation outcome.

        Raises:
            ValueError: If workspace not found or new_id conflicts.
        """
        from sunwell.knowledge.workspace.lifecycle import RenameResult, WorkspaceLifecycle

        # Validate new ID
        new_id = sanitize_workspace_id(new_id)
        if not new_id:
            raise ValueError("Invalid new workspace ID")

        # Find workspace
        project = self._registry.get(workspace_id)
        if not project:
            raise ValueError(f"Workspace not registered: {workspace_id}")

        # Check for conflicts
        if new_id != workspace_id and self._registry.get(new_id):
            raise ValueError(f"Workspace ID already exists: {new_id}")

        workspace_path = project.root.resolve()
        new_name = new_name or new_id

        # Update manifest if exists
        manifest_path = workspace_path / ".sunwell" / "project.toml"
        if manifest_path.exists():
            try:
                import tomllib
                with manifest_path.open("rb") as f:
                    manifest_data = tomllib.load(f)

                manifest_data["project"]["id"] = new_id
                manifest_data["project"]["name"] = new_name

                # Write back (use tomli_w if available, else manual)
                try:
                    import tomli_w
                    manifest_path.write_bytes(tomli_w.dumps(manifest_data))
                except ImportError:
                    # Fallback: just update the lines we need
                    content = manifest_path.read_text()
                    content = re.sub(
                        r'^id\s*=\s*"[^"]*"',
                        f'id = "{new_id}"',
                        content,
                        flags=re.MULTILINE,
                    )
                    content = re.sub(
                        r'^name\s*=\s*"[^"]*"',
                        f'name = "{new_name}"',
                        content,
                        flags=re.MULTILINE,
                    )
                    manifest_path.write_text(content)
            except Exception as e:
                logger.warning(f"Failed to update manifest: {e}")

        # Update registry
        self._registry.unregister(workspace_id)
        new_project = Project(
            id=new_id,
            name=new_name,
            root=project.root,
            workspace_type=project.workspace_type,
            created_at=project.created_at,
            manifest=project.manifest,
        )
        self._registry.register(new_project)

        # Update current workspace if this is it
        current = self.get_current()
        if current and current.id == workspace_id:
            _save_current_workspace(new_id, workspace_path)

        # Update runs
        lifecycle = WorkspaceLifecycle()
        runs_updated = lifecycle.update_runs_workspace_id(workspace_id, new_id)

        return RenameResult(
            success=True,
            old_id=workspace_id,
            new_id=new_id,
            runs_updated=runs_updated,
        )

    def move(self, workspace_id: str, new_path: Path) -> MoveResult:
        """Update workspace path after manual move.

        Call this after manually moving a workspace directory to update
        the registry and current workspace state.

        Args:
            workspace_id: The workspace ID.
            new_path: The new workspace path.

        Returns:
            MoveResult with operation outcome.

        Raises:
            ValueError: If workspace not found, new path doesn't exist,
                       or new path is already a registered workspace.
        """
        from sunwell.knowledge.workspace.lifecycle import MoveResult

        # Find workspace
        project = self._registry.get(workspace_id)
        if not project:
            raise ValueError(f"Workspace not registered: {workspace_id}")

        old_path = project.root.resolve()
        new_path = new_path.resolve()

        # Validate new path
        if not new_path.exists():
            raise ValueError(f"New path does not exist: {new_path}")

        if not new_path.is_dir():
            raise ValueError(f"New path is not a directory: {new_path}")

        # Check for conflicts
        existing = self._registry.find_by_root(new_path)
        if existing and existing.id != workspace_id:
            raise ValueError(f"Path already registered as workspace: {existing.id}")

        # Update registry
        self._registry.unregister(workspace_id)
        new_project = Project(
            id=workspace_id,
            name=project.name,
            root=new_path,
            workspace_type=project.workspace_type,
            created_at=project.created_at,
            manifest=project.manifest,
        )
        self._registry.register(new_project)

        # Update current workspace if this is it
        current = self.get_current()
        if current and current.id == workspace_id:
            _save_current_workspace(workspace_id, new_path)

        return MoveResult(
            success=True,
            workspace_id=workspace_id,
            old_path=old_path,
            new_path=new_path,
        )

    def cleanup_orphaned(self, *, dry_run: bool = True) -> CleanupResult:
        """Find and optionally clean up orphaned data.

        Finds:
        - Runs that reference non-existent workspaces
        - Registry entries with missing workspace paths

        Args:
            dry_run: If True, only report what would be cleaned.

        Returns:
            CleanupResult with findings and actions taken.
        """
        from sunwell.knowledge.workspace.lifecycle import CleanupResult, WorkspaceLifecycle

        lifecycle = WorkspaceLifecycle()

        # Find orphaned runs
        registered_ids = set(self._registry.projects.keys())
        orphaned_runs = lifecycle.find_orphaned_runs(registered_ids)

        # Find invalid registrations
        invalid_registrations = lifecycle.find_invalid_registrations(
            self._registry.projects
        )

        cleaned_runs = 0
        cleaned_registrations = 0

        if not dry_run:
            # Clean up orphaned runs (mark as deleted, don't actually delete)
            cleaned_runs = lifecycle.mark_runs_orphaned(orphaned_runs)

            # Clean up invalid registrations
            for workspace_id in invalid_registrations:
                self._registry.unregister(workspace_id)
                cleaned_registrations += 1

        return CleanupResult(
            dry_run=dry_run,
            orphaned_runs=tuple(orphaned_runs),
            invalid_registrations=tuple(invalid_registrations),
            cleaned_runs=cleaned_runs,
            cleaned_registrations=cleaned_registrations,
        )

    def has_active_runs(self, workspace_id: str) -> list[str]:
        """Check for active runs in a workspace.

        Args:
            workspace_id: The workspace ID to check.

        Returns:
            List of active run IDs.
        """
        import json

        runs_dir = Path.home() / ".sunwell" / "runs"
        if not runs_dir.exists():
            return []

        active: list[str] = []
        for run_file in runs_dir.glob("*.json"):
            try:
                data = json.loads(run_file.read_text())
                if data.get("project_id") == workspace_id:
                    status = data.get("status", "")
                    if status in ("running", "pending", "initializing"):
                        active.append(data.get("run_id", run_file.stem))
            except (json.JSONDecodeError, OSError):
                continue

        return active


def sanitize_workspace_id(name: str) -> str:
    """Sanitize workspace name to create a valid ID.

    Handles unicode, special characters, and case sensitivity.

    Args:
        name: Workspace name

    Returns:
        Sanitized ID
    """
    # Normalize unicode (NFKD decomposition)
    normalized = unicodedata.normalize("NFKD", name)

    # Convert to lowercase
    slug = normalized.lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    # Ensure not empty
    return slug or "workspace"
