"""Naaru Unified API Types (RFC-083).

Canonical type definitions for the unified Naaru orchestration layer.
These types define the contract between all entry points (CLI, chat, Studio, API).

All other layers (Rust/Tauri, Svelte) should generate their types from these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# =============================================================================
# ENUMS
# =============================================================================


class ProcessMode(str, Enum):
    """How to process the input."""

    AUTO = "auto"  # Naaru decides based on routing
    CHAT = "chat"  # Conversational (RFC-075 conversation)
    AGENT = "agent"  # Task execution (RFC-032)
    INTERFACE = "interface"  # UI composition (RFC-082)


class NaaruEventType(str, Enum):
    """All possible events from Naaru."""

    # Lifecycle
    PROCESS_START = "process_start"
    PROCESS_COMPLETE = "process_complete"
    PROCESS_ERROR = "process_error"

    # Routing
    ROUTE_DECISION = "route_decision"

    # Composition (RFC-082)
    COMPOSITION_READY = "composition_ready"
    COMPOSITION_UPDATED = "composition_updated"

    # Model
    MODEL_START = "model_start"
    MODEL_THINKING = "model_thinking"
    MODEL_TOKENS = "model_tokens"
    MODEL_COMPLETE = "model_complete"

    # Tasks
    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"

    # Tools
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # Validation
    VALIDATION_START = "validation_start"
    VALIDATION_RESULT = "validation_result"

    # Learning
    LEARNING_EXTRACTED = "learning_extracted"
    LEARNING_PERSISTED = "learning_persisted"


# =============================================================================
# INPUT/OUTPUT TYPES
# =============================================================================


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """A message in conversation history."""

    role: str
    """Role: 'user' or 'assistant'."""

    content: str
    """Message content."""


@dataclass(slots=True)
class ProcessInput:
    """Unified input for all Naaru processing.

    This is THE entry point contract. All paths through Naaru use this.
    """

    content: str
    """User input (goal, message, query)."""

    mode: ProcessMode = ProcessMode.AUTO
    """Processing mode: AUTO, CHAT, AGENT, INTERFACE."""

    page_type: str = "home"
    """Current UI page (for composition): home, project, research, planning, conversation."""

    conversation_history: list[ConversationMessage] = field(default_factory=list)
    """Prior messages for continuity."""

    workspace: Path | None = None
    """Project workspace if applicable."""

    stream: bool = True
    """Stream events as they happen."""

    timeout: float = 300.0
    """Max execution time in seconds."""

    # Optional context
    context: dict[str, Any] = field(default_factory=dict)
    """Additional context (cwd, file state, etc.)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "content": self.content,
            "mode": self.mode.value,
            "page_type": self.page_type,
            "conversation_history": [
                {"role": m.role, "content": m.content}
                for m in self.conversation_history
            ],
            "workspace": str(self.workspace) if self.workspace else None,
            "stream": self.stream,
            "timeout": self.timeout,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProcessInput:
        """Deserialize from dict."""
        history = [
            ConversationMessage(role=m["role"], content=m["content"])
            for m in data.get("conversation_history", [])
        ]
        workspace = Path(data["workspace"]) if data.get("workspace") else None
        return cls(
            content=data["content"],
            mode=ProcessMode(data.get("mode", "auto")),
            page_type=data.get("page_type", "home"),
            conversation_history=history,
            workspace=workspace,
            stream=data.get("stream", True),
            timeout=data.get("timeout", 300.0),
            context=data.get("context", {}),
        )


@dataclass(slots=True)
class CompositionSpec:
    """UI layout specification from Compositor Shard."""

    page_type: str
    """Target page: home, project, research, planning, conversation."""

    panels: list[dict[str, Any]] = field(default_factory=list)
    """Panels to render: [{"panel_type": "calendar", "title": "...", "data": {...}}]."""

    input_mode: str = "hero"
    """Input mode: hero, chat, command, search."""

    suggested_tools: list[str] = field(default_factory=list)
    """Suggested input tools: upload, camera, voice, location, draw."""

    confidence: float = 0.0
    """Confidence in this composition (0.0-1.0)."""

    source: str = "regex"
    """Source of composition: regex, fast_model, large_model."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "page_type": self.page_type,
            "panels": self.panels,
            "input_mode": self.input_mode,
            "suggested_tools": self.suggested_tools,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass(slots=True)
class RoutingDecision:
    """Routing decision from RoutingWorker."""

    interaction_type: str
    """Type: conversation, action, view, workspace, hybrid."""

    confidence: float
    """Routing confidence (0.0-1.0)."""

    tier: int = 1
    """Execution tier: 0=fast, 1=standard, 2=complex."""

    lens: str | None = None
    """Which lens to use (if any)."""

    page_type: str = "home"
    """Target page for UI composition."""

    tools: list[str] = field(default_factory=list)
    """What tools might be needed."""

    mood: str | None = None
    """User's emotional state (for empathetic response)."""

    reasoning: str | None = None
    """Why this routing was chosen."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "interaction_type": self.interaction_type,
            "confidence": self.confidence,
            "tier": self.tier,
            "lens": self.lens,
            "page_type": self.page_type,
            "tools": self.tools,
            "mood": self.mood,
            "reasoning": self.reasoning,
        }


@dataclass(slots=True)
class ProcessOutput:
    """Unified output from all Naaru processing.

    This is THE result contract. All paths through Naaru return this.
    """

    response: str
    """Text response to user."""

    route_type: str
    """How it was routed: conversation, action, view, workspace, hybrid."""

    confidence: float
    """Routing confidence (0.0-1.0)."""

    composition: CompositionSpec | None = None
    """UI layout spec for frontend."""

    tasks_completed: int = 0
    """Number of tasks completed (for agent mode)."""

    artifacts: list[str] = field(default_factory=list)
    """Paths to created artifacts."""

    events: list[NaaruEvent] = field(default_factory=list)
    """Events emitted during processing (for non-streaming)."""

    routing: RoutingDecision | None = None
    """Full routing decision (for debugging/transparency)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "response": self.response,
            "route_type": self.route_type,
            "confidence": self.confidence,
            "composition": self.composition.to_dict() if self.composition else None,
            "tasks_completed": self.tasks_completed,
            "artifacts": self.artifacts,
            "events": [e.to_dict() for e in self.events],
            "routing": self.routing.to_dict() if self.routing else None,
        }


