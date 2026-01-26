"""Learning dataclass for agent execution."""

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Learning:
    """A fact learned from generated code or fix attempts."""

    fact: str
    """The learned fact (e.g., "User.id is Integer primary key")."""

    category: str
    """Category: type, api, pattern, fix."""

    confidence: float = 0.8
    """Confidence in this learning (0-1)."""

    source_file: str | None = None
    """File this was learned from."""

    source_line: int | None = None
    """Line number if applicable."""

    # Cached ID to avoid recomputing hash on every access
    _id_cache: str | None = field(default=None, compare=False, hash=False, repr=False)

    @property
    def id(self) -> str:
        """Unique ID for this learning (cached, content-addressable)."""
        if self._id_cache is None:
            content = f"{self.category}:{self.fact}"
            # Use object.__setattr__ to bypass frozen restriction
            object.__setattr__(
                self,
                "_id_cache",
                hashlib.blake2b(content.encode(), digest_size=6).hexdigest(),
            )
        return self._id_cache  # type: ignore[return-value]
