"""Recovery API routes (RFC-125).

Provides endpoints for managing recovery states from failed agent runs.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/recovery", tags=["recovery"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class AutoFixRequest(BaseModel):
    """Request to trigger auto-fix for a recovery."""

    hint: str | None = None


class RecoverySummaryResponse(BaseModel):
    """Summary of a pending recovery."""

    goal_hash: str
    goal_preview: str
    passed: int
    failed: int
    waiting: int
    age_str: str
    timestamp: str


class RecoveryArtifactResponse(BaseModel):
    """Single artifact in recovery state."""

    path: str
    status: str
    content: str | None = None
    errors: list[str] | None = None
    original_error: str | None = None


class RecoveryStateResponse(BaseModel):
    """Full recovery state."""

    goal_hash: str
    goal: str
    run_id: str
    artifacts: list[RecoveryArtifactResponse]
    passed_count: int
    failed_count: int
    waiting_count: int
    failure_reason: str
    error_details: list[str]
    created_at: str
    iterations: list[dict[str, Any]] | None = None


class PendingRecoveriesResponse(BaseModel):
    """List of pending recoveries."""

    recoveries: list[RecoverySummaryResponse]


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _get_recovery_dir() -> Path:
    """Get the recovery directory for the current workspace."""
    return Path.cwd() / ".sunwell" / "recovery"


def _transform_summary(summary: Any) -> RecoverySummaryResponse:
    """Transform RecoverySummary to response model."""
    return RecoverySummaryResponse(
        goal_hash=summary.goal_hash,
        goal_preview=summary.goal_preview,
        passed=summary.passed,
        failed=summary.failed,
        waiting=summary.waiting,
        age_str=summary.age_str,
        timestamp=summary.timestamp.isoformat() if hasattr(summary, "timestamp") else "",
    )


def _transform_state(state: Any) -> RecoveryStateResponse:
    """Transform RecoveryState to response model."""
    artifacts = []
    for a in state.passed_artifacts:
        artifacts.append(
            RecoveryArtifactResponse(
                path=str(a.path),
                status="passed",
                content=a.content,
            )
        )
    for a in state.failed_artifacts:
        artifacts.append(
            RecoveryArtifactResponse(
                path=str(a.path),
                status="failed",
                content=a.content,
                errors=a.errors,
                original_error=a.errors[0] if a.errors else None,
            )
        )
    for a in state.waiting_artifacts:
        artifacts.append(
            RecoveryArtifactResponse(
                path=str(a.path),
                status="waiting",
            )
        )

    return RecoveryStateResponse(
        goal_hash=state.goal_hash,
        goal=state.goal,
        run_id=state.run_id,
        artifacts=artifacts,
        passed_count=len(state.passed_artifacts),
        failed_count=len(state.failed_artifacts),
        waiting_count=len(state.waiting_artifacts),
        failure_reason=state.failure_reason,
        error_details=state.error_details,
        created_at=state.created_at.isoformat() if hasattr(state, "created_at") else "",
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@router.get("/pending", response_model=PendingRecoveriesResponse)
async def list_pending_recoveries() -> PendingRecoveriesResponse:
    """List all pending recoveries.

    Returns summaries of all recoveries that haven't been resolved.
    """
    from sunwell.agent.recovery import RecoveryManager

    manager = RecoveryManager(_get_recovery_dir())
    pending = manager.list_pending()

    return PendingRecoveriesResponse(
        recoveries=[_transform_summary(s) for s in pending]
    )


@router.get("/{goal_hash}", response_model=RecoveryStateResponse)
async def get_recovery(goal_hash: str) -> RecoveryStateResponse:
    """Get a specific recovery by goal hash.

    Args:
        goal_hash: The goal hash (full or prefix) of the recovery to load.

    Returns:
        Full recovery state including all artifacts.

    Raises:
        HTTPException: If recovery not found.
    """
    from sunwell.agent.recovery import RecoveryManager

    manager = RecoveryManager(_get_recovery_dir())

    # Try exact match first
    state = manager.load(goal_hash)

    # If not found, try prefix match
    if not state:
        pending = manager.list_pending()
        matches = [s for s in pending if s.goal_hash.startswith(goal_hash)]
        if len(matches) == 1:
            state = manager.load(matches[0].goal_hash)
        elif len(matches) > 1:
            match_ids = [m.goal_hash[:8] for m in matches]
            raise HTTPException(
                status_code=400,
                detail=f"Ambiguous goal hash prefix: {goal_hash}. Matches: {match_ids}",
            )

    if not state:
        raise HTTPException(status_code=404, detail=f"Recovery not found: {goal_hash}")

    return _transform_state(state)


@router.post("/{goal_hash}/auto-fix")
async def auto_fix_recovery(
    goal_hash: str,
    request: AutoFixRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Trigger auto-fix for a recovery using the agent.

    This starts a background task that:
    1. Builds healing context from the recovery state
    2. Creates a focused fix goal for the failed artifacts
    3. Runs the agent with convergence enabled

    Args:
        goal_hash: The goal hash of the recovery.
        request: Optional hint to include in the fix context.

    Returns:
        Acknowledgment that the fix has been started.
    """
    from sunwell.agent.recovery import RecoveryManager

    manager = RecoveryManager(_get_recovery_dir())
    state = manager.load(goal_hash)

    if not state:
        raise HTTPException(status_code=404, detail=f"Recovery not found: {goal_hash}")

    # Schedule background auto-fix
    background_tasks.add_task(_run_auto_fix, state, request.hint)

    return {"status": "started", "goal_hash": goal_hash}


