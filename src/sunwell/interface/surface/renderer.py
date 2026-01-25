"""Surface Renderer (RFC-072).

Renders workspace layouts from WorkspaceSpec specifications.
"""

from types import MappingProxyType
from typing import Any

from sunwell.interface.generative.surface.registry import PrimitiveRegistry
from sunwell.interface.generative.surface.types import (
    PrimitiveSize,
    SurfaceArrangement,
    SurfaceLayout,
    SurfacePrimitive,
    WorkspaceSpec,
)

# Module-level constant for arrangement → size mapping (avoid per-call rebuild)
_ARRANGEMENT_SIZE_MAP: dict[str, PrimitiveSize] = {
    "standard": "full",
    "focused": "full",
    "split": "split",
    "dashboard": "split",
}


class SurfaceRenderer:
    """Renders workspace layouts from specs.

    Receives WorkspaceSpec from RFC-075 and produces a rendered SurfaceLayout.
    This is a deterministic operation — same spec always produces same layout.
    """

    def __init__(self, registry: PrimitiveRegistry) -> None:
        """Initialize renderer with primitive registry.

        Args:
            registry: Registry of available primitives
        """
        self.registry = registry

    def render(self, spec: WorkspaceSpec) -> SurfaceLayout:
        """Render a WorkspaceSpec into a SurfaceLayout.

        Args:
            spec: Workspace specification from RFC-075

        Returns:
            Rendered layout ready for Svelte

        Raises:
            ValueError: If spec contains unknown primitive IDs
        """
        # 1. Validate all primitive IDs exist in registry
        self._validate_spec(spec)

        # 2. Build primary primitive with appropriate size
        primary = self._build_primitive(
            primitive_id=spec.primary,
            size=self._primary_size_for_arrangement(spec.arrangement),
            props=spec.primary_props or {},
        )

        # 3. Build secondary primitives (max 3)
        secondary = tuple(
            self._build_primitive(
                primitive_id=pid,
                size=self._secondary_size(pid, spec.arrangement),
                props={},
            )
            for pid in spec.secondary[:3]
        )

        # 4. Build contextual primitives (max 2)
        contextual = tuple(
            self._build_primitive(
                primitive_id=pid,
                size="widget",
                props={},
            )
            for pid in spec.contextual[:2]
        )

        # 5. Apply seed content if provided
        if spec.seed_content:
            primary = self._apply_seed_content(primary, spec.seed_content)

        return SurfaceLayout(
            primary=primary,
            secondary=secondary,
            contextual=contextual,
            arrangement=spec.arrangement,
        )

    def _validate_spec(self, spec: WorkspaceSpec) -> None:
        """Validate all primitive IDs exist in registry.

        Args:
            spec: Workspace specification

        Raises:
            ValueError: If any primitive ID is unknown
        """
        all_ids = [spec.primary, *spec.secondary, *spec.contextual]

        for pid in all_ids:
            if pid not in self.registry:
                raise ValueError(f"Unknown primitive: {pid}")

    def _build_primitive(
        self,
        primitive_id: str,
        size: PrimitiveSize,
        props: dict[str, Any],
    ) -> SurfacePrimitive:
        """Build a primitive instance from registry definition.

        Args:
            primitive_id: Primitive ID
            size: Size mode
            props: Component props

        Returns:
            Instantiated primitive
        """
        defn = self.registry[primitive_id]

        return SurfacePrimitive(
            id=primitive_id,
            category=defn.category,
            size=size,
            props=MappingProxyType(props),
        )

    def _primary_size_for_arrangement(self, arrangement: SurfaceArrangement) -> PrimitiveSize:
        """Determine primary primitive size based on arrangement.

        Args:
            arrangement: Layout arrangement

        Returns:
            Appropriate size for primary primitive
        """
        return _ARRANGEMENT_SIZE_MAP.get(arrangement, "full")

    def _secondary_size(self, primitive_id: str, arrangement: SurfaceArrangement) -> PrimitiveSize:
        """Determine secondary primitive size.

        Args:
            primitive_id: Primitive ID
            arrangement: Layout arrangement

        Returns:
            Appropriate size for secondary primitive
        """
        defn = self.registry[primitive_id]

        # In focused mode, minimize secondaries
        if arrangement == "focused":
            return "floating"

        return defn.default_size

    def _apply_seed_content(
        self,
        primitive: SurfacePrimitive,
        seed: dict[str, Any],
    ) -> SurfacePrimitive:
        """Apply seed content to primitive props.

        Args:
            primitive: Primitive instance
            seed: Seed content to apply

        Returns:
            New primitive with seed content in props
        """
        return SurfacePrimitive(
            id=primitive.id,
            category=primitive.category,
            size=primitive.size,
            props=MappingProxyType({**primitive.props, "seed": seed}),
        )
