"""Pre-flight health checks for autonomous agent execution.

Validates workspace, disk space, git state, and model availability
before starting an unattended agent run.

Example:
    >>> health = await check_health(workspace, check_git=True)
    >>> if not health.ok:
    ...     for error in health.errors:
    ...         print(f"BLOCKED: {error}")
    >>> for warning in health.warnings:
    ...     print(f"WARNING: {warning}")
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Pre-flight health check results.

    Attributes:
        workspace_exists: Whether workspace directory exists
        workspace_writable: Whether we can write to workspace
        git_repo_clean: Whether git repo has no uncommitted changes
        disk_space_mb: Free disk space in megabytes
        model_available: Whether model is available (if checked)
    """

    workspace_exists: bool
    workspace_writable: bool
    git_repo_clean: bool
    disk_space_mb: int
    model_available: bool

    # Thresholds
    MIN_DISK_SPACE_MB: int = 100
    """Minimum required disk space (100MB)."""

    LOW_DISK_SPACE_MB: int = 500
    """Warning threshold for disk space (500MB)."""

    @property
    def ok(self) -> bool:
        """All critical checks pass."""
        return (
            self.workspace_exists
            and self.workspace_writable
            and self.disk_space_mb >= self.MIN_DISK_SPACE_MB
        )

    @property
    def warnings(self) -> list[str]:
        """Non-critical issues that should be noted."""
        warnings = []
        if not self.git_repo_clean:
            warnings.append("Git repo has uncommitted changes")
        if self.disk_space_mb < self.LOW_DISK_SPACE_MB:
            warnings.append(f"Low disk space: {self.disk_space_mb}MB")
        if not self.model_available:
            warnings.append("Model availability not confirmed")
        return warnings

    @property
    def errors(self) -> list[str]:
        """Critical issues that block execution."""
        errors = []
        if not self.workspace_exists:
            errors.append("Workspace does not exist")
        if not self.workspace_writable:
            errors.append("Workspace is not writable")
        if self.disk_space_mb < self.MIN_DISK_SPACE_MB:
            errors.append(f"Insufficient disk space: {self.disk_space_mb}MB")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workspace_exists": self.workspace_exists,
            "workspace_writable": self.workspace_writable,
            "git_repo_clean": self.git_repo_clean,
            "disk_space_mb": self.disk_space_mb,
            "model_available": self.model_available,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


async def check_health(
    workspace: Path,
    check_git: bool = True,
    check_model: bool = False,
    model_ping_fn: Any | None = None,
) -> HealthStatus:
    """Run pre-flight health checks.

    Args:
        workspace: Path to the workspace directory
        check_git: Whether to check git status
        check_model: Whether to check model availability
        model_ping_fn: Optional async function to ping model

    Returns:
        HealthStatus with check results
    """
    # Workspace existence
    workspace = Path(workspace).resolve()
    workspace_exists = workspace.exists() and workspace.is_dir()

    # Workspace writable
    workspace_writable = False
    if workspace_exists:
        workspace_writable = _check_writable(workspace)

    # Disk space
    disk_space_mb = _get_disk_space_mb(workspace if workspace_exists else Path.home())

    # Git status
    git_clean = True
    if check_git and workspace_exists:
        git_clean = _check_git_clean(workspace)

    # Model availability
    model_available = True
    if check_model and model_ping_fn:
        try:
            model_available = await model_ping_fn()
        except Exception:
            model_available = False

    return HealthStatus(
        workspace_exists=workspace_exists,
        workspace_writable=workspace_writable,
        git_repo_clean=git_clean,
        disk_space_mb=disk_space_mb,
        model_available=model_available,
    )


def _check_writable(workspace: Path) -> bool:
    """Check if workspace is writable."""
    try:
        test_file = workspace / ".sunwell_health_check"
        test_file.write_text("test")
        test_file.unlink()
        return True
    except (OSError, PermissionError):
        return False


def _get_disk_space_mb(path: Path) -> int:
    """Get free disk space in megabytes."""
    try:
        usage = shutil.disk_usage(path)
        return usage.free // (1024 * 1024)
    except OSError:
        return 0


def _check_git_clean(workspace: Path) -> bool:
    """Check if git repo has no uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Clean if no output
        return result.returncode == 0 and not result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        # Assume clean if git not available or not a git repo
        return True


def check_health_sync(
    workspace: Path,
    check_git: bool = True,
) -> HealthStatus:
    """Synchronous version of health check.

    Args:
        workspace: Path to the workspace directory
        check_git: Whether to check git status

    Returns:
        HealthStatus with check results
    """
    workspace = Path(workspace).resolve()
    workspace_exists = workspace.exists() and workspace.is_dir()
    workspace_writable = _check_writable(workspace) if workspace_exists else False
    disk_space_mb = _get_disk_space_mb(workspace if workspace_exists else Path.home())
    git_clean = _check_git_clean(workspace) if check_git and workspace_exists else True

    return HealthStatus(
        workspace_exists=workspace_exists,
        workspace_writable=workspace_writable,
        git_repo_clean=git_clean,
        disk_space_mb=disk_space_mb,
        model_available=True,  # Can't check async in sync context
    )
