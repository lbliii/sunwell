# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Persistent approval caching for security-first execution (RFC-089).

Caches security approvals across sessions with configurable expiry:
- Hash-based approval matching (permissions + context)
- Configurable TTL (time-to-live)
- User identity binding
- Audit trail integration

Storage backends:
- File-based (default, ~/.sunwell/security/approvals.json)
- SQLite (for high-volume usage)
"""


import hashlib
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# =============================================================================
# APPROVAL RECORD
# =============================================================================


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """A cached approval record."""

    approval_hash: str
    """Hash of the permission scope + context."""

    dag_id: str
    """DAG identifier that was approved."""

    user_id: str
    """User who gave approval."""

    skills: tuple[str, ...]
    """Skills that were approved."""

    risk_level: str
    """Risk level at time of approval (low/medium/high/critical)."""

    risk_score: float
    """Risk score at time of approval."""

    approved_at: datetime
    """When approval was given."""

    expires_at: datetime
    """When approval expires."""

    remember_session: bool = False
    """Whether this was a session-only approval (if True, shorter TTL)."""

    def is_expired(self) -> bool:
        """Check if approval has expired."""
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "approval_hash": self.approval_hash,
            "dag_id": self.dag_id,
            "user_id": self.user_id,
            "skills": list(self.skills),
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "approved_at": self.approved_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "remember_session": self.remember_session,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRecord:
        """Deserialize from storage."""
        return cls(
            approval_hash=data["approval_hash"],
            dag_id=data["dag_id"],
            user_id=data["user_id"],
            skills=tuple(data["skills"]),
            risk_level=data["risk_level"],
            risk_score=data["risk_score"],
            approved_at=datetime.fromisoformat(data["approved_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            remember_session=data.get("remember_session", False),
        )


# =============================================================================
# APPROVAL CACHE PROTOCOL
# =============================================================================


class ApprovalCacheBackend(ABC):
    """Abstract backend for approval caching."""

    @abstractmethod
    def get(self, approval_hash: str) -> ApprovalRecord | None:
        """Get approval by hash."""
        ...

    @abstractmethod
    def put(self, record: ApprovalRecord) -> None:
        """Store approval."""
        ...

    @abstractmethod
    def delete(self, approval_hash: str) -> None:
        """Delete approval."""
        ...

    @abstractmethod
    def prune_expired(self) -> int:
        """Remove expired approvals. Returns count removed."""
        ...

    @abstractmethod
    def list_active(self, user_id: str | None = None) -> list[ApprovalRecord]:
        """List active (non-expired) approvals."""
        ...


# =============================================================================
# FILE-BASED CACHE
# =============================================================================


class FileApprovalCache(ApprovalCacheBackend):
    """File-based approval cache (JSON storage).

    Suitable for single-user desktop usage.
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize file cache.

        Args:
            storage_path: Path to cache file (default: ~/.sunwell/security/approvals.json)
        """
        self.storage = storage_path or (
            Path.home() / ".sunwell" / "security" / "approvals.json"
        )
        self._lock = threading.Lock()
        self._cache: dict[str, ApprovalRecord] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if not self.storage.exists():
            return

        try:
            with open(self.storage) as f:
                data = json.load(f)
            self._cache = {
                k: ApprovalRecord.from_dict(v) for k, v in data.items()
            }
        except (json.JSONDecodeError, KeyError):
            self._cache = {}

    def _save(self) -> None:
        """Save cache to disk."""
        self.storage.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage, "w") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._cache.items()},
                f,
                indent=2,
            )

    def get(self, approval_hash: str) -> ApprovalRecord | None:
        """Get approval by hash."""
        with self._lock:
            record = self._cache.get(approval_hash)
            if record and record.is_expired():
                del self._cache[approval_hash]
                self._save()
                return None
            return record

    def put(self, record: ApprovalRecord) -> None:
        """Store approval."""
        with self._lock:
            self._cache[record.approval_hash] = record
            self._save()

    def delete(self, approval_hash: str) -> None:
        """Delete approval."""
        with self._lock:
            if approval_hash in self._cache:
                del self._cache[approval_hash]
                self._save()

    def prune_expired(self) -> int:
        """Remove expired approvals."""
        with self._lock:
            now = datetime.now()
            expired = [
                k for k, v in self._cache.items() if v.expires_at < now
            ]
            for k in expired:
                del self._cache[k]
            if expired:
                self._save()
            return len(expired)

    def list_active(self, user_id: str | None = None) -> list[ApprovalRecord]:
        """List active approvals."""
        with self._lock:
            now = datetime.now()
            active = [
                v for v in self._cache.values()
                if v.expires_at > now
                and (user_id is None or v.user_id == user_id)
            ]
            return sorted(active, key=lambda x: x.approved_at, reverse=True)


# =============================================================================
# SQLITE CACHE
# =============================================================================


class SQLiteApprovalCache(ApprovalCacheBackend):
    """SQLite-based approval cache for high-volume usage.

    Better for:
    - Multi-process access
    - Large number of approvals
    - Complex queries
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize SQLite cache.

        Args:
            db_path: Path to database (default: ~/.sunwell/security/approvals.db)
        """
        self.db_path = db_path or (
            Path.home() / ".sunwell" / "security" / "approvals.db"
        )
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_hash TEXT PRIMARY KEY,
                    dag_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    skills TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    remember_session INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires ON approvals(expires_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user ON approvals(user_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(str(self.db_path))

    def get(self, approval_hash: str) -> ApprovalRecord | None:
        """Get approval by hash."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "SELECT * FROM approvals WHERE approval_hash = ?",
                (approval_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            record = self._row_to_record(row)
            if record.is_expired():
                self.delete(approval_hash)
                return None
            return record
        finally:
            conn.close()

    def put(self, record: ApprovalRecord) -> None:
        """Store approval."""
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO approvals
                (approval_hash, dag_id, user_id, skills, risk_level, risk_score,
                 approved_at, expires_at, remember_session)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.approval_hash,
                    record.dag_id,
                    record.user_id,
                    json.dumps(record.skills),
                    record.risk_level,
                    record.risk_score,
                    record.approved_at.isoformat(),
                    record.expires_at.isoformat(),
                    1 if record.remember_session else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, approval_hash: str) -> None:
        """Delete approval."""
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM approvals WHERE approval_hash = ?",
                (approval_hash,),
            )
            conn.commit()
        finally:
            conn.close()

    def prune_expired(self) -> int:
        """Remove expired approvals."""
        conn = self._connect()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "DELETE FROM approvals WHERE expires_at < ?",
                (now,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def list_active(self, user_id: str | None = None) -> list[ApprovalRecord]:
        """List active approvals."""
        conn = self._connect()
        try:
            now = datetime.now().isoformat()
            if user_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM approvals
                    WHERE expires_at > ? AND user_id = ?
                    ORDER BY approved_at DESC
                    """,
                    (now, user_id),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM approvals
                    WHERE expires_at > ?
                    ORDER BY approved_at DESC
                    """,
                    (now,),
                )
            return [self._row_to_record(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_record(self, row: tuple) -> ApprovalRecord:
        """Convert database row to ApprovalRecord."""
        return ApprovalRecord(
            approval_hash=row[0],
            dag_id=row[1],
            user_id=row[2],
            skills=tuple(json.loads(row[3])),
            risk_level=row[4],
            risk_score=row[5],
            approved_at=datetime.fromisoformat(row[6]),
            expires_at=datetime.fromisoformat(row[7]),
            remember_session=bool(row[8]),
        )


# =============================================================================
# APPROVAL CACHE MANAGER
# =============================================================================


@dataclass(frozen=True, slots=True)
class ApprovalCacheConfig:
    """Configuration for approval caching."""

    # TTL settings
    default_ttl_hours: int = 24
    """Default approval TTL in hours."""

    session_ttl_hours: int = 4
    """TTL for session-only approvals."""

    high_risk_ttl_hours: int = 1
    """TTL for high-risk approvals."""

    # Risk thresholds for TTL
    high_risk_threshold: float = 0.7
    """Risk score above this uses high_risk_ttl."""

    # Storage
    backend: str = "file"
    """Backend type: 'file' or 'sqlite'."""

    storage_path: Path | None = None
    """Custom storage path."""

    # Pruning
    auto_prune: bool = True
    """Automatically prune expired on operations."""

    prune_interval_minutes: int = 60
    """Minimum interval between auto-prunes."""


class ApprovalCacheManager:
    """High-level manager for approval caching.

    Handles:
    - Approval hash computation
    - TTL calculation based on risk
    - Auto-pruning
    - Lookup and storage
    """

    def __init__(self, config: ApprovalCacheConfig | None = None):
        """Initialize cache manager.

        Args:
            config: Cache configuration
        """
        self.config = config or ApprovalCacheConfig()
        self._backend = self._create_backend()
        self._last_prune = datetime.min

    def _create_backend(self) -> ApprovalCacheBackend:
        """Create the appropriate backend."""
        if self.config.backend == "sqlite":
            return SQLiteApprovalCache(self.config.storage_path)
        return FileApprovalCache(self.config.storage_path)

    def compute_approval_hash(
        self,
        permissions: Any,  # PermissionScope
        context: dict[str, Any],
    ) -> str:
        """Compute approval hash from permissions and context.

        Args:
            permissions: Permission scope
            context: Execution context

        Returns:
            SHA-256 hash of permissions + context
        """
        # Deterministic serialization
        perm_dict = (
            permissions.to_dict()
            if hasattr(permissions, "to_dict")
            else dict(permissions)
        )
        content = json.dumps(
            {"permissions": perm_dict, "context_keys": sorted(context.keys())},
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def get_approval(
        self,
        permissions: Any,
        context: dict[str, Any],
    ) -> ApprovalRecord | None:
        """Get cached approval if valid.

        Args:
            permissions: Required permissions
            context: Execution context

        Returns:
            Cached approval or None
        """
        self._maybe_prune()
        approval_hash = self.compute_approval_hash(permissions, context)
        return self._backend.get(approval_hash)

    def cache_approval(
        self,
        dag_id: str,
        user_id: str,
        skills: list[str],
        permissions: Any,
        context: dict[str, Any],
        risk_level: str,
        risk_score: float,
        remember_session: bool = False,
    ) -> ApprovalRecord:
        """Cache an approval.

        Args:
            dag_id: DAG identifier
            user_id: User who approved
            skills: Skills approved
            permissions: Permission scope
            context: Execution context
            risk_level: Risk level (low/medium/high/critical)
            risk_score: Numeric risk score
            remember_session: Session-only approval

        Returns:
            Created ApprovalRecord
        """
        approval_hash = self.compute_approval_hash(permissions, context)

        # Calculate TTL based on risk
        if risk_score >= self.config.high_risk_threshold:
            ttl_hours = self.config.high_risk_ttl_hours
        elif remember_session:
            ttl_hours = self.config.session_ttl_hours
        else:
            ttl_hours = self.config.default_ttl_hours

        now = datetime.now()
        record = ApprovalRecord(
            approval_hash=approval_hash,
            dag_id=dag_id,
            user_id=user_id,
            skills=tuple(skills),
            risk_level=risk_level,
            risk_score=risk_score,
            approved_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
            remember_session=remember_session,
        )

        self._backend.put(record)
        return record

    def revoke_approval(self, permissions: Any, context: dict[str, Any]) -> bool:
        """Revoke a cached approval.

        Args:
            permissions: Permission scope
            context: Execution context

        Returns:
            True if approval was revoked
        """
        approval_hash = self.compute_approval_hash(permissions, context)
        record = self._backend.get(approval_hash)
        if record:
            self._backend.delete(approval_hash)
            return True
        return False

    def list_active_approvals(self, user_id: str | None = None) -> list[ApprovalRecord]:
        """List active approvals.

        Args:
            user_id: Filter by user

        Returns:
            List of active approvals
        """
        return self._backend.list_active(user_id)

    def prune_expired(self) -> int:
        """Manually prune expired approvals.

        Returns:
            Count of pruned approvals
        """
        count = self._backend.prune_expired()
        self._last_prune = datetime.now()
        return count

    def _maybe_prune(self) -> None:
        """Auto-prune if configured and interval elapsed."""
        if not self.config.auto_prune:
            return

        elapsed = datetime.now() - self._last_prune
        if elapsed > timedelta(minutes=self.config.prune_interval_minutes):
            self._backend.prune_expired()
            self._last_prune = datetime.now()
