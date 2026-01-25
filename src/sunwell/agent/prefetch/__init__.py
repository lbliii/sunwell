"""Prefetch subsystem for Sunwell (RFC-071).

Uses briefing signals to pre-load context before the main agent starts.
"""

from sunwell.agent.prefetch.dispatcher import (
    PREFETCH_TIMEOUT,
    analyze_briefing_for_prefetch,
    execute_prefetch,
)

__all__ = [
    "PREFETCH_TIMEOUT",
    "analyze_briefing_for_prefetch",
    "execute_prefetch",
]
