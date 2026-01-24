"""Surface Primitives & Layout System (RFC-072).

This package provides:
- SurfacePrimitive: A UI primitive that can be composed into a surface
- SurfaceLayout: A composed arrangement of primitives
- WorkspaceSpec: Specification for layout composition
- SurfaceRenderer: Renders workspace layouts from specs
- SurfaceComposer: Composes layouts from goals (RFC-075 prep)
- PrimitiveRegistry: Registry of available primitives
- Fallback chain: Ensures surface is never empty

Usage:
    from sunwell.surface import (
        SurfaceComposer,
        compose_surface,
        WorkspaceSpec,
        SurfaceRenderer,
        PrimitiveRegistry,
        render_with_fallback,
    )

    # Simple composition
    spec = compose_surface("Build a REST API with tests")

    # Full composition with reasoning
    composer = SurfaceComposer()
    result = composer.compose("Build a REST API", project_path=Path("."))
    print(f"Confidence: {result.confidence}")
    print(f"Primary: {result.spec.primary}")

    # Render to layout
    registry = PrimitiveRegistry.default()
    renderer = SurfaceRenderer(registry)
    layout = render_with_fallback(renderer, result.spec)
"""

from sunwell.surface.blocks import (
    DEFAULT_BLOCKS,
    BlockAction,
    BlockDef,
    BlockRegistry,
)
from sunwell.surface.composer import (
    CompositionResult,
    SurfaceComposer,
    compose_surface,
    compose_surface_with_reasoning,
)
from sunwell.surface.diataxis import (
    DiataxisDetection,
    DiataxisSignal,
    check_diataxis_purity,
    detect_diataxis,
    suggest_diataxis_type,
)
from sunwell.surface.fallback import (
    DEFAULT_LAYOUT,
    DOMAIN_DEFAULTS,
    render_with_fallback,
)
from sunwell.surface.intent import IntentSignals, extract_intent
from sunwell.surface.lens_detection import (
    detect_project_context,
    get_lens_for_project,
    get_mode_for_domain,
)
from sunwell.surface.registry import PrimitiveRegistry
from sunwell.surface.renderer import SurfaceRenderer
from sunwell.surface.scoring import ScoredPrimitive, ScoringContext, ScoringResult
from sunwell.surface.types import (
    DEFAULT_SELECTION_ACTIONS,
    DiataxisType,
    PrimitiveDef,
    SelectionAction,
    SelectionContext,
    SurfaceLayout,
    SurfacePrimitive,
    ValidationState,
    ValidationWarning,
    ViewMode,
    WorkspaceSpec,
    WriterLayout,
)

__all__ = [
    # Types
    "PrimitiveDef",
    "SurfacePrimitive",
    "SurfaceLayout",
    "WorkspaceSpec",
    # RFC-086: Writer types
    "ViewMode",
    "DiataxisType",
    "WriterLayout",
    "ValidationWarning",
    "ValidationState",
    "SelectionContext",
    "SelectionAction",
    "DEFAULT_SELECTION_ACTIONS",
    # Blocks (RFC-080)
    "BlockAction",
    "BlockDef",
    "BlockRegistry",
    "DEFAULT_BLOCKS",
    # Core
    "PrimitiveRegistry",
    "SurfaceRenderer",
    # Composition (RFC-075 prep)
    "SurfaceComposer",
    "CompositionResult",
    "compose_surface",
    "compose_surface_with_reasoning",
    # Intent
    "IntentSignals",
    "extract_intent",
    # Scoring
    "ScoredPrimitive",
    "ScoringContext",
    "ScoringResult",
    # Fallback
    "render_with_fallback",
    "DEFAULT_LAYOUT",
    "DOMAIN_DEFAULTS",
    # RFC-086: Lens detection
    "get_lens_for_project",
    "get_mode_for_domain",
    "detect_project_context",
    # RFC-086: Diataxis detection
    "DiataxisSignal",
    "DiataxisDetection",
    "detect_diataxis",
    "check_diataxis_purity",
    "suggest_diataxis_type",
]
