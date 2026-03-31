"""Intent classification for workflow vs single-step (Phase 4)."""

# Multi-step indicators: phrases that suggest multiple distinct tasks
_MULTI_STEP_PHRASES: frozenset[str] = frozenset(
    {
        " and then ",
        ", then ",
        " first ",
        " next ",
        " after that ",
        " research ",
        " draft ",
        " create ",
        " implement ",
        " and ",
        " followed by ",
        " step 1",
        " step 2",
        " 1. ",
        " 2. ",
    }
)

# Minimum length to consider (short messages are usually single-step)
_MIN_LENGTH = 60


def is_multi_step(message: str) -> bool:
    """Detect if user message describes a multi-step workflow.

    Uses heuristics: length, action verbs, sequencing words.
    Returns True when workflow path (ExecutionManager) is preferred.

    Args:
        message: User's raw message

    Returns:
        True if message suggests multiple dependent steps
    """
    if not message or len(message.strip()) < _MIN_LENGTH:
        return False

    lower = message.lower().strip()

    # Count multi-step phrase matches
    matches = sum(1 for p in _MULTI_STEP_PHRASES if p in lower)

    # Multiple action verbs or sequencing
    if matches >= 2:
        return True

    # Numbered steps (1. 2. 3.)
    if " 1." in lower and (" 2." in lower or " 3." in lower):
        return True

    # "research X, draft Y, email Z" pattern
    if matches >= 1 and len(lower) > 100:
        return True

    return False
