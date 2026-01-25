"""Integration verification and briefing event factories (RFC-067, RFC-071).

Event factories for integration lifecycle:
- integration_check_start_event, integration_check_pass_event, integration_check_fail_event
- stub_detected_event, orphan_detected_event, wire_task_generated_event
- briefing_loaded_event, briefing_saved_event
- prefetch_start_event, prefetch_complete_event, prefetch_timeout_event
- lens_suggested_event
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType

# =============================================================================
# RFC-067: Integration Verification Events
# =============================================================================


def integration_check_start_event(
    edge_id: str,
    check_type: str,
    source_artifact: str,
    target_artifact: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an integration check start event (RFC-067)."""
    return AgentEvent(
        EventType.INTEGRATION_CHECK_START,
        {
            "edge_id": edge_id,
            "check_type": check_type,
            "source_artifact": source_artifact,
            "target_artifact": target_artifact,
            **kwargs,
        },
    )


def integration_check_pass_event(
    edge_id: str,
    check_type: str,
    verification_method: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an integration check pass event (RFC-067)."""
    return AgentEvent(
        EventType.INTEGRATION_CHECK_PASS,
        {
            "edge_id": edge_id,
            "check_type": check_type,
            "verification_method": verification_method,
            **kwargs,
        },
    )


def integration_check_fail_event(
    edge_id: str,
    check_type: str,
    expected: str,
    actual: str,
    suggested_fix: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create an integration check fail event (RFC-067)."""
    return AgentEvent(
        EventType.INTEGRATION_CHECK_FAIL,
        {
            "edge_id": edge_id,
            "check_type": check_type,
            "expected": expected,
            "actual": actual,
            "suggested_fix": suggested_fix,
            **kwargs,
        },
    )


def stub_detected_event(
    artifact_id: str,
    file_path: str,
    stub_type: str,
    location: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a stub detected event (RFC-067)."""
    return AgentEvent(
        EventType.STUB_DETECTED,
        {
            "artifact_id": artifact_id,
            "file_path": file_path,
            "stub_type": stub_type,
            "location": location,
            **kwargs,
        },
    )


def orphan_detected_event(
    artifact_id: str,
    file_path: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an orphan detected event (RFC-067)."""
    return AgentEvent(
        EventType.ORPHAN_DETECTED,
        {
            "artifact_id": artifact_id,
            "file_path": file_path,
            **kwargs,
        },
    )


def wire_task_generated_event(
    task_id: str,
    source_artifact: str,
    target_artifact: str,
    integration_type: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a wire task generated event (RFC-067)."""
    return AgentEvent(
        EventType.WIRE_TASK_GENERATED,
        {
            "task_id": task_id,
            "source_artifact": source_artifact,
            "target_artifact": target_artifact,
            "integration_type": integration_type,
            **kwargs,
        },
    )


# =============================================================================
# RFC-071: Briefing Events
# =============================================================================


def briefing_loaded_event(
    mission: str,
    status: str,
    has_hazards: bool,
    has_dispatch_hints: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a briefing loaded event (RFC-071)."""
    return AgentEvent(
        EventType.BRIEFING_LOADED,
        {
            "mission": mission,
            "status": status,
            "has_hazards": has_hazards,
            "has_dispatch_hints": has_dispatch_hints,
            **kwargs,
        },
    )


def briefing_saved_event(
    status: str,
    next_action: str | None,
    tasks_completed: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a briefing saved event (RFC-071)."""
    return AgentEvent(
        EventType.BRIEFING_SAVED,
        {
            "status": status,
            "next_action": next_action,
            "tasks_completed": tasks_completed,
            **kwargs,
        },
    )


def prefetch_start_event(briefing_mission: str, **kwargs: Any) -> AgentEvent:
    """Create a prefetch start event (RFC-071)."""
    return AgentEvent(
        EventType.PREFETCH_START,
        {"briefing": briefing_mission, **kwargs},
    )


def prefetch_complete_event(
    files_loaded: int,
    learnings_loaded: int,
    skills_activated: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a prefetch complete event (RFC-071)."""
    return AgentEvent(
        EventType.PREFETCH_COMPLETE,
        {
            "files_loaded": files_loaded,
            "learnings_loaded": learnings_loaded,
            "skills_activated": skills_activated,
            **kwargs,
        },
    )


def prefetch_timeout_event(error: str | None = None, **kwargs: Any) -> AgentEvent:
    """Create a prefetch timeout event (RFC-071)."""
    data: dict[str, Any] = kwargs
    if error:
        data["error"] = error
    return AgentEvent(EventType.PREFETCH_TIMEOUT, data)


def lens_suggested_event(
    suggested: str,
    reason: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a lens suggested event (RFC-071)."""
    return AgentEvent(
        EventType.LENS_SUGGESTED,
        {"suggested": suggested, "reason": reason, **kwargs},
    )
