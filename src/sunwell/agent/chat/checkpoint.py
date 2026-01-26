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
