"""Client for interacting with Sunwell founts."""


from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sunwell.foundation.errors import ErrorCode, SunwellError

if TYPE_CHECKING:
    from sunwell.features.fount.cache import FountCache


@runtime_checkable
class FountProtocol(Protocol):
    """Protocol for fount clients."""

    async def fetch(self, source: str, version: str | None = None) -> str:
        """Fetch raw lens YAML from the fount."""
        ...

    async def publish(self, name: str, content: str, version: str) -> None:
        """Publish a lens to the fount."""
        ...


@dataclass(slots=True)
class FountClient:
    """Standard implementation of the Sunwell fount client."""

    base_url: str = "https://fount.sunwell.ai"
    cache: FountCache | None = None

    async def fetch(self, source: str, version: str | None = None) -> str:
        """Fetch lens from fount, using cache if available.

        Args:
            source: Lens name (e.g., 'nvidia/tech-writer')
            version: Optional version string

        Returns:
            Raw lens YAML content
        """
        from sunwell.core.types.types import LensReference
        ref = LensReference(source=source, version=version)

        # 1. Check cache
        if self.cache:
            cached = self.cache.get(ref)
            if cached:
                return cached

        # 2. Fetch from remote (Simulated for now)
        # TODO: Implement real HTTP fetch once server exists
        content = await self._mock_fetch(source, version)

        # 3. Store in cache
        if self.cache:
            self.cache.set(ref, content)

        return content

    async def publish(self, name: str, content: str, version: str) -> None:
        """Publish a lens to the fount."""
        # TODO: Implement real HTTP publish
        raise SunwellError(
            code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
            context={"detail": "Publishing to remote fount not yet implemented"},
        )

    async def _mock_fetch(self, source: str, version: str | None) -> str:
        """Temporary mock for fetching remote lenses."""
        # For development, we can mock some common lenses
        if source == "sunwell/base-writer":
            return """
lens:
  metadata:
    name: "Base Writer"
    version: "1.0.0"
  heuristics:
    - name: "Signal over Noise"
      rule: "Every sentence must earn its place"
"""

        raise SunwellError(
            code=ErrorCode.LENS_NOT_FOUND,
            context={"lens": source, "path": "fount", "detail": "Simulated client"},
        )
