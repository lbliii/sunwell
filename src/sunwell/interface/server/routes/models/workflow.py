"""Workflow response models (RFC-086)."""

from sunwell.interface.server.routes.models.base import CamelModel


class WorkflowRouteResponse(CamelModel):
    """Response for workflow intent routing."""

    category: str
    confidence: float
    signals: list[str]
    suggested_workflow: str | None
    tier: str


class WorkflowStep(CamelModel):
    """A step in a workflow execution."""

    id: str
    name: str
    status: str


class WorkflowExecutionResponse(CamelModel):
    """Response for workflow execution state."""

    id: str
    chain_name: str
    description: str
    current_step: int
    total_steps: int
    steps: list[WorkflowStep]
    status: str
    started_at: str
    updated_at: str
    context: dict[str, str]


class WorkflowStatusResponse(CamelModel):
    """Simple workflow status response."""

    status: str


class WorkflowChainItem(CamelModel):
    """A workflow chain definition."""

    name: str
    description: str
    steps: list[str]
    checkpoint_after: list[str]
    tier: str


class WorkflowChainsResponse(CamelModel):
    """List of available workflow chains."""

    chains: list[WorkflowChainItem]


class ActiveWorkflowsResponse(CamelModel):
    """List of active workflow executions."""

    workflows: list[WorkflowExecutionResponse]
