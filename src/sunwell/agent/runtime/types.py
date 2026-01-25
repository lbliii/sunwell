"""Runtime type definitions and protocols.

This module contains shared protocols and types for the runtime package.
"""

from pathlib import Path
from typing import Protocol, Self


class Saveable(Protocol):
    """Protocol for objects that can be saved/loaded to files.

    Implemented by:
    - EpisodeSnapshot
    - EpisodeChain
    - HandoffState
    """

    def save(self, path: Path) -> None:
        """Save object state to a file."""
        ...

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load object state from a file."""
        ...
