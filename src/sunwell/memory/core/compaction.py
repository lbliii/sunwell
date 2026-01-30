"""Compaction for journal-based learning storage.

Prevents unbounded journal growth by:
1. Writing checkpoints with all learnings
2. Truncating the journal after checkpoint
3. Keeping N recent checkpoints

Compaction can be triggered:
- Manually via compact()
- Automatically when journal exceeds size threshold
- On a schedule (e.g., daily)
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.core.journal import (
    CHECKPOINT_DIR,
    JournalEntry,
    LearningJournal,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_ENTRY_THRESHOLD = 10000  # 10,000 entries
DEFAULT_KEEP_CHECKPOINTS = 7  # Keep last 7 checkpoints


@dataclass(frozen=True, slots=True)
class CompactionResult:
    """Result of a compaction operation."""

    checkpoint_path: Path
    """Path to the created checkpoint."""

    entries_compacted: int
    """Number of journal entries compacted."""

    checkpoints_pruned: int
    """Number of old checkpoints deleted."""

    bytes_freed: int
    """Approximate bytes freed by compaction."""


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """A checkpoint containing compacted learnings."""

    timestamp: str
    """ISO timestamp when checkpoint was created."""

    entries: tuple[dict, ...]
    """Serialized journal entries."""

    metadata: dict
    """Additional metadata (version, source, etc.)."""

    @classmethod
    def from_entries(
        cls,
        entries: list[JournalEntry],
        metadata: dict | None = None,
    ) -> "Checkpoint":
        """Create a checkpoint from journal entries."""
        return cls(
            timestamp=datetime.now().isoformat(),
            entries=tuple(asdict(e) for e in entries),
            metadata=metadata or {},
        )

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "entries": self.entries,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_json(cls, data: str) -> "Checkpoint":
        """Deserialize from JSON."""
        obj = json.loads(data)
        return cls(
            timestamp=obj["timestamp"],
            entries=tuple(obj["entries"]),
            metadata=obj.get("metadata", {}),
        )

    def get_entries(self) -> list[JournalEntry]:
        """Convert stored entries back to JournalEntry objects."""
        return [JournalEntry(**e) for e in self.entries]


class JournalCompactor:
    """Handles compaction of the learning journal.

    Usage:
        compactor = JournalCompactor(workspace / ".sunwell" / "memory")
        if compactor.should_compact():
            result = compactor.compact()
    """

    def __init__(
        self,
        memory_dir: Path,
        size_threshold: int = DEFAULT_SIZE_THRESHOLD_BYTES,
        entry_threshold: int = DEFAULT_ENTRY_THRESHOLD,
        keep_checkpoints: int = DEFAULT_KEEP_CHECKPOINTS,
    ) -> None:
        """Initialize compactor.

        Args:
            memory_dir: Memory directory (workspace/.sunwell/memory)
            size_threshold: Compact when journal exceeds this size (bytes)
            entry_threshold: Compact when journal exceeds this many entries
            keep_checkpoints: Number of recent checkpoints to keep
        """
        self._memory_dir = Path(memory_dir)
        self._checkpoint_dir = self._memory_dir / CHECKPOINT_DIR
        self._journal = LearningJournal(memory_dir)
        self._size_threshold = size_threshold
        self._entry_threshold = entry_threshold
        self._keep_checkpoints = keep_checkpoints

    def should_compact(self) -> bool:
        """Check if compaction is needed.

        Returns:
            True if journal exceeds size or entry threshold
        """
        if not self._journal.exists():
            return False

        # Check size threshold
        if self._journal.size_bytes() >= self._size_threshold:
            return True

        # Check entry threshold (more expensive, check second)
        if self._journal.count() >= self._entry_threshold:
            return True

        return False

    def compact(self, force: bool = False) -> CompactionResult | None:
        """Run compaction.

        1. Load all journal entries
        2. Write checkpoint with deduplicated entries
        3. Truncate journal
        4. Prune old checkpoints

        Args:
            force: Compact even if thresholds not met

        Returns:
            CompactionResult or None if nothing to compact
        """
        if not force and not self.should_compact():
            return None

        if not self._journal.exists():
            return None

        # Record pre-compaction size
        pre_size = self._journal.size_bytes()

        # Load and deduplicate entries
        entries_dict = self._journal.load_deduplicated()
        entries = list(entries_dict.values())

        if not entries:
            return None

        # Create checkpoint
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = Checkpoint.from_entries(
            entries,
            metadata={
                "version": 1,
                "source": "compaction",
                "entry_count": len(entries),
            },
        )

        # Write checkpoint with timestamp-based name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        checkpoint_path = self._checkpoint_dir / f"{timestamp}.checkpoint.json"
        checkpoint_path.write_text(checkpoint.to_json(), encoding="utf-8")

        # Truncate journal
        self._journal.truncate()

        # Prune old checkpoints
        pruned = self._prune_old_checkpoints()

        return CompactionResult(
            checkpoint_path=checkpoint_path,
            entries_compacted=len(entries),
            checkpoints_pruned=pruned,
            bytes_freed=pre_size,
        )

    def _prune_old_checkpoints(self) -> int:
        """Delete old checkpoints, keeping only the most recent N.

        Returns:
            Number of checkpoints deleted
        """
        if not self._checkpoint_dir.exists():
            return 0

        checkpoints = sorted(
            self._checkpoint_dir.glob("*.checkpoint.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # Newest first
        )

        # Keep the most recent N
        to_delete = checkpoints[self._keep_checkpoints:]
        for checkpoint in to_delete:
            try:
                checkpoint.unlink()
            except OSError as e:
                logger.warning("Failed to delete checkpoint %s: %s", checkpoint, e)

        return len(to_delete)

    def get_latest_checkpoint(self) -> Checkpoint | None:
        """Load the most recent checkpoint.

        Returns:
            Latest Checkpoint or None if no checkpoints exist
        """
        if not self._checkpoint_dir.exists():
            return None

        checkpoints = sorted(
            self._checkpoint_dir.glob("*.checkpoint.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not checkpoints:
            return None

        try:
            return Checkpoint.from_json(checkpoints[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load checkpoint: %s", e)
            return None

    def recover_from_checkpoint(self) -> list[JournalEntry]:
        """Recover entries from the latest checkpoint.

        Used for startup recovery when journal is empty but checkpoint exists.

        Returns:
            List of recovered journal entries
        """
        checkpoint = self.get_latest_checkpoint()
        if checkpoint:
            return checkpoint.get_entries()
        return []

    def list_checkpoints(self) -> list[Path]:
        """List all checkpoints, newest first.

        Returns:
            List of checkpoint paths
        """
        if not self._checkpoint_dir.exists():
            return []

        return sorted(
            self._checkpoint_dir.glob("*.checkpoint.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def compact_if_needed(workspace: Path) -> CompactionResult | None:
    """Compact the journal if thresholds are exceeded.

    Args:
        workspace: Project workspace root

    Returns:
        CompactionResult or None if no compaction needed
    """
    memory_dir = workspace / ".sunwell" / "memory"
    compactor = JournalCompactor(memory_dir)
    return compactor.compact()


def force_compact(workspace: Path) -> CompactionResult | None:
    """Force compaction regardless of thresholds.

    Args:
        workspace: Project workspace root

    Returns:
        CompactionResult or None if journal is empty
    """
    memory_dir = workspace / ".sunwell" / "memory"
    compactor = JournalCompactor(memory_dir)
    return compactor.compact(force=True)
