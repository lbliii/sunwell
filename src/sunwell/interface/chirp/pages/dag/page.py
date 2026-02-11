"""DAG page - Execution graph visualization.

TODO Phase 2: Add Canvas graph visualization
- dagre layout
- Pan/zoom/select
- Interactive nodes
- Edge rendering
"""

from chirp import Page


def get() -> Page:
    """Render DAG page."""
    # TODO: Load actual DAG data
    dags = [
        {
            "id": "dag-1",
            "name": "Chirp Migration DAG",
            "nodes": 12,
            "edges": 15,
            "status": "complete",
        },
    ]

    return Page(
        "dag/page.html",
        "content",
        current_page="dag",
        dags=dags,
        title="DAG",
    )
