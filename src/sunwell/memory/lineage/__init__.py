"""Artifact lineage tracking (RFC-121).

Track the complete lineage of every artifact: which goal spawned it,
which model wrote it, what edits were made, and how it relates to other artifacts.

Example:
    >>> from sunwell.lineage import LineageStore, LineageEventListener
    >>> store = LineageStore(Path("/project"))
    >>> listener = LineageEventListener(store)
    >>>
    >>> # Record file creation
    >>> listener.on_file_created(
    ...     path="src/auth.py",
    ...     content="class Auth: pass",
    ...     goal_id="goal-1",
    ...     task_id="task-1",
    ...     reason="Auth module",
    ...     model="claude-sonnet",
    ... )
    >>>
    >>> # Query lineage
    >>> lineage = store.get_by_path("src/auth.py")
    >>> print(lineage.artifact_id)
"""

from sunwell.memory.lineage.dependencies import (
    detect_imports,
    detect_language,
    get_impact_analysis,
    update_dependency_graph,
)
from sunwell.memory.lineage.human_detection import HumanEditDetector
from sunwell.memory.lineage.listener import LineageEventListener, create_lineage_listener
from sunwell.memory.lineage.models import (
    ArtifactEdit,
    ArtifactLineage,
    compute_content_hash,
    generate_artifact_id,
)
from sunwell.memory.lineage.store import LineageStore

__all__ = [
    # Models
    "ArtifactEdit",
    "ArtifactLineage",
    "compute_content_hash",
    "generate_artifact_id",
    # Store
    "LineageStore",
    # Event handling
    "LineageEventListener",
    "HumanEditDetector",
    "create_lineage_listener",
    # Dependencies
    "detect_imports",
    "detect_language",
    "update_dependency_graph",
    "get_impact_analysis",
]
