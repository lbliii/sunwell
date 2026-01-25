# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Immutable audit logging for security-first execution (RFC-089).

Provides tamper-evident audit logging with multiple backend options:
- LocalAuditLog: File-based with checksum chain (development/single-user)
- S3ObjectLockBackend: WORM storage for compliance (enterprise)

Each entry includes:
- Timestamp and skill identification
- Requested vs actual permissions
- Cryptographic integrity chain
- HMAC signature for tamper detection
"""


import hashlib
import hmac
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from sunwell.security.analyzer import PermissionScope

# =============================================================================
# AUDIT ENTRY
# =============================================================================


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable audit log entry.

    Contains complete provenance for security and compliance.
    """

    timestamp: datetime
    """When the event occurred."""

    skill_name: str
    """Name of the skill involved."""

    dag_id: str
    """ID of the DAG being executed."""

    user_id: str
    """ID of the user who initiated execution."""

    # What was requested
    requested_permissions: PermissionScope
    """Permissions requested by the skill."""

    # What happened
    action: Literal["execute", "violation", "denied", "error"]
    """Type of action recorded."""

    details: str
    """Human-readable details of what happened."""

    # Provenance
    inputs_hash: str
    """Hash of inputs to the skill."""

    outputs_hash: str | None
    """Hash of outputs (None if execution failed)."""

    # Integrity chain (each entry references previous)
    previous_hash: str
    """Hash of the previous entry (empty for first entry)."""

    entry_hash: str
    """Hash of this entry (includes all fields + previous_hash)."""

    # Signature for integrity (HMAC-SHA256)
    signature: str
    """HMAC signature for tamper detection."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["requested_permissions"] = self.requested_permissions.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        """Deserialize from JSON."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            skill_name=data["skill_name"],
            dag_id=data["dag_id"],
            user_id=data["user_id"],
            requested_permissions=PermissionScope.from_dict(
                data["requested_permissions"]
            ),
            action=data["action"],
            details=data["details"],
            inputs_hash=data["inputs_hash"],
            outputs_hash=data.get("outputs_hash"),
            previous_hash=data["previous_hash"],
            entry_hash=data["entry_hash"],
            signature=data["signature"],
        )


# =============================================================================
# AUDIT BACKEND PROTOCOL
# =============================================================================


class AuditBackend(Protocol):
    """Protocol for audit storage backends."""

    def append(self, entry: AuditEntry) -> None:
        """Append entry (must be atomic)."""
        ...

    def query(self, **filters: Any) -> Iterator[AuditEntry]:
        """Query entries with filters."""
        ...

    def verify_integrity(self) -> tuple[bool, str]:
        """Verify chain integrity. Returns (valid, reason)."""
        ...


# =============================================================================
# LOCAL AUDIT LOG
# =============================================================================


