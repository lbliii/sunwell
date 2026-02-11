"""Spells - Portable Workflow Incantations (RFC-021).

Canonical definitions moved to sunwell.foundation.schema.models.spell;
re-exported here for backward compatibility.

This module also contains spell_to_routing_decision() which bridges
spells to the planning layer (cannot live in foundation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Re-export all types from foundation
from sunwell.foundation.schema.models.spell import (
    Grimoire,
    Reagent,
    ReagentMode,
    ReagentType,
    Spell,
    SpellExample,
    SpellResult,
    SpellValidation,
    ValidationMode,
    parse_spell,
    validate_spell_output,
)

if TYPE_CHECKING:
    from sunwell.planning.routing.unified import RoutingDecision


def spell_to_routing_decision(spell: Spell) -> RoutingDecision:
    """Convert a Spell to a RoutingDecision for UnifiedRouter.

    This function bridges the foundation (Spell) with the planning layer
    (RoutingDecision). It was extracted from Spell.to_routing_decision()
    during the layer burn-down to keep Spell in foundation (stdlib-only).

    Args:
        spell: The spell to convert.

    Returns:
        A RoutingDecision suitable for the UnifiedRouter.
    """
    from sunwell.planning.routing.unified import (
        Complexity,
        Intent,
        RoutingDecision,
        UserExpertise,
        UserMood,
    )

    # Map intent string to Intent enum, defaulting to CODE
    try:
        intent_enum = Intent(spell.intent)
    except ValueError:
        intent_enum = Intent.CODE

    # Map complexity string to Complexity enum
    try:
        complexity_enum = Complexity(spell.complexity)
    except ValueError:
        complexity_enum = Complexity.STANDARD

    return RoutingDecision(
        intent=intent_enum,
        complexity=complexity_enum,
        lens=None,  # Determined by active lens
        tools=(),
        mood=UserMood.NEUTRAL,
        expertise=UserExpertise.INTERMEDIATE,
        confidence=1.0,  # Spells are deterministic
        reasoning=f"Spell: {spell.incantation}",
        focus=tuple(spell.focus),
    )


__all__ = [
    # Types (re-exported from foundation)
    "Spell",
    "SpellValidation",
    "SpellExample",
    "Reagent",
    "ReagentType",
    "ReagentMode",
    "ValidationMode",
    "Grimoire",
    "SpellResult",
    "parse_spell",
    "validate_spell_output",
    # Bridge function (stays in core)
    "spell_to_routing_decision",
]
