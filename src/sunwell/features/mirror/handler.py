"""MirrorHandler stub (mirror feature removed)."""

from pathlib import Path


class MirrorHandler:
    """No-op MirrorHandler stub. Mirror feature was removed."""

    def __init__(
        self,
        workspace: Path,
        storage_path: Path | None = None,
        lens=None,
        simulacrum=None,
        executor=None,
    ) -> None:
        self.workspace = workspace
        self.storage_path = storage_path or workspace / ".sunwell" / "mirror"
        self.lens = lens
        self.simulacrum = simulacrum
        self.executor = executor

    async def handle(self, operation: str, payload: dict) -> str:
        """No-op: return empty JSON object."""
        return "{}"
