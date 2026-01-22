"""Interaction Router (RFC-075).

Routes analyzed intent to appropriate handler (workspace, view, action, conversation).
"""

from dataclasses import dataclass
from typing import Any, Protocol

from sunwell.interface.executor import ActionExecutor
from sunwell.interface.types import IntentAnalysis
from sunwell.interface.views import ViewRenderer


class InterfaceOutput(Protocol):
    """Protocol for rendered interface output."""

    pass


@dataclass(frozen=True, slots=True)
class WorkspaceOutput:
    """Full workspace was rendered."""

    layout_id: str
    response: str | None
    workspace_spec: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": "workspace",
            "layout_id": self.layout_id,
            "response": self.response,
            "workspace_spec": self.workspace_spec,
        }


@dataclass(frozen=True, slots=True)
class ViewOutput:
    """View was rendered."""

    view_type: str
    data: dict[str, Any]
    response: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": "view",
            "view_type": self.view_type,
            "data": self.data,
            "response": self.response,
        }


@dataclass(frozen=True, slots=True)
class ActionOutput:
    """Action was executed."""

    action_type: str
    success: bool
    response: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": "action",
            "action_type": self.action_type,
            "success": self.success,
            "response": self.response,
            "data": self.data,
        }


@dataclass(frozen=True, slots=True)
class AuxiliaryPanel:
    """Contextual panel to display alongside conversation."""

    panel_type: str
    """Panel type: "image", "chart", "upload", "table", "preview", "web"."""

    title: str | None = None
    """Optional panel title."""

    data: dict[str, Any] | None = None
    """Panel-specific data (e.g., {"url": "...", "alt": "..."} for images)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "panel_type": self.panel_type,
            "title": self.title,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuxiliaryPanel:
        """Deserialize from dictionary."""
        return cls(
            panel_type=data["panel_type"],
            title=data.get("title"),
            data=data.get("data"),
        )


@dataclass(frozen=True, slots=True)
class ConversationOutput:
    """Conversation response with optional contextual panels."""

    response: str
    mode: str | None
    auxiliary_panels: tuple[AuxiliaryPanel, ...] = ()
    """Contextual panels to display alongside the conversation."""

    suggested_tools: tuple[str, ...] = ()
    """Suggested input tools: "upload", "camera", "voice", "draw"."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": "conversation",
            "response": self.response,
            "mode": self.mode,
            "auxiliary_panels": [p.to_dict() for p in self.auxiliary_panels],
            "suggested_tools": list(self.suggested_tools),
        }


@dataclass(frozen=True, slots=True)
class HybridOutput:
    """Combined action + view."""

    action: ActionOutput
    view: ViewOutput

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": "hybrid",
            "action": self.action.to_dict(),
            "view": self.view.to_dict(),
        }


@dataclass
class InteractionRouter:
    """Routes analyzed intent to appropriate handler."""

    action_executor: ActionExecutor
    view_renderer: ViewRenderer
    surface_composer: Any | None = None  # SurfaceComposer from RFC-072

    async def route(
        self, analysis: IntentAnalysis
    ) -> WorkspaceOutput | ViewOutput | ActionOutput | ConversationOutput | HybridOutput:
        """Route intent analysis to appropriate handler."""
        match analysis.interaction_type:
            case "workspace":
                return await self._handle_workspace(analysis)
            case "view":
                return await self._handle_view(analysis)
            case "action":
                return await self._handle_action(analysis)
            case "conversation":
                return await self._handle_conversation(analysis)
            case "hybrid":
                return await self._handle_hybrid(analysis)
            case _:
                # Fallback to conversation
                return ConversationOutput(
                    response=analysis.response or "I'm here to help. What would you like to do?",
                    mode="informational",
                )

    async def _handle_workspace(self, analysis: IntentAnalysis) -> WorkspaceOutput:
        """Render a full workspace via RFC-072."""
        if not analysis.workspace:
            # Fallback to default workspace
            from sunwell.surface.types import WorkspaceSpec

            workspace = WorkspaceSpec(
                primary="CodeEditor",
                secondary=("FileTree",),
                contextual=(),
                arrangement="standard",
            )
        else:
            workspace = analysis.workspace

        # If we have a surface composer, use it to generate a layout ID
        layout_id = "default"
        if self.surface_composer:
            try:
                result = self.surface_composer.compose_minimal(analysis.response or "")
                layout_id = result.primary if hasattr(result, "primary") else "composed"
            except Exception:
                pass

        workspace_dict = {
            "primary": workspace.primary,
            "secondary": list(workspace.secondary),
            "contextual": list(workspace.contextual),
            "arrangement": workspace.arrangement,
            "seed_content": workspace.seed_content,
        }

        return WorkspaceOutput(
            layout_id=layout_id,
            response=analysis.response,
            workspace_spec=workspace_dict,
        )

    async def _handle_view(self, analysis: IntentAnalysis) -> ViewOutput:
        """Render a single-purpose view."""
        if not analysis.view:
            return ViewOutput(
                view_type="error",
                data={"message": "No view specified"},
                response=analysis.response,
            )

        # Render the view
        view_data = await self.view_renderer.render(analysis.view)

        return ViewOutput(
            view_type=analysis.view.type,
            data=view_data,
            response=analysis.response,
        )

    async def _handle_action(self, analysis: IntentAnalysis) -> ActionOutput:
        """Execute an action immediately."""
        if not analysis.action:
            return ActionOutput(
                action_type="none",
                success=False,
                response="I'm not sure what action to take.",
            )

        # Execute the action
        result = await self.action_executor.execute(analysis.action)

        return ActionOutput(
            action_type=analysis.action.type,
            success=result.success,
            response=analysis.response or result.message,
            data=result.data,
        )

    async def _handle_conversation(self, analysis: IntentAnalysis) -> ConversationOutput:
        """Return a conversation response with contextual panels."""
        # Convert panel dicts to AuxiliaryPanel objects
        panels = tuple(
            AuxiliaryPanel(
                panel_type=p.get("panel_type", "unknown"),
                title=p.get("title"),
                data=p.get("data"),
            )
            for p in analysis.auxiliary_panels
        )

        return ConversationOutput(
            response=analysis.response or "I'm here to help.",
            mode=analysis.conversation_mode,
            auxiliary_panels=panels,
            suggested_tools=analysis.suggested_tools,
        )

    async def _handle_hybrid(self, analysis: IntentAnalysis) -> HybridOutput:
        """Handle action + view combination."""
        # Execute action first
        action_output = await self._handle_action(analysis)

        # Then render view
        view_output = await self._handle_view(analysis)

        return HybridOutput(
            action=action_output,
            view=view_output,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def process_goal(
    goal: str,
    analyzer: Any,  # IntentAnalyzer
    router: InteractionRouter,
) -> WorkspaceOutput | ViewOutput | ActionOutput | ConversationOutput | HybridOutput:
    """Process a goal through the full pipeline.

    Args:
        goal: User's goal string
        analyzer: IntentAnalyzer instance
        router: InteractionRouter instance

    Returns:
        The appropriate output type based on intent
    """
    analysis = await analyzer.analyze(goal)
    return await router.route(analysis)
