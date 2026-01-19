"""Lens-schema compatibility checking (RFC-035).

This module provides functions for checking whether a lens is compatible
with a project schema, enabling domain-specific lenses that only work
with certain project types.

Example:
    ```python
    from sunwell.project.compatibility import is_lens_compatible

    # Check if lens can be used with project
    if is_lens_compatible(lens, schema):
        # Apply lens validators
        pass
    else:
        # Lens not compatible with this project type
        raise ValueError(f"Lens {lens.metadata.name} requires schema type ...")
    ```
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sunwell.project.schema import ProjectSchema, ValidatorConfig

if TYPE_CHECKING:
    from sunwell.core.lens import Lens


def is_lens_compatible(
    lens: Lens,
    schema: ProjectSchema | None,
) -> bool:
    """Check if a lens can be used with a project schema.

    Compatibility rules:
    1. Lens with no compatible_schemas → universal (works with any/no schema)
    2. Schema with no type → accepts any lens
    3. Otherwise → schema.project_type must be in lens.compatible_schemas

    Args:
        lens: The lens to check
        schema: The project schema (None if no schema)

    Returns:
        True if lens is compatible with schema
    """
    # Universal lens (no schema binding)
    if not lens.metadata.compatible_schemas:
        return True

    # No schema → accept any lens
    if schema is None:
        return True

    # Check if schema type is in lens's compatible list
    return schema.project_type in lens.metadata.compatible_schemas


def get_compatibility_error(
    lens: Lens,
    schema: ProjectSchema | None,
) -> str | None:
    """Get a detailed error message if lens is incompatible.

    Args:
        lens: The lens to check
        schema: The project schema

    Returns:
        Error message if incompatible, None if compatible
    """
    if is_lens_compatible(lens, schema):
        return None

    # Build helpful error message
    lens_name = lens.metadata.name
    compatible = lens.metadata.compatible_schemas

    if schema is None:
        return (
            f"Lens '{lens_name}' requires a project schema "
            f"(compatible with: {', '.join(compatible)}), "
            f"but no schema was found."
        )

    return (
        f"Lens '{lens_name}' is not compatible with project type '{schema.project_type}'. "
        f"This lens works with: {', '.join(compatible)}. "
        f"Consider using a universal lens or creating a lens for '{schema.project_type}'."
    )


def merge_validators(
    schema: ProjectSchema,
    lens: Lens,
) -> tuple[ValidatorConfig, ...]:
    """Merge schema validators with lens validators.

    Order:
    1. Schema validators run first (structural integrity)
    2. Lens schema_validators run second (domain expertise)

    Lens validators can override schema validators by name.

    Args:
        schema: The project schema
        lens: The active lens

    Returns:
        Merged tuple of validators
    """
    from sunwell.project.schema import ValidatorConfig

    # Start with schema validators
    validators: list[ValidatorConfig] = list(schema.validators)

    # Check for lens validator overrides
    # (lens can skip specific schema validators)
    override_names: set[str] = set()
    if hasattr(lens, "validator_overrides"):
        for override in lens.validator_overrides:  # type: ignore[attr-defined]
            if override.get("action") == "skip":
                override_names.add(override.get("name", ""))

    # Filter out overridden validators
    validators = [v for v in validators if v.name not in override_names]

    # Add lens schema_validators
    for sv in lens.schema_validators:
        validators.append(
            ValidatorConfig(
                name=sv.name,
                description=sv.check,
                rule=sv.check,  # For SchemaValidator, check IS the rule
                severity=sv.severity.value if hasattr(sv.severity, "value") else sv.severity,
                method=sv.method.value if hasattr(sv.method, "value") else sv.method,
                applies_to=sv.applies_to,
            )
        )

    return tuple(validators)


def get_schema_context_for_lens(
    schema: ProjectSchema,
) -> str:
    """Generate schema context for lens prompts.

    This provides the LLM with awareness of the domain's artifact
    types and relationships when using a schema-aware lens.

    Args:
        schema: The project schema

    Returns:
        Context string for injection into prompts
    """
    lines = [
        f"## Project Schema: {schema.name}",
        f"Type: {schema.project_type}",
        "",
        "### Artifact Types",
    ]

    for name, artifact_type in schema.artifact_types.items():
        lines.append(f"- **{name}**: {artifact_type.description}")

        if artifact_type.fields.required:
            lines.append(f"  - Required: {', '.join(artifact_type.fields.required)}")

        if artifact_type.requires_patterns:
            lines.append(f"  - Requires: {', '.join(artifact_type.requires_patterns)}")

        if artifact_type.is_contract:
            lines.append("  - (Contract type)")

    if schema.planning_config.phases:
        lines.extend(["", "### Planning Phases"])
        for phase in schema.planning_config.phases:
            parallel_status = "⚡ parallel" if phase.parallel else "→ sequential"
            lines.append(f"- **{phase.name}** ({parallel_status})")
            if phase.artifact_types:
                lines.append(f"  - Artifact types: {', '.join(phase.artifact_types)}")

    return "\n".join(lines)
