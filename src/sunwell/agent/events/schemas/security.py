"""Security event schemas (RFC-089)."""

from typing import Any, TypedDict


class SecurityApprovalRequestedData(TypedDict, total=False):
    """Data for security_approval_requested event."""
    dag_id: str  # Required
    dag_name: str  # Required
    skill_count: int  # Required
    risk_level: str  # Required: low/medium/high/critical
    risk_score: float  # Required: 0.0-1.0
    flags: list[str]  # Required - risk flags detected
    permissions: dict[str, Any]  # Permission scope (filesystem, network, etc.)


class SecurityApprovalReceivedData(TypedDict, total=False):
    """Data for security_approval_received event."""
    dag_id: str  # Required
    approved: bool  # Required
    modified: bool  # Whether permissions were modified
    remembered: bool  # Whether remembered for session


class SecurityViolationData(TypedDict, total=False):
    """Data for security_violation event."""
    skill_name: str  # Required
    violation_type: str  # Required: credential_leak, path_traversal, etc.
    evidence: str  # Required
    detection_method: str  # Required: deterministic/llm
    action_taken: str  # Required: logged/paused/aborted
    position: int | None  # Position in output


class SecurityScanCompleteData(TypedDict, total=False):
    """Data for security_scan_complete event."""
    output_length: int  # Required
    violations_found: int  # Required
    scan_duration_ms: int  # Required
    method: str  # Required: deterministic/llm/both


class AuditLogEntryData(TypedDict, total=False):
    """Data for audit_log_entry event."""
    skill_name: str  # Required
    action: str  # Required: execute/violation/denied/error
    risk_level: str  # Required: low/medium/high/critical
    details: str | None  # Human-readable details
    dag_id: str | None  # Associated DAG
