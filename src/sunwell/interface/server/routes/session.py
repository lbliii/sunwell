"""Session management routes for autonomous sessions.

Provides API for listing, viewing, resuming, and managing sessions.
Sessions are stored globally at ~/.sunwell/sessions/.
"""

from fastapi import APIRouter, HTTPException

from sunwell.interface.server.routes.models import CamelModel
from sunwell.planning.naaru.session_store import SessionStore, SessionSummary
from sunwell.planning.naaru.types import SessionStatus

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class SessionSummaryResponse(CamelModel):
    """Session summary for listing."""

    session_id: str
    status: str
    goals: list[str]
    started_at: str
    stopped_at: str | None
    stop_reason: str | None
    opportunities_total: int
    opportunities_completed: int
    project_id: str | None
    workspace_id: str | None


class SessionListResponse(CamelModel):
    """List of sessions."""

    sessions: list[SessionSummaryResponse]
    resumable_count: int


class SessionDetailResponse(CamelModel):
    """Full session details."""

    session_id: str
    status: str
    goals: list[str]
    started_at: str
    stopped_at: str | None
    checkpoint_at: str | None
    stop_reason: str | None

    # Progress
    opportunities_total: int
    opportunities_completed: int
    opportunities_remaining: int

    # Counters
    proposals_created: int
    proposals_auto_applied: int
    proposals_queued: int
    proposals_rejected: int

    # Timing
    total_runtime_seconds: float

    # Context
    project_id: str | None
    workspace_id: str | None


class ResumeSessionRequest(CamelModel):
    """Request to resume a session."""

    checkpoint: int | None = None
    """Specific checkpoint to resume from (or latest if None)."""


class UpdateSessionStatusRequest(CamelModel):
    """Request to update session status."""

    status: str
    """New status: paused, completed, failed."""

    reason: str | None = None
    """Optional reason for the status change."""


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def _summary_to_response(summary: SessionSummary) -> SessionSummaryResponse:
    """Convert SessionSummary to response model."""
    return SessionSummaryResponse(
        session_id=summary.session_id,
        status=summary.status.value,
        goals=list(summary.goals),
        started_at=summary.started_at.isoformat(),
        stopped_at=summary.stopped_at.isoformat() if summary.stopped_at else None,
        stop_reason=summary.stop_reason,
        opportunities_total=summary.opportunities_total,
        opportunities_completed=summary.opportunities_completed,
        project_id=summary.project_id,
        workspace_id=summary.workspace_id,
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@router.get("")
async def list_sessions(
    status: str | None = None,
    limit: int = 50,
) -> SessionListResponse:
    """List all sessions.

    Args:
        status: Optional filter by status (running, paused, completed, failed).
        limit: Maximum sessions to return.

    Returns:
        List of session summaries.
    """
    store = SessionStore()

    try:
        status_filter = SessionStatus(status) if status else None
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {status}. Must be one of: running, paused, completed, failed",
        ) from None

    try:
        sessions = store.list_sessions(status=status_filter, limit=limit)
        resumable = store.get_resumable_sessions()

        return SessionListResponse(
            sessions=[_summary_to_response(s) for s in sessions],
            resumable_count=len(resumable),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list sessions: {type(e).__name__}"
        ) from e


@router.get("/{session_id}")
async def get_session(session_id: str) -> SessionDetailResponse:
    """Get detailed session information.

    Args:
        session_id: Session to retrieve.

    Returns:
        Full session details.
    """
    store = SessionStore()

    try:
        state = store.load(session_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        # Get metadata for project/workspace info
        metadata = store._load_metadata(store._sessions_dir / session_id)

        progress = state.get_progress_summary()

        return SessionDetailResponse(
            session_id=state.session_id,
            status=state.status.value,
            goals=list(state.config.goals),
            started_at=state.started_at.isoformat(),
            stopped_at=state.stopped_at.isoformat() if state.stopped_at else None,
            checkpoint_at=state.checkpoint_at.isoformat() if state.checkpoint_at else None,
            stop_reason=state.stop_reason,
            opportunities_total=progress["opportunities_total"],
            opportunities_completed=progress["opportunities_completed"],
            opportunities_remaining=progress["opportunities_remaining"],
            proposals_created=state.proposals_created,
            proposals_auto_applied=state.proposals_auto_applied,
            proposals_queued=state.proposals_queued,
            proposals_rejected=state.proposals_rejected,
            total_runtime_seconds=state.total_runtime_seconds,
            project_id=metadata.get("project_id"),
            workspace_id=metadata.get("workspace_id"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get session: {type(e).__name__}"
        ) from e


@router.post("/{session_id}/resume")
async def resume_session(
    session_id: str,
    request: ResumeSessionRequest | None = None,
) -> SessionDetailResponse:
    """Resume a paused or interrupted session.

    Args:
        session_id: Session to resume.
        request: Optional resume configuration.

    Returns:
        Updated session details.

    Note:
        This endpoint marks the session as resumable. The actual resumption
        happens when the autonomous runner picks up the session.
    """
    store = SessionStore()

    try:
        state = store.load(session_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        if state.status not in (SessionStatus.PAUSED, SessionStatus.RUNNING):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume session with status: {state.status.value}",
            )

        # Update status to RUNNING to indicate resume requested
        state.status = SessionStatus.RUNNING
        store.save(state)

        # Return updated details
        return await get_session(session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to resume session: {type(e).__name__}"
        ) from e


@router.post("/{session_id}/pause")
async def pause_session(session_id: str) -> SessionDetailResponse:
    """Pause a running session.

    Args:
        session_id: Session to pause.

    Returns:
        Updated session details.
    """
    store = SessionStore()

    try:
        state = store.load(session_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        if state.status != SessionStatus.RUNNING:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot pause session with status: {state.status.value}",
            )

        state.status = SessionStatus.PAUSED
        state.stop_reason = "User requested pause"
        store.save(state)

        return await get_session(session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to pause session: {type(e).__name__}"
        ) from e


@router.patch("/{session_id}")
async def update_session_status(
    session_id: str,
    request: UpdateSessionStatusRequest,
) -> SessionDetailResponse:
    """Update session status.

    Args:
        session_id: Session to update.
        request: New status and optional reason.

    Returns:
        Updated session details.
    """
    store = SessionStore()

    try:
        status = SessionStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {request.status}",
        ) from None

    try:
        if not store.update_status(session_id, status, request.reason):
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return await get_session(session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update session: {type(e).__name__}"
        ) from e


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session.

    Args:
        session_id: Session to delete.

    Returns:
        Confirmation of deletion.
    """
    store = SessionStore()

    try:
        if not store.delete(session_id):
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete session: {type(e).__name__}"
        ) from e
