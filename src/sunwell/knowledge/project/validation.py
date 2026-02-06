"""Workspace validation for RFC-117.

Validates proposed workspace paths before use.  With out-of-tree state
isolation (see ``state.py``), the old self-repo guard is no longer needed
— any directory can be a valid workspace because runtime state is stored
externally when appropriate.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ProjectValidationError(Exception):
    """Raised when a workspace fails validation."""


def _is_sunwell_repo(root: Path) -> bool:
    """Detect whether *root* is Sunwell's own source repository.

    Used by the CLI to auto-configure external state when initializing
    Sunwell's own repo as a workspace.

    Uses two heuristics:
    1. ``pyproject.toml`` contains ``name = "sunwell"``
    2. ``src/sunwell/`` exists with >= 2 core module directories
    """
    root = root.resolve()

    # Heuristic 1: pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            if 'name = "sunwell"' in content and "[project]" in content:
                return True
        except OSError:
            pass

    # Heuristic 2: src/sunwell/ with core modules
    sunwell_src = root / "src" / "sunwell"
    if sunwell_src.is_dir():
        core_markers = [
            sunwell_src / "agent",
            sunwell_src / "tools",
            sunwell_src / "naaru",
        ]
        if sum(1 for m in core_markers if m.exists()) >= 2:
            return True

    return False


def validate_not_sunwell_directory(root: Path) -> None:
    """Refuse to use .sunwell directory as project workspace.

    The .sunwell directory is reserved for internal sunwell data (logs,
    config, metrics, snapshots). User-requested files must go in the
    actual project root, not inside .sunwell.

    Args:
        root: Proposed workspace root path

    Raises:
        ProjectValidationError: If root is a .sunwell directory
    """
    root = root.resolve()

    if root.name == ".sunwell":
        raise ProjectValidationError(
            f"Cannot use .sunwell directory as project workspace.\n"
            f"Root: {root}\n\n"
            f"The .sunwell directory is reserved for internal sunwell data.\n"
            f"Use the parent directory as your project root instead:\n"
            f"  cd {root.parent}\n"
        )


def validate_workspace(root: Path) -> None:
    """Validate a workspace root path.

    Runs all validation checks. Call this before using a path as workspace.

    Note: The old self-repo guard (``validate_not_sunwell_repo``) has been
    removed.  With out-of-tree state isolation, any directory (including
    Sunwell's own repo) is a valid workspace.  The CLI auto-detects
    Sunwell's repo and configures external state at init time.

    Args:
        root: Proposed workspace root path

    Raises:
        ProjectValidationError: If validation fails
    """
    validate_not_sunwell_directory(root)
    # Future: Add more validations (writable, not system dir, etc.)
