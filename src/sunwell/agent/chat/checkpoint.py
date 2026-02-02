"""Chat checkpoints for user-agent handoff (RFC-135).

Checkpoints are user-facing points where the unified loop yields control
back to the user for decisions. Distinct from naaru.checkpoint.CheckpointPhase
which tracks internal agent state for crash recovery.

Types:
    - CONFIRMATION: Before execution starts (approve plan)
    - CLARIFICATION: Need more info from user (during planning)
    - FAILURE: Gate failed, error occurred (recovery options)
    - COMPLETION: Task or goal complete (summary)
    - INTERRUPTION: User typed during execution (pause handling)
    - TRUST_UPGRADE: Offer to auto-approve certain operations (adaptive trust)
    - BACKGROUND_OFFER: Offer to run long task in background
    - AMBIENT_ALERT: Proactive alert about detected issue
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChatCheckpointType(Enum):
    """User-facing checkpoint types for chat-agent handoff.

    Distinct from naaru.checkpoint.CheckpointPhase which tracks internal
    agent state. These represent points where the unified loop yields
    control to the user for a decision.
    """

    CONFIRMATION = "confirmation"
    """Before execution starts (maps to PLAN_COMPLETE phase)."""

    CLARIFICATION = "clarification"
    """Need more info from user during planning."""

    FAILURE = "failure"
    """Gate failed or error occurred, needs recovery decision."""

    COMPLETION = "completion"
    """Task or goal complete (maps to REVIEW_COMPLETE phase)."""

    INTERRUPTION = "interruption"
    """User typed during execution, pause for handling."""

    # ═══════════════════════════════════════════════════════════════════════════
    # Adaptive Trust (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    TRUST_UPGRADE = "trust_upgrade"
    """Offer to auto-approve operations after consistent approval pattern."""

    # ═══════════════════════════════════════════════════════════════════════════
    # Background Tasks (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    BACKGROUND_OFFER = "background_offer"
    """Offer to run long-running task in background with notifications."""

    # ═══════════════════════════════════════════════════════════════════════════
    # Ambient Intelligence (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    AMBIENT_ALERT = "ambient_alert"
    """Proactive alert about detected issue during execution."""


@dataclass(frozen=True, slots=True)
class ChatCheckpoint:
    """A point where agent yields control to chat.

    This is the user-facing checkpoint yielded by UnifiedChatLoop.
    For internal agent state persistence, see naaru.checkpoint.AgentCheckpoint.

    Example:
        >>> checkpoint = ChatCheckpoint(
        ...     type=ChatCheckpointType.CONFIRMATION,
        ...     message="Plan ready (4 tasks). Proceed?",
        ...     options=("Y", "n", "edit"),
        ...     default="Y",
        ... )
    """

    type: ChatCheckpointType
    """Type of checkpoint."""

    message: str
    """Human-readable message explaining the checkpoint."""

    options: tuple[str, ...] = ()
    """Available choices for the user."""

    default: str | None = None
    """Default choice if user just presses Enter."""

    context: dict[str, Any] = field(default_factory=dict)
    """Additional data for UI rendering."""

    # For FAILURE checkpoints
    error: str | None = None
    """Error message if this is a failure checkpoint."""

    recovery_options: tuple[str, ...] = ()
    """Available recovery actions (auto-fix, skip, manual, retry, abort)."""

    # For COMPLETION checkpoints
    summary: str | None = None
    """Completion summary text."""

    files_changed: tuple[str, ...] = ()
    """List of files created or modified."""

    # Link to internal agent checkpoint (for resume support)
    agent_checkpoint_id: str | None = None
    """ID linking to internal AgentCheckpoint for recovery."""

    # ═══════════════════════════════════════════════════════════════════════════
    # TRUST_UPGRADE checkpoint fields
    # ═══════════════════════════════════════════════════════════════════════════

    intent_path: tuple[str, ...] = ()
    """Intent DAG path for trust upgrade (e.g., ("ACT", "WRITE", "CREATE"))."""

    approval_count: int = 0
    """Number of approvals that triggered the upgrade suggestion."""

    # ═══════════════════════════════════════════════════════════════════════════
    # BACKGROUND_OFFER checkpoint fields
    # ═══════════════════════════════════════════════════════════════════════════

    estimated_duration_seconds: int | None = None
    """Estimated task duration in seconds for background offer."""

    plan_summary: str | None = None
    """Human-readable plan summary, e.g., "12 tasks across 8 files"."""

    confidence_range: tuple[int, int] | None = None
    """Confidence interval (low, high) seconds based on historical data."""

    task_count: int | None = None
    """Number of tasks in the plan."""

    # ═══════════════════════════════════════════════════════════════════════════
    # AMBIENT_ALERT checkpoint fields
    # ═══════════════════════════════════════════════════════════════════════════

    alert_type: str | None = None
    """Type of ambient alert (security, optimization, drift, etc.)."""

    severity: str | None = None
    """Alert severity (info, warning, error)."""

    suggested_fix: str | None = None
    """Suggested fix for the detected issue."""


@dataclass(frozen=True, slots=True)
class CheckpointResponse:
    """User's response to a checkpoint.

    Provides convenience properties for common response patterns.

    Example:
        >>> response = CheckpointResponse("y")
        >>> assert response.proceed
        >>> response = CheckpointResponse("abort")
        >>> assert response.abort
    """

    choice: str
    """User's selection from checkpoint options."""

    additional_input: str | None = None
    """Optional additional text from user."""

    @property
    def proceed(self) -> bool:
        """True if user wants to continue/proceed."""
        return self.choice.lower() in ("y", "yes", "proceed", "continue")

    @property
    def skip(self) -> bool:
        """True if user wants to skip this step."""
        return self.choice.lower() in ("s", "skip", "n", "no")

    @property
    def manual(self) -> bool:
        """True if user wants to handle manually."""
        return self.choice.lower() in ("m", "manual")

    @property
    def abort(self) -> bool:
        """True if user wants to abort execution."""
        return self.choice.lower() in ("q", "quit", "abort", "cancel")

    @property
    def edit(self) -> bool:
        """True if user wants to edit the plan."""
        return self.choice.lower() in ("e", "edit", "modify")

    @property
    def retry(self) -> bool:
        """True if user wants to retry."""
        return self.choice.lower() in ("r", "retry", "again")

    @property
    def autofix(self) -> bool:
        """True if user wants to attempt auto-fix."""
        return self.choice.lower() in ("a", "auto", "auto-fix", "autofix", "fix")

    # ═══════════════════════════════════════════════════════════════════════════
    # TRUST_UPGRADE response properties
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def enable_auto_approve(self) -> bool:
        """True if user wants to enable auto-approve for this path."""
        return self.choice.lower() in ("y", "yes", "enable", "auto", "always")

    @property
    def decline_auto_approve(self) -> bool:
        """True if user declines auto-approve (keep asking)."""
        return self.choice.lower() in ("n", "no", "decline", "keep", "ask")

    @property
    def never_suggest(self) -> bool:
        """True if user never wants this suggestion again."""
        return self.choice.lower() in ("never", "stop", "disable")

    # ═══════════════════════════════════════════════════════════════════════════
    # BACKGROUND_OFFER response properties
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def run_background(self) -> bool:
        """True if user wants to run task in background."""
        return self.choice.lower() in ("b", "background", "bg", "async")

    @property
    def wait_foreground(self) -> bool:
        """True if user wants to wait for task in foreground."""
        return self.choice.lower() in ("w", "wait", "foreground", "fg")

    # ═══════════════════════════════════════════════════════════════════════════
    # AMBIENT_ALERT response properties
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def fix_alert(self) -> bool:
        """True if user wants to fix the detected issue."""
        return self.choice.lower() in ("f", "fix", "resolve")

    @property
    def ignore_alert(self) -> bool:
        """True if user wants to ignore this specific alert."""
        return self.choice.lower() in ("i", "ignore", "skip")

    @property
    def suppress_alert_type(self) -> bool:
        """True if user wants to suppress this type of alert."""
        return self.choice.lower() in ("s", "suppress", "mute", "hide")
