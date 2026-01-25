"""Generic validation utilities.

RFC-138: Module Architecture Consolidation
"""

import re

# Regex for valid slug: lowercase alphanumeric with hyphens
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_slug(slug: str) -> None:
    """Validate a slug for path traversal attacks and format.

    Args:
        slug: Slug to validate

    Raises:
        ValueError: If slug is invalid
    """
    if ".." in slug or "/" in slug or "\\" in slug or "\x00" in slug:
        raise ValueError(f"Invalid slug (path traversal): {slug}")

    if not _SLUG_PATTERN.match(slug):
        raise ValueError(f"Invalid slug format (use lowercase alphanumeric with hyphens): {slug}")
