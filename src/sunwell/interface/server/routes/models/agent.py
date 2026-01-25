"""Agent run response models (RFC-119, RFC-112)."""

from sunwell.interface.server.routes.models.base import CamelModel


class RunStartResponse(CamelModel):
    """Response when starting an agent run."""

    run_id: str
    status: str
    use_v2: bool


class RunStatusResponse(CamelModel):
    """Agent run status."""

    run_id: str
    status: str
    goal: str
    event_count: int
    error: str | None = None


class RunCancelResponse(CamelModel):
    """Response when cancelling a run."""

    status: str
    error: str | None = None


class RunItem(CamelModel):
    """A run in the runs list."""

    run_id: str
    goal: str
    status: str
    source: str
    started_at: str
    completed_at: str | None = None
    event_count: int


class RunsListResponse(CamelModel):
    """List of agent runs."""

    runs: list[RunItem]


class RunHistoryItem(CamelModel):
    """A run in the history list with extended details."""

    run_id: str
    goal: str
    status: str
    source: str
    started_at: str
    completed_at: str | None = None
    event_count: int
    workspace: str | None = None
    lens: str | None = None
    model: str | None = None


class RunEventsResponse(CamelModel):
    """Events for an agent run."""

    run_id: str
    events: list[dict[str, str | int | float | bool | None]]
    error: str | None = None
