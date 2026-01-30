"""Append-only journal for durable learning persistence.

Provides immediate durability for learnings by appending to a JSONL file
before yielding events. This ensures learnings survive crashes.

Journal format: One JSON object per line (JSONL)
```
{"id": "abc123", "fact": "...", "category": "...", "confidence": 0.9, "timestamp": "..."}
```

Recovery: On startup, replay journal entries after last checkpoint.
Compaction: Periodically write checkpoint and truncate journal.
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.agent.learning.learning import Learning

logger = logging.getLogger(__name__)

# Default journal filename
JOURNAL_FILENAME = "learnings.jsonl"

# Default checkpoint directory
CHECKPOINT_DIR = "checkpoints"


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A single entry in the learning journal."""

    id: str
    """Learning ID (content-addressable hash)."""

    fact: str
    """The learned fact."""

    category: str
    """Category: type, api, pattern, fix, preference, etc."""

    confidence: float
    """Confidence score (0-1)."""

    timestamp: str
    """ISO timestamp when this was recorded."""

    source_file: str | None = None
    """Source file if applicable."""

    source_line: int | None = None
    """Source line if applicable."""

    @classmethod
    def from_learning(cls, learning: Learning) -> "JournalEntry":
        """Create a journal entry from a Learning object."""
        return cls(
            id=learning.id,
            fact=learning.fact,
            category=learning.category,
            confidence=learning.confidence,
            source_file=learning.source_file,
            source_line=learning.source_line,
            timestamp=datetime.now().isoformat(),
        )

    def to_json(self) -> str:
        """Serialize to JSON string (one line, no trailing newline)."""
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> "JournalEntry":
        """Deserialize from JSON string."""
        data = json.loads(line)
        return cls(**data)

    def to_learning(self) -> "Learning":
        """Convert back to a Learning object."""
        from sunwell.agent.learning.learning import Learning

        return Learning(
            fact=self.fact,
            category=self.category,
            confidence=self.confidence,
            source_file=self.source_file,
            source_line=self.source_line,
        )


class LearningJournal:
    """Append-only journal for durable learning persistence.

    Thread-safe (3.14t compatible) via lock on write operations.

    Usage:
        journal = LearningJournal(workspace / ".sunwell" / "memory")
        journal.append(learning)  # Immediately durable
        learnings = journal.load_all()  # Recovery on startup
    """

    def __init__(self, memory_dir: Path) -> None:
        """Initialize journal.

        Args:
            memory_dir: Directory for memory storage (e.g., workspace/.sunwell/memory)
        """
        self._memory_dir = Path(memory_dir)
        self._journal_path = self._memory_dir / JOURNAL_FILENAME
        self._checkpoint_dir = self._memory_dir / CHECKPOINT_DIR
        self._lock = threading.Lock()

        # Ensure directory exists
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    @property
    def journal_path(self) -> Path:
        """Path to the journal file."""
        return self._journal_path

    def append(self, learning: Learning) -> None:
        """Append a learning to the journal (thread-safe, durable).

        This is the critical path for durability - the learning is written
        to disk before this method returns.

        Args:
            learning: The learning to persist
        """
        entry = JournalEntry.from_learning(learning)
        line = entry.to_json() + "\n"

        with self._lock:
            # Open in append mode, write, and flush to OS buffer
            with self._journal_path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                # Ensure durability by syncing to disk
                os.fsync(f.fileno())

    def append_batch(self, learnings: list[Learning]) -> int:
        """Append multiple learnings atomically (thread-safe).

        Args:
            learnings: List of learnings to persist

        Returns:
            Number of learnings appended
        """
        if not learnings:
            return 0

        lines = [JournalEntry.from_learning(l).to_json() + "\n" for l in learnings]

        with self._lock:
            with self._journal_path.open("a", encoding="utf-8") as f:
                f.writelines(lines)
                f.flush()
                os.fsync(f.fileno())

        return len(lines)

    def load_all(self) -> list[JournalEntry]:
        """Load all entries from the journal.

        Returns:
            List of journal entries (may contain duplicates by ID)
        """
        if not self._journal_path.exists():
            return []

        entries: list[JournalEntry] = []
        with self._journal_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(JournalEntry.from_json(line))
                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    logger.warning(
                        "Skipping malformed journal entry at line %d: %s",
                        line_num,
                        e,
                    )

        return entries

    def load_deduplicated(self) -> dict[str, JournalEntry]:
        """Load entries deduplicated by ID (latest entry wins).

        Returns:
            Dict mapping learning ID to most recent entry
        """
        entries = self.load_all()
        # Last entry for each ID wins (handles updates/corrections)
        return {e.id: e for e in entries}

    def load_as_learnings(self) -> list[Learning]:
        """Load journal and convert to Learning objects (deduplicated).

        Returns:
            List of unique Learning objects
        """
        deduplicated = self.load_deduplicated()
        return [entry.to_learning() for entry in deduplicated.values()]

    def load_since(self, after_timestamp: str) -> list[JournalEntry]:
        """Load entries after a given timestamp.

        Args:
            after_timestamp: ISO timestamp string

        Returns:
            List of entries with timestamp > after_timestamp
        """
        entries = self.load_all()
        return [e for e in entries if e.timestamp > after_timestamp]

    def count(self) -> int:
        """Count total entries in journal (including duplicates)."""
        if not self._journal_path.exists():
            return 0

        with self._journal_path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def size_bytes(self) -> int:
        """Get journal file size in bytes."""
        if not self._journal_path.exists():
            return 0
        return self._journal_path.stat().st_size

    def truncate(self) -> None:
        """Truncate the journal (use after checkpoint).

        WARNING: This removes all data from the journal.
        Only call after successfully writing a checkpoint.
        """
        with self._lock:
            self._journal_path.write_text("", encoding="utf-8")

    def exists(self) -> bool:
        """Check if journal file exists."""
        return self._journal_path.exists()


# =============================================================================
# Module-level convenience functions
# =============================================================================


def get_journal(workspace: Path) -> LearningJournal:
    """Get a LearningJournal for a workspace.

    Args:
        workspace: Project workspace root

    Returns:
        LearningJournal instance
    """
    memory_dir = workspace / ".sunwell" / "memory"
    return LearningJournal(memory_dir)


def append_learning(workspace: Path, learning: Learning) -> None:
    """Append a learning to the workspace journal.

    Convenience function for one-off appends.

    Args:
        workspace: Project workspace root
        learning: Learning to persist
    """
    journal = get_journal(workspace)
    journal.append(learning)
