"""SQLite-backed execution cache with provenance tracking for RFC-074.

Replaces JSON file storage (RFC-040) with indexed database:
- O(1) provenance queries via recursive CTE
- Transaction safety for concurrent access
- Automatic schema migration

Storage location: `.sunwell/cache/execution.db`

Inspired by Pachyderm's provenance tracking:
https://github.com/pachyderm/pachyderm/blob/master/src/internal/pfsdb/commit_provenance.go

Example:
    >>> cache = ExecutionCache(Path(".sunwell/cache/execution.db"))
    >>> cache.set("artifact_a", "hash123", ExecutionStatus.COMPLETED, {"output": "value"})
    >>> cached = cache.get("artifact_a")
    >>> print(cached.input_hash)
    'hash123'
"""

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ExecutionStatus(Enum):
    """Status of an artifact execution."""

    PENDING = "pending"
    """Artifact is queued for execution."""

    RUNNING = "running"
    """Artifact is currently being executed."""

    COMPLETED = "completed"
    """Artifact execution succeeded."""

    FAILED = "failed"
    """Artifact execution failed."""

    SKIPPED = "skipped"
    """Artifact was skipped (cache hit)."""


@dataclass(frozen=True, slots=True)
class CachedExecution:
    """A cached artifact execution result.

    Attributes:
        artifact_id: The artifact this cache entry is for.
        input_hash: Hash of inputs at execution time.
        status: Execution status.
        result: JSON-serializable result data (if completed).
        executed_at: Unix timestamp of execution.
        execution_time_ms: Time taken to execute.
        skip_count: How many times this was reused (cache hits).
    """

    artifact_id: str
    input_hash: str
    status: ExecutionStatus
    result: dict[str, Any] | None
    executed_at: float
    execution_time_ms: float
    skip_count: int


