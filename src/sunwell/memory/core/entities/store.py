"""Entity store with SQLite persistence.

Stores entities and their relationships to learnings.
Enables fast entity-aware retrieval and co-occurrence analysis.

Part of Phase 1: Foundation.
"""

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.core.entities.types import Entity, EntityMention, EntityType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# SQLite schema for entities
ENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    aliases TEXT,  -- JSON array
    first_seen TEXT NOT NULL,
    mention_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_canonical_name ON entities(canonical_name);

CREATE TABLE IF NOT EXISTS learning_entities (
    learning_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    mention_text TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (learning_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_learning_entities_learning ON learning_entities(learning_id);
CREATE INDEX IF NOT EXISTS idx_learning_entities_entity ON learning_entities(entity_id);

-- Co-occurrence table for entity relationships
CREATE TABLE IF NOT EXISTS entity_cooccurrence (
    entity_id1 TEXT NOT NULL,
    entity_id2 TEXT NOT NULL,
    cooccurrence_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_id1, entity_id2)
);

CREATE INDEX IF NOT EXISTS idx_cooccurrence_entity1 ON entity_cooccurrence(entity_id1);
CREATE INDEX IF NOT EXISTS idx_cooccurrence_entity2 ON entity_cooccurrence(entity_id2);
"""


@dataclass(slots=True)
class EntityStore:
    """SQLite-backed storage for entities and their relationships.

    Provides:
    - Entity CRUD operations
    - Entity-learning associations
    - Co-occurrence tracking
    - Fast entity lookup
    """

    db_path: Path
    """Path to SQLite database."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Lock for write operations."""

    _initialized: bool = field(default=False, init=False)
    """Whether schema has been created."""

    def __post_init__(self) -> None:
        """Initialize database path."""
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode enabled."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for concurrent readers
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure schema exists."""
        if self._initialized:
            return

        conn.executescript(ENTITY_SCHEMA)
        conn.commit()
        self._initialized = True

    def add_entity(self, entity: Entity) -> bool:
        """Add an entity to the store.

        Args:
            entity: Entity to add

        Returns:
            True if added, False if already exists
        """
        with self._lock:
            conn = self._get_connection()
            try:
                self._ensure_schema(conn)

                conn.execute(
                    """
                    INSERT OR IGNORE INTO entities
                    (entity_id, canonical_name, entity_type, aliases, first_seen, mention_count, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity.entity_id,
                        entity.canonical_name,
                        entity.entity_type.value,
                        json.dumps(list(entity.aliases)),
                        entity.first_seen,
                        entity.mention_count,
                        entity.confidence,
                    ),
                )
                added = conn.total_changes > 0
                conn.commit()
                return added
            finally:
                conn.close()

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID.

        Args:
            entity_id: Entity ID to look up

        Returns:
            Entity if found, None otherwise
        """
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            row = conn.execute(
                "SELECT * FROM entities WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()

            if row:
                return self._row_to_entity(row)
            return None
        finally:
            conn.close()

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get all entities of a specific type.

        Args:
            entity_type: Type to filter by

        Returns:
            List of entities
        """
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            rows = conn.execute(
                "SELECT * FROM entities WHERE entity_type = ?",
                (entity_type.value,),
            ).fetchall()

            return [self._row_to_entity(row) for row in rows]
        finally:
            conn.close()

    def get_entities_for_learning(self, learning_id: str) -> list[Entity]:
        """Get all entities associated with a learning.

        Args:
            learning_id: Learning ID

        Returns:
            List of entities
        """
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            rows = conn.execute(
                """
                SELECT e.* FROM entities e
                INNER JOIN learning_entities le ON e.entity_id = le.entity_id
                WHERE le.learning_id = ?
                """,
                (learning_id,),
            ).fetchall()

            return [self._row_to_entity(row) for row in rows]
        finally:
            conn.close()

    def get_learnings_by_entity(self, entity_id: str) -> list[str]:
        """Get all learning IDs that mention an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of learning IDs
        """
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            rows = conn.execute(
                "SELECT learning_id FROM learning_entities WHERE entity_id = ?",
                (entity_id,),
            ).fetchall()

            return [row["learning_id"] for row in rows]
        finally:
            conn.close()

    def add_mention(self, mention: EntityMention) -> bool:
        """Add an entity mention (entity-learning association).

        Args:
            mention: Entity mention to add

        Returns:
            True if added, False if already exists
        """
        with self._lock:
            conn = self._get_connection()
            try:
                self._ensure_schema(conn)

                conn.execute(
                    """
                    INSERT OR IGNORE INTO learning_entities
                    (learning_id, entity_id, mention_text, confidence)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        mention.learning_id,
                        mention.entity_id,
                        mention.mention_text,
                        mention.confidence,
                    ),
                )
                added = conn.total_changes > 0

                # Increment mention count on entity
                if added:
                    conn.execute(
                        """
                        UPDATE entities
                        SET mention_count = mention_count + 1
                        WHERE entity_id = ?
                        """,
                        (mention.entity_id,),
                    )

                conn.commit()
                return added
            finally:
                conn.close()

    def update_cooccurrence(self, entity_id1: str, entity_id2: str) -> None:
        """Update co-occurrence count for two entities.

        Args:
            entity_id1: First entity ID
            entity_id2: Second entity ID
        """
        # Ensure consistent ordering (id1 < id2)
        if entity_id1 > entity_id2:
            entity_id1, entity_id2 = entity_id2, entity_id1

        with self._lock:
            conn = self._get_connection()
            try:
                self._ensure_schema(conn)

                conn.execute(
                    """
                    INSERT INTO entity_cooccurrence (entity_id1, entity_id2, cooccurrence_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT (entity_id1, entity_id2)
                    DO UPDATE SET cooccurrence_count = cooccurrence_count + 1
                    """,
                    (entity_id1, entity_id2),
                )
                conn.commit()
            finally:
                conn.close()

    def get_cooccurring_entities(
        self,
        entity_id: str,
        min_count: int = 2,
        limit: int = 10,
    ) -> list[tuple[Entity, int]]:
        """Get entities that co-occur with the given entity.

        Args:
            entity_id: Entity ID to find co-occurrences for
            min_count: Minimum co-occurrence count
            limit: Maximum results

        Returns:
            List of (entity, count) tuples sorted by count
        """
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            # Query both directions (entity can be id1 or id2)
            rows = conn.execute(
                """
                SELECT
                    CASE
                        WHEN entity_id1 = ? THEN entity_id2
                        ELSE entity_id1
                    END as related_entity_id,
                    cooccurrence_count
                FROM entity_cooccurrence
                WHERE (entity_id1 = ? OR entity_id2 = ?)
                    AND cooccurrence_count >= ?
                ORDER BY cooccurrence_count DESC
                LIMIT ?
                """,
                (entity_id, entity_id, entity_id, min_count, limit),
            ).fetchall()

            results = []
            for row in rows:
                related_entity = self.get_entity(row["related_entity_id"])
                if related_entity:
                    results.append((related_entity, row["cooccurrence_count"]))

            return results
        finally:
            conn.close()

    def count_entities(self) -> int:
        """Get total number of entities."""
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            row = conn.execute("SELECT COUNT(*) FROM entities").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        """Convert a database row to Entity."""
        aliases = json.loads(row["aliases"]) if row["aliases"] else []
        return Entity(
            entity_id=row["entity_id"],
            canonical_name=row["canonical_name"],
            entity_type=EntityType(row["entity_type"]),
            aliases=tuple(aliases),
            first_seen=row["first_seen"],
            mention_count=row["mention_count"],
            confidence=row["confidence"],
        )

    def stats(self) -> dict:
        """Get entity store statistics."""
        conn = self._get_connection()
        try:
            self._ensure_schema(conn)

            total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            total_mentions = conn.execute("SELECT COUNT(*) FROM learning_entities").fetchone()[0]
            total_cooccurrences = conn.execute(
                "SELECT COUNT(*) FROM entity_cooccurrence"
            ).fetchone()[0]

            # Count by type
            type_counts = {}
            for entity_type in EntityType:
                count = conn.execute(
                    "SELECT COUNT(*) FROM entities WHERE entity_type = ?",
                    (entity_type.value,),
                ).fetchone()[0]
                type_counts[entity_type.value] = count

            return {
                "total_entities": total_entities,
                "total_mentions": total_mentions,
                "total_cooccurrences": total_cooccurrences,
                "by_type": type_counts,
            }
        finally:
            conn.close()
