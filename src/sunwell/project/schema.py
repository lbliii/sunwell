"""Project schema definitions for domain-agnostic projects (RFC-035).

This module defines the core data structures for project schemas that allow
users to define their domain's artifact types, relationships, and validation
rules. Combined with existing Lenses (which define *how* to approach work),
this creates a complete domain-agnostic framework.

Example schema (fiction):
    ```yaml
    project:
      name: "The London Conspiracy"
      type: fiction
      version: "1.0.0"

    artifact_types:
      character:
        description: "A person in the story"
        fields:
          required: [name, traits]
          optional: [age, backstory]
        produces: "Character_{id}"
    ```
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class ArtifactField:
    """Field specification for an artifact type.

    Attributes:
        required: Fields that must be present
        optional: Fields that may be present
    """

    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionalRequirement:
    """Conditional dependency for an artifact.

    Example:
        - if: "characters_present"
          requires: "Character_{char}" for char in characters_present
    """

    condition: str  # Field name or expression that must be truthy
    requires_pattern: str  # Pattern for required artifacts
    iterate_over: str | None = None  # Field to iterate over (e.g., "characters_present")


@dataclass(frozen=True, slots=True)
class ArtifactType:
    """Definition of an artifact type in a domain.

    Artifact types define what kinds of entities exist in a domain,
    their required/optional fields, and how they relate to other artifacts.

    Example (fiction):
        character:
          description: "A person in the story"
          fields:
            required: [name, traits]
            optional: [age, backstory]
          produces: "Character_{id}"

        scene:
          description: "A unit of narrative action"
          requires: ["Character_{pov}", "Setting_{location}"]
          produces: "Scene_{id}"
    """

    name: str
    description: str
    fields: ArtifactField
    produces_pattern: str  # Template like "Character_{id}"
    requires_patterns: tuple[str, ...] = ()  # Templates like "Character_{pov}"
    modifies_patterns: tuple[str, ...] = ()  # Templates like "timeline/{timeline_position}"
    conditional_requirements: tuple[ConditionalRequirement, ...] = ()
    is_contract: bool = False  # True if this type defines interfaces


@dataclass(frozen=True, slots=True)
class ValidatorConfig:
    """Configuration for a schema validator.

    Validators check constraints across artifacts. They can be:
    - constraint: Deterministic DSL (FOR/WHERE/ASSERT)
    - llm: LLM-based judgment

    Example:
        - name: timeline_consistency
          description: "No character can be in two places at the same time"
          rule: |
            FOR character IN artifacts.characters
            FOR scene_a, scene_b IN artifacts.scenes
            WHERE character IN scene_a.characters_present
              AND character IN scene_b.characters_present
              AND scene_a.timeline_position == scene_b.timeline_position
            ASSERT scene_a.location == scene_b.location
          severity: error
          method: constraint
    """

    name: str
    description: str
    rule: str
    severity: str = "error"  # error, warning, info
    method: str = "constraint"  # constraint, llm
    applies_to: str | None = None  # Optional: only for this artifact type


@dataclass(frozen=True, slots=True)
class PlanningPhase:
    """A phase in the planning strategy.

    Phases group artifact types and define parallelization hints.

    Example:
        - name: worldbuilding
          artifact_types: [character, location, relationship]
          parallel: true
          maps_to: contracts
    """

    name: str
    artifact_types: tuple[str, ...] = ()
    parallel: bool = True
    maps_to: str | None = None  # RFC-034 parallel_group mapping
    description: str | None = None


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    """Planning configuration for a project schema.

    Defines how tasks should be organized and executed,
    integrating with RFC-034's contract-first planning.
    """

    default_strategy: str = "contract_first"  # contract_first, resource_aware, sequential
    phases: tuple[PlanningPhase, ...] = ()
    resolution_policy: str = "merge"  # schema_wins, rfc034_wins, merge


@dataclass(slots=True)
class ProjectSchema:
    """Domain-agnostic project definition (RFC-035).

    A ProjectSchema defines the structure of a domain:
    - What kinds of artifacts exist (characters, scenes, etc.)
    - How artifacts relate to each other (dependencies)
    - Validation rules (consistency checks)
    - Planning hints (phases, parallelization)

    Example:
        >>> schema = ProjectSchema.load(Path("my-novel"))
        >>> print(schema.name)
        "The London Conspiracy"
        >>> print(schema.artifact_types.keys())
        ["character", "location", "scene"]
    """

    name: str
    project_type: str
    version: str = "1.0.0"
    artifact_types: dict[str, ArtifactType] = field(default_factory=dict)
    validators: tuple[ValidatorConfig, ...] = ()
    planning_config: PlanningConfig = field(default_factory=PlanningConfig)
    project_root: Path | None = None

    @classmethod
    def load(cls, project_root: Path) -> ProjectSchema:
        """Load schema from .sunwell/schema.yaml.

        Args:
            project_root: Root directory of the project

        Returns:
            Loaded ProjectSchema

        Raises:
            FileNotFoundError: If schema file doesn't exist
            ValueError: If schema is invalid
        """
        schema_path = project_root / ".sunwell" / "schema.yaml"

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        with open(schema_path) as f:
            data = yaml.safe_load(f)

        return cls._parse(data, project_root)

    @classmethod
    def load_or_default(cls, project_root: Path) -> ProjectSchema | None:
        """Load schema if present, return None otherwise.

        This allows existing projects without schemas to continue
        working unchanged.

        Args:
            project_root: Root directory of the project

        Returns:
            ProjectSchema if found, None otherwise
        """
        schema_path = project_root / ".sunwell" / "schema.yaml"

        if not schema_path.exists():
            return None

        return cls.load(project_root)

    @classmethod
    def _parse(cls, data: dict[str, Any], project_root: Path) -> ProjectSchema:
        """Parse raw YAML data into ProjectSchema."""
        # Parse project metadata
        project_data = data.get("project", {})
        name = project_data.get("name", "Unnamed Project")
        project_type = project_data.get("type", "general")
        version = project_data.get("version", "1.0.0")

        # Parse artifact types
        artifact_types = {}
        for type_name, type_data in data.get("artifact_types", {}).items():
            artifact_types[type_name] = cls._parse_artifact_type(type_name, type_data)

        # Parse validators
        validators = tuple(
            cls._parse_validator(v)
            for v in data.get("validators", [])
        )

        # Parse planning config
        planning_config = cls._parse_planning_config(data.get("planning", {}))

        return cls(
            name=name,
            project_type=project_type,
            version=version,
            artifact_types=artifact_types,
            validators=validators,
            planning_config=planning_config,
            project_root=project_root,
        )

    @classmethod
    def _parse_artifact_type(cls, name: str, data: dict[str, Any]) -> ArtifactType:
        """Parse an artifact type definition."""
        # Parse fields
        fields_data = data.get("fields", {})
        fields = ArtifactField(
            required=tuple(fields_data.get("required", [])),
            optional=tuple(fields_data.get("optional", [])),
        )

        # Parse requires patterns
        requires_raw = data.get("requires", [])
        if isinstance(requires_raw, str):
            requires_patterns = (requires_raw,)
        else:
            requires_patterns = tuple(requires_raw)

        # Parse modifies patterns
        modifies_raw = data.get("modifies", [])
        if isinstance(modifies_raw, str):
            modifies_patterns = (modifies_raw,)
        else:
            modifies_patterns = tuple(modifies_raw)

        # Parse conditional requirements
        conditional_requirements = tuple(
            cls._parse_conditional_requirement(cond)
            for cond in data.get("when", [])
        )

        return ArtifactType(
            name=name,
            description=data.get("description", f"{name} artifact"),
            fields=fields,
            produces_pattern=data.get("produces", f"{name.title()}_{{{name}_id}}"),
            requires_patterns=requires_patterns,
            modifies_patterns=modifies_patterns,
            conditional_requirements=conditional_requirements,
            is_contract=data.get("is_contract", False),
        )

    @classmethod
    def _parse_conditional_requirement(cls, data: dict[str, Any]) -> ConditionalRequirement:
        """Parse a conditional requirement."""
        condition = data.get("if", "")
        requires = data.get("requires", "")

        # Check for iteration pattern: "Foo_{x} for x in field"
        iterate_over = None
        if " for " in requires:
            # Parse "Character_{char} for char in characters_present"
            pattern_part, iteration_part = requires.rsplit(" for ", 1)
            if " in " in iteration_part:
                _, iterate_over = iteration_part.split(" in ", 1)
            requires = pattern_part.strip()

        return ConditionalRequirement(
            condition=condition,
            requires_pattern=requires,
            iterate_over=iterate_over,
        )

    @classmethod
    def _parse_validator(cls, data: dict[str, Any]) -> ValidatorConfig:
        """Parse a validator configuration."""
        return ValidatorConfig(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            rule=data.get("rule", ""),
            severity=data.get("severity", "error"),
            method=data.get("method", "constraint"),
            applies_to=data.get("applies_to"),
        )

    @classmethod
    def _parse_planning_config(cls, data: dict[str, Any]) -> PlanningConfig:
        """Parse planning configuration."""
        phases = tuple(
            PlanningPhase(
                name=p.get("name", "unnamed"),
                artifact_types=tuple(p.get("artifact_types", [])),
                parallel=p.get("parallel", True) if isinstance(p.get("parallel"), bool) else True,
                maps_to=p.get("maps_to"),
                description=p.get("description"),
            )
            for p in data.get("phases", [])
        )

        return PlanningConfig(
            default_strategy=data.get("default_strategy", "contract_first"),
            phases=phases,
            resolution_policy=data.get("resolution_policy", "merge"),
        )

    def get_phase_for_artifact_type(self, artifact_type: str) -> PlanningPhase | None:
        """Get the planning phase for an artifact type."""
        for phase in self.planning_config.phases:
            if artifact_type in phase.artifact_types:
                return phase
        return None

    def get_artifact_type(self, type_name: str) -> ArtifactType | None:
        """Get an artifact type by name."""
        return self.artifact_types.get(type_name)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "project": {
                "name": self.name,
                "type": self.project_type,
                "version": self.version,
            },
            "artifact_types": {
                name: {
                    "description": at.description,
                    "fields": {
                        "required": list(at.fields.required),
                        "optional": list(at.fields.optional),
                    },
                    "produces": at.produces_pattern,
                    "requires": list(at.requires_patterns),
                    "modifies": list(at.modifies_patterns),
                    "is_contract": at.is_contract,
                }
                for name, at in self.artifact_types.items()
            },
            "validators": [
                {
                    "name": v.name,
                    "description": v.description,
                    "rule": v.rule,
                    "severity": v.severity,
                    "method": v.method,
                }
                for v in self.validators
            ],
            "planning": {
                "default_strategy": self.planning_config.default_strategy,
                "phases": [
                    {
                        "name": p.name,
                        "artifact_types": list(p.artifact_types),
                        "parallel": p.parallel,
                        "maps_to": p.maps_to,
                    }
                    for p in self.planning_config.phases
                ],
            },
        }
