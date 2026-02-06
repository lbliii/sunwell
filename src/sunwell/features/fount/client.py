"""Client for interacting with Sunwell founts."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import httpx

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
    """Standard implementation of the Sunwell fount client.

    The fount is a remote lens registry. This client fetches and publishes
    lenses via HTTP. The API follows REST conventions:

        GET  /api/v1/lenses/{owner}/{name}?version={version}
        POST /api/v1/lenses/{owner}/{name}

    When the fount server is unavailable, falls back to mock responses
    for known development lenses.
    """

    base_url: str = "https://fount.sunwell.ai"
    cache: FountCache | None = None
    timeout: float = 30.0
    _mock_fetch_override: Callable[[str, str | None], str] | None = field(
        default=None, repr=False, compare=False
    )

    async def fetch(self, source: str, version: str | None = None) -> str:
        """Fetch lens from fount, using cache if available.

        Args:
            source: Lens name (e.g., 'nvidia/tech-writer')
            version: Optional version string (defaults to latest)

        Returns:
            Raw lens YAML content

        Raises:
            SunwellError: If lens not found or fount unavailable
        """
        from sunwell.core.types.types import LensReference

        ref = LensReference(source=source, version=version)

        # 1. Check cache first
        if self.cache:
            cached = self.cache.get(ref)
            if cached:
                return cached

        # 2. Allow test override
        if self._mock_fetch_override:
            content = await self._mock_fetch_override(source, version)
            if self.cache:
                self.cache.set(ref, content)
            return content

        # 3. Fetch from remote fount
        content = await self._http_fetch(source, version)

        # 4. Store in cache
        if self.cache:
            self.cache.set(ref, content)

        return content

    async def publish(self, name: str, content: str, version: str) -> None:
        """Publish a lens to the fount.

        Args:
            name: Lens name (e.g., 'myorg/my-lens')
            content: Raw lens YAML content
            version: Version string (e.g., '1.0.0')

        Raises:
            SunwellError: If publish fails or fount unavailable
        """
        await self._http_publish(name, content, version)

    async def _http_fetch(self, source: str, version: str | None) -> str:
        """Fetch lens via HTTP from the fount server."""
        # Parse owner/name from source
        if "/" not in source:
            raise SunwellError(
                code=ErrorCode.LENS_NOT_FOUND,
                context={
                    "lens": source,
                    "detail": "Lens source must be in format 'owner/name'",
                },
            )

        url = f"{self.base_url}/api/v1/lenses/{source}"
        params = {"version": version} if version else {}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code == 404:
                    raise SunwellError(
                        code=ErrorCode.LENS_NOT_FOUND,
                        context={"lens": source, "version": version},
                    )

                if response.status_code != 200:
                    raise SunwellError(
                        code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
                        context={
                            "lens": source,
                            "status": response.status_code,
                            "detail": response.text[:200],
                        },
                    )

                return response.text

        except httpx.ConnectError:
            # Fount server not reachable - fall back to mock for dev lenses
            return await self._mock_fetch(source, version)
        except httpx.TimeoutException:
            raise SunwellError(
                code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
                context={"lens": source, "detail": "Request timed out"},
            )

    async def _http_publish(self, name: str, content: str, version: str) -> None:
        """Publish lens via HTTP to the fount server."""
        if "/" not in name:
            raise SunwellError(
                code=ErrorCode.LENS_INVALID,
                context={
                    "lens": name,
                    "detail": "Lens name must be in format 'owner/name'",
                },
            )

        url = f"{self.base_url}/api/v1/lenses/{name}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json={"content": content, "version": version},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 401:
                    raise SunwellError(
                        code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
                        context={"detail": "Authentication required to publish"},
                    )

                if response.status_code == 409:
                    raise SunwellError(
                        code=ErrorCode.LENS_INVALID,
                        context={
                            "lens": name,
                            "version": version,
                            "detail": "Version already exists",
                        },
                    )

                if response.status_code not in (200, 201):
                    raise SunwellError(
                        code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
                        context={
                            "lens": name,
                            "status": response.status_code,
                            "detail": response.text[:200],
                        },
                    )

        except httpx.ConnectError:
            raise SunwellError(
                code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
                context={"detail": "Cannot connect to fount server"},
            )
        except httpx.TimeoutException:
            raise SunwellError(
                code=ErrorCode.LENS_FOUNT_UNAVAILABLE,
                context={"detail": "Request timed out"},
            )

    async def _mock_fetch(self, source: str, version: str | None) -> str:
        """Fallback mock for development when fount server is unavailable."""
        # Built-in development lenses
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
            context={"lens": source, "path": "fount", "detail": "Fount unavailable"},
        )
