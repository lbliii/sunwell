"""Event types for Adaptive Agent streaming (RFC-042, RFC-097, RFC-134, RFC-137).

Events enable live progress streaming so users see what's happening,
reducing perceived wait time. Events are yielded as the agent works.

Event categories:
- Memory: Simulacrum load/save, learning extraction
- Signal: Goal analysis, routing decisions
- Planning: Plan candidates, selection, expansion
- Execution: Task progress, completion
- Validation: Gate checks, errors
- Fix: Auto-repair progress
- Tool Calling: S-Tier tool loop events (RFC-134)
- Delegation: Smart-to-dumb model delegation (RFC-137)

Relationship with schemas package:
- This module provides simple event factory functions (e.g., `task_start_event`)
- schemas/ provides TypedDict schemas and validated versions
- Use simple factories for quick event creation
- Use validated versions (e.g., `validated_task_start_event`) when schema
  compliance is critical or for contract enforcement with frontends

Event Bus (Agentic Infrastructure Upgrade):
- Use `emit()` to emit events with automatic run context injection
- Use `on_event()` to subscribe to events (pub/sub pattern)
- Use `set_run_context()` to establish run context for sequencing
- Events emitted via the bus include: seq (sequence number), run_id, session_id

RFC-097: Events now support optional UI hints for richer frontend rendering.
RFC-134: Added tool introspection and escalation events.
RFC-137: Added delegation and ephemeral lens events.
"""

# =============================================================================
# Event Bus (Agentic Infrastructure Upgrade)
# =============================================================================
from sunwell.agent.events.bus import (
    EventDispatcher,
    clear_run_context,
    collect_events,
    crash_session,
    emit,
    emit_typed,
    end_session,
    get_run_context,
    on_event,
    reset_for_tests,
    set_run_context,
    start_session,
)

# =============================================================================
# Types and Base Classes
# =============================================================================
# =============================================================================
# Constellation Events (RFC-130)
# =============================================================================
from sunwell.agent.events.constellation import (
    autonomous_action_blocked_event,
    checkpoint_found_event,
    checkpoint_saved_event,
    guard_evolution_suggested_event,
    phase_complete_event,
    specialist_completed_event,
    specialist_spawned_event,
)

# =============================================================================
# Convergence Events (RFC-123)
# =============================================================================
from sunwell.agent.events.convergence import (
    convergence_budget_exceeded_event,
    convergence_fixing_event,
    convergence_iteration_complete_event,
    convergence_iteration_start_event,
    convergence_max_iterations_event,
    convergence_stable_event,
    convergence_start_event,
    convergence_stuck_event,
    convergence_timeout_event,
)

# =============================================================================
# Delegation Events (RFC-137)
# =============================================================================
from sunwell.agent.events.delegation import (
    delegation_started_event,
    ephemeral_lens_created_event,
)

# =============================================================================
# Intent Events (Conversational DAG Architecture)
# =============================================================================
from sunwell.agent.events.intent import (
    intent_classified_event,
    node_transition_event,
)

# =============================================================================
# Integration Events (RFC-067, RFC-071)
# =============================================================================
from sunwell.agent.events.integration import (
    briefing_loaded_event,
    briefing_saved_event,
    integration_check_fail_event,
    integration_check_pass_event,
    integration_check_start_event,
    lens_suggested_event,
    orphan_detected_event,
    prefetch_complete_event,
    prefetch_start_event,
    prefetch_timeout_event,
    stub_detected_event,
    wire_task_generated_event,
)

# =============================================================================
# Lifecycle Events
# =============================================================================
from sunwell.agent.events.lifecycle import (
    complete_event,
    fix_progress_event,
    gate_start_event,
    gate_step_event,
    goal_analyzing_event,
    goal_complete_event,
    goal_failed_event,
    goal_ready_event,
    goal_received_event,
    lens_selected_event,
    memory_learning_event,
    signal_event,
    signal_route_event,
    task_complete_event,
    task_output_event,
    task_start_event,
    validate_error_event,
)

# =============================================================================
# Memory Events (RFC-MEMORY)
# =============================================================================
from sunwell.agent.events.memory import (
    briefing_updated_event,
    decision_made_event,
    failure_recorded_event,
    learning_added_event,
    orient_event,
)

# =============================================================================
# Model Events (RFC-081)
# =============================================================================
from sunwell.agent.events.model import (
    model_complete_event,
    model_heartbeat_event,
    model_start_event,
    model_thinking_event,
    model_tokens_event,
)

# =============================================================================
# Planning Events (RFC-090)
# =============================================================================
from sunwell.agent.events.planning import plan_winner_event

# =============================================================================
# Security Events (RFC-089)
# =============================================================================
from sunwell.agent.events.security import (
    audit_log_entry_event,
    security_approval_received_event,
    security_approval_requested_event,
    security_scan_complete_event,
    security_violation_event,
)

