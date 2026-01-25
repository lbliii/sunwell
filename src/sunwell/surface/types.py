"""Surface Primitives & Layout Types (RFC-072).

Core types for the surface composition system.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Protocol, TypeVar

# TypeVar for generic registry protocol
_T = TypeVar("_T")


class RegistryProtocol(Protocol[_T]):
    """Protocol for registries with lookup by ID.

    Both PrimitiveRegistry and BlockRegistry implement this interface.
    """

    def __contains__(self, item_id: str) -> bool:
        """Check if an item ID exists in registry."""
        ...

    def __getitem__(self, item_id: str) -> _T:
        """Get an item by ID. Raises KeyError if not found."""
        ...

    def get(self, item_id: str) -> _T | None:
        """Get an item by ID, or None if not found."""
        ...

    def list_all(self) -> list[_T]:
        """Get all items."""
        ...

    def list_by_category(self, category: str) -> list[_T]:
        """Get items by category."""
        ...

# Type aliases for clarity
PrimitiveSize = Literal["full", "split", "panel", "sidebar", "widget", "floating", "bottom"]
PrimitiveCategory = Literal["code", "planning", "writing", "data", "universal"]
SurfaceArrangement = Literal["standard", "focused", "split", "dashboard", "writer"]

# RFC-086: View modes for writer arrangement
ViewMode = Literal["source", "preview"]

# RFC-086: Diataxis content types
DiataxisType = Literal["TUTORIAL", "HOW_TO", "EXPLANATION", "REFERENCE"]


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

    props: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """Component props (file path, initial state, etc.). Immutable mapping."""


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


# =============================================================================
# RFC-086: Writer-Specific Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class WriterLayout(SurfaceLayout):
    """Layout configuration for writer arrangement (RFC-086).

    Extends SurfaceLayout with writer-specific settings like view mode toggle.
    """

    view_mode: ViewMode = "source"
    """Current view: "source" (editing) or "preview" (reviewing)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base = super().to_dict()
        base["view_mode"] = self.view_mode
        return base


@dataclass(frozen=True, slots=True)
class ValidationWarning:
    """A validation warning from lens validators (RFC-086)."""

    line: int
    """Line number in the document."""

    message: str
    """Warning message."""

    rule: str
    """Validator rule name (e.g., "no_marketing_fluff")."""

    severity: Literal["warning", "error", "info"] = "warning"
    """Severity level."""

    column: int | None = None
    """Optional column number."""

    suggestion: str | None = None
    """Optional fix suggestion."""


# NOTE: DiataxisSignal and DiataxisDetection are defined in diataxis.py
# They are re-exported from __init__.py


@dataclass(frozen=True, slots=True)
class ValidationState:
    """Current validation state for a document (RFC-086)."""

    warnings: tuple[ValidationWarning, ...] = ()
    """Current warnings."""

    errors: tuple[ValidationWarning, ...] = ()
    """Current errors."""

    suggestions: tuple[ValidationWarning, ...] = ()
    """Current suggestions (info level)."""

    is_running: bool = False
    """Whether validation is currently running."""

    last_validated_at: str | None = None
    """ISO timestamp of last validation."""


@dataclass(frozen=True, slots=True)
class SelectionContext:
    """Context for text selection in source or preview (RFC-086).

    Universal selection model — same actions work in both views.
    """

    text: str
    """Selected text content."""

    file: str
    """File path."""

    start: int
    """Start character offset."""

    end: int
    """End character offset."""

    view_mode: ViewMode
    """Which view the selection was made in."""

    line_start: int | None = None
    """Start line number (1-indexed)."""

    line_end: int | None = None
    """End line number (1-indexed)."""

    surrounding_context: str | None = None
    """±5 lines around selection for AI context."""


@dataclass(frozen=True, slots=True)
class SelectionAction:
    """An action that can be performed on selected text (RFC-086)."""

    id: str
    """Action identifier: "improve", "audit", "ask", "explain"."""

    label: str
    """Display label."""

    shortcut: str | None = None
    """Keyboard shortcut (e.g., "⌘I")."""


# Default selection actions (RFC-086)
DEFAULT_SELECTION_ACTIONS: tuple[SelectionAction, ...] = (
    SelectionAction(id="improve", label="Improve", shortcut="⌘I"),
    SelectionAction(id="audit", label="Audit", shortcut="⌘A"),
    SelectionAction(id="ask", label="Ask...", shortcut="⌘K"),
    SelectionAction(id="explain", label="Explain"),
)