# =============================================================================
# EVENTS
# =============================================================================


@dataclass(slots=True)
class NaaruEvent:
    """Single event type for all Naaru activity.

    Events flow through MessageBus and are consumed by:
    - CLI (progress display)
    - Studio frontend (real-time UI)
    - Logging/metrics
    """

    type: NaaruEventType
    """Event type."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the event occurred."""

    data: dict[str, Any] = field(default_factory=dict)
    """Event payload."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    def to_json(self) -> str:
        """Serialize to JSON string for streaming."""
        import json

        return json.dumps(self.to_dict())


# =============================================================================
# ERRORS
# =============================================================================


@dataclass(frozen=True, slots=True)
class NaaruError(Exception):
    """Unified error model for Naaru.

    All errors from Naaru are wrapped in this type for consistent handling.
    """

    code: str
    """Error code: ROUTE_FAILED, TIMEOUT, MODEL_ERROR, TOOL_ERROR, etc."""

    message: str
    """Human-readable error message."""

    recoverable: bool
    """Whether the operation can be retried."""

    context: dict[str, Any] | None = None
    """Additional context about the error."""

    def __str__(self) -> str:
        """String representation."""
        return f"NaaruError({self.code}): {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "context": self.context,
        }


# =============================================================================
# CONVERGENCE SLOTS (RFC-083)
# =============================================================================


# Standard slot prefixes and their TTLs in seconds
SLOT_TTL_SECONDS: dict[str, float] = {
    "routing": 30,  # Routing decisions are request-specific
    "composition": 300,  # UI state persists across interactions (5 min)
    "context": 1800,  # Workspace/lens context changes slowly (30 min)
    "memories": float("inf"),  # User identity persists for session
    "execution": 300,  # Task state needed for follow-ups (5 min)
    "validation": 30,  # Validation is per-request
    "learnings": float("inf"),  # Learnings persist to SimulacrumStore
}


def get_slot_ttl(slot_id: str) -> float:
    """Get TTL for a slot based on its prefix.

    Args:
        slot_id: Slot identifier like "routing:current" or "context:lens"

    Returns:
        TTL in seconds, or 300 (5 min) default
    """
    prefix = slot_id.split(":")[0]
    return SLOT_TTL_SECONDS.get(prefix, 300)


# Standard Convergence slot definitions
CONVERGENCE_SLOTS = {
    # Routing (set by RoutingWorker)
    "routing:current": "Current routing decision",
    # UI Composition (set by Compositor Shard)
    "composition:current": "UI layout spec",
    "composition:previous": "Previous layout (for transitions)",
    # Context (set by Context Shards)
    "context:lens": "Active lens components",
    "context:workspace": "Workspace files/structure",
    "context:history": "Conversation history",
    # Memory (set by Memory Shard)
    "memories:relevant": "Retrieved from SimulacrumStore",
    "memories:user": "User identity/preferences",
    # Execution (set by Execute Region)
    "execution:current_task": "Task being executed",
    "execution:dag": "Task/artifact dependency graph",
    "execution:artifacts": "Produced artifacts",
    # Validation (set by Validation Worker)
    "validation:result": "Quality check result",
    # Learning (set by Consolidator Shard)
    "learnings:pending": "To persist after task",
}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "ProcessMode",
    "NaaruEventType",
    # Types
    "ConversationMessage",
    "ProcessInput",
    "ProcessOutput",
    "CompositionSpec",
    "RoutingDecision",
    "NaaruEvent",
    "NaaruError",
    # Convergence
    "SLOT_TTL_SECONDS",
    "CONVERGENCE_SLOTS",
    "get_slot_ttl",
]
