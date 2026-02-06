"""MCP formatting utilities for token-conscious serialization.

Provides shared helpers for format tiers (summary/compact/full),
content truncation, and compact JSON serialization across all MCP tools.
"""

from __future__ import annotations

import json
from typing import Any

# Default format tier for all tools. Can be overridden per-tool or globally.
DEFAULT_FORMAT = "compact"

# Format tier constants
FORMAT_SUMMARY = "summary"
FORMAT_COMPACT = "compact"
FORMAT_FULL = "full"

VALID_FORMATS = frozenset({FORMAT_SUMMARY, FORMAT_COMPACT, FORMAT_FULL})


def mcp_json(data: Any, format: str = DEFAULT_FORMAT) -> str:
    """Serialize to JSON with format-aware compactness.

    - summary/compact: no whitespace (separators=(",",":"))
    - full: pretty-printed (indent=2)

    All modes use default=str to handle datetimes, Paths, enums, etc.

    Args:
        data: Data to serialize
        format: Format tier (summary, compact, full)

    Returns:
        JSON string
    """
    if format == FORMAT_FULL:
        return json.dumps(data, indent=2, default=str)
    return json.dumps(data, separators=(",", ":"), default=str)


def truncate(text: str | None, max_len: int = 200) -> str:
    """Truncate text to first line, capped at max_len chars.

    Args:
        text: Text to truncate (None returns empty string)
        max_len: Maximum character length

    Returns:
        Truncated string
    """
    if not text:
        return ""
    first_line = text.split("\n")[0]
    if len(first_line) > max_len:
        return first_line[: max_len - 3] + "..."
    return first_line


def omit_empty(d: dict) -> dict:
    """Remove keys with empty/None values for compact serialization.

    Removes keys where the value is None, empty list, empty tuple,
    empty dict, or empty string.

    Args:
        d: Dictionary to compact

    Returns:
        Dictionary with empty values removed
    """
    return {k: v for k, v in d.items() if v not in (None, [], {}, "", ())}


def resolve_format(format: str | None) -> str:
    """Resolve and validate a format string.

    Args:
        format: Requested format (may be None or invalid)

    Returns:
        Valid format string, defaulting to DEFAULT_FORMAT
    """
    if not format or format.lower() not in VALID_FORMATS:
        return DEFAULT_FORMAT
    return format.lower()
