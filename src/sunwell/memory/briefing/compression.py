"""Briefing compression logic (RFC-071).

Compression function that creates new briefings by compressing old state
and session work. This is the "telephone game" compression function.
"""

from sunwell.memory.briefing.briefing import Briefing, BriefingStatus, ExecutionSummary


def compress_briefing(
    old_briefing: Briefing | None,
    summary: ExecutionSummary,
    new_status: BriefingStatus,
    blockers: list[str] | None = None,
    predicted_skills: list[str] | None = None,
    suggested_lens: str | None = None,
    complexity_estimate: str | None = None,
) -> Briefing:
    """Create new briefing by compressing old state + session work.

    This is the "telephone game" compression function.
    Each call produces a fresh briefing that captures current state.

    Args:
        old_briefing: Previous briefing (or None for first session)
        summary: Execution summary from this session
        new_status: Current status after this session
        blockers: Current blockers (replaces old)
        predicted_skills: Skills predicted for next session
        suggested_lens: Lens suggested for next session
        complexity_estimate: Complexity estimate for remaining work

    Returns:
        New briefing that overwrites the old one
    """
    # Start with old briefing or defaults
    if old_briefing:
        mission = old_briefing.mission
        goal_hash = old_briefing.goal_hash
        session_id = old_briefing.session_id

        # Carry forward hazards, removing resolved ones
        old_hazards = set(old_briefing.hazards)
        if summary.resolved_hazards:
            old_hazards -= set(summary.resolved_hazards)
        hazards = list(old_hazards)

        # Carry forward learnings
        old_learning_ids = list(old_briefing.related_learnings)
    else:
        mission = "Unknown mission"
        goal_hash = None
        session_id = ""
        hazards = []
        old_learning_ids = []

    # Add new hazards (keep max 3 most recent)
    if summary.new_hazards:
        hazards = (list(summary.new_hazards) + hazards)[:3]

    # Update learning references (keep max 5 most recent)
    learning_ids = list(summary.new_learnings) + old_learning_ids
    learning_ids = learning_ids[:5]

    # Construct progress summary
    if new_status == BriefingStatus.COMPLETE:
        progress = f"Complete. {summary.last_action}"
    elif new_status == BriefingStatus.BLOCKED:
        progress = f"Blocked. {summary.last_action}"
    else:
        progress = summary.last_action

    return Briefing(
        mission=mission,
        status=new_status,
        progress=progress,
        last_action=summary.last_action,
        next_action=summary.next_action,
        hazards=tuple(hazards),
        blockers=tuple(blockers or []),
        hot_files=tuple(summary.modified_files[:5]),
        goal_hash=goal_hash,
        related_learnings=tuple(learning_ids),
        # Dispatch hints
        predicted_skills=tuple(predicted_skills or []),
        suggested_lens=suggested_lens,
        complexity_estimate=complexity_estimate,
        estimated_files_touched=len(summary.modified_files) if summary.modified_files else None,
        # Metadata
        session_id=session_id,
    )
