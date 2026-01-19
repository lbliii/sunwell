"""Routing-related type definitions."""

from enum import Enum


class RoutingTier(int, Enum):
    """Execution tiers for routing decisions (RFC-020).

    This is separate from core.Tier which is for router execution tiers.
    This enum is specifically for cognitive routing tier decisions.
    """

    FAST = 0    # No analysis, direct dispatch, ~50ms
    LIGHT = 1   # Brief acknowledgment, auto-proceed, ~200ms
    FULL = 2    # Full CoT reasoning, confirmation required, ~500ms
