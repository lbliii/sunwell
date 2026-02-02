"""Session hooks for awareness extraction.

Provides integration points for awareness extraction at session end
and awareness loading at session start.
"""

import logging
from pathlib import Path

from sunwell.awareness.extractor import AwarenessExtractor
from sunwell.awareness.patterns import AwarenessPattern, format_patterns_for_prompt
from sunwell.awareness.store import AwarenessStore

logger = logging.getLogger(__name__)


def extract_awareness_end_of_session(
    workspace: Path,
    *,
    tool_audit_log: list[dict] | None = None,
) -> int:
    """Extract awareness patterns at end of session.

    Runs the awareness extractor on the most recent session data
    and persists any new patterns.

    This should be called after session/briefing is saved but before
    the CLI exits.

    Args:
        workspace: Working directory
        tool_audit_log: Optional tool call audit log from the session

    Returns:
        Number of patterns extracted/updated
    """
    from sunwell.agent.learning.store import LearningStore
    from sunwell.memory.session.tracker import SessionTracker

    # Load the most recent session
    sessions_dir = workspace / ".sunwell" / "sessions"
    recent_sessions = SessionTracker.list_recent(sessions_dir, limit=1)

    if not recent_sessions:
        logger.debug("No recent sessions found for awareness extraction")
        return 0

    try:
        tracker = SessionTracker.load(recent_sessions[0])
        session_summary = tracker.get_summary()
    except Exception as e:
        logger.warning("Failed to load session for awareness: %s", e)
        return 0

    # Load learning store from disk
    learning_store = LearningStore()
    try:
        loaded = learning_store.load_from_disk(workspace)
        logger.debug("Loaded %d learnings for awareness analysis", loaded)
    except Exception as e:
        logger.warning("Failed to load learnings for awareness: %s", e)

    # Run extractor
    extractor = AwarenessExtractor()
    patterns = extractor.analyze_session(
        session_summary=session_summary,
        learning_store=learning_store,
        tool_audit_log=tool_audit_log,
    )

    if not patterns:
        logger.debug("No awareness patterns extracted from session")
        return 0

    # Save to awareness store
    awareness_dir = workspace / ".sunwell" / "awareness"
    store = AwarenessStore.load(awareness_dir)
    count = store.add_patterns(patterns)
    store.save()

    logger.info("Extracted %d awareness patterns from session", count)
    return count


def load_awareness_for_prompt(
    workspace: Path,
    activity_day: int = 0,
) -> list[AwarenessPattern]:
    """Load awareness patterns for system prompt injection.

    Should be called at session start to get patterns for injection
    into the system prompt.

    Args:
        workspace: Working directory
        activity_day: Current activity day for decay calculation

    Returns:
        List of significant patterns for prompt injection
    """
    from sunwell.awareness.store import load_awareness_for_session
    return load_awareness_for_session(workspace, activity_day)


def get_awareness_prompt_section(
    workspace: Path,
    activity_day: int = 0,
) -> str:
    """Get formatted awareness section for system prompt.

    Convenience function that loads patterns and formats them.

    Args:
        workspace: Working directory
        activity_day: Current activity day

    Returns:
        Formatted string or empty if no patterns
    """
    patterns = load_awareness_for_prompt(workspace, activity_day)
    return format_patterns_for_prompt(patterns)
