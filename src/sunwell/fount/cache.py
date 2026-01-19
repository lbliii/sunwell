"""Local cache for lenses fetched from the fount."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.types import LensReference


@dataclass
class FountCache:
    """Manages local storage of remote lenses."""

    root: Path

    def __post_init__(self) -> None:
        """Ensure cache directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "lenses").mkdir(exist_ok=True)
        (self.root / "metadata").mkdir(exist_ok=True)

    def get(self, ref: LensReference) -> str | None:
        """Get lens YAML from cache if it exists."""
        cache_path = self._get_lens_path(ref)
        if cache_path.exists():
            return cache_path.read_text()
        return None

    def set(self, ref: LensReference, content: str, metadata: dict | None = None) -> None:
        """Save lens YAML and metadata to cache."""
        self._get_lens_path(ref).write_text(content)
        if metadata:
            meta_path = self._get_metadata_path(ref)
            meta_path.write_text(json.dumps(metadata, indent=2))

    def clear(self) -> None:
        """Clear all cached lenses."""
        if self.root.exists():
            shutil.rmtree(self.root)
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / "lenses").mkdir(exist_ok=True)
            (self.root / "metadata").mkdir(exist_ok=True)

    def _get_lens_path(self, ref: LensReference) -> Path:
        """Get filesystem path for a lens in the cache."""
        # Sanitize name for filesystem
        safe_name = ref.source.replace("/", "__").replace(":", "__")
        if ref.version:
            safe_name = f"{safe_name}@{ref.version}"
        return self.root / "lenses" / f"{safe_name}.lens"

    def _get_metadata_path(self, ref: LensReference) -> Path:
        """Get filesystem path for lens metadata in the cache."""
        # Sanitize name for filesystem
        safe_name = ref.source.replace("/", "__").replace(":", "__")
        if ref.version:
            safe_name = f"{safe_name}@{ref.version}"
        return self.root / "metadata" / f"{safe_name}.json"
