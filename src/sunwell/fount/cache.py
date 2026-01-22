"""Local cache for lenses fetched from the fount (RFC-094: thread-safe with integrity verification)."""


import hashlib
import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.types import LensReference


@dataclass
class FountCache:
    """Manages local storage of remote lenses with integrity verification.

    Thread-safe via internal locking. Verifies content integrity on read (RFC-094).
    """

    root: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        """Ensure cache directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "lenses").mkdir(exist_ok=True)
        (self.root / "metadata").mkdir(exist_ok=True)

    def get(self, ref: LensReference) -> str | None:
        """Get lens YAML from cache if valid.

        Returns None if:
        - Cache miss (file doesn't exist)
        - Integrity check fails (hash mismatch)
        """
        with self._lock:
            cache_path = self._get_lens_path(ref)
            meta_path = self._get_metadata_path(ref)

            if not cache_path.exists():
                return None

            content = cache_path.read_text()

            # Verify integrity if metadata exists
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    expected_hash = meta.get("content_hash")
                    if expected_hash:
                        actual_hash = hashlib.blake2b(
                            content.encode(), digest_size=16
                        ).hexdigest()
                        if actual_hash != expected_hash:
                            # Cache corrupted — invalidate
                            cache_path.unlink(missing_ok=True)
                            meta_path.unlink(missing_ok=True)
                            return None
                except (json.JSONDecodeError, OSError):
                    pass  # Metadata corrupted, but content may still be valid

            return content

    def set(self, ref: LensReference, content: str, metadata: dict | None = None) -> None:
        """Save lens YAML with content hash for integrity verification."""
        with self._lock:
            self._get_lens_path(ref).write_text(content)

            # Always store content hash for integrity verification
            meta = metadata.copy() if metadata else {}
            meta["content_hash"] = hashlib.blake2b(
                content.encode(), digest_size=16
            ).hexdigest()
            self._get_metadata_path(ref).write_text(json.dumps(meta, indent=2))

    def clear(self) -> None:
        """Clear all cached lenses."""
        with self._lock:
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
