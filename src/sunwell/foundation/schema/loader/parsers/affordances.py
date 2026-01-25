"""Affordances parsing (RFC-072)."""

from typing import Any

from sunwell.foundation.core.lens import Affordances, PrimitiveAffordance


def parse_affordances(data: dict[str, Any] | None) -> Affordances | None:
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
