"""Lens usage tracking (RFC-100).

Tracks lens activations locally for discovery features like sparklines.

Storage: ~/.sunwell/usage.json
Privacy: All tracking is local-only. No data leaves the device.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


def _get_usage_path() -> Path:
    """Get the path to the usage tracking file."""
    return Path.home() / ".sunwell" / "usage.json"


def _load_usage_data() -> dict:
    """Load usage data from disk."""
    path = _get_usage_path()
    if not path.exists():
        return {"lens_activations": {}}

    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"lens_activations": {}}


def _save_usage_data(data: dict) -> None:
    """Save usage data to disk."""
    path = _get_usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def record_lens_activation(lens_name: str) -> None:
    """Record that a lens was activated.

    Args:
        lens_name: Name of the lens that was activated
    """
    data = _load_usage_data()
    activations = data.setdefault("lens_activations", {})

    # Get or create lens entry
    lens_entries = activations.setdefault(lens_name, [])

    # Add current timestamp
    now = datetime.now().isoformat()
    lens_entries.append(now)

    # Keep only last 30 days of activations
    cutoff = datetime.now() - timedelta(days=30)
    activations[lens_name] = [
        ts for ts in lens_entries
        if datetime.fromisoformat(ts) > cutoff
    ]

    _save_usage_data(data)


def get_lens_usage(lens_name: str) -> dict:
    """Get usage data for a lens.

    Args:
        lens_name: Name of the lens

    Returns:
        dict with:
            - last_used: ISO timestamp of last activation (or None)
            - history: List of 7 numbers representing daily usage counts
    """
    data = _load_usage_data()
    activations = data.get("lens_activations", {}).get(lens_name, [])

    if not activations:
        return {"last_used": None, "history": []}

    # Parse timestamps
    timestamps = []
    for ts in activations:
        try:
            timestamps.append(datetime.fromisoformat(ts))
        except ValueError:
            continue

    if not timestamps:
        return {"last_used": None, "history": []}

    timestamps.sort()
    last_used = timestamps[-1].isoformat()

    # Calculate daily usage for last 7 days
    today = datetime.now().date()
    history = []
    for i in range(6, -1, -1):  # 6 days ago to today
        day = today - timedelta(days=i)
        count = sum(
            1 for ts in timestamps
            if ts.date() == day
        )
        history.append(count)

    return {
        "last_used": last_used,
        "history": history,
    }


def get_most_used_lenses(limit: int = 5) -> list[tuple[str, int]]:
    """Get the most frequently used lenses.

    Args:
        limit: Maximum number of lenses to return

    Returns:
        List of (lens_name, total_activations) tuples, sorted by usage
    """
    data = _load_usage_data()
    activations = data.get("lens_activations", {})

    usage_counts = [
        (name, len(entries))
        for name, entries in activations.items()
    ]

    usage_counts.sort(key=lambda x: x[1], reverse=True)
    return usage_counts[:limit]


def clear_usage_data() -> None:
    """Clear all usage tracking data."""
    path = _get_usage_path()
    if path.exists():
        path.unlink()
