"""Logic for resolving lens inheritance and composition graphs.

RFC-131: Added default composition support via `apply_defaults` parameter.
Default lenses (from config.lens.default_compose) are prepended to the
resolution chain, providing global base layers like M'uru identity.
"""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.types.types import LensReference
    from sunwell.foundation.core.lens import Lens, QualityPolicy
    from sunwell.foundation.schema.loader import LensLoader

# Lazy singleton for default QualityPolicy (avoid per-call allocation)
_DEFAULT_QUALITY_POLICY: QualityPolicy | None = None


def _get_default_policy() -> QualityPolicy:
    """Lazy singleton for default QualityPolicy."""
    global _DEFAULT_QUALITY_POLICY
    if _DEFAULT_QUALITY_POLICY is None:
        from sunwell.foundation.core.lens import QualityPolicy

        _DEFAULT_QUALITY_POLICY = QualityPolicy()
    return _DEFAULT_QUALITY_POLICY


@dataclass(slots=True)
class LensResolver:
    """Resolves and merges nested lens dependencies.

    RFC-131: Supports Helm-style layering with default composition.
    Resolution order:
    1. defaults.yaml default_compose → Implicit base layers
    2. lens.extends → Single inheritance
    3. lens.compose[] → Mixin layers (ordered)
    4. lens fields → Root overrides
    """

    loader: LensLoader
    _resolution_stack: list[str] = field(default_factory=list)

    async def resolve(
        self,
        ref: LensReference,
        *,
        apply_defaults: bool = True,
    ) -> Lens:
        """Resolve a lens and all its dependencies recursively.

        Args:
            ref: Reference to the root lens to resolve
            apply_defaults: Whether to apply global default_compose lenses (RFC-131)

        Returns:
            A fully resolved and merged Lens object
        """
        # Resolve the lens tree first (without defaults)
        resolved = await self._resolve_internal(ref)

        # RFC-131: Apply default composition if enabled
        if apply_defaults:
            resolved = await self._apply_default_composition(resolved)

        return resolved

    async def _resolve_internal(self, ref: LensReference) -> Lens:
        """Internal resolution without default composition.

        This is the original resolution logic, now separated so we can
        apply defaults at the end of the full resolution chain.
        """
        # 1. Prevent circular dependencies
        if ref.source in self._resolution_stack:
            from sunwell.core.types.types import LensResolutionError

            raise LensResolutionError.create(
                lens_name=ref.source,
                error_type="circular_dependency",
                message=f"Circular dependency detected: {' -> '.join(self._resolution_stack)} -> {ref.source}",
            )

        self._resolution_stack.append(ref.source)
        try:
            # 2. Load the base lens
            lens = await self.loader.load_ref(ref)

            # 3. Resolve dependencies (extends and compose)
            # Fetch all dependent lenses
            extended_lens = None
            if lens.extends:
                extended_lens = await self._resolve_internal(lens.extends)

            composed_lenses = []
            for comp_ref in lens.compose:
                composed_lenses.append(await self._resolve_internal(comp_ref))

            # 4. Merge all lenses
            # Order: Extended lens (base) -> Composed lenses (in order) -> Root lens (overrides)
            base_lenses = []
            if extended_lens:
                base_lenses.append(extended_lens)
            base_lenses.extend(composed_lenses)

            if not base_lenses:
                return lens

            return self._merge_lenses(lens, base_lenses)

        finally:
            self._resolution_stack.pop()

    async def _apply_default_composition(self, lens: Lens) -> Lens:
        """Apply default_compose lenses from config (RFC-131).

        Default lenses are prepended so the root lens overrides them.
        This enables Helm-style global values that can be overridden
        by any lens.
        """
        from sunwell.core.types.types import LensReference
        from sunwell.foundation.config import get_config

        config = get_config()
        default_compose = config.lens.default_compose

        if not default_compose:
            return lens

        # Resolve default lenses (without applying defaults again to avoid recursion)
        default_lenses = []
        for source in default_compose:
            # Skip if lens already has this default in its compose chain
            # (prevents duplicates when lens explicitly composes a default)
            try:
                default_ref = LensReference(source=source)
                default_lens = await self._resolve_internal(default_ref)
                default_lenses.append(default_lens)
            except Exception:
                # Default lens not found - skip silently
                # This allows graceful degradation if base lens is missing
                pass

        if not default_lenses:
            return lens

        # Merge: defaults first (so root lens overrides them)
        return self._merge_lenses(lens, default_lenses)

    def _merge_lenses(self, root: Lens, bases: list[Lens]) -> Lens:
        """Merge root lens with its base/composed lenses.

        Root lens fields override or extend the base lenses.
        """
        from dataclasses import replace

        # Start with root fields and build name indexes once (O(n) total, not O(n²))
        heuristics = list(root.heuristics)
        anti_heuristics = list(root.anti_heuristics)
        personas = list(root.personas)
        det_validators = list(root.deterministic_validators)
        heur_validators = list(root.heuristic_validators)
        workflows = list(root.workflows)
        refiners = list(root.refiners)
        skills = list(root.skills)

        # Build sets once before loop, update incrementally O(1) per insert
        existing_h = {h.name for h in heuristics}
        existing_ah = {ah.name for ah in anti_heuristics}
        existing_p = {p.name for p in personas}
        existing_dv = {v.name for v in det_validators}
        existing_hv = {v.name for v in heur_validators}
        existing_w = {w.name for w in workflows}
        existing_r = {r.name for r in refiners}
        existing_s = {s.name for s in skills}

        # Collect from bases (additive, deduplicated by name)
        for base in bases:
            # Heuristics
            for h in base.heuristics:
                if h.name not in existing_h:
                    heuristics.append(h)
                    existing_h.add(h.name)

            # Anti-heuristics
            for ah in base.anti_heuristics:
                if ah.name not in existing_ah:
                    anti_heuristics.append(ah)
                    existing_ah.add(ah.name)

            # Personas
            for p in base.personas:
                if p.name not in existing_p:
                    personas.append(p)
                    existing_p.add(p.name)

            # Validators
            for v in base.deterministic_validators:
                if v.name not in existing_dv:
                    det_validators.append(v)
                    existing_dv.add(v.name)

            for v in base.heuristic_validators:
                if v.name not in existing_hv:
                    heur_validators.append(v)
                    existing_hv.add(v.name)

            # Workflows
            for w in base.workflows:
                if w.name not in existing_w:
                    workflows.append(w)
                    existing_w.add(w.name)

            # Refiners
            for r in base.refiners:
                if r.name not in existing_r:
                    refiners.append(r)
                    existing_r.add(r.name)

            # Skills
            for s in base.skills:
                if s.name not in existing_s:
                    skills.append(s)
                    existing_s.add(s.name)

        # Non-collection fields: Root overrides bases
        communication = root.communication
        if not communication:
            for base in bases:
                if base.communication:
                    communication = base.communication
                    break

        framework = root.framework
        if not framework:
            for base in bases:
                if base.framework:
                    framework = base.framework
                    break

        provenance = root.provenance
        if not provenance:
            for base in bases:
                if base.provenance:
                    provenance = base.provenance
                    break

        router = root.router
        if not router:
            for base in bases:
                if base.router:
                    router = base.router
                    break

        skill_retry = root.skill_retry
        if not skill_retry:
            for base in bases:
                if base.skill_retry:
                    skill_retry = base.skill_retry
                    break

        quality_policy = root.quality_policy
        # If root policy is just defaults, try to get from bases
        default_policy = _get_default_policy()
        if quality_policy == default_policy:
            for base in bases:
                if base.quality_policy != default_policy:
                    quality_policy = base.quality_policy
                    break

        return replace(
            root,
            heuristics=tuple(heuristics),
            anti_heuristics=tuple(anti_heuristics),
            personas=tuple(personas),
            deterministic_validators=tuple(det_validators),
            heuristic_validators=tuple(heur_validators),
            workflows=tuple(workflows),
            refiners=tuple(refiners),
            skills=tuple(skills),
            communication=communication,
            framework=framework,
            provenance=provenance,
            router=router,
            skill_retry=skill_retry,
            quality_policy=quality_policy,
        )
