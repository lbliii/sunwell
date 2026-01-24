"""Artifact lineage tracking (RFC-121).

Track the complete lineage of every artifact: which goal spawned it,
which model wrote it, what edits were made, and how it relates to other artifacts.

Example:
    >>> from sunwell.lineage import LineageStore
    >>> store = LineageStore(Path("/project"))
    >>> lineage = store.record_create(
    ...     path="src/auth.py",
    ...     content="class Auth: pass",
    ...     goal_id="goal-1",
    ...     task_id="task-1",
    ...     reason="Auth module",
    ...     model="claude-sonnet",
    ... )
    >>> print(lineage.artifact_id)
"""

from sunwell.lineage.models import (
    ArtifactEdit,
    ArtifactLineage,
    compute_content_hash,
    generate_artifact_id,
)
from sunwell.lineage.store import LineageStore

__all__ = [
    "ArtifactEdit",
    "ArtifactLineage",
    "LineageStore",
    "compute_content_hash",
    "generate_artifact_id",
]
