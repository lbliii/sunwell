"""Personas parsing."""

from sunwell.foundation.schema.models.persona import Persona


def parse_personas(data: list[dict]) -> tuple[Persona, ...]:
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
