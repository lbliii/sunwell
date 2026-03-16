"""Self singleton stub (mirror feature removed)."""

from pathlib import Path


class _AnalysisStub:
    """No-op analysis stub."""

    def record_execution(self, event) -> None:
        """No-op."""


class Self:
    """No-op Self singleton stub. Mirror feature was removed."""

    _instance: Self | None = None

    def __init__(self) -> None:
        self.source_root = Path(__file__).resolve().parents[5]
        self.storage_root = Path.home() / ".sunwell" / "self"
        self.analysis = _AnalysisStub()

    @classmethod
    def get(cls) -> Self:
        """Return singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
