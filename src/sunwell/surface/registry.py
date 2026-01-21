"""Primitive Registry (RFC-072).

Central registry of all available UI primitives with their definitions.
"""

from sunwell.surface.types import PrimitiveDef


class PrimitiveRegistry:
    """Registry of available UI primitives.

    The registry provides fast lookup by ID and validation of primitive
    capabilities (can_be_primary, can_be_secondary, can_be_contextual).
    """

    def __init__(self, primitives: list[PrimitiveDef]) -> None:
        """Initialize registry with primitive definitions.

        Args:
            primitives: List of primitive definitions
        """
        self._primitives: dict[str, PrimitiveDef] = {p.id: p for p in primitives}

    def __contains__(self, primitive_id: str) -> bool:
        """Check if a primitive ID exists in registry."""
        return primitive_id in self._primitives

    def __getitem__(self, primitive_id: str) -> PrimitiveDef:
        """Get a primitive definition by ID.

        Raises:
            KeyError: If primitive not found
        """
        return self._primitives[primitive_id]

    def get(self, primitive_id: str) -> PrimitiveDef | None:
        """Get a primitive definition by ID, or None if not found."""
        return self._primitives.get(primitive_id)

    def list_all(self) -> list[PrimitiveDef]:
        """Get all primitive definitions."""
        return list(self._primitives.values())

    def list_by_category(self, category: str) -> list[PrimitiveDef]:
        """Get primitives by category."""
        return [p for p in self._primitives.values() if p.category == category]

    def list_primary_capable(self) -> list[PrimitiveDef]:
        """Get primitives that can be primary."""
        return [p for p in self._primitives.values() if p.can_be_primary]

    def list_secondary_capable(self) -> list[PrimitiveDef]:
        """Get primitives that can be secondary."""
        return [p for p in self._primitives.values() if p.can_be_secondary]

    def list_contextual_capable(self) -> list[PrimitiveDef]:
        """Get primitives that can be contextual."""
        return [p for p in self._primitives.values() if p.can_be_contextual]

    @classmethod
    def default(cls) -> PrimitiveRegistry:
        """Create registry with all default primitives."""
        return cls(_DEFAULT_PRIMITIVES)


# =============================================================================
# DEFAULT PRIMITIVE DEFINITIONS
# =============================================================================

_DEFAULT_PRIMITIVES: list[PrimitiveDef] = [
    # -------------------------------------------------------------------------
    # Code Domain
    # -------------------------------------------------------------------------
    PrimitiveDef(
        id="CodeEditor",
        category="code",
        component="CodeEditor",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="full",
        size_options=("full", "split", "panel"),
    ),
    PrimitiveDef(
        id="FileTree",
        category="code",
        component="FileTree",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="sidebar",
        size_options=("sidebar", "floating"),
    ),
    PrimitiveDef(
        id="Terminal",
        category="code",
        component="Terminal",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="bottom",
        size_options=("bottom", "split", "floating"),
    ),
    PrimitiveDef(
        id="TestRunner",
        category="code",
        component="TestRunner",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=True,
        default_size="panel",
        size_options=("panel", "floating", "widget"),
    ),
    PrimitiveDef(
        id="DiffView",
        category="code",
        component="DiffView",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="split",
        size_options=("full", "split"),
    ),
    PrimitiveDef(
        id="Preview",
        category="code",
        component="Preview",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="split",
        size_options=("split", "floating", "full"),
    ),
    PrimitiveDef(
        id="Dependencies",
        category="code",
        component="Dependencies",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="sidebar",
        size_options=("sidebar", "floating"),
    ),
    # -------------------------------------------------------------------------
    # Planning Domain
    # -------------------------------------------------------------------------
    PrimitiveDef(
        id="Kanban",
        category="planning",
        component="KanbanBoard",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="full",
        size_options=("full", "split"),
    ),
    PrimitiveDef(
        id="Timeline",
        category="planning",
        component="Timeline",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="full",
        size_options=("full", "panel"),
    ),
    PrimitiveDef(
        id="GoalTree",
        category="planning",
        component="GoalTree",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="sidebar",
        size_options=("sidebar", "full"),
    ),
    PrimitiveDef(
        id="TaskList",
        category="planning",
        component="TaskList",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=True,
        default_size="panel",
        size_options=("panel", "widget"),
    ),
    PrimitiveDef(
        id="Calendar",
        category="planning",
        component="Calendar",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="full",
        size_options=("full", "panel"),
    ),
    PrimitiveDef(
        id="Metrics",
        category="planning",
        component="Metrics",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=True,
        default_size="widget",
        size_options=("widget", "panel"),
    ),
    # -------------------------------------------------------------------------
    # Writing Domain
    # -------------------------------------------------------------------------
    PrimitiveDef(
        id="ProseEditor",
        category="writing",
        component="ProseEditor",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="full",
        size_options=("full", "split"),
    ),
    PrimitiveDef(
        id="Outline",
        category="writing",
        component="Outline",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="sidebar",
        size_options=("sidebar",),
    ),
    PrimitiveDef(
        id="References",
        category="writing",
        component="References",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=True,
        default_size="panel",
        size_options=("panel", "floating"),
    ),
    PrimitiveDef(
        id="WordCount",
        category="writing",
        component="WordCount",
        can_be_primary=False,
        can_be_secondary=False,
        can_be_contextual=True,
        default_size="widget",
        size_options=("widget",),
    ),
    # -------------------------------------------------------------------------
    # Data Domain
    # -------------------------------------------------------------------------
    PrimitiveDef(
        id="DataTable",
        category="data",
        component="DataTable",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="full",
        size_options=("full", "panel"),
    ),
    PrimitiveDef(
        id="Chart",
        category="data",
        component="Chart",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="panel",
        size_options=("panel", "full"),
    ),
    PrimitiveDef(
        id="QueryBuilder",
        category="data",
        component="QueryBuilder",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="panel",
        size_options=("panel",),
    ),
    PrimitiveDef(
        id="Summary",
        category="data",
        component="Summary",
        can_be_primary=False,
        can_be_secondary=False,
        can_be_contextual=True,
        default_size="widget",
        size_options=("widget",),
    ),
    # -------------------------------------------------------------------------
    # Universal (Always Available)
    # -------------------------------------------------------------------------
    PrimitiveDef(
        id="MemoryPane",
        category="universal",
        component="MemoryPane",
        can_be_primary=False,
        can_be_secondary=True,
        can_be_contextual=True,
        default_size="sidebar",
        size_options=("sidebar", "floating", "widget"),
    ),
    PrimitiveDef(
        id="Input",
        category="universal",
        component="InputBar",
        can_be_primary=False,
        can_be_secondary=False,
        can_be_contextual=False,
        default_size="bottom",
        size_options=("bottom",),
    ),
    PrimitiveDef(
        id="DAGView",
        category="universal",
        component="DAGView",
        can_be_primary=True,
        can_be_secondary=True,
        can_be_contextual=False,
        default_size="panel",
        size_options=("panel", "full"),
    ),
    PrimitiveDef(
        id="BriefingCard",
        category="universal",
        component="BriefingCard",
        can_be_primary=False,
        can_be_secondary=False,
        can_be_contextual=True,
        default_size="widget",
        size_options=("widget",),
    ),
]
