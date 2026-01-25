"""Surface composition and home routes (RFC-072, RFC-080)."""

from typing import Any

from fastapi import APIRouter

from sunwell.interface.server.routes.models import (
    CamelModel,
    HomeBlockActionResponse,
    HomePredictPanel,
    HomePredictResponse,
    HomeProcessGoalResponse,
    SuccessResponse,
    SurfaceComposeResponse,
    SurfacePrimitive,
    SurfaceRegistryResponse,
)

router = APIRouter(prefix="/api", tags=["surface"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class ComposeSurfaceRequest(CamelModel):
    goal: str
    project_path: str | None = None
    lens: str | None = None
    arrangement: str | None = None


class SurfaceSuccessRequest(CamelModel):
    layout: dict[str, Any]
    goal: str
    duration_seconds: int
    completed: bool


class SurfaceEventRequest(CamelModel):
    primitive_id: str
    event_type: str
    data: dict[str, Any]


class CompositionPredictRequest(CamelModel):
    input: str
    current_page: str = "home"


class HomePredictCompositionRequest(CamelModel):
    input: str
    current_page: str = "home"


class HomeProcessGoalRequest(CamelModel):
    goal: str
    data_dir: str | None = None
    history: list[dict[str, str]] | None = None


class HomeExecuteBlockActionRequest(CamelModel):
    action_id: str
    item_id: str | None = None
    data_dir: str | None = None


# ═══════════════════════════════════════════════════════════════
# SURFACE ROUTES (RFC-072)
# ═══════════════════════════════════════════════════════════════


@router.get("/surface/registry")
async def get_surface_registry() -> SurfaceRegistryResponse:
    """Get primitive registry."""
    return SurfaceRegistryResponse(primitives=[])


@router.post("/surface/compose")
async def compose_surface(request: ComposeSurfaceRequest) -> SurfaceComposeResponse:
    """Compose a surface layout for a goal."""
    return SurfaceComposeResponse(
        primary=SurfacePrimitive(id="code-editor", category="code", size="large", props={}),
        secondary=[],
        contextual=[],
        arrangement=request.arrangement or "standard",
    )


@router.post("/surface/success")
async def record_surface_success(request: SurfaceSuccessRequest) -> SuccessResponse:
    """Record layout success metrics."""
    return SuccessResponse(success=True, message="recorded")


@router.post("/surface/event")
async def emit_surface_event(request: SurfaceEventRequest) -> SuccessResponse:
    """Emit a primitive event."""
    return SuccessResponse(success=True, message="emitted")


# ═══════════════════════════════════════════════════════════════
# COMPOSITION ROUTES (RFC-072)
# ═══════════════════════════════════════════════════════════════


@router.post("/composition/predict")
async def predict_composition(request: CompositionPredictRequest) -> dict[str, Any] | None:
    """Predict composition for input."""
    return None


# ═══════════════════════════════════════════════════════════════
# CONVERGENCE (RFC-113)
# ═══════════════════════════════════════════════════════════════


@router.get("/convergence/{slot}")
async def get_convergence_slot(slot: str) -> dict[str, Any] | None:
    """Get convergence slot data."""
    return None


# ═══════════════════════════════════════════════════════════════
# HOME ROUTES (RFC-080)
# ═══════════════════════════════════════════════════════════════


@router.post("/home/predict-composition")
async def home_predict_composition(
    request: HomePredictCompositionRequest,
) -> HomePredictResponse:
    """Fast Tier 0/1 composition prediction for speculative UI."""
    input_lower = request.input.lower()

    page_type = "conversation"
    panels: list[HomePredictPanel] = []
    input_mode = "chat"
    suggested_tools: list[str] = []

    if any(k in input_lower for k in ["project", "open", "create project"]):
        page_type = "project"
        panels = [HomePredictPanel(panel_type="project_selector", title="Projects")]
        suggested_tools = ["file_tree", "terminal"]
    elif any(k in input_lower for k in ["plan", "design", "architect"]):
        page_type = "planning"
        panels = [HomePredictPanel(panel_type="dag_view", title="Plan")]
        suggested_tools = ["dag", "notes"]
    elif any(k in input_lower for k in ["research", "find", "search", "learn"]):
        page_type = "research"
        panels = [HomePredictPanel(panel_type="search_results", title="Research")]
        suggested_tools = ["web_search", "codebase_search"]
    elif any(k in input_lower for k in ["build", "implement", "code", "fix", "add"]):
        page_type = "project"
        panels = [HomePredictPanel(panel_type="code_editor", title="Code")]
        input_mode = "command"
        suggested_tools = ["editor", "terminal", "git"]

    return HomePredictResponse(
        page_type=page_type,
        panels=panels,
        input_mode=input_mode,
        suggested_tools=suggested_tools,
        confidence=0.75,
        source="regex",
    )


@router.post("/home/process-goal")
async def home_process_goal(request: HomeProcessGoalRequest) -> HomeProcessGoalResponse:
    """Process a goal through the interaction router (Tier 2)."""
    goal_lower = request.goal.lower()

    if any(k in goal_lower for k in ["hello", "hi", "hey", "help"]):
        return HomeProcessGoalResponse(
            type="conversation",
            response=(
                "Hello! I'm Sunwell, your AI development assistant. I can help you:\n\n"
                "• **Build projects** - 'Build a REST API for...' or 'Create a todo app'\n"
                "• **Research code** - 'How does X work?' or 'Find where Y is defined'\n"
                "• **Plan work** - 'Design a system for...' or 'Break down this feature'\n"
                "• **Fix issues** - 'Fix the bug in...' or 'Why is this failing?'\n\n"
                "What would you like to work on?"
            ),
            mode="informational",
            suggested_tools=["project_selector", "terminal"],
        )

    if any(k in goal_lower for k in ["build", "create", "implement", "code", "fix", "add"]):
        return HomeProcessGoalResponse(
            type="workspace",
            layout_id="code_workspace",
            response=f"I'll help you with: {request.goal}",
            workspace_spec={
                "primary": "code_editor",
                "secondary": ["file_tree", "terminal"],
                "contextual": ["agent_status"],
                "arrangement": "standard",
                "seed_content": {"goal": request.goal},
            },
        )

    if any(k in goal_lower for k in ["plan", "design", "architect", "break down"]):
        return HomeProcessGoalResponse(
            type="view",
            view_type="planning",
            response=f"Let me help you plan: {request.goal}",
            data={"goal": request.goal},
        )

    if any(k in goal_lower for k in ["show", "list", "what", "where", "find"]):
        return HomeProcessGoalResponse(
            type="view",
            view_type="search_results",
            response=f"Searching for: {request.goal}",
            data={"query": request.goal},
        )

    return HomeProcessGoalResponse(
        type="conversation",
        response=(
            f"I understand you want to: {request.goal}\n\n"
            "How would you like me to help? I can build it, research it, or break it down."
        ),
        mode="collaborative",
        suggested_tools=[],
    )


@router.post("/home/execute-block-action")
async def home_execute_block_action(request: HomeExecuteBlockActionRequest) -> HomeBlockActionResponse:
    """Execute a block action (e.g., complete habit, open project)."""
    return HomeBlockActionResponse(success=True, message=f"Action {request.action_id} executed")
