"""Configuration and state for the agentic tool loop.

Extracted from loop.py for better organization.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class LoopConfig:
    """Configuration for the agentic loop."""

    max_turns: int = 20
    """Maximum turns before stopping (prevents infinite loops)."""

    temperature: float = 0.3
    """Temperature for model generation."""

    tool_choice: Literal["auto", "none", "required"] | str = "auto"
    """Tool choice mode: auto (model decides), none, required, or specific tool name."""

    enable_confidence_routing: bool = True
    """Use confidence-based routing (Vortex/Interference/Single-shot)."""

    enable_learning_injection: bool = True
    """Inject relevant learnings into tool call context."""

    enable_validation_gates: bool = True
    """Run validation gates after file operations."""

    enable_recovery: bool = True
    """Save recovery state on failures."""

    enable_expertise_injection: bool = True
    """Enhance tool descriptions with lens-specific heuristics."""

    enable_self_reflection: bool = True
    """Reflect on tool patterns every N turns and adjust strategy."""

    reflection_interval: int = 5
    """How often to trigger self-reflection (every N turns)."""

    # RFC-134: Tool call introspection
    enable_introspection: bool = True
    """Intercept and repair malformed tool arguments before execution."""

    # RFC-134: Automatic retry with strategy escalation
    enable_strategy_escalation: bool = True
    """Escalate through strategies (single → interference → vortex) on failures."""

    max_retries_per_tool: int = 3
    """Maximum retries per tool call before escalating to user."""

    # RFC-134: Tool usage learning
    enable_tool_learning: bool = True
    """Track which tool sequences succeed for which task types."""

    # RFC-134: Progressive tool enablement
    enable_progressive_tools: bool = False
    """Start with read-only tools and unlock write tools as trust builds."""

    # RFC-137: Smart-to-dumb model delegation
    enable_delegation: bool = False
    """Enable smart-to-dumb model delegation for cost optimization.

    When enabled and delegation criteria are met, the loop will:
    1. Use a smart model to create an EphemeralLens
    2. Execute the task with a cheaper delegation model using the lens
    """

    delegation_threshold_tokens: int = 2000
    """Minimum expected output tokens to trigger delegation.

    Tasks expected to generate more than this many tokens will use
    delegation if enabled. Lower values = more aggressive delegation.
    """

    # =========================================================================
    # Subagent Coordination (Agentic Infrastructure Upgrade)
    # =========================================================================
    enable_subagents: bool = False
    """Allow spawning subagents for parallel work.

    When enabled, the agent can spawn child sessions for parallelizable
    subtasks. Each subagent runs in its own context with inherited
    workspace access.
    """

    max_subagent_depth: int = 2
    """Maximum nesting depth for subagents.

    Prevents runaway recursion. Depth 0 = root session.
    Depth 1 = first-level subagent, etc.
    """

    max_concurrent_subagents: int = 3
    """Maximum parallel subagents per parent.

    Limits resource consumption. Set based on available
    compute and API rate limits.
    """

    subagent_timeout_seconds: int = 300
    """Timeout for individual subagent runs.

    Prevents hung subagents from blocking the parent.
    """

    subagent_cleanup: Literal["delete", "keep"] = "delete"
    """Default cleanup policy for completed subagents.

    - 'delete': Remove session artifacts after completion (default)
    - 'keep': Preserve for debugging/resumption
    """


@dataclass(slots=True)
class LoopState:
    """Mutable state for the agentic loop."""

    messages: list = field(default_factory=list)
    """Conversation history (list of Message objects)."""

    turn: int = 0
    """Current turn number."""

    tool_calls_total: int = 0
    """Total tool calls executed."""

    file_writes: list[str] = field(default_factory=list)
    """Paths of files written (for validation gates)."""

    # RFC-134: Failure tracking for strategy escalation
    failure_counts: dict[str, int] = field(default_factory=dict)
    """tool_call_id -> failure count for retry escalation."""

    # RFC-134: Tool sequence tracking for learning
    tool_sequence: list[str] = field(default_factory=list)
    """Ordered list of tools called in this turn (for pattern learning)."""

    # RFC-134: Introspection repairs tracking
    repairs_made: int = 0
    """Count of repairs made by introspection."""
