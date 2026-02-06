"""Configuration and state for the agentic tool loop.

Extracted from loop.py for better organization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ExecutionLane(Enum):
    """Execution lanes for workload isolation.

    Different lane types have independent concurrency limits to prevent
    resource starvation between workload types.
    """

    MAIN = "main"
    """Root agent work - primary user-facing execution."""

    SUBAGENT = "subagent"
    """Child session work - parallelizable subtasks."""

    BACKGROUND = "background"
    """Background work - learning extraction, memory compaction, etc."""


# Default concurrency limits per lane
DEFAULT_LANE_CONCURRENCY: dict[str, int] = {
    ExecutionLane.MAIN.value: 4,
    ExecutionLane.SUBAGENT.value: 8,
    ExecutionLane.BACKGROUND.value: 1,
}


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

    enable_contract_validation: bool = True
    """Run contract validation when protocol context is available (RFC-034)."""

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

    # RFC-XXX: Multi-signal tool selection
    enable_tool_selection: bool = True
    """Use DAG-based progressive tool disclosure for better small model accuracy."""

    tool_selection_max_tools: int | None = None
    """Override max tools for selection (None = model-adaptive)."""

    # =========================================================================
    # Reliability Settings (Solo Dev Hardening)
    # =========================================================================
    circuit_breaker_threshold: int = 5
    """Consecutive failures before opening circuit breaker."""

    circuit_breaker_recovery_seconds: float = 60.0
    """Seconds to wait before attempting recovery after circuit opens."""

    max_tokens: int = 50_000
    """Maximum tokens for this session. Agent stops when exhausted."""

    budget_warning_threshold: float = 0.2
    """Emit warning when budget remaining drops below this ratio (0.0-1.0)."""

    enable_circuit_breaker: bool = True
    """Enable circuit breaker to stop after consecutive failures."""

    enable_budget_enforcement: bool = True
    """Enable hard budget enforcement (stop when exhausted)."""

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

    # =========================================================================
    # Parallel Isolation (Agentic Infrastructure)
    # =========================================================================
    enable_parallel_tasks: bool = True
    """Enable parallel task execution within goals.

    When enabled, TaskDispatcher will route parallelizable task groups
    to ParallelExecutor for concurrent execution. Tasks are identified
    as parallelizable via TaskGraph.get_parallelizable_groups() based on
    their parallel_group assignment and non-overlapping modifies sets.

    When disabled, all tasks execute sequentially regardless of parallel_group.
    """

    max_parallel_tasks: int = 4
    """Maximum concurrent tasks within a parallel group.

    Limits resource consumption during parallel execution. Set based on
    available compute and API rate limits. The actual parallelism may be
    lower if tasks have overlapping modifies sets (file conflicts).
    """

    auto_init_git: bool = False
    """Auto-initialize git for worktree isolation if needed.

    When True and workspace isn't a git repo, automatically run 'git init'
    with an initial commit to enable worktree isolation for parallel tasks.
    When False, falls back to in-memory staging for non-git workspaces.
    """

    enable_worktree_isolation: bool = True
    """Enable git worktree isolation for parallel tasks.

    When enabled, each parallel task gets its own isolated git worktree.
    This prevents file conflicts by construction - tasks cannot interfere
    with each other's file writes.

    When disabled (or for non-git workspaces), falls back to in-memory
    staging with validation before commit.
    """

    enable_content_validation: bool = True
    """Enable content validation before file commits.

    Defense-in-depth: validates that file content isn't tool output
    contamination (e.g., "✓ Wrote file.py" as content). Runs regardless
    of whether worktree isolation is enabled.
    """

    # =========================================================================
    # Freshness and Context Drift Prevention
    # =========================================================================
    # Inspired by Cursor's self-driving codebases: "Ensuring freshness"
    # mechanisms prevent context drift during long autonomous runs.

    enable_scratchpad: bool = True
    """Enable scratchpad pattern for long-running sessions.

    Each subplanner/worker maintains an in-memory scratchpad that gets
    REWRITTEN (not appended to) every N tool calls. This forces the
    agent to synthesize rather than accumulate, preventing context drift.
    """

    scratchpad_rewrite_interval: int = 10
    """Rewrite the scratchpad every N tool calls.

    Lower values mean more frequent synthesis but more overhead.
    Higher values mean less overhead but risk context drift.
    """

    enable_alignment_checkpoints: bool = True
    """Inject self-reflection prompts at regular intervals.

    Every M tool calls, ask: 'Are you still aligned with the original
    goal? What has changed? Should you adjust your approach?'
    """

    alignment_checkpoint_interval: int = 15
    """How often to inject alignment checkpoints (every N tool calls).

    Should be a multiple of scratchpad_rewrite_interval for
    cleaner execution flow.
    """

    enable_context_summarization: bool = True
    """Auto-summarize when approaching context limits.

    When the context window is >80% consumed, automatically summarize
    the current state into a compact briefing and restart with the
    summary injected. Prevents degraded performance from context overflow.
    """

    context_summarization_threshold: float = 0.8
    """Trigger context summarization when this fraction of context is consumed.

    Range: 0.0 to 1.0. At 0.8 (default), summarization triggers when
    80% of the context window is used.
    """

    # =========================================================================
    # Trinket Composition
    # =========================================================================
    refresh_trinkets_per_turn: bool = False
    """Refresh dynamic trinkets each turn.

    When True, non-cacheable trinkets regenerate their content
    at the start of each turn. When False, only regenerates
    when context changes significantly.

    Note: Trinket composition is always enabled. The system uses modular
    trinkets to compose system prompts from independent components
    (time, briefing, learnings, tool guidance, memory context).
    """

    # =========================================================================
    # Execution Lanes (Agentic Infrastructure Phase 2)
    # =========================================================================
    execution_lane: ExecutionLane = ExecutionLane.MAIN
    """Which lane this loop runs in.

    Determines concurrency limits and queue isolation.
    """

    lane_concurrency: dict[str, int] | None = None
    """Override default concurrency limits per lane.

    Keys are lane values ("main", "subagent", "background").
    If None, uses DEFAULT_LANE_CONCURRENCY.

    Example: {"main": 2, "subagent": 4} for lower parallelism.
    """

    def get_lane_concurrency(self, lane: ExecutionLane) -> int:
        """Get concurrency limit for a lane."""
        if self.lane_concurrency and lane.value in self.lane_concurrency:
            return self.lane_concurrency[lane.value]
        return DEFAULT_LANE_CONCURRENCY.get(lane.value, 1)


@dataclass(slots=True)
class LoopState:
    """Mutable state for the agentic loop."""

    messages: list = field(default_factory=list)
    """Conversation history (list of Message objects)."""

    turn: int = 0
    """Current turn number."""

    tool_calls_total: int = 0
    """Total tool calls executed."""

    model_calls: int = 0
    """Total LLM API calls made (for telemetry)."""

    tokens_input: int = 0
    """Total input tokens used (for telemetry)."""

    tokens_output: int = 0
    """Total output tokens generated (for telemetry)."""

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

    # Adaptive routing tracking
    routing_strategy: str | None = None
    """Strategy used: 'vortex', 'interference', or 'single_shot'."""

    routing_confidence: float | None = None
    """Confidence score used for routing decision."""

    # RFC-034: Contract validation context
    contract_protocol: str | None = None
    """Protocol name for contract validation (set when implementing a contract)."""

    contract_file: str | None = None
    """Path to file containing the Protocol definition."""

    # Freshness tracking (Context Drift Prevention)
    scratchpad: str = ""
    """In-memory scratchpad for the current session.

    REWRITTEN (not appended to) every scratchpad_rewrite_interval tool calls.
    Contains a synthesis of the current execution state.
    """

    last_scratchpad_rewrite: int = 0
    """Tool call count at last scratchpad rewrite."""

    last_alignment_checkpoint: int = 0
    """Tool call count at last alignment checkpoint."""

    context_tokens_estimate: int = 0
    """Estimated tokens consumed in the current context window."""
