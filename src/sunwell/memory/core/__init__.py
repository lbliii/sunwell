"""Core memory types and models."""

from sunwell.memory.core.compaction import (
    Checkpoint,
    CompactionResult,
    JournalCompactor,
    compact_if_needed,
    force_compact,
)
from sunwell.memory.core.embedding_worker import (
    EmbeddingQueue,
    EmbeddingQueueIntegration,
    EmbeddingWorker,
    create_embedding_worker,
)
from sunwell.memory.core.journal import (
    JournalEntry,
    LearningJournal,
    append_learning,
    get_journal,
)
from sunwell.memory.core.migration import (
    MigrationResult,
    is_migration_complete,
    migrate_if_needed,
    migrate_learnings,
)
from sunwell.memory.core.types import (
    MemoryContext,
    Promptable,
    SyncResult,
    TaskMemoryContext,
)

__all__ = [
    # Types
    "MemoryContext",
    "Promptable",
    "SyncResult",
    "TaskMemoryContext",
    # Journal
    "JournalEntry",
    "LearningJournal",
    "append_learning",
    "get_journal",
    # Embedding worker
    "EmbeddingQueue",
    "EmbeddingQueueIntegration",
    "EmbeddingWorker",
    "create_embedding_worker",
    # Compaction
    "Checkpoint",
    "CompactionResult",
    "JournalCompactor",
    "compact_if_needed",
    "force_compact",
    # Migration
    "MigrationResult",
    "is_migration_complete",
    "migrate_if_needed",
    "migrate_learnings",
]
