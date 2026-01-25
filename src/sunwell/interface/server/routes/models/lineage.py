"""Lineage response models (RFC-121)."""

from sunwell.interface.server.routes.models.base import CamelModel


class LineageByGoalResponse(CamelModel):
    """Artifacts created/modified by a goal."""

    goal_id: str
    artifacts: list[dict[str, str | int | float | bool | None]]
    count: int


class FileDependenciesResponse(CamelModel):
    """Dependency graph for a file."""

    path: str
    imports: list[str]
    imported_by: list[str]


class ImpactAnalysisResponse(CamelModel):
    """Impact analysis for modifying/deleting a file."""

    path: str
    direct_dependents: list[str]
    transitive_dependents: list[str]
    affected_goals: list[str]
    risk_level: str


class LineageStatsResponse(CamelModel):
    """Lineage statistics for a project."""

    tracked_files: int
    deleted_files: int
    total_edits: int
    sunwell_edits: int
    human_edits: int
    human_edited_files: int
    dependency_edges: int


class UntrackedChangesResponse(CamelModel):
    """Files modified outside Sunwell."""

    untracked: list[str]
    count: int


class SyncChangesResponse(CamelModel):
    """Result of syncing untracked changes."""

    synced: list[str]
    count: int


class LineageGraphNode(CamelModel):
    """A node in the lineage dependency graph."""

    id: str
    artifact_id: str
    human_edited: bool
    edit_count: int
    created_by_goal: str | None
    model: str | None


class LineageGraphEdge(CamelModel):
    """An edge in the lineage dependency graph."""

    source: str
    target: str
    type: str


class DependencyGraphResponse(CamelModel):
    """Full dependency graph for visualization."""

    nodes: list[LineageGraphNode]
    edges: list[LineageGraphEdge]
    node_count: int
    edge_count: int