# =============================================================================
# Skill Events (RFC-087, RFC-111)
# =============================================================================
from sunwell.agent.events.skill import (
    skill_cache_hit_event,
    skill_compile_cache_hit_event,
    skill_compile_complete_event,
    skill_compile_start_event,
    skill_execute_complete_event,
    skill_execute_start_event,
    skill_graph_resolved_event,
    skill_subgraph_extracted_event,
    skill_wave_complete_event,
    skill_wave_start_event,
)

# =============================================================================
# Tool Events (RFC-134)
# =============================================================================
from sunwell.agent.events.tool import (
    circuit_breaker_open_event,
    health_check_failed_event,
    health_warning_event,
    progressive_unlock_event,
    tool_blocked_event,
    tool_complete_event,
    tool_error_event,
    tool_escalate_event,
    tool_loop_budget_exhausted_event,
    tool_loop_budget_warning_event,
    tool_loop_complete_event,
    tool_loop_start_event,
    tool_loop_turn_event,
    tool_pattern_learned_event,
    tool_repair_event,
    tool_retry_event,
    tool_start_event,
)
from sunwell.agent.events.types import (
    DEFAULT_UI_HINTS,
    AgentEvent,
    EventType,
    EventUIHints,
    GateSummary,
    TaskSummary,
)

__all__ = [
    # Types
    "AgentEvent",
    "EventType",
    "EventUIHints",
    "TaskSummary",
    "GateSummary",
    "DEFAULT_UI_HINTS",
    # Event Bus
    "emit",
    "emit_typed",
    "on_event",
    "EventDispatcher",
    "set_run_context",
    "get_run_context",
    "clear_run_context",
    "start_session",
    "end_session",
    "crash_session",
    "collect_events",
    "reset_for_tests",
    # Lifecycle
    "signal_event",
    "signal_route_event",
    "task_start_event",
    "task_complete_event",
    "task_output_event",
    "gate_start_event",
    "gate_step_event",
    "validate_error_event",
    "fix_progress_event",
    "memory_learning_event",
    "complete_event",
    "lens_selected_event",
    # Goal Lifecycle (RFC-131)
    "goal_received_event",
    "goal_analyzing_event",
    "goal_ready_event",
    "goal_complete_event",
    "goal_failed_event",
    # Tool
    "tool_start_event",
    "tool_complete_event",
    "tool_error_event",
    "tool_loop_start_event",
    "tool_loop_turn_event",
    "tool_loop_complete_event",
    "tool_repair_event",
    "tool_blocked_event",
    "tool_retry_event",
    "tool_escalate_event",
    "tool_pattern_learned_event",
    "progressive_unlock_event",
    # Reliability
    "circuit_breaker_open_event",
    "tool_loop_budget_exhausted_event",
    "tool_loop_budget_warning_event",
    "health_check_failed_event",
    "health_warning_event",
    # Model
    "model_start_event",
    "model_tokens_event",
    "model_thinking_event",
    "model_complete_event",
    "model_heartbeat_event",
    # Skill
    "skill_graph_resolved_event",
    "skill_wave_start_event",
    "skill_wave_complete_event",
    "skill_cache_hit_event",
    "skill_execute_start_event",
    "skill_execute_complete_event",
    "skill_compile_start_event",
    "skill_compile_complete_event",
    "skill_compile_cache_hit_event",
    "skill_subgraph_extracted_event",
    # Integration
    "integration_check_start_event",
    "integration_check_pass_event",
    "integration_check_fail_event",
    "stub_detected_event",
    "orphan_detected_event",
    "wire_task_generated_event",
    "briefing_loaded_event",
    "briefing_saved_event",
    "prefetch_start_event",
    "prefetch_complete_event",
    "prefetch_timeout_event",
    "lens_suggested_event",
    # Security
    "security_approval_requested_event",
    "security_approval_received_event",
    "security_violation_event",
    "security_scan_complete_event",
    "audit_log_entry_event",
    # Planning
    "plan_winner_event",
    # Convergence
    "convergence_start_event",
    "convergence_iteration_start_event",
    "convergence_iteration_complete_event",
    "convergence_fixing_event",
    "convergence_stable_event",
    "convergence_timeout_event",
    "convergence_stuck_event",
    "convergence_max_iterations_event",
    "convergence_budget_exceeded_event",
    # Memory
    "orient_event",
    "learning_added_event",
    "decision_made_event",
    "failure_recorded_event",
    "briefing_updated_event",
    # Constellation
    "specialist_spawned_event",
    "specialist_completed_event",
    "checkpoint_found_event",
    "checkpoint_saved_event",
    "phase_complete_event",
    "autonomous_action_blocked_event",
    "guard_evolution_suggested_event",
    # Delegation
    "delegation_started_event",
    "ephemeral_lens_created_event",
    # Intent
    "intent_classified_event",
    "node_transition_event",
]
