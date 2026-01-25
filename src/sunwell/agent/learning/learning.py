"""Learning dataclass for agent execution."""

from dataclasses import dataclass


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

    @property
    def id(self) -> str:
        """Unique ID for this learning."""
        import hashlib

        content = f"{self.category}:{self.fact}"
        return hashlib.blake2b(content.encode(), digest_size=6).hexdigest()
