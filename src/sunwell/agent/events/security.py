"""Security event factories (RFC-089).

Event factories for security lifecycle:
- security_approval_requested_event: DAG requires user approval
- security_approval_received_event: User responded to approval
- security_violation_event: Violation detected
- security_scan_complete_event: Scan completed
- audit_log_entry_event: Audit log entry
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def security_approval_requested_event(
    dag_id: str,
    dag_name: str,
    skill_count: int,
    risk_level: str,
    risk_score: float,
    flags: list[str],
    permissions: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security approval requested event (RFC-089).

    Emitted when a DAG requires user approval before execution.

    Args:
        dag_id: Unique DAG identifier
        dag_name: Human-readable DAG name
        skill_count: Number of skills in the DAG
        risk_level: Risk classification (low/medium/high/critical)
        risk_score: Numeric risk score (0.0-1.0)
        flags: Risk flags detected
        permissions: Permission scope requested (filesystem, network, shell, env)
    """
    return AgentEvent(
        EventType.SECURITY_APPROVAL_REQUESTED,
        {
            "dag_id": dag_id,
            "dag_name": dag_name,
            "skill_count": skill_count,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "flags": flags,
            "permissions": permissions or {},
            **kwargs,
        },
    )


def security_approval_received_event(
    dag_id: str,
    approved: bool,
    modified: bool = False,
    remembered: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security approval received event (RFC-089).

    Emitted when user responds to an approval request.

    Args:
        dag_id: DAG that was approved/rejected
        approved: Whether user approved execution
        modified: Whether permissions were modified
        remembered: Whether approval was remembered for session
    """
    return AgentEvent(
        EventType.SECURITY_APPROVAL_RECEIVED,
        {
            "dag_id": dag_id,
            "approved": approved,
            "modified": modified,
            "remembered": remembered,
            **kwargs,
        },
    )


def security_violation_event(
    skill_name: str,
    violation_type: str,
    evidence: str,
    detection_method: str,
    action_taken: str,
    position: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security violation event (RFC-089).

    Emitted when a security violation is detected during execution.

    Args:
        skill_name: Skill that caused the violation
        violation_type: Type of violation (credential_leak, path_traversal, etc.)
        evidence: Evidence supporting detection
        detection_method: How detected (deterministic/llm)
        action_taken: Response action (logged/paused/aborted)
        position: Position in output where detected
    """
    return AgentEvent(
        EventType.SECURITY_VIOLATION,
        {
            "skill_name": skill_name,
            "violation_type": violation_type,
            "evidence": evidence,
            "detection_method": detection_method,
            "action_taken": action_taken,
            "position": position,
            **kwargs,
        },
    )


def security_scan_complete_event(
    output_length: int,
    violations_found: int,
    scan_duration_ms: int,
    method: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security scan complete event (RFC-089).

    Emitted when output security scan completes.

    Args:
        output_length: Length of scanned output
        violations_found: Number of violations detected
        scan_duration_ms: Scan duration in milliseconds
        method: Scan method (deterministic/llm/both)
    """
    return AgentEvent(
        EventType.SECURITY_SCAN_COMPLETE,
        {
            "output_length": output_length,
            "violations_found": violations_found,
            "scan_duration_ms": scan_duration_ms,
            "method": method,
            **kwargs,
        },
    )


def audit_log_entry_event(
    skill_name: str,
    action: str,
    risk_level: str,
    details: str | None = None,
    dag_id: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create an audit log entry event (RFC-089).

    Emitted when an audit log entry is recorded.

    Args:
        skill_name: Skill involved
        action: Action type (execute/violation/denied/error)
        risk_level: Risk level at time of action
        details: Human-readable details
        dag_id: Associated DAG ID
    """
    return AgentEvent(
        EventType.AUDIT_LOG_ENTRY,
        {
            "skill_name": skill_name,
            "action": action,
            "risk_level": risk_level,
            "details": details,
            "dag_id": dag_id,
            **kwargs,
        },
    )
