"""Workspace validation for RFC-117.

Prevents the agent from writing to Sunwell's own repository.
"""

from pathlib import Path


class ProjectValidationError(Exception):
    """Raised when a workspace fails validation."""


def validate_not_sunwell_repo(root: Path) -> None:
    """Refuse to use Sunwell's own repo as a project workspace.

    This is a safety guard to prevent agent-generated content from
    polluting Sunwell's source tree when running from the repo directory.

    Args:
        root: Proposed workspace root path

    Raises:
        ProjectValidationError: If root appears to be Sunwell's repository
    """
    root = root.resolve()

    # Check for pyproject.toml with sunwell name
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            # Check for sunwell package definition
            if 'name = "sunwell"' in content and "[project]" in content:
                raise ProjectValidationError(
                    f"Cannot use Sunwell's own repository as project workspace.\n"
                    f"Root: {root}\n\n"
                    f"This would cause agent-generated files to pollute Sunwell's source.\n"
                    f"Create a separate directory for your project:\n"
                    f"  mkdir ~/projects/my-app && cd ~/projects/my-app\n"
                    f"  sunwell project init .\n"
                )
        except OSError:
            pass  # File unreadable, skip check

    # Additional marker: src/sunwell directory structure
    sunwell_src = root / "src" / "sunwell"
    if sunwell_src.is_dir():
        # Verify it's actually sunwell by checking for core modules
        core_markers = [
            sunwell_src / "agent",
            sunwell_src / "tools",
            sunwell_src / "naaru",
        ]
        if sum(1 for m in core_markers if m.exists()) >= 2:
            raise ProjectValidationError(
                f"Cannot use Sunwell's own repository as project workspace.\n"
                f"Root: {root}\n"
                f"Detected: src/sunwell/ with core modules\n\n"
                f"Create a separate directory for your project."
            )


def validate_workspace(root: Path) -> None:
    """Validate a workspace root path.

    Runs all validation checks. Call this before using a path as workspace.

    Args:
        root: Proposed workspace root path

    Raises:
        ProjectValidationError: If validation fails
    """
    validate_not_sunwell_repo(root)
    # Future: Add more validations (writable, not system dir, etc.)
