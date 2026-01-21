"""Surface Primitives & Layout Types (RFC-072).

Core types for the surface composition system.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

# Type aliases for clarity
PrimitiveSize = Literal["full", "split", "panel", "sidebar", "widget", "floating", "bottom"]
PrimitiveCategory = Literal["code", "planning", "writing", "data", "universal"]
SurfaceArrangement = Literal["standard", "focused", "split", "dashboard"]


@dataclass(frozen=True, slots=True)
class PrimitiveDef:
    """Definition of a UI primitive.

    This defines the capabilities and constraints of a primitive,
    not an instance of it.
    """

    id: str
    """Unique identifier (e.g., "CodeEditor", "Kanban")."""

    category: PrimitiveCategory
    """Domain category: "code", "planning", "writing", "data", "universal"."""

    component: str
    """Svelte component name to render."""

    can_be_primary: bool = True
    """Whether this primitive can be the main focus."""

    can_be_secondary: bool = True
    """Whether this primitive can be in secondary slots."""

    can_be_contextual: bool = False
    """Whether this primitive can be a floating widget."""

    default_size: PrimitiveSize = "panel"
    """Default size when not specified."""

    size_options: tuple[PrimitiveSize, ...] = ("panel",)
    """Valid size options for this primitive."""


@dataclass(frozen=True, slots=True)
class SurfacePrimitive:
    """A UI primitive instance that can be composed into a surface.

    This is an instantiated primitive with a specific size and props.
    """

    id: str
    """Primitive ID (e.g., "CodeEditor", "Terminal")."""

    category: str
    """Domain category: "code", "planning", "writing", "data", "universal"."""

    size: PrimitiveSize
    """Size mode: "full", "split", "panel", "sidebar", "widget", "floating", "bottom"."""

    props: dict[str, Any] = field(default_factory=dict)
    """Component props (file path, initial state, etc.)."""


@dataclass(frozen=True, slots=True)
class SurfaceLayout:
    """A composed arrangement of primitives.

    This is the output of the SurfaceRenderer — a complete layout
    ready to be rendered by Svelte.
    """

    primary: SurfacePrimitive
    """The main primitive (always present)."""

    secondary: tuple[SurfacePrimitive, ...] = ()
    """Secondary primitives (sidebars, panels, bottom). Max 3."""

    contextual: tuple[SurfacePrimitive, ...] = ()
    """Contextual widgets (floating). Max 2."""

    arrangement: SurfaceArrangement = "standard"
    """Layout arrangement: "standard", "focused", "split", "dashboard"."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "primary": {
                "id": self.primary.id,
                "category": self.primary.category,
                "size": self.primary.size,
                "props": self.primary.props,
            },
            "secondary": [
                {
                    "id": p.id,
                    "category": p.category,
                    "size": p.size,
                    "props": p.props,
                }
                for p in self.secondary
            ],
            "contextual": [
                {
                    "id": p.id,
                    "category": p.category,
                    "size": p.size,
                    "props": p.props,
                }
                for p in self.contextual
            ],
            "arrangement": self.arrangement,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceSpec:
    """Specification received from RFC-075 (Generative Interface).

    This is the contract between intent analysis and rendering.
    RFC-075 decides WHAT to show; RFC-072 decides HOW to show it.
    """

    primary: str
    """Primary primitive ID: "CodeEditor", "ProseEditor", "Kanban", etc."""

    secondary: tuple[str, ...] = ()
    """Secondary primitive IDs: ("FileTree", "Terminal")."""

    contextual: tuple[str, ...] = ()
    """Contextual widget IDs: ("WordCount", "MemoryPane")."""

    arrangement: SurfaceArrangement = "standard"
    """Layout arrangement: "standard", "focused", "split", "dashboard"."""

    seed_content: dict[str, Any] | None = None
    """Pre-populated content: {"outline": ["Chapter 1", "Chapter 2"]}."""

    primary_props: dict[str, Any] | None = None
    """Props for primary primitive: {"file": "/path/to/file.py"}."""
