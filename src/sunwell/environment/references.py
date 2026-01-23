"""Reference project management for User Environment Model (RFC-104).

Manages "gold standard" projects that serve as templates for new work.
References are suggested based on health scores and can be manually set.
"""

from pathlib import Path

from sunwell.environment.model import ProjectEntry, UserEnvironment

# =============================================================================
# Constants
# =============================================================================

REFERENCE_HEALTH_THRESHOLD = 0.90
"""Minimum health score to suggest as a reference project."""

REFERENCE_HEALTH_WARNING = 0.85
"""Health score below which we warn about degraded references."""


# =============================================================================
# Reference Suggestions
# =============================================================================


def suggest_references(projects: list[ProjectEntry]) -> dict[str, Path]:
    """Identify gold standard projects by category.

    Automatically suggests the healthiest project of each type as
    a reference, provided it meets the health threshold.

    Args:
        projects: All known projects.

    Returns:
        Dictionary mapping category → project path.
    """
    references: dict[str, Path] = {}

    # Group by project type
    by_type: dict[str, list[ProjectEntry]] = {}
    for project in projects:
        by_type.setdefault(project.project_type, []).append(project)

    # Best per type (must meet threshold)
    for project_type, type_projects in by_type.items():
        if project_type == "unknown":
            continue  # Skip unknown types

        # Filter to projects with health scores
        with_health = [p for p in type_projects if p.health_score is not None]
        if not with_health:
            continue

        # Find best project
        best = max(with_health, key=lambda p: p.health_score or 0)
        if best.health_score and best.health_score >= REFERENCE_HEALTH_THRESHOLD:
            references[project_type] = best.path

    return references


def check_reference_health(env: UserEnvironment) -> list[str]:
    """Return warnings for degraded reference projects.

    Checks all reference projects and returns warnings for any
    that have dropped below the warning threshold.

    Args:
        env: The user environment.

    Returns:
        List of warning messages.
    """
    warnings: list[str] = []

    for category, path in env.reference_projects.items():
        project = env.get_project(path)
        if not project:
            warnings.append(
                f"Reference '{category}' ({path.name}) no longer exists in environment. "
                f"Consider `sunwell env reference remove {category}`"
            )
            continue

        if project.health_score is not None and project.health_score < REFERENCE_HEALTH_WARNING:
            health_pct = project.health_score * 100
            warnings.append(
                f"Reference '{category}' ({path.name}) health dropped to {health_pct:.0f}%. "
                f"Consider: sunwell env reference remove {category}"
            )

    return warnings


# =============================================================================
# Reference Operations
# =============================================================================


def add_reference(
    env: UserEnvironment,
    category: str,
    path: Path,
) -> tuple[bool, str]:
    """Add a reference project for a category.

    Args:
        env: The user environment.
        category: Category name (e.g., "docs", "python").
        path: Path to the project.

    Returns:
        Tuple of (success, message).
    """
    path = path.resolve()
    project = env.get_project(path)

    if not project:
        return False, f"Project not found in environment: {path}"

    # Warn if health is low
    message = f"Set {path.name} as reference for '{category}'"
    if project.health_score is not None and project.health_score < REFERENCE_HEALTH_THRESHOLD:
        health = project.health_score * 100
        threshold = REFERENCE_HEALTH_THRESHOLD * 100
        message += f" (health: {health:.0f}% - below recommended {threshold:.0f}%)"

    env.set_reference(category, path)
    return True, message


def remove_reference(env: UserEnvironment, category: str) -> tuple[bool, str]:
    """Remove a reference for a category.

    Args:
        env: The user environment.
        category: Category to remove reference for.

    Returns:
        Tuple of (success, message).
    """
    if category not in env.reference_projects:
        return False, f"No reference set for category: {category}"

    path = env.reference_projects[category]
    env.remove_reference(category)
    return True, f"Removed reference for '{category}' (was: {path.name})"


def list_references(env: UserEnvironment) -> list[dict]:
    """List all reference projects with details.

    Args:
        env: The user environment.

    Returns:
        List of reference info dictionaries.
    """
    refs: list[dict] = []

    for category, path in env.reference_projects.items():
        project = env.get_project(path)
        refs.append({
            "category": category,
            "path": path,
            "name": project.name if project else path.name,
            "health_score": project.health_score if project else None,
            "exists": project is not None,
            "healthy": (
                project is not None
                and project.health_score is not None
                and project.health_score >= REFERENCE_HEALTH_WARNING
            ),
        })

    return refs


# =============================================================================
# Reference Usage
# =============================================================================


def get_reference_for_new_project(
    env: UserEnvironment,
    project_type: str,
) -> ProjectEntry | None:
    """Get the reference project to use when creating a new project.

    Returns the reference for the exact type if available, otherwise
    returns None.

    Args:
        env: The user environment.
        project_type: Type of project being created.

    Returns:
        ProjectEntry to use as reference, or None.
    """
    return env.get_reference_for(project_type)


def find_similar_references(
    env: UserEnvironment,
    project: ProjectEntry,
) -> list[ProjectEntry]:
    """Find reference projects similar to the given project.

    Returns references of the same type, sorted by health.

    Args:
        env: The user environment.
        project: The project to find references for.

    Returns:
        List of similar reference projects.
    """
    similar = env.find_similar(project.path)

    # Filter to reference projects only
    refs = [p for p in similar if p.is_reference]

    # Sort by health (highest first)
    return sorted(
        refs,
        key=lambda p: p.health_score or 0,
        reverse=True,
    )
