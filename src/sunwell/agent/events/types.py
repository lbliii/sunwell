"""Event types and base classes for Adaptive Agent streaming.

This module contains the core event infrastructure:
- EventUIHints: UI rendering hints for frontend (RFC-097)
- EventType: Enum of all event types
- AgentEvent: The base event dataclass
- Default UI hints mapping

Type definitions moved to sunwell.contracts.events; re-exported here
for backward compatibility. DEFAULT_UI_HINTS remains here as it is
runtime configuration, not a shared contract.
"""

# Re-export all types from contracts
from typing import Any

from sunwell.contracts.events import (
    AgentEvent,
    EventEmitter,
    EventType,
    EventUIHints,
    GateSummary,
    TaskSummary,
)

# Default UI hints for common event types
# RFC-131: Character-map shapes only (no emojis) for consistent terminal rendering
DEFAULT_UI_HINTS: dict[str, EventUIHints] = {
    # ═══════════════════════════════════════════════════════════════
    # TASK LIFECYCLE
    # ═══════════════════════════════════════════════════════════════
    "task_start": EventUIHints(icon="✧", severity="info", animation="pulse"),
    "task_complete": EventUIHints(icon="✓", severity="success", animation="fade-in"),
    "task_failed": EventUIHints(icon="✗", severity="error", animation="shake"),
    "task_progress": EventUIHints(icon="·", severity="info"),
    # Parallel execution
    "parallel_group_start": EventUIHints(icon="⊕", severity="info", animation="pulse"),
    "parallel_group_complete": EventUIHints(icon="⊙", severity="success", animation="fade-in"),
    "parallel_dispatch_start": EventUIHints(icon="◎", severity="info", animation="pulse"),
    "parallel_dispatch_complete": EventUIHints(icon="✓", severity="success", animation="sparkle"),
    "isolation_warning": EventUIHints(icon="⚠", severity="warning"),
    "task_output": EventUIHints(icon="◦", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # TOOL CALLING
    # ═══════════════════════════════════════════════════════════════
    "tool_start": EventUIHints(icon="⚙", severity="info", animation="pulse"),
    "tool_complete": EventUIHints(icon="✓", severity="success"),
    "tool_error": EventUIHints(icon="✗", severity="error"),
    "tool_loop_start": EventUIHints(icon="◎", severity="info", animation="pulse"),
    "tool_loop_turn": EventUIHints(icon="·", severity="info"),
    "tool_loop_complete": EventUIHints(icon="✓", severity="success"),
    # RFC-134: Introspection and escalation events
    "tool_repair": EventUIHints(icon="⚙", severity="warning"),
    "tool_blocked": EventUIHints(icon="⊘", severity="error"),
    "tool_retry": EventUIHints(icon="↻", severity="warning", animation="pulse"),
    "tool_escalate": EventUIHints(icon="△", severity="warning", dismissible=False),
    "tool_pattern_learned": EventUIHints(icon="≡", severity="success"),
    "progressive_unlock": EventUIHints(icon="✧", severity="success", animation="fade-in"),
    # Reliability detection
    "reliability_warning": EventUIHints(icon="⚠", severity="warning", dismissible=False),
    "reliability_hallucination": EventUIHints(
        icon="⊘", severity="error", dismissible=False, animation="shake"
    ),
    # ═══════════════════════════════════════════════════════════════
    # COMPLETION & ERROR
    # ═══════════════════════════════════════════════════════════════
    "error": EventUIHints(icon="✗", severity="error", dismissible=False, animation="shake"),
    "complete": EventUIHints(icon="★", severity="success", animation="sparkle"),
    "escalate": EventUIHints(icon="△", severity="warning", dismissible=False),
    # ═══════════════════════════════════════════════════════════════
    # MODEL/INFERENCE (RFC-081)
    # ═══════════════════════════════════════════════════════════════
    "model_start": EventUIHints(icon="◎", severity="info", animation="pulse"),
    "model_tokens": EventUIHints(icon="◎", severity="info"),
    "model_thinking": EventUIHints(icon="◜", severity="info", animation="spiral"),
    "model_complete": EventUIHints(icon="✓", severity="success"),
    "model_heartbeat": EventUIHints(icon="·", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # VALIDATION GATES
    # ═══════════════════════════════════════════════════════════════
    "gate_start": EventUIHints(icon="═", severity="info"),
    "gate_step": EventUIHints(icon="├", severity="info"),
    "gate_pass": EventUIHints(icon="✧", severity="success"),
    "gate_fail": EventUIHints(icon="✗", severity="error"),
    # ═══════════════════════════════════════════════════════════════
    # FIX LIFECYCLE
    # ═══════════════════════════════════════════════════════════════
    "fix_start": EventUIHints(icon="⚙", severity="warning", animation="pulse"),
    "fix_progress": EventUIHints(icon="·", severity="info"),
    "fix_attempt": EventUIHints(icon="◇", severity="info"),
    "fix_complete": EventUIHints(icon="✓", severity="success"),
    "fix_failed": EventUIHints(icon="✗", severity="error"),
    # ═══════════════════════════════════════════════════════════════
    # SECURITY (RFC-089)
    # ═══════════════════════════════════════════════════════════════
    "security_violation": EventUIHints(
        icon="⊘", severity="error", dismissible=False, animation="shake"
    ),
    "security_approval_requested": EventUIHints(
        icon="⊗", severity="warning", dismissible=False
    ),
    "security_approval_received": EventUIHints(icon="✓", severity="success"),
    "security_scan_complete": EventUIHints(icon="✓", severity="success"),
    "audit_log_entry": EventUIHints(icon="·", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # SKILL COMPILATION (RFC-111)
    # ═══════════════════════════════════════════════════════════════
    "skill_compile_start": EventUIHints(icon="⚙", severity="info", animation="pulse"),
    "skill_compile_complete": EventUIHints(icon="✓", severity="success", animation="fade-in"),
    "skill_compile_cache_hit": EventUIHints(icon="⋆", severity="success"),
    "skill_subgraph_extracted": EventUIHints(icon="◆", severity="info"),
    "skill_graph_resolved": EventUIHints(icon="◆", severity="info", animation="fade-in"),
    "skill_wave_start": EventUIHints(icon="◇", severity="info"),
    "skill_wave_complete": EventUIHints(icon="✧", severity="info"),
    "skill_cache_hit": EventUIHints(icon="⋆", severity="success"),
    "skill_execute_start": EventUIHints(icon="✧", severity="info", animation="pulse"),
    "skill_execute_complete": EventUIHints(icon="✓", severity="success"),
    # ═══════════════════════════════════════════════════════════════
    # CONVERGENCE (RFC-123)
    # ═══════════════════════════════════════════════════════════════
    "convergence_start": EventUIHints(icon="↻", severity="info", animation="pulse"),
    "convergence_iteration_start": EventUIHints(icon="◇", severity="info"),
    "convergence_iteration_complete": EventUIHints(icon="✧", severity="info"),
    "convergence_fixing": EventUIHints(icon="⚙", severity="warning", animation="pulse"),
    "convergence_stable": EventUIHints(icon="★", severity="success", animation="sparkle"),
    "convergence_timeout": EventUIHints(icon="◔", severity="error"),
    "convergence_stuck": EventUIHints(icon="⟳", severity="error", animation="shake"),
    "convergence_max_iterations": EventUIHints(icon="△", severity="warning"),
    "convergence_budget_exceeded": EventUIHints(icon="¤", severity="error"),
    # ═══════════════════════════════════════════════════════════════
    # MEMORY (RFC-MEMORY)
    # ═══════════════════════════════════════════════════════════════
    "memory_load": EventUIHints(icon="◎", severity="info", animation="pulse"),
    "memory_loaded": EventUIHints(icon="✧", severity="success", animation="fade-in"),
    "memory_new": EventUIHints(icon="✦", severity="info", animation="fade-in"),
    "memory_learning": EventUIHints(icon="≡", severity="info"),
    "memory_dead_end": EventUIHints(icon="⊘", severity="warning"),
    "memory_checkpoint": EventUIHints(icon="▤", severity="info"),
    "memory_saved": EventUIHints(icon="✓", severity="success"),
    "orient": EventUIHints(icon="◐", severity="info", animation="fade-in"),
    "learning_added": EventUIHints(icon="※", severity="success"),
    "decision_made": EventUIHints(icon="▣", severity="info"),
    "failure_recorded": EventUIHints(icon="✗", severity="warning"),
    "briefing_updated": EventUIHints(icon="▢", severity="success"),
    "knowledge_retrieved": EventUIHints(icon="◎", severity="info"),
    "template_matched": EventUIHints(icon="◆", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # PLANNING
    # ═══════════════════════════════════════════════════════════════
    "signal": EventUIHints(icon="✦", severity="info", animation="pulse"),
    "signal_route": EventUIHints(icon="→", severity="info"),
    "plan_start": EventUIHints(icon="✦", severity="info", animation="pulse"),
    "plan_candidate": EventUIHints(icon="◇", severity="info"),
    "plan_candidate_start": EventUIHints(icon="◇", severity="info", animation="pulse"),
    "plan_candidate_generated": EventUIHints(icon="✧", severity="info", animation="fade-in"),
    "plan_candidates_complete": EventUIHints(icon="◆", severity="info"),
    "plan_candidate_scored": EventUIHints(icon="·", severity="info"),
    "plan_scoring_complete": EventUIHints(icon="✧", severity="info"),
    "plan_winner": EventUIHints(icon="★", severity="success", animation="sparkle"),
    "plan_expanded": EventUIHints(icon="✧", severity="info", animation="fade-in"),
    "plan_assess": EventUIHints(icon="◇", severity="info"),
    "plan_refine_start": EventUIHints(icon="◇", severity="info", animation="pulse"),
    "plan_refine_attempt": EventUIHints(icon="·", severity="info"),
    "plan_refine_complete": EventUIHints(icon="✧", severity="info"),
    "plan_refine_final": EventUIHints(icon="◆", severity="info", animation="fade-in"),
    "plan_discovery_progress": EventUIHints(icon="·", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # LENS
    # ═══════════════════════════════════════════════════════════════
    "lens_selected": EventUIHints(icon="◐", severity="info", animation="fade-in"),
    "lens_changed": EventUIHints(icon="↻", severity="info"),
    "lens_suggested": EventUIHints(icon="※", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # INTEGRATION (RFC-067)
    # ═══════════════════════════════════════════════════════════════
    "integration_check_start": EventUIHints(icon="⊕", severity="info", animation="pulse"),
    "integration_check_pass": EventUIHints(icon="✧", severity="success"),
    "integration_check_fail": EventUIHints(icon="✗", severity="error"),
    "stub_detected": EventUIHints(icon="△", severity="warning"),
    "orphan_detected": EventUIHints(icon="⊘", severity="warning"),
    "wire_task_generated": EventUIHints(icon="+", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # CONTRACT VERIFICATION
    # ═══════════════════════════════════════════════════════════════
    "contract_verify_start": EventUIHints(icon="⊕", severity="info", animation="pulse"),
    "contract_verify_pass": EventUIHints(icon="✓", severity="success", animation="fade-in"),
    "contract_verify_fail": EventUIHints(icon="✗", severity="error", animation="shake"),
    # ═══════════════════════════════════════════════════════════════
    # BRIEFING & PREFETCH (RFC-071)
    # ═══════════════════════════════════════════════════════════════
    "briefing_loaded": EventUIHints(icon="▢", severity="info", animation="fade-in"),
    "briefing_saved": EventUIHints(icon="✓", severity="success"),
    "prefetch_start": EventUIHints(icon="✦", severity="info", animation="pulse"),
    "prefetch_complete": EventUIHints(icon="✓", severity="success"),
    "prefetch_timeout": EventUIHints(icon="◔", severity="warning"),
    # ═══════════════════════════════════════════════════════════════
    # RECOVERY (RFC-125)
    # ═══════════════════════════════════════════════════════════════
    "recovery_saved": EventUIHints(icon="▤", severity="warning"),
    "recovery_loaded": EventUIHints(icon="▼", severity="info", animation="fade-in"),
    "recovery_resolved": EventUIHints(icon="✓", severity="success", animation="sparkle"),
    "recovery_aborted": EventUIHints(icon="✗", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # BACKLOG (RFC-094)
    # ═══════════════════════════════════════════════════════════════
    "backlog_goal_added": EventUIHints(icon="+", severity="info", animation="fade-in"),
    "backlog_goal_started": EventUIHints(icon="✧", severity="info", animation="pulse"),
    "backlog_goal_completed": EventUIHints(icon="✓", severity="success", animation="sparkle"),
    "backlog_goal_failed": EventUIHints(icon="✗", severity="error"),
    "backlog_refreshed": EventUIHints(icon="↻", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # MODEL DELEGATION (RFC-137)
    # ═══════════════════════════════════════════════════════════════
    "delegation_started": EventUIHints(icon="◈", severity="info", animation="pulse"),
    "ephemeral_lens_created": EventUIHints(icon="◐", severity="success", animation="fade-in"),
    # ═══════════════════════════════════════════════════════════════
    # AGENT CONSTELLATION (RFC-130)
    # ═══════════════════════════════════════════════════════════════
    "specialist_spawned": EventUIHints(icon="◈", severity="info", animation="pulse"),
    "specialist_completed": EventUIHints(icon="✧", severity="success", animation="fade-in"),
    "checkpoint_found": EventUIHints(icon="▼", severity="info", animation="fade-in"),
    "checkpoint_saved": EventUIHints(icon="▤", severity="success"),
    "phase_complete": EventUIHints(icon="◆", severity="info", animation="fade-in"),
    "autonomous_action_blocked": EventUIHints(icon="⊗", severity="error", animation="shake"),
    "guard_evolution_suggested": EventUIHints(icon="※", severity="warning"),
    # ═══════════════════════════════════════════════════════════════
    # RELIABILITY (Solo Dev Hardening)
    # ═══════════════════════════════════════════════════════════════
    "circuit_breaker_open": EventUIHints(
        icon="⊗", severity="error", dismissible=False, animation="shake"
    ),
    "budget_exhausted": EventUIHints(
        icon="¤", severity="error", dismissible=False, animation="shake"
    ),
    "budget_warning": EventUIHints(icon="¤", severity="warning"),
    "health_check_failed": EventUIHints(
        icon="⊘", severity="error", dismissible=False, animation="shake"
    ),
    "health_warning": EventUIHints(icon="△", severity="warning"),
    "timeout": EventUIHints(icon="◔", severity="error"),
    # ═══════════════════════════════════════════════════════════════
    # CONVERSATIONAL DAG
    # ═══════════════════════════════════════════════════════════════
    "intent_classified": EventUIHints(icon="→", severity="info", animation="fade-in"),
    "node_transition": EventUIHints(icon="◇", severity="info"),
    # ═══════════════════════════════════════════════════════════════
    # DOMAIN DETECTION
    # ═══════════════════════════════════════════════════════════════
    "domain_detected": EventUIHints(icon="◉", severity="info", animation="fade-in"),
    # ═══════════════════════════════════════════════════════════════
    # SESSION LIFECYCLE (RFC-131)
    # ═══════════════════════════════════════════════════════════════
    "session_start": EventUIHints(icon="✦", severity="info", animation="fade-in"),
    "session_ready": EventUIHints(icon="✧", severity="info"),
    "session_end": EventUIHints(icon="★", severity="success", animation="sparkle"),
    "session_crash": EventUIHints(icon="⊗", severity="error", animation="shake"),
    # ═══════════════════════════════════════════════════════════════
    # GOAL LIFECYCLE (RFC-131)
    # ═══════════════════════════════════════════════════════════════
    "goal_received": EventUIHints(icon="✦", severity="info", animation="pulse"),
    "goal_analyzing": EventUIHints(icon="✧", severity="info", animation="spiral"),
    "goal_ready": EventUIHints(icon="◆", severity="info"),
    "goal_complete": EventUIHints(icon="★", severity="success", animation="sparkle"),
    "goal_failed": EventUIHints(icon="✗", severity="error"),
    "goal_paused": EventUIHints(icon="◈", severity="info"),
}


def event_to_dict(event: AgentEvent) -> dict[str, Any]:
    """Serialize an AgentEvent with DEFAULT_UI_HINTS fallback.

    The contracts-layer ``AgentEvent.to_dict()`` does not know about
    ``DEFAULT_UI_HINTS`` (runtime configuration).  This helper adds the
    fallback lookup so that serialised events always carry UI hints when
    a default mapping exists.

    Use this instead of ``event.to_dict()`` when you need the full
    serialisation including default hints (e.g. SSE streaming, JSONL logs).
    """
    result = event.to_dict()
    if "ui_hints" not in result:
        hints = DEFAULT_UI_HINTS.get(event.type.value)
        if hints:
            result["ui_hints"] = hints.to_dict()
    return result
