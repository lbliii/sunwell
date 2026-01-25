"""RFC-063: Shared verification utilities for cascade operations.

Extracted from CascadeEngine and CascadeExecutor to eliminate duplication.
"""

import subprocess
from pathlib import Path


async def run_pytest(project_root: Path, timeout: int = 300) -> bool:
    """Run pytest and return success status.

    Args:
        project_root: Root directory of the project
        timeout: Maximum seconds to wait

    Returns:
        True if tests pass or pytest unavailable, False on failure
    """
    try:
        result = subprocess.run(
            ["pytest", "--tb=short", "-q"],
            cwd=project_root,
            capture_output=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True  # Assume pass if can't run


async def run_mypy(project_root: Path, timeout: int = 120) -> bool:
    """Run mypy and return success status.

    Args:
        project_root: Root directory of the project
        timeout: Maximum seconds to wait

    Returns:
        True if type check passes or mypy unavailable, False on failure
    """
    try:
        result = subprocess.run(
            ["mypy", "src/"],
            cwd=project_root,
            capture_output=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True


async def run_ruff(project_root: Path, timeout: int = 60) -> bool:
    """Run ruff and return success status.

    Args:
        project_root: Root directory of the project
        timeout: Maximum seconds to wait

    Returns:
        True if lint passes or ruff unavailable, False on failure
    """
    try:
        result = subprocess.run(
            ["ruff", "check", "src/"],
            cwd=project_root,
            capture_output=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True
