"""DeadEnd dataclass for tracking failed approaches."""

import hashlib
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

    @property
    def id(self) -> str:
        """Unique ID for this dead end (content-addressable)."""
        content = f"{self.approach}:{self.reason}:{self.gate or ''}"
        return hashlib.blake2b(content.encode(), digest_size=6).hexdigest()
