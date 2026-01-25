"""Routing, provenance, and quality policy parsing."""

from sunwell.core.lens import Provenance, QualityPolicy, Router, RouterTier
from sunwell.core.types import Tier


def parse_provenance(data: dict) -> Provenance:
    """Parse provenance configuration."""
    return Provenance(
        format=data.get("format", "file:line"),
        types=tuple(data.get("types", [])),
        required_contexts=tuple(data.get("required_contexts", [])),
    )


def parse_router(data: dict) -> Router:
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


def parse_quality_policy(data: dict) -> QualityPolicy:
    """Parse quality policy."""
    return QualityPolicy(
        min_confidence=data.get("min_confidence", 0.7),
        required_validators=tuple(data.get("required_validators", [])),
        persona_agreement=data.get("persona_agreement", 0.5),
        retry_limit=data.get("retry_limit", 3),
    )
