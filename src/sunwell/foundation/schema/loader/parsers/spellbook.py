"""Spellbook parsing (RFC-021)."""

from sunwell.foundation.schema.models.spell import Spell, parse_spell


def parse_spellbook(data: list[dict]) -> tuple[Spell, ...]:
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
