"""Migration to populate journal from existing learning sources.

One-time migration that:
1. Reads learnings from SimulacrumStore DAG
2. Reads learnings from legacy .sunwell/intelligence/learnings.jsonl
3. Writes them to the new journal
4. Marks migration as complete to avoid re-running

The migration is idempotent - running it multiple times is safe
because the journal deduplicates by learning ID.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.core.journal import JournalEntry, LearningJournal

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

logger = logging.getLogger(__name__)

# Migration marker filename
MIGRATION_MARKER = ".journal_migration_complete"


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Result of a migration operation."""

    migrated_from_simulacrum: int
    """Learnings migrated from SimulacrumStore."""

    migrated_from_legacy: int
    """Learnings migrated from legacy JSONL file."""

    total_migrated: int
    """Total learnings migrated."""

    already_in_journal: int
    """Learnings that were already in the journal."""


def is_migration_complete(workspace: Path) -> bool:
    """Check if migration has already been completed.

    Args:
        workspace: Project workspace root

    Returns:
        True if migration marker exists
    """
    marker = workspace / ".sunwell" / "memory" / MIGRATION_MARKER
    return marker.exists()


def mark_migration_complete(workspace: Path) -> None:
    """Mark migration as complete.

    Args:
        workspace: Project workspace root
    """
    memory_dir = workspace / ".sunwell" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    marker = memory_dir / MIGRATION_MARKER
    marker.write_text(
        json.dumps({
            "completed_at": datetime.now().isoformat(),
            "version": 1,
        }),
        encoding="utf-8",
    )


def migrate_learnings(
    workspace: Path,
    force: bool = False,
) -> MigrationResult | None:
    """Migrate existing learnings to the journal.

    Reads from:
    1. SimulacrumStore DAG (if exists)
    2. Legacy .sunwell/intelligence/learnings.jsonl

    Writes to:
    - .sunwell/memory/learnings.jsonl (the journal)

    Args:
        workspace: Project workspace root
        force: Run migration even if already complete

    Returns:
        MigrationResult or None if migration was skipped
    """
    workspace = Path(workspace).resolve()

    if not force and is_migration_complete(workspace):
        logger.debug("Migration already complete, skipping")
        return None

    memory_dir = workspace / ".sunwell" / "memory"
    journal = LearningJournal(memory_dir)

    # Track existing journal IDs to count duplicates
    existing_ids = set(journal.load_deduplicated().keys())
    initial_existing = len(existing_ids)

    migrated_simulacrum = 0
    migrated_legacy = 0
    already_present = 0

    # Source 1: SimulacrumStore DAG
    try:
        migrated_simulacrum, already_sim = _migrate_from_simulacrum(
            workspace, journal, existing_ids
        )
        already_present += already_sim
    except Exception as e:
        logger.warning("Failed to migrate from SimulacrumStore: %s", e)

    # Source 2: Legacy JSONL
    try:
        migrated_legacy, already_leg = _migrate_from_legacy_jsonl(
            workspace, journal, existing_ids
        )
        already_present += already_leg
    except Exception as e:
        logger.warning("Failed to migrate from legacy JSONL: %s", e)

    # Mark complete
    if migrated_simulacrum > 0 or migrated_legacy > 0:
        mark_migration_complete(workspace)
        logger.info(
            "Migration complete: %d from simulacrum, %d from legacy",
            migrated_simulacrum,
            migrated_legacy,
        )

    return MigrationResult(
        migrated_from_simulacrum=migrated_simulacrum,
        migrated_from_legacy=migrated_legacy,
        total_migrated=migrated_simulacrum + migrated_legacy,
        already_in_journal=already_present,
    )


def _migrate_from_simulacrum(
    workspace: Path,
    journal: LearningJournal,
    existing_ids: set[str],
) -> tuple[int, int]:
    """Migrate learnings from SimulacrumStore DAG.

    Returns:
        Tuple of (migrated_count, already_present_count)
    """
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    memory_dir = workspace / ".sunwell" / "memory"
    if not memory_dir.exists():
        return 0, 0

    store = SimulacrumStore(memory_dir)

    # Try to load existing session
    sessions = list(memory_dir.glob("*.session"))
    if sessions:
        latest = max(sessions, key=lambda p: p.stat().st_mtime)
        store.load_session(latest.stem)

    dag = store.get_dag()
    migrated = 0
    already_present = 0

    for learning_id, learning in dag.learnings.items():
        if learning_id in existing_ids:
            already_present += 1
            continue

        # Create journal entry from SimLearning
        entry = JournalEntry(
            id=learning_id,
            fact=learning.fact,
            category=learning.category,
            confidence=learning.confidence,
            timestamp=learning.timestamp,
            source_file=None,
            source_line=None,
        )

        # Append to journal
        try:
            with journal._journal_path.open("a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
            existing_ids.add(learning_id)
            migrated += 1
        except OSError as e:
            logger.warning("Failed to write learning %s: %s", learning_id, e)

    return migrated, already_present


def _migrate_from_legacy_jsonl(
    workspace: Path,
    journal: LearningJournal,
    existing_ids: set[str],
) -> tuple[int, int]:
    """Migrate learnings from legacy JSONL format.

    Legacy format is at .sunwell/intelligence/learnings.jsonl

    Returns:
        Tuple of (migrated_count, already_present_count)
    """
    from sunwell.agent.learning.learning import Learning

    legacy_path = workspace / ".sunwell" / "intelligence" / "learnings.jsonl"
    if not legacy_path.exists():
        return 0, 0

    migrated = 0
    already_present = 0

    with legacy_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                # Create Learning to get the content-addressable ID
                learning = Learning(
                    fact=data["fact"],
                    category=data.get("category", "pattern"),
                    confidence=data.get("confidence", 0.7),
                    source_file=data.get("source_file"),
                    source_line=data.get("source_line"),
                )

                if learning.id in existing_ids:
                    already_present += 1
                    continue

                # Create journal entry
                entry = JournalEntry(
                    id=learning.id,
                    fact=learning.fact,
                    category=learning.category,
                    confidence=learning.confidence,
                    timestamp=data.get("created_at", datetime.now().isoformat()),
                    source_file=learning.source_file,
                    source_line=learning.source_line,
                )

                # Append to journal
                with journal._journal_path.open("a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
                existing_ids.add(learning.id)
                migrated += 1

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skipping malformed legacy entry at line %d: %s", line_num, e)

    return migrated, already_present


def migrate_if_needed(workspace: Path) -> MigrationResult | None:
    """Run migration if not already complete.

    This is the primary entry point for automatic migration.

    Args:
        workspace: Project workspace root

    Returns:
        MigrationResult or None if already migrated
    """
    return migrate_learnings(workspace, force=False)
