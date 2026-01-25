"""Prerequisite checking for project preview (RFC: Universal Project Readiness).

Checks whether prerequisites are satisfied and determines if a project
can be previewed.
"""

import subprocess
from typing import Any

from sunwell.knowledge.project.intent_types import (
    Prerequisite,
    PreviewType,
    ProjectAnalysis,
)


def check_prerequisites(analysis: ProjectAnalysis) -> list[Prerequisite]:
    """Check which prerequisites are satisfied.

    Examines dev_command.prerequisites and returns updated list
    with satisfaction status.

    Args:
        analysis: Project analysis with dev_command.

    Returns:
        List of Prerequisite with updated satisfied status.
    """
    if not analysis.dev_command or not analysis.dev_command.prerequisites:
        return []

    checked = []
    for prereq in analysis.dev_command.prerequisites:
        satisfied = _check_single_prerequisite(prereq)
        checked.append(
            Prerequisite(
                command=prereq.command,
                description=prereq.description,
                check_command=prereq.check_command,
                satisfied=satisfied,
                required=prereq.required,
            )
        )

    return checked


def _check_single_prerequisite(prereq: Prerequisite) -> bool:
    """Check if a single prerequisite is satisfied.

    Args:
        prereq: Prerequisite to check.

    Returns:
        True if satisfied (check_command returns 0), False otherwise.
    """
    if not prereq.check_command:
        return False  # Can't verify, assume not satisfied

    try:
        result = subprocess.run(
            prereq.check_command,
            shell=True,
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def can_preview(analysis: ProjectAnalysis) -> bool:
    """Check if preview is ready (no server needed or prerequisites met).

    Content previews (prose, screenplay, dialogue) have no prerequisites
    and can always be previewed. Web/terminal previews need dev_command
    prerequisites to be met.

    Args:
        analysis: Project analysis to check.

    Returns:
        True if project can be previewed, False otherwise.
    """
    # Content previews have no prerequisites
    if analysis.preview_type in (
        PreviewType.PROSE,
        PreviewType.SCREENPLAY,
        PreviewType.DIALOGUE,
        PreviewType.STATIC,
    ):
        return True

    # No preview means nothing to check
    if analysis.preview_type == PreviewType.NONE:
        return False

    # Web/terminal/notebook previews need dev_command prerequisites
    if analysis.dev_command:
        checked = check_prerequisites(analysis)
        return all(p.satisfied or not p.required for p in checked)

    # No dev_command but has WEB_VIEW/TERMINAL/NOTEBOOK preview type
    # means we can preview (e.g., notebook without explicit dev command)
    return True


def missing_prerequisites(analysis: ProjectAnalysis) -> list[Prerequisite]:
    """Get list of missing required prerequisites.

    Args:
        analysis: Project analysis to check.

    Returns:
        List of unsatisfied required prerequisites.
    """
    checked = check_prerequisites(analysis)
    return [p for p in checked if not p.satisfied and p.required]


def get_preview_status(analysis: ProjectAnalysis) -> dict[str, Any]:
    """Get comprehensive preview status for UI display.

    Args:
        analysis: Project analysis to check.

    Returns:
        Dictionary with preview status information:
        - ready: bool - Whether preview is ready
        - preview_type: str - Type of preview
        - preview_url: str | None - URL for web previews
        - preview_file: str | None - File for content previews
        - missing: list[dict] - Missing prerequisites
        - all_prerequisites: list[dict] - All prerequisites with status
    """
    checked = check_prerequisites(analysis)
    missing = [p for p in checked if not p.satisfied and p.required]

    return {
        "ready": can_preview(analysis),
        "preview_type": analysis.preview_type.value,
        "preview_url": analysis.preview_url,
        "preview_file": analysis.preview_file,
        "missing": [
            {
                "command": p.command,
                "description": p.description,
                "required": p.required,
            }
            for p in missing
        ],
        "all_prerequisites": [
            {
                "command": p.command,
                "description": p.description,
                "satisfied": p.satisfied,
                "required": p.required,
            }
            for p in checked
        ],
    }


__all__ = [
    "check_prerequisites",
    "can_preview",
    "missing_prerequisites",
    "get_preview_status",
]