class ExecutionCache:
    """SQLite-backed execution cache with provenance tracking.

    Provides:
    - Content-addressed lookup (by input hash)
    - Bi-directional provenance queries (upstream/downstream)
    - Transaction safety for concurrent access
    - Cache statistics for monitoring

    Schema:
    - artifacts: id → input_hash, status, result, timestamps
    - provenance: from_id → to_id (bi-directional lineage)

    Example:
        >>> cache = ExecutionCache(Path(".sunwell/cache/execution.db"))
        >>> cache.set("A", "hash_a", ExecutionStatus.COMPLETED, {"output": "..."})
        >>> cache.add_provenance("B", "A", "requires")
        >>> cache.get_upstream("B")
        ['A']
    """

    SCHEMA_VERSION = 1

    # fmt: off
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY,
        input_hash TEXT NOT NULL,
        spec_hash TEXT,
        status TEXT NOT NULL CHECK (
            status IN ('pending', 'running', 'completed', 'failed', 'skipped')
        ),
        result TEXT,
        error TEXT,
        executed_at REAL NOT NULL,
        execution_time_ms REAL DEFAULT 0,
        skip_count INTEGER DEFAULT 0,
        created_at REAL DEFAULT (unixepoch('now')),
        updated_at REAL DEFAULT (unixepoch('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_artifacts_hash ON artifacts(input_hash);
    CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status);

    CREATE TABLE IF NOT EXISTS provenance (
        from_id TEXT NOT NULL,
        to_id TEXT NOT NULL,
        relation TEXT DEFAULT 'requires',
        created_at REAL DEFAULT (unixepoch('now')),
        PRIMARY KEY (from_id, to_id)
    );

    CREATE INDEX IF NOT EXISTS idx_provenance_from ON provenance(from_id);
    CREATE INDEX IF NOT EXISTS idx_provenance_to ON provenance(to_id);

    CREATE TABLE IF NOT EXISTS execution_runs (
        id TEXT PRIMARY KEY,
        started_at REAL NOT NULL,
        finished_at REAL,
        total_artifacts INTEGER,
        executed INTEGER,
        skipped INTEGER,
        failed INTEGER,
        status TEXT CHECK (status IN ('running', 'completed', 'failed', 'cancelled'))
    );

    CREATE INDEX IF NOT EXISTS idx_runs_status ON execution_runs(status);

    CREATE TABLE IF NOT EXISTS goal_executions (
        goal_hash TEXT PRIMARY KEY,
        artifact_ids TEXT NOT NULL,
        executed_at REAL NOT NULL,
        execution_time_ms REAL
    );

    CREATE INDEX IF NOT EXISTS idx_goal_executions_time
        ON goal_executions(executed_at DESC);

    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """
    # fmt: on

    def __init__(self, cache_path: Path) -> None:
        """Initialize cache at the given path.

        Creates parent directories and schema if needed.

        Args:
            cache_path: Path to SQLite database file.
        """
        self.cache_path = cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(cache_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._lock = threading.Lock()

        # Store schema version
        self._set_metadata("schema_version", str(self.SCHEMA_VERSION))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> ExecutionCache:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    @contextmanager
    def transaction(self):
        """Context manager for transactions.

        Automatically commits on success, rolls back on exception.

        Example:
            >>> with cache.transaction():
            ...     cache.set("A", "hash", ExecutionStatus.COMPLETED)
            ...     cache.add_provenance("B", "A")
        """
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _set_metadata(self, key: str, value: str) -> None:
        """Set a metadata value."""
        self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
        )
        self._conn.commit()

    def _get_metadata(self, key: str) -> str | None:
        """Get a metadata value."""
        row = self._conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def get(self, artifact_id: str) -> CachedExecution | None:
        """Get cached execution for an artifact.

        Args:
            artifact_id: The artifact ID to look up.

        Returns:
            CachedExecution if found, None otherwise.
        """
        row = self._conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()

        if not row:
            return None

        return CachedExecution(
            artifact_id=row["id"],
            input_hash=row["input_hash"],
            status=ExecutionStatus(row["status"]),
            result=json.loads(row["result"]) if row["result"] else None,
            executed_at=row["executed_at"],
            execution_time_ms=row["execution_time_ms"],
            skip_count=row["skip_count"],
        )

    def get_by_hash(self, input_hash: str) -> list[CachedExecution]:
        """Get all cached executions with the given input hash.

        Useful for finding potential cache hits across artifacts.

        Args:
            input_hash: The input hash to look up.

        Returns:
            List of matching CachedExecution objects.
        """
        rows = self._conn.execute(
            "SELECT * FROM artifacts WHERE input_hash = ?", (input_hash,)
        ).fetchall()

        return [
            CachedExecution(
                artifact_id=row["id"],
                input_hash=row["input_hash"],
                status=ExecutionStatus(row["status"]),
                result=json.loads(row["result"]) if row["result"] else None,
                executed_at=row["executed_at"],
                execution_time_ms=row["execution_time_ms"],
                skip_count=row["skip_count"],
            )
            for row in rows
        ]

    def set(
        self,
        artifact_id: str,
        input_hash: str,
        status: ExecutionStatus,
        result: dict[str, Any] | None = None,
        execution_time_ms: float = 0,
        spec_hash: str | None = None,
        error: str | None = None,
    ) -> None:
        """Set or update cached execution.

        Uses INSERT ... ON CONFLICT for atomic upsert.

        Args:
            artifact_id: The artifact ID.
            input_hash: Hash of inputs.
            status: Execution status.
            result: Result data (for completed executions).
            execution_time_ms: Execution duration.
            spec_hash: Optional spec-only hash.
            error: Error message (for failed executions).
        """
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO artifacts (
                    id, input_hash, spec_hash, status, result, error,
                    executed_at, execution_time_ms, skip_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET
                    input_hash = excluded.input_hash,
                    spec_hash = excluded.spec_hash,
                    status = excluded.status,
                    result = excluded.result,
                    error = excluded.error,
                    executed_at = excluded.executed_at,
                    execution_time_ms = excluded.execution_time_ms,
                    updated_at = unixepoch('now')
                """,
                (
                    artifact_id,
                    input_hash,
                    spec_hash,
                    status.value,
                    json.dumps(result) if result else None,
                    error,
                    time.time(),
                    execution_time_ms,
                ),
            )

    def record_skip(self, artifact_id: str) -> None:
        """Record that an artifact was skipped (cache hit).

        Increments skip_count for monitoring cache effectiveness.

        Args:
            artifact_id: The artifact that was skipped.
        """
        with self.transaction():
            self._conn.execute(
                """
                UPDATE artifacts
                SET skip_count = skip_count + 1, updated_at = unixepoch('now')
                WHERE id = ?
                """,
                (artifact_id,),
            )

    def delete(self, artifact_id: str) -> bool:
        """Delete a cached execution.

        Also removes related provenance entries.

        Args:
            artifact_id: The artifact ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self.transaction():
            # Delete provenance entries
            self._conn.execute(
                "DELETE FROM provenance WHERE from_id = ? OR to_id = ?", (artifact_id, artifact_id)
            )
            # Delete artifact
            cursor = self._conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
            return cursor.rowcount > 0

    # =========================================================================
    # Provenance Tracking
    # =========================================================================

    def add_provenance(
        self,
        from_id: str,
        to_id: str,
        relation: str = "requires",
    ) -> None:
        """Add a provenance relationship.

        Records that `from_id` depends on `to_id`.

        Args:
            from_id: The dependent artifact.
            to_id: The dependency artifact.
            relation: Relationship type (default: "requires").
        """
        with self.transaction():
            self._conn.execute(
                """
                INSERT OR IGNORE INTO provenance (from_id, to_id, relation)
                VALUES (?, ?, ?)
                """,
                (from_id, to_id, relation),
            )

    def get_direct_dependencies(self, artifact_id: str) -> list[str]:
        """Get direct dependencies of an artifact.

        Args:
            artifact_id: The artifact to query.

        Returns:
            List of artifact IDs that this artifact directly depends on.
        """
        rows = self._conn.execute(
            "SELECT to_id FROM provenance WHERE from_id = ?", (artifact_id,)
        ).fetchall()
        return [row["to_id"] for row in rows]

    def get_direct_dependents(self, artifact_id: str) -> list[str]:
        """Get direct dependents of an artifact.

        Args:
            artifact_id: The artifact to query.

        Returns:
            List of artifact IDs that directly depend on this artifact.
        """
        rows = self._conn.execute(
            "SELECT from_id FROM provenance WHERE to_id = ?", (artifact_id,)
        ).fetchall()
        return [row["from_id"] for row in rows]

    def get_upstream(self, artifact_id: str, max_depth: int = 100) -> list[str]:
        """Get all artifacts upstream of (depended on by) this artifact.

        Uses recursive CTE for O(1) provenance queries (vs O(n) BFS).

        Args:
            artifact_id: Starting artifact.
            max_depth: Maximum recursion depth (prevents infinite loops).

        Returns:
            List of artifact IDs in dependency order (closest first).
        """
        rows = self._conn.execute(
            """
            WITH RECURSIVE upstream(id, depth) AS (
                SELECT to_id, 1
                FROM provenance
                WHERE from_id = ?
                UNION ALL
                SELECT p.to_id, u.depth + 1
                FROM upstream u
                JOIN provenance p ON p.from_id = u.id
                WHERE u.depth < ?
            )
            SELECT DISTINCT id FROM upstream ORDER BY depth
            """,
            (artifact_id, max_depth),
        ).fetchall()

        return [row["id"] for row in rows]

    def get_downstream(self, artifact_id: str, max_depth: int = 100) -> list[str]:
        """Get all artifacts downstream of (depending on) this artifact.

        Useful for invalidation: "what needs to be recomputed if X changes?"

        Args:
            artifact_id: Starting artifact.
            max_depth: Maximum recursion depth.

        Returns:
            List of artifact IDs in dependency order (closest first).
        """
        rows = self._conn.execute(
            """
            WITH RECURSIVE downstream(id, depth) AS (
                SELECT from_id, 1
                FROM provenance
                WHERE to_id = ?
                UNION ALL
                SELECT p.from_id, d.depth + 1
                FROM downstream d
                JOIN provenance p ON p.to_id = d.id
                WHERE d.depth < ?
            )
            SELECT DISTINCT id FROM downstream ORDER BY depth
            """,
            (artifact_id, max_depth),
        ).fetchall()

        return [row["id"] for row in rows]

    def invalidate_downstream(self, artifact_id: str) -> list[str]:
        """Invalidate all artifacts downstream of the given artifact.

        Sets their status to 'pending', requiring re-execution.

        Args:
            artifact_id: The artifact whose downstream should be invalidated.

        Returns:
            List of invalidated artifact IDs.
        """
        downstream = self.get_downstream(artifact_id)

        if downstream:
            with self.transaction():
                placeholders = ",".join("?" * len(downstream))
                self._conn.execute(
                    f"""
                    UPDATE artifacts
                    SET status = 'pending', updated_at = unixepoch('now')
                    WHERE id IN ({placeholders})
                    """,
                    downstream,
                )

        return downstream

    # =========================================================================
    # Execution Runs
    # =========================================================================

    def start_run(
        self,
        run_id: str,
        total_artifacts: int,
    ) -> None:
        """Record the start of an execution run.

        Args:
            run_id: Unique identifier for this run.
            total_artifacts: Total artifacts to process.
        """
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO execution_runs (
                    id, started_at, total_artifacts, executed, skipped, failed, status
                )
                VALUES (?, ?, ?, 0, 0, 0, 'running')
                """,
                (run_id, time.time(), total_artifacts),
            )

    def finish_run(
        self,
        run_id: str,
        executed: int,
        skipped: int,
        failed: int,
        status: str = "completed",
    ) -> None:
        """Record the end of an execution run.

        Args:
            run_id: The run identifier.
            executed: Number of artifacts executed.
            skipped: Number of artifacts skipped (cache hits).
            failed: Number of artifacts that failed.
            status: Final status ('completed', 'failed', 'cancelled').
        """
        with self.transaction():
            self._conn.execute(
                """
                UPDATE execution_runs SET
                    finished_at = ?,
                    executed = ?,
                    skipped = ?,
                    failed = ?,
                    status = ?
                WHERE id = ?
                """,
                (time.time(), executed, skipped, failed, status, run_id),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get execution run details.

        Args:
            run_id: The run identifier.

        Returns:
            Run details dict, or None if not found.
        """
        row = self._conn.execute("SELECT * FROM execution_runs WHERE id = ?", (run_id,)).fetchone()

        if not row:
            return None

        return dict(row)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with by_status counts, total_skips, avg_execution_time_ms.
        """
        stats: dict[str, Any] = {}

        # Count by status
        rows = self._conn.execute(
            "SELECT status, COUNT(*) as count FROM artifacts GROUP BY status"
        ).fetchall()
        stats["by_status"] = {row["status"]: row["count"] for row in rows}

        # Total artifacts
        row = self._conn.execute("SELECT COUNT(*) as total FROM artifacts").fetchone()
        stats["total_artifacts"] = row["total"] if row else 0

        # Total skip count
        row = self._conn.execute("SELECT SUM(skip_count) as total_skips FROM artifacts").fetchone()
        stats["total_skips"] = row["total_skips"] or 0

        # Average execution time
        row = self._conn.execute(
            "SELECT AVG(execution_time_ms) as avg_time FROM artifacts WHERE status = 'completed'"
        ).fetchone()
        stats["avg_execution_time_ms"] = row["avg_time"] or 0

        # Total execution time saved (skips * avg time)
        if stats["total_skips"] > 0 and stats["avg_execution_time_ms"] > 0:
            stats["estimated_time_saved_ms"] = stats["total_skips"] * stats["avg_execution_time_ms"]
        else:
            stats["estimated_time_saved_ms"] = 0

        # Cache hit rate
        total = stats["total_artifacts"]
        skipped = stats["by_status"].get("skipped", 0)
        stats["cache_hit_rate"] = (skipped / total * 100) if total > 0 else 0

        return stats

    def clear(self) -> None:
        """Clear all cached data.

        Warning: This deletes all artifacts, provenance, and run history.
        """
        with self.transaction():
            self._conn.execute("DELETE FROM artifacts")
            self._conn.execute("DELETE FROM provenance")
            self._conn.execute("DELETE FROM execution_runs")

    def clear_artifact(self, artifact_id: str) -> bool:
        """Clear cache for a specific artifact.

        Args:
            artifact_id: The artifact to clear.

        Returns:
            True if cleared, False if not found.
        """
        return self.delete(artifact_id)

    def vacuum(self) -> None:
        """Compact the database to reclaim space.

        Call after clearing large amounts of data.
        """
        self._conn.execute("VACUUM")

    # =========================================================================
    # Goal Tracking (RFC-076)
    # =========================================================================

    def record_goal_execution(
        self,
        goal_hash: str,
        artifact_ids: list[str],
        execution_time_ms: float | None = None,
    ) -> None:
        """Record which artifacts belong to a goal execution.

        Links a goal (by hash) to the artifacts that were executed for it,
        enabling goal-based lookups and incremental re-execution.

        Args:
            goal_hash: Hash of the goal text.
            artifact_ids: List of artifact IDs executed for this goal.
            execution_time_ms: Optional total execution time.
        """
        with self.transaction():
            self._conn.execute(
                """INSERT OR REPLACE INTO goal_executions
                   (goal_hash, artifact_ids, executed_at, execution_time_ms)
                   VALUES (?, ?, ?, ?)""",
                (goal_hash, json.dumps(artifact_ids), time.time(), execution_time_ms),
            )

    def get_artifacts_for_goal(self, goal_hash: str) -> list[str] | None:
        """Get artifact IDs from a previous goal execution.

        Args:
            goal_hash: Hash of the goal text.

        Returns:
            List of artifact IDs if found, None otherwise.
        """
        row = self._conn.execute(
            "SELECT artifact_ids FROM goal_executions WHERE goal_hash = ?",
            (goal_hash,),
        ).fetchone()
        return json.loads(row["artifact_ids"]) if row else None

    def get_goal_execution(self, goal_hash: str) -> dict[str, Any] | None:
        """Get full goal execution details.

        Args:
            goal_hash: Hash of the goal text.

        Returns:
            Dict with goal_hash, artifact_ids, executed_at, execution_time_ms.
        """
        row = self._conn.execute(
            "SELECT * FROM goal_executions WHERE goal_hash = ?",
            (goal_hash,),
        ).fetchone()

        if not row:
            return None

        return {
            "goal_hash": row["goal_hash"],
            "artifact_ids": json.loads(row["artifact_ids"]),
            "executed_at": row["executed_at"],
            "execution_time_ms": row["execution_time_ms"],
        }

    def list_artifacts(self) -> list[dict[str, Any]]:
        """List all cached artifacts with their state.

        Returns:
            List of artifact info dicts with id, input_hash, status, executed_at, skip_count.
        """
        rows = self._conn.execute(
            """
            SELECT id, input_hash, spec_hash, status, executed_at, skip_count, execution_time_ms
            FROM artifacts
            ORDER BY executed_at DESC
            """
        ).fetchall()

        return [
            {
                "artifact_id": row["id"],
                "input_hash": row["input_hash"],
                "spec_hash": row["spec_hash"],
                "status": row["status"],
                "executed_at": row["executed_at"],
                "skip_count": row["skip_count"],
                "execution_time_ms": row["execution_time_ms"],
            }
            for row in rows
        ]
