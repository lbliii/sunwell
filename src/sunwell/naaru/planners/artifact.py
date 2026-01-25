"""Artifact-first planner for RFC-036.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from `sunwell.naaru.planners.artifact` instead.

This module provides artifact-first planning: instead of decomposing goals into
steps, it identifies what artifacts must exist when the goal is complete.
Dependency resolution then determines execution order.

Migration guide:
    # Old (still works)
    from sunwell.naaru.planners.artifact import ArtifactPlanner

    # New (same import, but now from package)
    from sunwell.naaru.planners.artifact import ArtifactPlanner
"""

# Re-export everything from the new modular structure for backward compatibility
from sunwell.naaru.planners.artifact import ArtifactPlanner

__all__ = ["ArtifactPlanner"]
