"""Utility functions for turn processing."""

from sunwell.memory.simulacrum.core.turn import Turn


def estimate_token_count(turn: Turn) -> Turn:
    """Estimate token count for a turn.

    Args:
        turn: Turn to estimate

    Returns:
        Turn with token_count populated
    """
    # Rough estimate: ~1.3 tokens per word
    word_count = len(turn.content.split())
    estimated = max(1, int(word_count * 1.3))

    return Turn(
        content=turn.content,
        turn_type=turn.turn_type,
        timestamp=turn.timestamp,
        parent_ids=turn.parent_ids,
        source=turn.source,
        token_count=estimated,
        model=turn.model,
        confidence=turn.confidence,
        tags=turn.tags,
    )
