"""Parser for tool profile configuration (RFC-XXX: Multi-Signal Tool Selection)."""

from typing import Any

from sunwell.foundation.core.lens import ToolProfile


def parse_tool_profile(data: dict[str, Any] | None) -> ToolProfile | None:
    """Parse tool_profile section from lens YAML.

    Args:
        data: Raw dict from YAML, e.g.:
            {
                "primary": ["search_files", "read_file", "edit_file"],
                "secondary": ["git_status", "git_diff"],
                "avoid": ["web_search"]
            }

    Returns:
        ToolProfile instance or None if no data
    """
    if not data:
        return None

    primary = tuple(data.get("primary", []) or [])
    secondary = tuple(data.get("secondary", []) or [])
    avoid = tuple(data.get("avoid", []) or [])

    # Only return a profile if at least one field is set
    if not primary and not secondary and not avoid:
        return None

    return ToolProfile(
        primary=primary,
        secondary=secondary,
        avoid=avoid,
    )
