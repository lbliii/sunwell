"""Self-Knowledge Architecture for Sunwell.

RFC-085: Enables Sunwell to understand, debug, and improve itself.

The `Self` singleton provides unified access to self-knowledge capabilities:
- Source introspection (read/search/explain Sunwell's code)
- Analysis (failure diagnosis, pattern detection, performance tracking)
- Proposals (safe self-improvement with sandbox testing)

Usage:
    >>> from sunwell.self import Self
    >>> Self.get().source.read_module("sunwell.tools.executor")
    >>> Self.get().analysis.recent_failures()
    >>> Self.get().proposals.create(...)

Thread-safe under Python 3.14t free-threading.
"""

import threading
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.self.analysis import AnalysisKnowledge
    from sunwell.self.proposals import ProposalManager
    from sunwell.self.source import SourceKnowledge


@dataclass(slots=True)
class Self:
    """Sunwell's self-knowledge service.

    Singleton — there is exactly one Sunwell installation to know about.
    Auto-resolves source location from package metadata.

    Thread-safe under Python 3.14t free-threading via double-checked locking.

    Access via Self.get():
        >>> Self.get().source.read_module("sunwell.tools.executor")
        >>> Self.get().analysis.recent_failures()
        >>> Self.get().proposals.create(...)

    Note: Not frozen because cached_property requires mutability.
    """

    _source_root: Path
    _storage_root: Path

    # === Components (lazy-initialized) ===

    @cached_property
    def source(self) -> SourceKnowledge:
        """Read and understand Sunwell's source code."""
        from sunwell.self.source import SourceKnowledge

        return SourceKnowledge(self._source_root)

    @cached_property
    def analysis(self) -> AnalysisKnowledge:
        """Analyze Sunwell's behavior and performance."""
        from sunwell.self.analysis import AnalysisKnowledge

        return AnalysisKnowledge(self._storage_root / "analysis")

    @cached_property
    def proposals(self) -> ProposalManager:
        """Create and manage self-improvement proposals."""
        from sunwell.self.proposals import ProposalManager

        return ProposalManager(
            source_root=self._source_root,
            storage_root=self._storage_root / "proposals",
        )

    # === Thread-Safe Singleton Access (3.14t compatible) ===

    _instance: Self | None = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get(cls) -> Self:
        """Get the global Self instance (thread-safe).

        Uses double-checked locking for performance:
        - Fast path: no lock if already initialized
        - Slow path: lock only during first initialization
        """
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            # Double-check after acquiring lock
            if cls._instance is None:
                cls._instance = cls._create_default()
            return cls._instance

    @classmethod
    def _create_default(cls) -> Self:
        """Create Self with auto-resolved paths."""
        import sunwell

        # sunwell/__init__.py → src/sunwell → src → <project_root>
        source_root = Path(sunwell.__file__).parent.parent.parent

        # Global storage in ~/.sunwell/ (not per-workspace)
        storage_root = Path.home() / ".sunwell" / "self"
        storage_root.mkdir(parents=True, exist_ok=True)

        return cls(
            _source_root=source_root,
            _storage_root=storage_root,
        )

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing).

        Thread-safe — acquires lock before clearing.
        """
        with cls._lock:
            cls._instance = None

    @classmethod
    def _create_for_testing(cls, source_root: Path, storage_root: Path) -> Self:
        """Create Self with explicit paths (for testing only).

        This does NOT set the singleton instance — use for isolated tests.
        """
        return cls(
            _source_root=source_root,
            _storage_root=storage_root,
        )

    @property
    def source_root(self) -> Path:
        """Get the Sunwell source root directory."""
        return self._source_root

    @property
    def storage_root(self) -> Path:
        """Get the self-knowledge storage root directory."""
        return self._storage_root


__all__ = ["Self"]
