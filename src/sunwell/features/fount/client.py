"""FountClient stub (fount feature removed)."""

from sunwell.contracts.fount import FountProtocol


class FountClient(FountProtocol):
    """No-op FountClient stub. Fount feature was removed."""

    async def fetch(self, source: str, version: str | None = None) -> str:
        """No-op: raise NotImplementedError (remote fetch disabled)."""
        raise NotImplementedError("Fount remote fetch removed in Sunwell reboot")

    async def publish(self, name: str, content: str, version: str) -> None:
        """No-op."""
        pass
