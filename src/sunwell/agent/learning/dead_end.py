"""DeadEnd dataclass for tracking failed approaches."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeadEnd:
    """An approach that didn't work."""

    approach: str
    """What was tried."""

    reason: str
    """Why it failed."""

    context: str = ""
    """Additional context."""

    gate: str | None = None
    """Gate where this failed."""
