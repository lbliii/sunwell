"""Generic string manipulation utilities.

RFC-138: Module Architecture Consolidation
"""

import re


def slugify(name: str) -> str:
    """Convert a display name to a filesystem-safe slug.

    Args:
        name: Human-readable name

    Returns:
        Lowercase slug with hyphens
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"
