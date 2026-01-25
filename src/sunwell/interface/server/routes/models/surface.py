"""Surface/Home response models (RFC-072, RFC-080)."""

from sunwell.interface.server.routes.models.base import CamelModel


class SurfacePrimitive(CamelModel):
    """A UI primitive in the surface."""

    id: str
    category: str
    size: str
    props: dict[str, str | int | float | bool]


class SurfaceComposeResponse(CamelModel):
    """Composed surface layout for a goal."""

    primary: SurfacePrimitive
    secondary: list[SurfacePrimitive]
    contextual: list[SurfacePrimitive]
    arrangement: str


class SurfaceRegistryResponse(CamelModel):
    """Primitive registry."""

    primitives: list[dict[str, str | int | float | bool | None]]


class HomePredictPanel(CamelModel):
    """A panel in the home prediction."""

    panel_type: str
    title: str


class HomePredictResponse(CamelModel):
    """Fast composition prediction for speculative UI."""

    page_type: str
    panels: list[HomePredictPanel]
    input_mode: str
    suggested_tools: list[str]
    confidence: float
    source: str


class HomeProcessGoalResponse(CamelModel):
    """Result of processing a goal through interaction router."""

    type: str
    response: str
    mode: str | None = None
    view_type: str | None = None
    layout_id: str | None = None
    workspace_spec: dict[str, str | list[str] | dict[str, str]] | None = None
    data: dict[str, str] | None = None
    suggested_tools: list[str] | None = None


class HomeBlockActionResponse(CamelModel):
    """Result of executing a block action."""

    success: bool
    message: str
