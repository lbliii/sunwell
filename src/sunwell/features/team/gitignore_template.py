"""ensure_sunwell_structure stub (team feature removed)."""

from pathlib import Path


def ensure_sunwell_structure(project_root: Path) -> None:
    """No-op: ensure .sunwell exists. Team feature was removed."""
    (project_root / ".sunwell").mkdir(parents=True, exist_ok=True)
