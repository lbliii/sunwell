"""Artifact lineage tracking routes (RFC-121)."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from sunwell.interface.server.routes.models import (
    CamelModel,
    DependencyGraphResponse,
    FileDependenciesResponse,
    ImpactAnalysisResponse,
    LineageByGoalResponse,
    LineageGraphEdge,
    LineageGraphNode,
    LineageStatsResponse,
    SyncChangesResponse,
    UntrackedChangesResponse,
)
from sunwell.memory.lineage import HumanEditDetector, LineageStore, get_impact_analysis

router = APIRouter(prefix="/api/lineage", tags=["lineage"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class SyncLineageRequest(CamelModel):
    workspace: str | None = None
    mark_as_human: bool = True


# ═══════════════════════════════════════════════════════════════
# LINEAGE ROUTES
# IMPORTANT: Specific routes MUST come before the catch-all /{file_path:path}
# FastAPI matches routes in registration order.
# ═══════════════════════════════════════════════════════════════


@router.get("/goal/{goal_id}")
async def get_lineage_by_goal(goal_id: str, workspace: str | None = None) -> LineageByGoalResponse:
    """Get all artifacts created/modified by a goal."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)
    artifacts = store.get_by_goal(goal_id)

    return LineageByGoalResponse(
        goal_id=goal_id,
        artifacts=[a.to_dict() for a in artifacts],
        count=len(artifacts),
    )


@router.get("/deps/{file_path:path}")
async def get_file_dependencies(file_path: str, workspace: str | None = None) -> FileDependenciesResponse:
    """Get dependency graph for a file."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)
    lineage = store.get_by_path(file_path)

    if not lineage:
        return FileDependenciesResponse(path=file_path, imports=[], imported_by=[])

    return FileDependenciesResponse(
        path=file_path,
        imports=list(lineage.imports),
        imported_by=list(lineage.imported_by),
    )


@router.get("/impact/{file_path:path}")
async def get_impact_analysis_api(file_path: str, workspace: str | None = None) -> ImpactAnalysisResponse:
    """Analyze impact of modifying/deleting a file."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)
    impact = get_impact_analysis(store, file_path)

    return ImpactAnalysisResponse(
        path=file_path,
        direct_dependents=impact.get("direct_dependents", []),
        transitive_dependents=impact.get("transitive_dependents", []),
        affected_goals=list(impact.get("affected_goals", [])),
        risk_level=impact.get("risk_level", "low"),
    )


@router.get("/stats")
async def get_lineage_stats(workspace: str | None = None) -> LineageStatsResponse:
    """Get lineage statistics for a project."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)

    artifact_count = len(store._index)
    deleted_count = len(store._deleted)
    total_edits = 0
    sunwell_edits = 0
    human_edits = 0
    human_edited_files = 0
    total_imports = 0

    for artifact_id in store._list_artifact_ids():
        artifact = store._load_artifact(artifact_id)
        if artifact:
            total_edits += len(artifact.edits)
            sunwell_edits += sum(1 for e in artifact.edits if e.source == "sunwell")
            human_edits += sum(1 for e in artifact.edits if e.source == "human")
            if artifact.human_edited:
                human_edited_files += 1
            total_imports += len(artifact.imports)

    return LineageStatsResponse(
        tracked_files=artifact_count,
        deleted_files=deleted_count,
        total_edits=total_edits,
        sunwell_edits=sunwell_edits,
        human_edits=human_edits,
        human_edited_files=human_edited_files,
        dependency_edges=total_imports,
    )


@router.get("/sync")
async def detect_untracked_changes(workspace: str | None = None) -> UntrackedChangesResponse:
    """Detect files modified outside Sunwell."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)
    detector = HumanEditDetector(store)

    untracked = detector.detect_untracked_changes(project_path)
    return UntrackedChangesResponse(untracked=untracked, count=len(untracked))


@router.post("/sync")
async def sync_untracked_changes(request: SyncLineageRequest) -> SyncChangesResponse:
    """Sync untracked changes by recording them as human edits."""
    project_path = (
        Path(request.workspace).expanduser().resolve() if request.workspace else Path.cwd()
    )
    store = LineageStore(project_path)
    detector = HumanEditDetector(store)

    synced = detector.sync_untracked(project_path, mark_as_human=request.mark_as_human)
    return SyncChangesResponse(synced=synced, count=len(synced))


@router.get("/graph")
async def get_dependency_graph(workspace: str | None = None) -> dict[str, Any]:
    """Get full dependency graph for visualization."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for path, artifact_id in store._index.items():
        artifact = store._load_artifact(artifact_id)
        if not artifact:
            continue

        nodes.append({
            "id": path,
            "artifact_id": artifact_id,
            "human_edited": artifact.human_edited,
            "edit_count": len(artifact.edits),
            "created_by_goal": artifact.created_by_goal,
            "model": artifact.model,
        })

        for imp in artifact.imports:
            edges.append({
                "source": path,
                "target": imp,
                "type": "imports",
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


# ═══════════════════════════════════════════════════════════════
# CATCH-ALL FILE PATH ROUTE (must be LAST)
# ═══════════════════════════════════════════════════════════════


@router.get("/{file_path:path}")
async def get_file_lineage(file_path: str, workspace: str | None = None) -> dict[str, Any]:
    """Get lineage for a specific file."""
    project_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    store = LineageStore(project_path)
    lineage = store.get_by_path(file_path)

    if not lineage:
        return {"error": "No lineage found", "path": file_path}

    return lineage.to_dict()