async def _run_auto_fix(state: Any, hint: str | None) -> None:
    """Background task to run auto-fix (RFC-MEMORY)."""
    from sunwell.agent import AdaptiveBudget, Agent, RunOptions
    from sunwell.interface.generative.cli.helpers import resolve_model
    from sunwell.agent.context.session import SessionContext
    from sunwell.memory import PersistentMemory
    from sunwell.agent.recovery import RecoveryManager, build_healing_context
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    cwd = Path.cwd()
    healing_context = build_healing_context(state, hint)

    # Build focused fix goal
    failed_files = [str(a.path) for a in state.failed_artifacts]
    fix_goal = f"Fix the following files: {', '.join(failed_files)}\n\n{healing_context}"

    # Create agent
    try:
        synthesis_model = resolve_model(None, None)
    except Exception:
        return  # Can't load model, abort silently

    tool_executor = ToolExecutor(
        workspace=cwd,
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    agent = Agent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=cwd,
        budget=AdaptiveBudget(total_budget=30_000),
    )

    # RFC-MEMORY: Build session and load memory
    options = RunOptions(trust="workspace", timeout_seconds=300)
    session = SessionContext.build(cwd, fix_goal, options)
    memory = PersistentMemory.load(cwd)

    # Run agent (events will be streamed via SSE if client is connected)
    try:
        async for _event in agent.run(session, memory):
            pass  # Events stream to connected clients
        # Success — mark resolved
        manager = RecoveryManager(_get_recovery_dir())
        manager.mark_resolved(state.goal_hash)
    except Exception:
        pass  # Recovery state preserved for another attempt


@router.post("/{goal_hash}/skip")
async def skip_recovery(goal_hash: str) -> dict[str, Any]:
    """Write only passed artifacts, skip failed ones.

    This writes all artifacts that passed validation and marks
    the recovery as resolved (skipped).

    Args:
        goal_hash: The goal hash of the recovery.

    Returns:
        Summary of written files.
    """
    from sunwell.agent.recovery import RecoveryManager

    manager = RecoveryManager(_get_recovery_dir())
    state = manager.load(goal_hash)

    if not state:
        raise HTTPException(status_code=404, detail=f"Recovery not found: {goal_hash}")

    passed = state.passed_artifacts
    written = 0
    errors = []

    for artifact in passed:
        try:
            artifact.path.parent.mkdir(parents=True, exist_ok=True)
            artifact.path.write_text(artifact.content)
            written += 1
        except Exception as e:
            errors.append({"path": str(artifact.path), "error": str(e)})

    # Mark resolved
    manager.mark_resolved(goal_hash)

    return {
        "status": "skipped",
        "written": written,
        "total_passed": len(passed),
        "errors": errors,
    }


@router.delete("/{goal_hash}")
async def delete_recovery(goal_hash: str) -> dict[str, str]:
    """Delete a recovery state.

    Args:
        goal_hash: The goal hash of the recovery to delete.

    Returns:
        Confirmation of deletion.
    """
    from sunwell.agent.recovery import RecoveryManager

    manager = RecoveryManager(_get_recovery_dir())

    # Verify exists
    state = manager.load(goal_hash)
    if not state:
        raise HTTPException(status_code=404, detail=f"Recovery not found: {goal_hash}")

    manager.delete(goal_hash)

    return {"status": "deleted", "goal_hash": goal_hash}
