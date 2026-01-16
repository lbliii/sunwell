"""Logic for resolving lens inheritance and composition graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.core.types import LensReference
    from sunwell.schema.loader import LensLoader


@dataclass
class LensResolver:
    """Resolves and merges nested lens dependencies."""

    loader: LensLoader
    _resolution_stack: list[str] = field(default_factory=list)

    async def resolve(self, ref: LensReference) -> Lens:
        """Resolve a lens and all its dependencies recursively.
        
        Args:
            ref: Reference to the root lens to resolve
            
        Returns:
            A fully resolved and merged Lens object
        """
        # 1. Prevent circular dependencies
        if ref.source in self._resolution_stack:
            from sunwell.core.types import LensResolutionError
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
                extended_lens = await self.resolve(lens.extends)

            composed_lenses = []
            for comp_ref in lens.compose:
                composed_lenses.append(await self.resolve(comp_ref))

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

    def _merge_lenses(self, root: Lens, bases: list[Lens]) -> Lens:
        """Merge root lens with its base/composed lenses.
        
        Root lens fields override or extend the base lenses.
        """
        from dataclasses import replace
        
        # Start with root fields
        heuristics = list(root.heuristics)
        anti_heuristics = list(root.anti_heuristics)
        personas = list(root.personas)
        det_validators = list(root.deterministic_validators)
        heur_validators = list(root.heuristic_validators)
        workflows = list(root.workflows)
        refiners = list(root.refiners)
        skills = list(root.skills)
        
        # Collect from bases (additive, deduplicated by name)
        for base in bases:
            # Heuristics
            existing_h = {h.name for h in heuristics}
            for h in base.heuristics:
                if h.name not in existing_h:
                    heuristics.append(h)
            
            # Anti-heuristics
            existing_ah = {ah.name for ah in anti_heuristics}
            for ah in base.anti_heuristics:
                if ah.name not in existing_ah:
                    anti_heuristics.append(ah)
                    
            # Personas
            existing_p = {p.name for p in personas}
            for p in base.personas:
                if p.name not in existing_p:
                    personas.append(p)
                    
            # Validators
            existing_dv = {v.name for v in det_validators}
            for v in base.deterministic_validators:
                if v.name not in existing_dv:
                    det_validators.append(v)
                    
            existing_hv = {v.name for v in heur_validators}
            for v in base.heuristic_validators:
                if v.name not in existing_hv:
                    heur_validators.append(v)
                    
            # Workflows
            existing_w = {w.name for w in workflows}
            for w in base.workflows:
                if w.name not in existing_w:
                    workflows.append(w)
                    
            # Refiners
            existing_r = {r.name for r in refiners}
            for r in base.refiners:
                if r.name not in existing_r:
                    refiners.append(r)
                    
            # Skills
            existing_s = {s.name for s in skills}
            for s in base.skills:
                if s.name not in existing_s:
                    skills.append(s)

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
        from sunwell.core.lens import QualityPolicy
        default_policy = QualityPolicy()
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
