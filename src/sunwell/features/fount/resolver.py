"""LensResolver stub (fount feature removed)."""

from pathlib import Path

from sunwell.foundation.schema.models.types import LensReference


class LensResolver:
    """LensResolver stub - resolves local paths only (fount removed)."""

    def __init__(self, loader) -> None:
        self.loader = loader

    async def resolve(self, ref: LensReference) -> object | None:
        """Resolve lens from local path. Remote fount resolution disabled."""
        source = ref.source or ""
        path = Path(source)
        if not path.is_absolute():
            path = Path.cwd() / source
        if not path.exists() and not path.suffix:
            path = path.with_suffix(".lens")
        if path.exists():
            return self.loader.load(path)
        return None
