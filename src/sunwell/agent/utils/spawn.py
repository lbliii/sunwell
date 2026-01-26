"""Spawn types for Agent Constellation (RFC-130).

Types for dynamic specialist spawning. Agent can delegate complex subtasks
to specialists when the task exceeds its expertise or complexity threshold.

Example:
    >>> request = SpawnRequest(
    ...     parent_id="agent-main",
    ...     role="code_reviewer",
    ...     focus="Review auth module for security issues",
    ...     reason="Task requires security expertise",
    ...     tools=("read_file", "grep"),
    ... )
    >>> specialist_id = await naaru.spawn_specialist(request, context)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class SpawnDepthExceeded(Exception):
    """Raised when spawn depth limit is reached.

    Prevents infinite recursion of specialist spawning.
    Default max depth is 3 (agent → specialist → sub-specialist → limit).
    """

    def __init__(self, current_depth: int, max_depth: int) -> None:
        self.current_depth = current_depth
        self.max_depth = max_depth
        super().__init__(
            f"Spawn depth {current_depth} exceeds maximum {max_depth}. "
            "Specialists cannot spawn further sub-specialists."
        )


@dataclass(frozen=True, slots=True)
class SpawnRequest:
    """Request from agent to spawn a specialist.

    When the agent encounters a task that exceeds its expertise or
    complexity threshold, it creates a SpawnRequest to delegate the work.

    Attributes:
        parent_id: ID of the requesting agent/specialist
        role: Specialist role (e.g., "code_reviewer", "architect", "debugger")
        focus: Specific focus for this specialist (the subtask)
        reason: Why spawning is needed (logged for observability)
        tools: Tools the specialist can use (subset of parent's tools)
        context_keys: Context keys to pass from parent
        budget_tokens: Token budget for this specialist
    """

    parent_id: str
    """ID of the requesting agent/specialist."""

    role: str
    """Specialist role (e.g., 'code_reviewer', 'architect', 'debugger')."""

    focus: str
    """Specific focus for this specialist (the subtask description)."""

    reason: str
    """Why spawning is needed (for observability and learning)."""

    tools: tuple[str, ...] = ()
    """Tools the specialist can use (default: inherit from parent)."""

    context_keys: tuple[str, ...] = ()
    """Context keys to pass from parent to specialist."""

    budget_tokens: int = 5_000
    """Token budget allocated to this specialist."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "parent_id": self.parent_id,
            "role": self.role,
            "focus": self.focus,
            "reason": self.reason,
            "tools": list(self.tools),
            "context_keys": list(self.context_keys),
            "budget_tokens": self.budget_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpawnRequest:
        """Create from dict."""
        return cls(
            parent_id=data["parent_id"],
            role=data["role"],
            focus=data["focus"],
            reason=data["reason"],
            tools=tuple(data.get("tools", [])),
            context_keys=tuple(data.get("context_keys", [])),
            budget_tokens=data.get("budget_tokens", 5_000),
        )


@dataclass(slots=True)
class SpecialistState:
    """Tracking state for a spawned specialist.

    Naaru maintains a registry of spawned specialists for:
    - Observability (who spawned what, when)
    - Resource management (budget tracking)
    - Result collection (await completion)
    - Constellation visualization (parent-child relationships)

    Attributes:
        id: Unique specialist ID
        parent_id: ID of the parent that spawned this specialist
        focus: What this specialist is working on
        started_at: When the specialist was spawned
        completed_at: When the specialist finished (None if still running)
        result: Result from the specialist (None until complete)
        tokens_used: Tokens consumed by this specialist
        depth: Spawn depth (0 = direct child of agent)
    """

    id: str
    """Unique specialist identifier."""

    parent_id: str
    """ID of the parent agent/specialist."""

    focus: str
    """What this specialist is working on."""

    started_at: datetime = field(default_factory=datetime.now)
    """When the specialist was spawned."""

    completed_at: datetime | None = None
    """When the specialist finished (None if still running)."""

    result: Any = None
    """Result from the specialist (None until complete)."""

    tokens_used: int = 0
    """Tokens consumed by this specialist."""

    depth: int = 0
    """Spawn depth (0 = direct child of main agent)."""

    @property
    def is_running(self) -> bool:
        """Whether specialist is still running."""
        return self.completed_at is None

    @property
    def duration_seconds(self) -> float | None:
        """Duration in seconds, or None if still running."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def mark_complete(self, result: Any, tokens_used: int = 0) -> None:
        """Mark specialist as complete with result."""
        self.completed_at = datetime.now()
        self.result = result
        self.tokens_used = tokens_used

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "focus": self.focus,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "tokens_used": self.tokens_used,
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecialistState:
        """Create from dict."""
        return cls(
            id=data["id"],
            parent_id=data["parent_id"],
            focus=data["focus"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            result=data.get("result"),
            tokens_used=data.get("tokens_used", 0),
            depth=data.get("depth", 0),
        )


@dataclass(frozen=True, slots=True)
class SpecialistResult:
    """Result from a completed specialist.

    Returned by Naaru.wait_specialist() when specialist completes.

    Attributes:
        specialist_id: ID of the specialist
        success: Whether the specialist succeeded
        output: The specialist's output/result
        summary: Brief summary of what was accomplished
        tokens_used: Tokens consumed
        duration_seconds: How long execution took
        learnings: Any learnings extracted during execution
    """

    specialist_id: str
    """ID of the specialist."""

    success: bool
    """Whether the specialist succeeded."""

    output: Any
    """The specialist's output/result."""

    summary: str
    """Brief summary of what was accomplished."""

    tokens_used: int = 0
    """Tokens consumed by the specialist."""

    duration_seconds: float = 0.0
    """How long execution took."""

    learnings: tuple[str, ...] = ()
    """Any learnings extracted during execution."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "specialist_id": self.specialist_id,
            "success": self.success,
            "output": self.output,
            "summary": self.summary,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "learnings": list(self.learnings),
        }
