"""Project-centric workspace isolation (RFC-117).

This module provides explicit project binding for all file operations,
eliminating the class of bugs where agent content pollutes Sunwell's
own source tree.

Phase 1: Self-pollution guard (immediate safety)
Phase 2+: Full project model (see RFC-117)
"""

from sunwell.project.validation import (
    ProjectValidationError,
    validate_not_sunwell_repo,
)

__all__ = [
    "ProjectValidationError",
    "validate_not_sunwell_repo",
]
