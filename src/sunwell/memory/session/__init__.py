"""Session tracking and summarization (RFC-120).

Provides session-level observability for understanding what Sunwell
accomplished during a coding session.

Example:
    >>> from sunwell.session import SessionTracker
    >>> tracker = SessionTracker()
    >>> tracker.record_goal_complete(...)
    >>> summary = tracker.get_summary()
"""

from sunwell.memory.session.summary import GoalSummary, SessionSummary
from sunwell.memory.session.tracker import SessionTracker

__all__ = [
    "GoalSummary",
    "SessionSummary",
    "SessionTracker",
]