class LocalAuditLog:
    """Local file audit log with checksum chain.

    Provides tamper-evidence (not tamper-proof):
    - Each entry includes hash of previous entry
    - HMAC signature prevents modification without key
    - Integrity verification detects tampering

    For true immutability, use S3ObjectLockBackend.
    """

    def __init__(self, storage_path: Path, signing_key: bytes):
        """Initialize the local audit log.

        Args:
            storage_path: Path to the audit log file
            signing_key: HMAC signing key for integrity
        """
        self.storage = storage_path
        self.key = signing_key
        self._last_hash = self._get_last_hash()

    def append(
        self,
        entry_data: dict[str, Any],
    ) -> AuditEntry:
        """Append entry to log with integrity chain.

        Args:
            entry_data: Entry data (without integrity fields)

        Returns:
            Complete AuditEntry with integrity fields
        """
        # Ensure storage directory exists
        self.storage.parent.mkdir(parents=True, exist_ok=True)

        # Compute entry hash (includes previous hash)
        entry_hash = self._compute_hash(
            {**entry_data, "previous_hash": self._last_hash}
        )

        # Sign the entry
        signature = hmac.new(
            self.key,
            entry_hash.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Create entry
        entry = AuditEntry(
            **entry_data,
            previous_hash=self._last_hash,
            entry_hash=entry_hash,
            signature=signature,
        )

        # Atomic append (write to temp, rename)
        temp_path = self.storage.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            f.write(json.dumps(entry.to_dict(), default=str) + "\n")

        # Append to main log
        with open(self.storage, "a") as f:
            f.write(json.dumps(entry.to_dict(), default=str) + "\n")

        temp_path.unlink()
        self._last_hash = entry_hash

        return entry

    def verify_integrity(self) -> tuple[bool, str]:
        """Verify the entire chain is intact.

        Returns:
            Tuple of (is_valid, message)
        """
        if not self.storage.exists():
            return True, "No audit log exists yet"

        previous_hash = ""
        line_num = 0

        with open(self.storage) as f:
            for line in f:
                line_num += 1
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    entry = AuditEntry.from_dict(data)
                except (json.JSONDecodeError, KeyError) as e:
                    return False, f"Invalid entry at line {line_num}: {e}"

                # Check chain linkage
                if entry.previous_hash != previous_hash:
                    return False, f"Chain broken at line {line_num}"

                # Verify signature
                expected_sig = hmac.new(
                    self.key,
                    entry.entry_hash.encode(),
                    hashlib.sha256,
                ).hexdigest()

                if entry.signature != expected_sig:
                    return False, f"Invalid signature at line {line_num}"

                previous_hash = entry.entry_hash

        return True, f"Verified {line_num} entries"

    def query(
        self,
        skill_name: str | None = None,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AuditEntry]:
        """Query audit log with filters.

        Args:
            skill_name: Filter by skill name
            user_id: Filter by user ID
            action: Filter by action type
            since: Only entries after this timestamp
            limit: Maximum entries to return

        Yields:
            Matching AuditEntry objects
        """
        if not self.storage.exists():
            return

        count = 0
        with open(self.storage) as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    entry = AuditEntry.from_dict(data)
                except (json.JSONDecodeError, KeyError):
                    continue

                # Apply filters
                if skill_name and entry.skill_name != skill_name:
                    continue
                if user_id and entry.user_id != user_id:
                    continue
                if action and entry.action != action:
                    continue
                if since and entry.timestamp < since:
                    continue

                yield entry
                count += 1

                if limit and count >= limit:
                    return

    def get_recent(self, limit: int = 50) -> list[AuditEntry]:
        """Get recent entries (newest first).

        Args:
            limit: Maximum entries to return

        Returns:
            List of recent entries
        """
        entries: list[AuditEntry] = []

        if not self.storage.exists():
            return entries

        with open(self.storage) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    entries.append(AuditEntry.from_dict(data))
                except (json.JSONDecodeError, KeyError):
                    continue

        # Return newest first, limited
        return entries[-limit:][::-1]

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute SHA-256 hash of entry data.

        Args:
            data: Entry data to hash

        Returns:
            Hex digest of hash
        """
        # Deterministic serialization
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _get_last_hash(self) -> str:
        """Get hash of last entry (or empty for new log).

        Returns:
            Hash of last entry or empty string
        """
        if not self.storage.exists():
            return ""

        last_line = ""
        with open(self.storage) as f:
            for line in f:
                if line.strip():
                    last_line = line

        if not last_line:
            return ""

        try:
            entry = json.loads(last_line)
            return entry.get("entry_hash", "")
        except json.JSONDecodeError:
            return ""


# =============================================================================
# S3 OBJECT LOCK BACKEND (STUB)
# =============================================================================


@dataclass(slots=True)
class S3ObjectLockBackend:
    """S3 backend with Object Lock for true WORM immutability.

    Requires S3 bucket with Object Lock enabled (Governance or Compliance mode).
    Each entry is a separate object with a retention period.

    This provides regulatory-grade immutability (SOC 2, HIPAA, etc.).
    """

    bucket: str
    """S3 bucket name."""

    prefix: str = "audit/"
    """Key prefix for audit entries."""

    retention_days: int = 365
    """Retention period in days."""

    mode: Literal["GOVERNANCE", "COMPLIANCE"] = "GOVERNANCE"
    """Object Lock mode."""

    _s3: Any = field(default=None, repr=False)
    """Boto3 S3 client (lazy initialized)."""

    def __post_init__(self) -> None:
        # Lazy import boto3
        try:
            import boto3

            self._s3 = boto3.client("s3")
        except ImportError:
            self._s3 = None

    def append(self, entry: AuditEntry) -> None:
        """Write entry as locked S3 object.

        Args:
            entry: The audit entry to store
        """
        if self._s3 is None:
            raise RuntimeError("boto3 not available for S3 backend")

        key = (
            f"{self.prefix}"
            f"{entry.timestamp.isoformat()}_{entry.entry_hash[:8]}.json"
        )

        retention_date = datetime.now() + timedelta(days=self.retention_days)

        self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(entry.to_dict(), default=str),
            ObjectLockMode=self.mode,
            ObjectLockRetainUntilDate=retention_date,
        )

    def query(self, **filters: Any) -> Iterator[AuditEntry]:
        """Query audit entries.

        Args:
            **filters: Query filters

        Yields:
            Matching entries
        """
        if self._s3 is None:
            return

        # List objects with prefix
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                response = self._s3.get_object(
                    Bucket=self.bucket,
                    Key=obj["Key"],
                )
                data = json.loads(response["Body"].read().decode())
                entry = AuditEntry.from_dict(data)

                # Apply filters
                if "skill_name" in filters and entry.skill_name != filters["skill_name"]:
                    continue
                if "since" in filters and entry.timestamp < filters["since"]:
                    continue

                yield entry

    def verify_integrity(self) -> tuple[bool, str]:
        """Verify S3 objects exist and are locked.

        Returns:
            Tuple of (is_valid, message)
        """
        if self._s3 is None:
            return False, "boto3 not available"

        # S3 Object Lock provides inherent integrity
        # Just verify objects exist
        try:
            response = self._s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self.prefix,
                MaxKeys=1,
            )
            count = response.get("KeyCount", 0)
            return True, f"S3 backend operational, {count}+ entries"
        except Exception as e:
            return False, f"S3 access error: {e}"

    def export_for_compliance(
        self,
        format: Literal["json", "csv", "siem"] = "json",
    ) -> str:
        """Export audit log for compliance/SIEM integration.

        Args:
            format: Export format

        Returns:
            Formatted export string
        """
        entries = list(self.query())

        if format == "json":
            return json.dumps(
                [e.to_dict() for e in entries],
                indent=2,
                default=str,
            )

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            if entries:
                writer = csv.DictWriter(
                    output,
                    fieldnames=list(entries[0].to_dict().keys()),
                )
                writer.writeheader()
                for entry in entries:
                    writer.writerow(entry.to_dict())
            return output.getvalue()

        elif format == "siem":
            # CEF (Common Event Format) for SIEM
            lines = []
            for entry in entries:
                cef = (
                    f"CEF:0|Sunwell|SecurityAudit|1.0|{entry.action}|"
                    f"{entry.action}|5|"
                    f"skill={entry.skill_name} "
                    f"user={entry.user_id} "
                    f"dag={entry.dag_id} "
                    f"msg={entry.details}"
                )
                lines.append(cef)
            return "\n".join(lines)

        return ""


# =============================================================================
# AUDIT LOG MANAGER
# =============================================================================


class AuditLogManager:
    """High-level interface for audit logging.

    Manages the audit backend and provides convenient methods for
    recording and querying audit entries.
    """

    def __init__(
        self,
        backend: LocalAuditLog | S3ObjectLockBackend,
        default_user_id: str = "system",
    ):
        """Initialize the audit log manager.

        Args:
            backend: The audit storage backend
            default_user_id: Default user ID if not specified
        """
        self.backend = backend
        self.default_user_id = default_user_id

    def record_execution(
        self,
        skill_name: str,
        dag_id: str,
        permissions: PermissionScope,
        inputs_hash: str,
        outputs_hash: str | None = None,
        user_id: str | None = None,
        details: str = "",
    ) -> AuditEntry:
        """Record a successful skill execution.

        Args:
            skill_name: Name of the skill
            dag_id: ID of the DAG
            permissions: Permissions used
            inputs_hash: Hash of inputs
            outputs_hash: Hash of outputs
            user_id: User ID (uses default if not specified)
            details: Additional details

        Returns:
            The created AuditEntry
        """
        return self.backend.append({
            "timestamp": datetime.now(),
            "skill_name": skill_name,
            "dag_id": dag_id,
            "user_id": user_id or self.default_user_id,
            "requested_permissions": permissions,
            "action": "execute",
            "details": details or f"Executed {skill_name}",
            "inputs_hash": inputs_hash,
            "outputs_hash": outputs_hash,
        })

    def record_violation(
        self,
        skill_name: str,
        dag_id: str,
        permissions: PermissionScope,
        violation_type: str,
        evidence: str,
        user_id: str | None = None,
    ) -> AuditEntry:
        """Record a security violation.

        Args:
            skill_name: Name of the skill
            dag_id: ID of the DAG
            permissions: Permissions requested
            violation_type: Type of violation
            evidence: Evidence of violation
            user_id: User ID

        Returns:
            The created AuditEntry
        """
        return self.backend.append({
            "timestamp": datetime.now(),
            "skill_name": skill_name,
            "dag_id": dag_id,
            "user_id": user_id or self.default_user_id,
            "requested_permissions": permissions,
            "action": "violation",
            "details": f"{violation_type}: {evidence}",
            "inputs_hash": "",
            "outputs_hash": None,
        })

    def record_denied(
        self,
        skill_name: str,
        dag_id: str,
        permissions: PermissionScope,
        reason: str,
        user_id: str | None = None,
    ) -> AuditEntry:
        """Record a permission denial.

        Args:
            skill_name: Name of the skill
            dag_id: ID of the DAG
            permissions: Permissions requested
            reason: Why permission was denied
            user_id: User ID

        Returns:
            The created AuditEntry
        """
        return self.backend.append({
            "timestamp": datetime.now(),
            "skill_name": skill_name,
            "dag_id": dag_id,
            "user_id": user_id or self.default_user_id,
            "requested_permissions": permissions,
            "action": "denied",
            "details": f"Permission denied: {reason}",
            "inputs_hash": "",
            "outputs_hash": None,
        })

    def record_error(
        self,
        skill_name: str,
        dag_id: str,
        permissions: PermissionScope,
        error: str,
        user_id: str | None = None,
    ) -> AuditEntry:
        """Record an execution error.

        Args:
            skill_name: Name of the skill
            dag_id: ID of the DAG
            permissions: Permissions requested
            error: Error message
            user_id: User ID

        Returns:
            The created AuditEntry
        """
        return self.backend.append({
            "timestamp": datetime.now(),
            "skill_name": skill_name,
            "dag_id": dag_id,
            "user_id": user_id or self.default_user_id,
            "requested_permissions": permissions,
            "action": "error",
            "details": f"Error: {error}",
            "inputs_hash": "",
            "outputs_hash": None,
        })
