"""Timestamp utilities for consistent temporal formatting.

First-person voice requires absolute timestamps ("On Feb 2") instead of
relative time ("yesterday") because relative time becomes stale as soon
as time passes.
"""

from datetime import datetime


def absolute_timestamp(dt: datetime | None = None) -> str:
    """Format timestamp absolutely, never relatively.

    Args:
        dt: Datetime to format. Defaults to now.

    Returns:
        Absolute timestamp like "On Feb 2" or "On Feb 2, 2025"

    Examples:
        >>> absolute_timestamp(datetime(2025, 2, 2))  # In 2025
        'On Feb 2'
        >>> absolute_timestamp(datetime(2024, 12, 25))  # Previous year
        'On Dec 25, 2024'
    """
    dt = dt or datetime.now()
    if dt.year == datetime.now().year:
        return dt.strftime("On %b %-d")
    return dt.strftime("On %b %-d, %Y")


def absolute_timestamp_full(dt: datetime | None = None) -> str:
    """Format timestamp with time component.

    Args:
        dt: Datetime to format. Defaults to now.

    Returns:
        Absolute timestamp like "On Feb 2 at 3:45 PM"

    Examples:
        >>> absolute_timestamp_full(datetime(2025, 2, 2, 15, 45))
        'On Feb 2 at 3:45 PM'
    """
    dt = dt or datetime.now()
    if dt.year == datetime.now().year:
        return dt.strftime("On %b %-d at %-I:%M %p")
    return dt.strftime("On %b %-d, %Y at %-I:%M %p")


def format_for_summary(dt: datetime | None = None) -> str:
    """Format timestamp for inclusion in memory summaries.

    This is the format recommended for LLM-generated summaries.

    Args:
        dt: Datetime to format. Defaults to now.

    Returns:
        Timestamp suitable for summary text like "On Feb 2"
    """
    return absolute_timestamp(dt)
