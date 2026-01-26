"""Generative Interface Types (RFC-075).

Core types for the LLM-driven interaction routing system.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from sunwell.foundation.types.protocol import Serializable

if TYPE_CHECKING:
    from sunwell.interface.surface.types import WorkspaceSpec

InteractionType = Literal["workspace", "view", "action", "conversation", "hybrid"]

# Auxiliary panel types for conversation layouts
AuxiliaryPanelType = Literal[
    "calendar",   # Calendar/scheduling view
    "tasks",      # Task/todo list
    "chart",      # Data visualization (line, bar, pie)
    "image",      # Visual aid or preview
    "upload",     # File upload prompt
    "code",       # Code block with syntax highlighting
    "map",        # Location/geographic reference
    "editor",     # Editable text panel
    "document",   # Document preview
    "products",   # Product comparison list
    "links",      # Related resources/references
]

# Suggested input tool types
InputToolType = Literal["upload", "camera", "voice", "location", "draw"]


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """Specification for an executable action."""

    type: str
    """Action type: "add_to_list", "create_event", "create_reminder", etc."""

    params: dict[str, Any]
    """Action parameters: {"list": "grocery", "item": "broccoli"}."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.type,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionSpec:
        """Deserialize from dictionary."""
        return cls(
            type=data["type"],
            params=data.get("params", {}),
        )


@dataclass(frozen=True, slots=True)
class ViewSpec:
    """Specification for a view to display."""

    type: str
    """View type: "calendar", "list", "notes", "search"."""

    focus: dict[str, Any] | None = None
    """Focus parameters: {"date_range": "2026-01-25..2026-01-26"}."""

    query: str | None = None
    """Search query if applicable."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.type,
            "focus": self.focus,
            "query": self.query,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ViewSpec:
        """Deserialize from dictionary."""
        return cls(
            type=data["type"],
            focus=data.get("focus"),
            query=data.get("query"),
        )


@dataclass(frozen=True, slots=True)
class IntentAnalysis:
    """LLM's analysis of user intent."""

    interaction_type: InteractionType
    """What kind of interaction this needs."""

    confidence: float
    """Model's confidence in this analysis (0.0-1.0)."""

    action: ActionSpec | None = None
    """For action/hybrid: what to execute."""

    view: ViewSpec | None = None
    """For view/hybrid: what to display."""

    workspace: WorkspaceSpec | None = None
    """For workspace: layout specification (from surface/types.py)."""

    response: str | None = None
    """Natural language response to user."""

    reasoning: str | None = None
    """Why this interaction type was chosen (for debugging/transparency)."""

    conversation_mode: str | None = None
    """For conversation: "informational", "empathetic", "collaborative"."""

    auxiliary_panels: tuple[dict[str, Any], ...] = ()
    """Contextual panels to display alongside conversation (image, chart, etc.)."""

    suggested_tools: tuple[str, ...] = ()
    """Suggested input tools: "upload", "camera", "voice", "draw"."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""

        result: dict[str, Any] = {
            "interaction_type": self.interaction_type,
            "confidence": self.confidence,
            "response": self.response,
            "reasoning": self.reasoning,
            "conversation_mode": self.conversation_mode,
            "auxiliary_panels": list(self.auxiliary_panels),
            "suggested_tools": list(self.suggested_tools),
        }

        if self.action:
            result["action"] = self.action.to_dict()
        if self.view:
            result["view"] = self.view.to_dict()
        if self.workspace:
            result["workspace"] = {
                "primary": self.workspace.primary,
                "secondary": list(self.workspace.secondary),
                "contextual": list(self.workspace.contextual),
                "arrangement": self.workspace.arrangement,
                "seed_content": self.workspace.seed_content,
            }

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentAnalysis:
        """Deserialize from dictionary."""
        from sunwell.interface.surface.types import WorkspaceSpec

        action = ActionSpec.from_dict(data["action"]) if data.get("action") else None
        view = ViewSpec.from_dict(data["view"]) if data.get("view") else None

        workspace = None
        if data.get("workspace"):
            ws = data["workspace"]
            workspace = WorkspaceSpec(
                primary=ws["primary"],
                secondary=tuple(ws.get("secondary", [])),
                contextual=tuple(ws.get("contextual", [])),
                arrangement=ws.get("arrangement", "standard"),
                seed_content=ws.get("seed_content"),
            )

        return cls(
            interaction_type=data["interaction_type"],
            confidence=data.get("confidence", 0.8),
            action=action,
            view=view,
            workspace=workspace,
            response=data.get("response"),
            reasoning=data.get("reasoning"),
            conversation_mode=data.get("conversation_mode"),
        )


__all__ = [
    "ActionSpec",
    "AuxiliaryPanelType",
    "InputToolType",
    "IntentAnalysis",
    "InteractionType",
    "Serializable",
    "ViewSpec",
    # WorkspaceSpec is imported from sunwell.interface.surface.types
]
