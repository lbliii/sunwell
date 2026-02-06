"""Serialization and persistence protocols.

Extracted from sunwell.foundation.types.protocol per the Contracts Layer plan.
This module imports ONLY from stdlib.
"""

from pathlib import Path
from typing import Any, Protocol, Self


class Serializable(Protocol):
    """Protocol for objects that can serialize to dict.

    Consolidated from: routing, project/types, providers/base,
    interface/types, incremental/events, backlog/tracker.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        ...


class DictSerializable(Protocol):
    """Protocol for types that serialize to/from dicts (bidirectional).

    Consolidated from: lens/identity, environment/model.
    Use this when you need both serialization AND deserialization.
    """

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        """Create instance from dictionary representation."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        ...


class Promptable(Protocol):
    """Protocol for objects that can be formatted into prompts.

    Consolidated from: memory/core/types.
    Implemented by: MemoryContext, TaskMemoryContext, Briefing.
    """

    def to_prompt(self) -> str:
        """Format this object for inclusion in an LLM prompt."""
        ...


class Embeddable(Protocol):
    """Protocol for types that can be converted to text for embedding/search.

    Consolidated from: features/team/types.
    Implemented by: TeamDecision, TeamFailure.
    """

    def to_text(self) -> str:
        """Convert to text suitable for embedding generation."""
        ...


class Saveable(Protocol):
    """Protocol for objects that can be saved/loaded to files.

    Consolidated from: agent/runtime/types.
    Implemented by: EpisodeSnapshot, EpisodeChain, HandoffState.
    """

    def save(self, path: Path) -> None:
        """Save object state to a file."""
        ...

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load object state from a file."""
        ...
