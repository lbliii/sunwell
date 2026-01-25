"""Load lens definitions from YAML/JSON files."""


from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.fount.client import FountClient

import yaml

from sunwell.core.errors import ErrorCode, SunwellError, lens_error
from sunwell.core.framework import Framework, FrameworkCategory
from sunwell.core.heuristic import AntiHeuristic, CommunicationStyle, Example, Heuristic, Identity
from sunwell.core.lens import (
    Affordances,
    Lens,
    LensMetadata,
    PrimitiveAffordance,
    Provenance,
    QualityPolicy,
    Router,
    RouterTier,
)
from sunwell.core.persona import Persona
from sunwell.core.spell import (
    Spell,
    parse_spell,
)
from sunwell.core.types import (
    LensReference,
    SemanticVersion,
    Severity,
    Tier,
    ValidationMethod,
)
from sunwell.core.validator import (
    DeterministicValidator,
    HeuristicValidator,
    SchemaValidationMethod,
    SchemaValidator,
)
from sunwell.core.workflow import Refiner, Workflow, WorkflowStep
from sunwell.skills.types import (
    Resource,
    Script,
    Skill,
    SkillRetryPolicy,
    SkillType,
    SkillValidation,
    Template,
    TrustLevel,
)


class LensLoader:
    """Load lens definitions from files."""

    def __init__(self, fount_client: FountClient | None = None):
        self.fount = fount_client
        self._presets: dict[str, dict] | None = None  # Lazy-loaded presets

    def _load_presets(self) -> dict[str, dict]:
        """Load permission presets from YAML (RFC-092).

        Presets are loaded lazily and cached. Searches for permission-presets.yaml
        in standard locations:
        1. Package skills directory
        2. Current working directory skills/
        """
        if self._presets is not None:
            return self._presets

        # Search paths for presets file
        search_paths: list[Path] = []

        # Check package skills directory
        from importlib.resources import files

        try:
            package_presets = files("sunwell") / "skills" / "permission-presets.yaml"
            if package_presets.is_file():
                search_paths.append(Path(str(package_presets)))
        except (ImportError, TypeError):
            pass

        # Check current working directory
        search_paths.append(Path.cwd() / "skills" / "permission-presets.yaml")
        search_paths.append(Path.cwd() / "permission-presets.yaml")

        # Find and load the file
        for path in search_paths:
            if path.exists():
                data = yaml.safe_load(path.read_text())
                self._presets = data.get("presets", {}) if data else {}
                return self._presets

        # No presets file found - return empty dict
        self._presets = {}
        return self._presets

    def _resolve_preset(self, skill_data: dict) -> dict:
        """Resolve preset inheritance for a skill (RFC-092).

        If skill has a preset, merge preset permissions/security into skill data.
        Skill-specific values override preset values.

        Args:
            skill_data: Raw skill dict from YAML

        Returns:
            Skill dict with resolved permissions/security
        """
        preset_name = skill_data.get("preset")
        if not preset_name:
            return skill_data

        presets = self._load_presets()
        preset = presets.get(preset_name)

        if preset is None:
            raise ValueError(
                f"Unknown permission preset: '{preset_name}'. "
                f"Available presets: {list(presets.keys())}"
            )

        # Create a copy to avoid mutating original
        resolved = dict(skill_data)

        # Merge permissions (skill overrides preset)
        if "permissions" in preset:
            preset_perms = dict(preset["permissions"])
            skill_perms = resolved.get("permissions", {})
            if skill_perms:
                self._deep_merge(preset_perms, skill_perms)
            resolved["permissions"] = preset_perms

        # Merge security (skill overrides preset)
        if "security" in preset:
            preset_sec = dict(preset["security"])
            skill_sec = resolved.get("security", {})
            if skill_sec:
                self._deep_merge(preset_sec, skill_sec)
            resolved["security"] = preset_sec

        return resolved

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        """Deep merge override into base (mutates base).

        Used for merging skill-specific permissions into preset permissions.
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

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
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
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
        from sunwell.config import get_config

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
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
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
        metadata = self._parse_metadata(lens_data.get("metadata", {}))

        # Parse extends
        extends = None
        if "extends" in lens_data:
            extends = self._parse_lens_reference(lens_data["extends"])

        # Parse compose
        compose = ()
        if "compose" in lens_data:
            compose = tuple(
                self._parse_lens_reference(ref) for ref in lens_data["compose"]
            )

        # Parse heuristics
        heuristics = ()
        anti_heuristics = ()
        communication = None

        if "heuristics" in lens_data:
            h_data = lens_data["heuristics"]

            if "principles" in h_data:
                heuristics = self._parse_heuristics(h_data["principles"])
            elif isinstance(h_data, list):
                # Direct list of heuristics
                heuristics = self._parse_heuristics(h_data)

            if "anti_heuristics" in h_data:
                anti_heuristics = self._parse_anti_heuristics(h_data["anti_heuristics"])

            if "communication" in h_data:
                communication = self._parse_communication(h_data["communication"])

        # Parse framework
        framework = None
        if "framework" in lens_data:
            framework = self._parse_framework(lens_data["framework"])

        # Parse personas
        personas = ()
        if "personas" in lens_data:
            personas = self._parse_personas(lens_data["personas"])

        # Parse validators
        det_validators = ()
        heur_validators = ()
        if "validators" in lens_data:
            v_data = lens_data["validators"]
            if "deterministic" in v_data:
                det_validators = self._parse_deterministic_validators(v_data["deterministic"])
            if "heuristic" in v_data:
                heur_validators = self._parse_heuristic_validators(v_data["heuristic"])

        # Parse workflows
        workflows = ()
        if "workflows" in lens_data:
            workflows = self._parse_workflows(lens_data["workflows"])

        # Parse refiners
        refiners = ()
        if "refiners" in lens_data:
            refiners = self._parse_refiners(lens_data["refiners"])

        # Parse provenance
        provenance = None
        if "provenance" in lens_data:
            provenance = self._parse_provenance(lens_data["provenance"])

        # Parse router
        router = None
        if "router" in lens_data:
            router = self._parse_router(lens_data["router"])

        # Parse quality policy
        quality_policy = QualityPolicy()
        if "quality_policy" in lens_data:
            quality_policy = self._parse_quality_policy(lens_data["quality_policy"])

        # Parse skills (RFC-011: Agent Skills integration)
        skills = ()
        if "skills" in lens_data:
            base_path = source_path.parent if source_path else None
            skills = self._parse_skills(lens_data["skills"], base_path=base_path)

        # Parse skill retry policy
        skill_retry = None
        if "skill_retry" in lens_data:
            skill_retry = self._parse_skill_retry(lens_data["skill_retry"])

        # Parse spellbook (RFC-021: Portable Workflow Incantations)
        spellbook = ()
        if "spellbook" in lens_data:
            spellbook = self._parse_spellbook(lens_data["spellbook"])

        # Parse schema_validators (RFC-035: Schema-aware validation)
        schema_validators = ()
        if "schema_validators" in lens_data:
            schema_validators = self._parse_schema_validators(lens_data["schema_validators"])

        # Also check schema_extensions.validators for backwards compatibility
        if "schema_extensions" in lens_data:
            ext_validators = lens_data["schema_extensions"].get("validators", [])
            if ext_validators:
                ext_parsed = self._parse_schema_validators(ext_validators)
                schema_validators = schema_validators + ext_parsed

        # Parse affordances (RFC-072: Surface primitives)
        affordances = None
        if "affordances" in lens_data:
            affordances = self._parse_affordances(lens_data["affordances"])

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
            source_path=source_path,
        )

    @staticmethod
    def _parse_metadata(data: dict[str, Any]) -> LensMetadata:
        """Parse lens metadata.

        RFC-035: Also parses compatible_schemas for domain-specific lenses.
        RFC-070: Also parses library metadata (use_cases, tags, icon).
        """
        name = data.get("name", "Unnamed Lens")

        version = SemanticVersion(0, 1, 0)
        if "version" in data:
            version = SemanticVersion.parse(data["version"])

        # RFC-035: Parse compatible_schemas
        compatible_schemas = tuple(data.get("compatible_schemas", []))

        # RFC-070: Parse library metadata
        use_cases = tuple(data.get("use_cases", []))
        tags = tuple(data.get("tags", []))
        icon = data.get("icon")

        return LensMetadata(
            name=name,
            domain=data.get("domain"),
            version=version,
            description=data.get("description"),
            author=data.get("author"),
            license=data.get("license"),
            compatible_schemas=compatible_schemas,
            use_cases=use_cases,
            tags=tags,
            icon=icon,
        )

    @staticmethod
    def _parse_lens_reference(data: str | dict) -> LensReference:
        """Parse a lens reference."""
        if isinstance(data, str):
            # Simple string reference "sunwell/tech-writer@1.0"
            if "@" in data:
                source, version = data.rsplit("@", 1)
                return LensReference(source=source, version=version)
            return LensReference(source=data)

        return LensReference(
            source=data["lens"],
            version=data.get("version"),
            priority=data.get("priority", 1),
        )

    @staticmethod
    def _parse_heuristics(data: list[dict]) -> tuple[Heuristic, ...]:
        """Parse list of heuristics."""
        heuristics = []
        for h in data:
            examples = Example()
            if "examples" in h:
                ex = h["examples"]
                examples = Example(
                    good=tuple(ex.get("good", [])),
                    bad=tuple(ex.get("bad", [])),
                )

            heuristics.append(
                Heuristic(
                    name=h["name"],
                    rule=h["rule"],
                    test=h.get("test"),
                    always=tuple(h.get("always", [])),
                    never=tuple(h.get("never", [])),
                    examples=examples,
                    priority=h.get("priority", 1),
                )
            )
        return tuple(heuristics)

    @staticmethod
    def _parse_anti_heuristics(data: list[dict]) -> tuple[AntiHeuristic, ...]:
        """Parse list of anti-heuristics."""
        return tuple(
            AntiHeuristic(
                name=ah["name"],
                description=ah["description"],
                triggers=tuple(ah.get("triggers", [])),
                correction=ah["correction"],
            )
            for ah in data
        )

    def _parse_communication(self, data: dict) -> CommunicationStyle:
        """Parse communication style.

        RFC-131: Also parses identity for agent persona configuration.
        """
        identity = None
        if "identity" in data:
            identity = self._parse_identity(data["identity"])

        return CommunicationStyle(
            tone=tuple(data.get("tone", [])),
            structure=data.get("structure"),
            identity=identity,
        )

    @staticmethod
    def _parse_identity(data: dict) -> Identity:
        """Parse identity configuration (RFC-131).

        Example YAML:
            identity:
              name: "M'uru"
              nature: "A Naaru — a being of light and wisdom"
              style: "Helpful, warm, genuinely interested in assisting"
              prohibitions:
                - "Do NOT start responses with 'My name is M'uru' unless asked"
        """
        return Identity(
            name=data["name"],
            nature=data.get("nature"),
            style=data.get("style"),
            prohibitions=tuple(data.get("prohibitions", [])),
        )

    @staticmethod
    def _parse_framework(data: dict) -> Framework:
        """Parse framework."""
        categories = ()
        if "categories" in data:
            categories = tuple(
                FrameworkCategory(
                    name=c["name"],
                    purpose=c["purpose"],
                    structure=tuple(c.get("structure", [])),
                    includes=tuple(c.get("includes", [])),
                    excludes=tuple(c.get("excludes", [])),
                    triggers=tuple(c.get("triggers", [])),
                )
                for c in data["categories"]
            )

        return Framework(
            name=data["name"],
            description=data.get("description"),
            decision_tree=data.get("decision_tree"),
            categories=categories,
        )

    @staticmethod
    def _parse_personas(data: list[dict]) -> tuple[Persona, ...]:
        """Parse list of personas."""
        return tuple(
            Persona(
                name=p["name"],
                description=p.get("description"),
                background=p.get("background"),
                goals=tuple(p.get("goals", [])),
                friction_points=tuple(p.get("friction_points", [])),
                attack_vectors=tuple(p.get("attack_vectors", [])),
                evaluation_prompt=p.get("evaluation_prompt"),
                output_format=p.get("output_format"),
            )
            for p in data
        )

    @staticmethod
    def _parse_deterministic_validators(
        data: list[dict],
    ) -> tuple[DeterministicValidator, ...]:
        """Parse deterministic validators."""
        return tuple(
            DeterministicValidator(
                name=v["name"],
                script=v["script"],
                severity=Severity(v.get("severity", "error")),
                description=v.get("description"),
                timeout_seconds=v.get("timeout_seconds", 30.0),
            )
            for v in data
        )

    @staticmethod
    def _parse_heuristic_validators(
        data: list[dict],
    ) -> tuple[HeuristicValidator, ...]:
        """Parse heuristic validators."""
        return tuple(
            HeuristicValidator(
                name=v["name"],
                check=v["check"],
                method=ValidationMethod(v.get("method", "pattern_match")),
                confidence_threshold=v.get("confidence_threshold", 0.8),
                severity=Severity(v.get("severity", "warning")),
                description=v.get("description"),
            )
            for v in data
        )

    @staticmethod
    def _parse_schema_validators(
        data: list[dict],
    ) -> tuple[SchemaValidator, ...]:
        """Parse schema validators (RFC-035).

        Schema validators are lens-provided validators that target specific
        artifact types defined in a project schema.
        """
        return tuple(
            SchemaValidator(
                name=v["name"],
                check=v["check"],
                applies_to=v["applies_to"],
                condition=v.get("condition") or v.get("when"),
                severity=Severity(v.get("severity", "warning")),
                method=SchemaValidationMethod(v.get("method", "llm")),
            )
            for v in data
        )

    @staticmethod
    def _parse_workflows(data: list[dict]) -> tuple[Workflow, ...]:
        """Parse workflows."""
        workflows = []
        for w in data:
            steps = tuple(
                WorkflowStep(
                    name=s["name"],
                    action=s["action"],
                    quality_gates=tuple(s.get("quality_gates", [])),
                )
                for s in w.get("steps", [])
            )
            workflows.append(
                Workflow(
                    name=w["name"],
                    trigger=w.get("trigger"),
                    steps=steps,
                    state_management=w.get("state_management", False),
                )
            )
        return tuple(workflows)

    @staticmethod
    def _parse_refiners(data: list[dict]) -> tuple[Refiner, ...]:
        """Parse refiners."""
        return tuple(
            Refiner(
                name=r["name"],
                purpose=r["purpose"],
                when=r.get("when"),
                operations=tuple(r.get("operations", [])),
            )
            for r in data
        )

    @staticmethod
    def _parse_provenance(data: dict) -> Provenance:
        """Parse provenance configuration."""
        return Provenance(
            format=data.get("format", "file:line"),
            types=tuple(data.get("types", [])),
            required_contexts=tuple(data.get("required_contexts", [])),
        )

    @staticmethod
    def _parse_router(data: dict) -> Router:
        """Parse router configuration.

        RFC-070: Also parses shortcuts for skill invocation.
        """
        tiers = ()
        if "tiers" in data:
            tiers = tuple(
                RouterTier(
                    level=Tier(t.get("level", 1)),
                    name=t["name"],
                    triggers=tuple(t.get("triggers", [])),
                    retrieval=t.get("retrieval", True),
                    validation=t.get("validation", True),
                    personas=tuple(t.get("personas", [])),
                    require_confirmation=t.get("require_confirmation", False),
                )
                for t in data["tiers"]
            )

        # RFC-070: Parse shortcuts
        shortcuts = data.get("shortcuts", {})

        return Router(
            tiers=tiers,
            intent_categories=tuple(data.get("intent_categories", [])),
            signals=data.get("signals", {}),
            shortcuts=shortcuts,
        )

    @staticmethod
    def _parse_quality_policy(data: dict) -> QualityPolicy:
        """Parse quality policy."""
        return QualityPolicy(
            min_confidence=data.get("min_confidence", 0.7),
            required_validators=tuple(data.get("required_validators", [])),
            persona_agreement=data.get("persona_agreement", 0.5),
            retry_limit=data.get("retry_limit", 3),
        )

    # RFC-011: Skills parsing

    def _parse_skills(
        self, data: list[dict], base_path: Path | None = None
    ) -> tuple[Skill, ...]:
        """Parse list of skills, supporting includes from external files.

        Skills can be:
        - Inline skill definitions (dict with 'name', 'description', etc.)
        - Include directives (dict with 'include' key pointing to skill file)

        Example:
            skills:
              - include: core-skills.yaml    # Load all skills from file
              - include: core-skills.yaml::search-codebase  # Load specific skill
              - name: custom-skill           # Inline skill
                description: My custom skill
        """
        skills = []
        for s in data:
            if "include" in s:
                # Include directive - load from external file
                include_path = s["include"]
                included = self._load_skill_include(include_path, base_path)
                skills.extend(included)
            else:
                # Regular skill definition
                skill = self._parse_skill(s)
                skills.append(skill)
        return tuple(skills)

    def _load_skill_include(
        self, include_ref: str, base_path: Path | None = None
    ) -> list[Skill]:
        """Load skills from an external file.

        Supports:
        - "core-skills.yaml" - load all skills from file
        - "core-skills.yaml::skill-name" - load specific skill by name
        - "core-skills.yaml::skill1,skill2" - load multiple specific skills
        """
        # Parse include reference
        if "::" in include_ref:
            file_path, skill_filter = include_ref.split("::", 1)
            skill_names = {s.strip() for s in skill_filter.split(",")}
        else:
            file_path = include_ref
            skill_names = None  # Load all

        # Resolve path relative to base_path (lens directory) or skills directory
        search_paths = []
        if base_path:
            search_paths.append(base_path / file_path)
            search_paths.append(base_path.parent / "skills" / file_path)

        # Also check the standard skills directory
        from importlib.resources import files
        try:
            package_skills = files("sunwell") / "skills" / file_path
            if package_skills.is_file():
                search_paths.append(Path(str(package_skills)))
        except (ImportError, TypeError):
            pass

        # Add current working directory
        search_paths.append(Path.cwd() / file_path)
        search_paths.append(Path.cwd() / "skills" / file_path)

        # Find the file
        skill_file = None
        for p in search_paths:
            if p.exists():
                skill_file = p
                break

        if not skill_file:
            raise ValueError(
                f"Skill include not found: {include_ref}. "
                f"Searched: {[str(p) for p in search_paths]}"
            )

        # Load and parse the skill file
        skill_data = yaml.safe_load(skill_file.read_text())

        # The file should have a 'skills' key
        if "skills" not in skill_data:
            raise ValueError(
                f"Skill file {skill_file} must have a 'skills' key"
            )

        # Parse skills from the file
        all_skills = []
        for s in skill_data["skills"]:
            skill = self._parse_skill(s)
            all_skills.append(skill)

        # Filter if specific skills requested
        if skill_names:
            all_skills = [s for s in all_skills if s.name in skill_names]
            missing = skill_names - {s.name for s in all_skills}
            if missing:
                raise ValueError(
                    f"Skills not found in {skill_file}: {missing}"
                )

        return all_skills

    def _parse_skill(self, data: dict) -> Skill:
        """Parse a single skill definition.

        RFC-070: Also parses triggers for automatic skill discovery.
        RFC-092: Resolves preset inheritance for permissions/security.
        """
        # RFC-092: Resolve preset inheritance first
        resolved_data = self._resolve_preset(data)

        # Determine skill type
        skill_type_str = resolved_data.get("type", "inline")
        skill_type = SkillType(skill_type_str)

        # Parse trust level
        trust_str = resolved_data.get("trust", "sandboxed")
        trust = TrustLevel(trust_str)

        # RFC-070: Parse triggers for automatic discovery
        triggers = resolved_data.get("triggers", [])
        if isinstance(triggers, str):
            triggers = triggers.split()
        triggers = tuple(triggers)

        # Parse scripts
        scripts = ()
        if "scripts" in resolved_data:
            scripts = tuple(
                Script(
                    name=sc["name"],
                    content=sc["content"],
                    language=sc.get("language", "python"),
                    description=sc.get("description"),
                )
                for sc in resolved_data["scripts"]
            )

        # Parse templates
        templates = ()
        if "templates" in resolved_data:
            templates = tuple(
                Template(
                    name=t["name"],
                    content=t["content"],
                )
                for t in resolved_data["templates"]
            )

        # Parse resources
        resources = ()
        if "resources" in resolved_data:
            resources = tuple(
                Resource(
                    name=r["name"],
                    url=r.get("url"),
                    path=r.get("path"),
                )
                for r in resolved_data["resources"]
            )

        # Parse validation binding
        validate_with = SkillValidation()
        if "validate_with" in resolved_data:
            vw = resolved_data["validate_with"]
            validate_with = SkillValidation(
                validators=tuple(vw.get("validators", [])),
                personas=tuple(vw.get("personas", [])),
                min_confidence=vw.get("min_confidence", 0.7),
            )

        # Parse allowed_tools (can be space-delimited string or list)
        allowed_tools = resolved_data.get("allowed_tools", [])
        if isinstance(allowed_tools, str):
            allowed_tools = allowed_tools.split()
        allowed_tools = tuple(allowed_tools)

        # RFC-092: Get preset name and resolved permissions/security
        preset_name = data.get("preset")  # Original data has preset name
        permissions = resolved_data.get("permissions")
        security = resolved_data.get("security")

        return Skill(
            name=resolved_data["name"],
            description=resolved_data["description"],
            skill_type=skill_type,
            preset=preset_name,
            triggers=triggers,
            permissions=permissions,
            security=security,
            compatibility=resolved_data.get("compatibility"),
            allowed_tools=allowed_tools,
            instructions=resolved_data.get("instructions"),
            scripts=scripts,
            templates=templates,
            resources=resources,
            source=resolved_data.get("source"),
            path=resolved_data.get("path"),
            trust=trust,
            timeout=resolved_data.get("timeout", 30),
            override=resolved_data.get("override", False),
            validate_with=validate_with,
        )

    @staticmethod
    def _parse_skill_retry(data: dict) -> SkillRetryPolicy:
        """Parse skill retry policy."""
        return SkillRetryPolicy(
            max_attempts=data.get("max_attempts", 3),
            backoff_ms=tuple(data.get("backoff_ms", [100, 500, 2000])),
            retry_on=tuple(data.get("retry_on", ["timeout", "validation_failure"])),
            abort_on=tuple(data.get("abort_on", ["security_violation", "script_crash"])),
        )

    # RFC-021: Spellbook parsing

    @staticmethod
    def _parse_spellbook(data: list[dict]) -> tuple[Spell, ...]:
        """Parse spellbook (list of spells) from YAML.

        Supports both inline spell definitions and includes from external files.

        Example:
            spellbook:
              - incantation: "::security"
                description: "Security review"
                ...
              - include: security-spells.yaml  # Load from file
        """
        spells = []
        for spell_data in data:
            if "include" in spell_data:
                # Include directive - load from external file
                # (Future: implement spell includes like skills)
                continue
            else:
                # Use the parse_spell function from spell.py
                spell = parse_spell(spell_data)
                spells.append(spell)
        return tuple(spells)

    # RFC-072: Affordances parsing

    @staticmethod
    def _parse_affordances(data: dict[str, Any] | None) -> Affordances | None:
        """Parse affordances section from lens YAML.

        Handles the RFC-072 affordances schema:

        affordances:
          primary:
            - primitive: CodeEditor
              default_size: full
              weight: 1.0
          secondary:
            - primitive: TestRunner
              trigger: "test|coverage"
              weight: 0.7
          contextual:
            - primitive: MemoryPane
              trigger: "decision|pattern"
              weight: 0.6

        Args:
            data: Raw affordances dict from YAML

        Returns:
            Parsed Affordances or None if data is empty
        """
        if not data:
            return None

        def parse_list(items: list[dict] | None) -> tuple[PrimitiveAffordance, ...]:
            if not items:
                return ()
            return tuple(
                PrimitiveAffordance(
                    primitive=item["primitive"],
                    default_size=item.get("default_size", "panel"),
                    weight=item.get("weight", 0.5),
                    trigger=item.get("trigger"),
                    mode_hint=item.get("mode_hint"),
                )
                for item in items
            )

        return Affordances(
            primary=parse_list(data.get("primary")),
            secondary=parse_list(data.get("secondary")),
            contextual=parse_list(data.get("contextual")),
        )
