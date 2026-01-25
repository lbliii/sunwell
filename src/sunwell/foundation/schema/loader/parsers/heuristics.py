"""Heuristics, anti-heuristics, communication, and identity parsing."""

from sunwell.core.models.heuristic import (
    AntiHeuristic,
    CommunicationStyle,
    Example,
    Heuristic,
    Identity,
)


def parse_heuristics(data: list[dict]) -> tuple[Heuristic, ...]:
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


def parse_anti_heuristics(data: list[dict]) -> tuple[AntiHeuristic, ...]:
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


def parse_communication(data: dict, parse_identity_fn) -> CommunicationStyle:
    """Parse communication style.

    RFC-131: Also parses identity for agent persona configuration.
    """
    identity = None
    if "identity" in data:
        identity = parse_identity_fn(data["identity"])

    return CommunicationStyle(
        tone=tuple(data.get("tone", [])),
        style=tuple(data.get("style", [])),
        format_guidelines=tuple(data.get("format_guidelines", [])),
        identity=identity,
    )


def parse_identity(data: dict) -> Identity:
    """Parse identity configuration."""
    return Identity(
        name=data.get("name"),
        role=data.get("role"),
        background=tuple(data.get("background", [])),
        expertise=tuple(data.get("expertise", [])),
        constraints=tuple(data.get("constraints", [])),
    )
