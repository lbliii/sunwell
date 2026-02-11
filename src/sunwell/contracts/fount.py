"""Fount client protocol.

Extracted from sunwell.features.fount.client per the Contracts Layer plan.
This module imports ONLY from stdlib.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class FountProtocol(Protocol):
    """Protocol for fount clients.

    The fount is a remote lens registry. This protocol defines the
    interface for fetching and publishing lenses.
    """

    async def fetch(self, source: str, version: str | None = None) -> str:
        """Fetch raw lens YAML from the fount."""
        ...

    async def publish(self, name: str, content: str, version: str) -> None:
        """Publish a lens to the fount."""
        ...
