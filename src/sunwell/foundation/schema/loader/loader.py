"""Main LensLoader class that coordinates all parsers."""

from pathlib import Path
from typing import Any

from sunwell.contracts.fount import FountProtocol
from sunwell.foundation.schema.models.types import LensReference
from sunwell.foundation.core.lens import Lens
from sunwell.foundation.errors import ErrorCode, lens_error
from sunwell.foundation.schema.loader.parsers import (
    parse_affordances,
    parse_anti_heuristics,
    parse_communication,
    parse_deterministic_validators,
    parse_framework,
    parse_heuristic_validators,
    parse_heuristics,
    parse_identity,
    parse_lens_reference,
    parse_metadata,
    parse_personas,
    parse_provenance,
    parse_quality_policy,
    parse_refiners,
    parse_router,
    parse_schema_validators,
    parse_skill,
    parse_skill_retry,
    parse_skills,
    parse_spellbook,
    parse_tool_profile,
    parse_workflows,
)
from sunwell.foundation.schema.loader.presets import load_presets, resolve_preset
from sunwell.foundation.utils import safe_yaml_load, safe_yaml_loads


class LensLoader:
    """Load lens definitions from files."""

    def __init__(self, fount_client: FountProtocol | None = None):
        self.fount = fount_client
        self._presets: dict[str, dict] | None = None  # Lazy-loaded presets

    def _load_presets(self) -> dict[str, dict]:
        """Load permission presets from YAML (RFC-092)."""
        if self._presets is not None:
            return self._presets
        self._presets = load_presets()
        return self._presets

    def _resolve_preset(self, skill_data: dict) -> dict:
        """Resolve preset inheritance for a skill (RFC-092)."""
        presets = self._load_presets()
        return resolve_preset(skill_data, presets)

    def load(self, path: Path | str) -> Lens:
        """Load a lens from a YAML file."""
        path = Path(path)

        if not path.exists():
            raise lens_error(
                code=ErrorCode.LENS_NOT_FOUND,
                lens=path.stem,
                path=str(path),
            )

        try:
            data = safe_yaml_load(path)
        except ValueError as e:
            raise lens_error(
                code=ErrorCode.LENS_PARSE_ERROR,
                lens=path.stem,
                path=str(path),
                detail=str(e),
                cause=e,
            ) from e

        lens = self._parse_lens(data, source_path=path)
        return lens

    def resolve_lens_path(self, ref: str) -> Path | None:
        """Resolve a lens reference to an actual file path (RFC-131).

        Searches for lens files in configured search paths, trying:
        1. Exact path as given
        2. With .lens extension added
        3. In each search path directory

        Args:
            ref: Lens reference (e.g., "base/muru", "coder-v2")

        Returns:
            Resolved Path or None if not found
        """
        from sunwell.foundation.config import get_config

        config = get_config()
        search_paths = config.lens.search_paths

        # Candidates to try
        candidates = [ref, f"{ref}.lens"]

        # Try exact path first
        for candidate in candidates:
            p = Path(candidate)
            if p.exists():
                return p

        # Try each search path
        for search_dir in search_paths:
            # Expand ~ to home directory
            search_path = Path(search_dir).expanduser()
            if not search_path.exists():
                continue

            for candidate in candidates:
                p = search_path / candidate
                if p.exists():
                    return p

        return None

    def load_string(self, content: str, source_path: Path | None = None) -> Lens:
        """Load a lens from a YAML string."""
        try:
            data = safe_yaml_loads(content)
        except ValueError as e:
            raise lens_error(
                code=ErrorCode.LENS_PARSE_ERROR,
                lens="<string>",
                detail=str(e),
                cause=e,
            ) from e

        return self._parse_lens(data, source_path=source_path)

    async def load_ref(self, ref: LensReference) -> Lens:
        """Load a lens from a reference (local path or fount).

        RFC-131: Try local resolution first (via search paths), then fount.
        This enables references like "base/muru" to resolve to
        "lenses/base/muru.lens" without requiring "./" prefix.
        """
        # RFC-131: Always try local resolution first
        resolved = self.resolve_lens_path(ref.source)
        if resolved is not None:
            return self.load(resolved)

        # Fall back to fount if available
        if self.fount and ref.is_fount:
            content = await self.fount.fetch(ref.source, ref.version)
            return self.load_string(content)

        # Not found locally and no fount available
        raise lens_error(
            code=ErrorCode.LENS_NOT_FOUND,
            lens=ref.source,
            path=ref.source,
        )

    def _parse_lens(self, data: dict[str, Any], source_path: Path | None = None) -> Lens:
        """Parse raw dict into Lens dataclass."""
        if "lens" not in data:
            raise lens_error(
                code=ErrorCode.LENS_INVALID_SCHEMA,
                lens=str(source_path) if source_path else "<unknown>",
                detail="Missing 'lens' key in lens definition",
            )

        lens_data = data["lens"]

        # Parse metadata (required)
        metadata = parse_metadata(lens_data.get("metadata", {}))

        # Parse extends
        extends = None
        if "extends" in lens_data:
            extends = parse_lens_reference(lens_data["extends"])

        # Parse compose
        compose = ()
        if "compose" in lens_data:
            compose = tuple(
                parse_lens_reference(ref) for ref in lens_data["compose"]
            )

        # Parse heuristics
        heuristics = ()
        anti_heuristics = ()
        communication = None

        if "heuristics" in lens_data:
            h_data = lens_data["heuristics"]

            if "principles" in h_data:
                heuristics = parse_heuristics(h_data["principles"])
            elif isinstance(h_data, list):
                # Direct list of heuristics
                heuristics = parse_heuristics(h_data)

            if "anti_heuristics" in h_data:
                anti_heuristics = parse_anti_heuristics(h_data["anti_heuristics"])

            if "communication" in h_data:
                communication = parse_communication(h_data["communication"], parse_identity)

        # Parse framework
        framework = None
        if "framework" in lens_data:
            framework = parse_framework(lens_data["framework"])

        # Parse personas
        personas = ()
        if "personas" in lens_data:
            personas = parse_personas(lens_data["personas"])

        # Parse validators
        det_validators = ()
        heur_validators = ()
        if "validators" in lens_data:
            v_data = lens_data["validators"]
            if "deterministic" in v_data:
                det_validators = parse_deterministic_validators(v_data["deterministic"])
            if "heuristic" in v_data:
                heur_validators = parse_heuristic_validators(v_data["heuristic"])

        # Parse workflows
        workflows = ()
        if "workflows" in lens_data:
            workflows = parse_workflows(lens_data["workflows"])

        # Parse refiners
        refiners = ()
        if "refiners" in lens_data:
            refiners = parse_refiners(lens_data["refiners"])

        # Parse provenance
        provenance = None
        if "provenance" in lens_data:
            provenance = parse_provenance(lens_data["provenance"])

        # Parse router
        router = None
        if "router" in lens_data:
            router = parse_router(lens_data["router"])

        # Parse quality policy
        from sunwell.foundation.core.lens import QualityPolicy
        quality_policy = QualityPolicy()
        if "quality_policy" in lens_data:
            quality_policy = parse_quality_policy(lens_data["quality_policy"])

        # Parse skills (RFC-011: Agent Skills integration)
        skills = ()
        if "skills" in lens_data:
            base_path = source_path.parent if source_path else None
            skills = parse_skills(
                lens_data["skills"],
                base_path=base_path,
                resolve_preset_fn=self._resolve_preset,
                parse_skill_fn=lambda d: parse_skill(d, self._resolve_preset),
            )

        # Parse skill retry policy
        skill_retry = None
        if "skill_retry" in lens_data:
            skill_retry = parse_skill_retry(lens_data["skill_retry"])

        # Parse spellbook (RFC-021: Portable Workflow Incantations)
        spellbook = ()
        if "spellbook" in lens_data:
            spellbook = parse_spellbook(lens_data["spellbook"])

        # Parse schema_validators (RFC-035: Schema-aware validation)
        schema_validators = ()
        if "schema_validators" in lens_data:
            schema_validators = parse_schema_validators(lens_data["schema_validators"])

        # Also check schema_extensions.validators for backwards compatibility
        if "schema_extensions" in lens_data:
            ext_validators = lens_data["schema_extensions"].get("validators", [])
            if ext_validators:
                ext_parsed = parse_schema_validators(ext_validators)
                schema_validators = schema_validators + ext_parsed

        # Parse affordances (RFC-072: Surface primitives)
        affordances = None
        if "affordances" in lens_data:
            affordances = parse_affordances(lens_data["affordances"])

        # Parse tool_profile (RFC-XXX: Multi-Signal Tool Selection)
        tool_profile = None
        if "tool_profile" in lens_data:
            tool_profile = parse_tool_profile(lens_data["tool_profile"])

        return Lens(
            metadata=metadata,
            extends=extends,
            compose=compose,
            heuristics=heuristics,
            anti_heuristics=anti_heuristics,
            communication=communication,
            framework=framework,
            personas=personas,
            deterministic_validators=det_validators,
            heuristic_validators=heur_validators,
            workflows=workflows,
            refiners=refiners,
            provenance=provenance,
            router=router,
            quality_policy=quality_policy,
            skills=skills,
            skill_retry=skill_retry,
            spellbook=spellbook,
            schema_validators=schema_validators,
            affordances=affordances,
            tool_profile=tool_profile,
            source_path=source_path,
        )
