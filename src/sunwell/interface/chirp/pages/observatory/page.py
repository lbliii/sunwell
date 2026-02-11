"""Observatory page - Agent execution visualization.

TODO Phase 2: Add Canvas visualizations
- ResonanceWave
- PrismFracture
- ExecutionCinema
- MemoryLattice
"""

from chirp import Page
from sunwell.interface.chirp.services import SessionService


def get(session_svc: SessionService) -> Page:
    """Render observatory page."""
    # Load actual runs from BackgroundManager
    sessions = session_svc.list_sessions(limit=50)

    # Convert to runs format for template
    runs = []
    for session in sessions:
        runs.append({
            "id": session["id"],
            "goal": session["goal"],
            "status": session["status"],
            "started": session["started_at"] or 0.0,
            "events": session["tasks_completed"],  # Use tasks as proxy for events
        })

    return Page(
        "observatory/page.html",
        "content",
        current_page="observatory",
        runs=runs,
        title="Observatory",
    )
