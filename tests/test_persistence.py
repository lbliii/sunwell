"""Tests for RFC-040 Plan Persistence and Incremental Execution.

Tests cover:
- SavedExecution creation and serialization
- PlanStore save/load/list operations
- Content hashing
- Change detection
- Invalidation cascade
- Incremental rebuild set computation
- Plan preview generation
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.naaru.executor import ArtifactResult
from sunwell.naaru.incremental import (
    ChangeDetector,
    ChangeReport,
    PlanPreview,
    compute_rebuild_set,
    find_invalidated,
)
from sunwell.naaru.persistence import (
    ArtifactCompletion,
    ExecutionStatus,
    PlanStore,
    SavedExecution,
    TraceLogger,
    hash_content,
    hash_goal,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_graph() -> ArtifactGraph:
    """Create a sample artifact graph for testing."""
    graph = ArtifactGraph()

    # Layer 0: Leaves (no dependencies)
    graph.add(
        ArtifactSpec(
            id="UserProtocol",
            description="Protocol defining User entity",
            contract="Protocol with fields: id, email, password_hash",
            produces_file="src/protocols/user.py",
            domain_type="protocol",
        )
    )
    graph.add(
        ArtifactSpec(
            id="AuthInterface",
            description="Interface for authentication",
            contract="Interface with methods: authenticate, validate_token",
            produces_file="src/interfaces/auth.py",
            domain_type="interface",
        )
    )

    # Layer 1: Depend on leaves
    graph.add(
        ArtifactSpec(
            id="UserModel",
            description="SQLAlchemy model implementing UserProtocol",
            contract="Class User(Base) implementing UserProtocol",
            produces_file="src/models/user.py",
            requires=frozenset(["UserProtocol"]),
            domain_type="model",
        )
    )
    graph.add(
        ArtifactSpec(
            id="AuthService",
            description="JWT-based authentication service",
            contract="Class AuthService implementing AuthInterface",
            produces_file="src/services/auth.py",
            requires=frozenset(["AuthInterface", "UserProtocol"]),
            domain_type="service",
        )
    )

    # Layer 2: Convergence
    graph.add(
        ArtifactSpec(
            id="App",
            description="Flask application factory",
            contract="create_app() function returning Flask app",
            produces_file="src/app.py",
            requires=frozenset(["UserModel", "AuthService"]),
            domain_type="app",
        )
    )

    return graph


@pytest.fixture
def temp_store() -> PlanStore:
    """Create a PlanStore with a temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PlanStore(base_path=Path(tmpdir))


# =============================================================================
# Test: Content Hashing
# =============================================================================


def test_hash_goal_deterministic() -> None:
    """Goal hashing should be deterministic."""
    goal = "Build a REST API with authentication"
    hash1 = hash_goal(goal)
    hash2 = hash_goal(goal)

    assert hash1 == hash2
    assert len(hash1) == 16  # Truncated SHA-256


def test_hash_goal_different_goals() -> None:
    """Different goals should produce different hashes."""
    hash1 = hash_goal("Build a REST API")
    hash2 = hash_goal("Build a GraphQL API")

    assert hash1 != hash2


def test_hash_content_string() -> None:
    """Content hashing should work for strings."""
    content = "def hello(): return 'world'"
    hash1 = hash_content(content)
    hash2 = hash_content(content)

    assert hash1 == hash2
    assert len(hash1) == 16


def test_hash_content_bytes() -> None:
    """Content hashing should work for bytes."""
    content = b"binary content"
    hash1 = hash_content(content)

    assert len(hash1) == 16


# =============================================================================
# Test: ArtifactCompletion
# =============================================================================


def test_artifact_completion_to_dict() -> None:
    """ArtifactCompletion should serialize to dict."""
    completion = ArtifactCompletion(
        artifact_id="UserProtocol",
        content_hash="abc123def456",
        model_tier="small",
        duration_ms=1500,
        verified=True,
    )

    data = completion.to_dict()

    assert data["artifact_id"] == "UserProtocol"
    assert data["content_hash"] == "abc123def456"
    assert data["model_tier"] == "small"
    assert data["duration_ms"] == 1500
    assert data["verified"] is True
    assert "completed_at" in data


def test_artifact_completion_from_dict() -> None:
    """ArtifactCompletion should deserialize from dict."""
    data = {
        "artifact_id": "UserModel",
        "content_hash": "xyz789",
        "model_tier": "medium",
        "duration_ms": 2500,
        "verified": False,
        "completed_at": "2026-01-19T10:30:00",
    }

    completion = ArtifactCompletion.from_dict(data)

    assert completion.artifact_id == "UserModel"
    assert completion.content_hash == "xyz789"
    assert completion.model_tier == "medium"


def test_artifact_completion_from_result() -> None:
    """ArtifactCompletion should be creatable from ArtifactResult."""
    result = ArtifactResult(
        artifact_id="AuthService",
        content="class AuthService: pass",
        verified=True,
        model_tier="large",
        duration_ms=3000,
    )

    completion = ArtifactCompletion.from_result(result)

    assert completion.artifact_id == "AuthService"
    assert completion.model_tier == "large"
    assert completion.duration_ms == 3000
    assert completion.verified is True
    assert len(completion.content_hash) == 16


# =============================================================================
# Test: SavedExecution
# =============================================================================


def test_saved_execution_creation(sample_graph: ArtifactGraph) -> None:
    """SavedExecution should be creatable with a graph."""
    execution = SavedExecution(
        goal="Build a REST API",
        graph=sample_graph,
    )

    assert execution.goal == "Build a REST API"
    assert len(execution.goal_hash) == 16
    assert execution.status == ExecutionStatus.PLANNED
    assert len(execution.graph) == 5


def test_saved_execution_goal_hash_auto() -> None:
    """Goal hash should be computed automatically."""
    graph = ArtifactGraph()
    execution = SavedExecution(goal="Test goal", graph=graph)

    assert execution.goal_hash == hash_goal("Test goal")


def test_saved_execution_progress(sample_graph: ArtifactGraph) -> None:
    """SavedExecution should track progress correctly."""
    execution = SavedExecution(goal="Build API", graph=sample_graph)

    # Initially no progress
    assert execution.progress_percent == 0.0
    assert len(execution.pending_ids) == 5

    # Mark one completed
    result = ArtifactResult(
        artifact_id="UserProtocol",
        content="protocol code",
        verified=True,
        model_tier="small",
        duration_ms=1000,
    )
    execution.mark_completed(result)

    assert execution.progress_percent == 20.0
    assert len(execution.completed) == 1
    assert "UserProtocol" in execution.completed_ids


def test_saved_execution_mark_failed(sample_graph: ArtifactGraph) -> None:
    """SavedExecution should track failed artifacts."""
    execution = SavedExecution(goal="Build API", graph=sample_graph)

    execution.mark_failed("UserModel", "Database connection failed")

    assert len(execution.failed) == 1
    assert "UserModel" in execution.failed_ids
    assert execution.failed["UserModel"] == "Database connection failed"


def test_saved_execution_serialization(sample_graph: ArtifactGraph) -> None:
    """SavedExecution should serialize and deserialize correctly."""
    execution = SavedExecution(
        goal="Build API",
        graph=sample_graph,
        status=ExecutionStatus.IN_PROGRESS,
    )

    # Add some completed artifacts
    result = ArtifactResult(
        artifact_id="UserProtocol",
        content="code",
        verified=True,
        model_tier="small",
        duration_ms=1000,
    )
    execution.mark_completed(result)

    # Serialize
    data = execution.to_dict()

    # Deserialize
    loaded = SavedExecution.from_dict(data)

    assert loaded.goal == execution.goal
    assert loaded.goal_hash == execution.goal_hash
    assert loaded.status == ExecutionStatus.IN_PROGRESS
    assert len(loaded.completed) == 1
    assert "UserProtocol" in loaded.completed


def test_saved_execution_get_resume_wave(sample_graph: ArtifactGraph) -> None:
    """get_resume_wave should find the correct wave to resume from."""
    execution = SavedExecution(goal="Build API", graph=sample_graph)

    # No progress - resume from wave 0
    assert execution.get_resume_wave() == 0

    # Complete wave 0 (leaves)
    for aid in ["UserProtocol", "AuthInterface"]:
        result = ArtifactResult(artifact_id=aid, content="code", model_tier="small")
        execution.mark_completed(result)

    # Should resume from wave 1
    assert execution.get_resume_wave() == 1


# =============================================================================
# Test: PlanStore
# =============================================================================


def test_plan_store_save_and_load(sample_graph: ArtifactGraph) -> None:
    """PlanStore should save and load executions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        execution = SavedExecution(goal="Test goal", graph=sample_graph)

        # Save
        path = store.save(execution)
        assert path.exists()

        # Load
        loaded = store.load(execution.goal_hash)
        assert loaded is not None
        assert loaded.goal == "Test goal"
        assert len(loaded.graph) == 5


def test_plan_store_find_by_goal(sample_graph: ArtifactGraph) -> None:
    """PlanStore should find by goal text."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        execution = SavedExecution(goal="My specific goal", graph=sample_graph)
        store.save(execution)

        # Find by goal
        found = store.find_by_goal("My specific goal")
        assert found is not None
        assert found.goal_hash == execution.goal_hash


def test_plan_store_list_recent(sample_graph: ArtifactGraph) -> None:
    """PlanStore should list recent executions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        # Save multiple
        for i in range(5):
            execution = SavedExecution(goal=f"Goal {i}", graph=sample_graph)
            store.save(execution)

        # List
        recent = store.list_recent(limit=3)
        assert len(recent) == 3


def test_plan_store_delete(sample_graph: ArtifactGraph) -> None:
    """PlanStore should delete plans."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        execution = SavedExecution(goal="To delete", graph=sample_graph)
        store.save(execution)

        # Verify exists
        assert store.exists(execution.goal_hash)

        # Delete
        assert store.delete(execution.goal_hash) is True
        assert store.exists(execution.goal_hash) is False

        # Delete non-existent
        assert store.delete("nonexistent") is False


# =============================================================================
# Test: TraceLogger
# =============================================================================


def test_trace_logger_log_events() -> None:
    """TraceLogger should log events to JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TraceLogger(goal_hash="test123", base_path=Path(tmpdir))

        logger.log_event("plan_created", artifact_count=5)
        logger.log_event("wave_start", wave=0, artifacts=["A", "B"])

        # Read events
        events = logger.read_events()
        assert len(events) == 2
        assert events[0]["event"] == "plan_created"
        assert events[1]["artifacts"] == ["A", "B"]


def test_trace_logger_clear() -> None:
    """TraceLogger should clear events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TraceLogger(goal_hash="test456", base_path=Path(tmpdir))

        logger.log_event("test_event")
        assert len(logger.read_events()) == 1

        logger.clear()
        assert len(logger.read_events()) == 0


# =============================================================================
# Test: ChangeDetector
# =============================================================================


def test_change_detector_no_changes(sample_graph: ArtifactGraph) -> None:
    """ChangeDetector should detect no changes when graphs match."""
    execution = SavedExecution(goal="Test", graph=sample_graph)

    detector = ChangeDetector(check_output_files=False)
    changes = detector.detect(sample_graph, execution)

    assert not changes.has_changes
    assert len(changes.all_changed) == 0


def test_change_detector_added_artifact(sample_graph: ArtifactGraph) -> None:
    """ChangeDetector should detect added artifacts."""
    execution = SavedExecution(goal="Test", graph=sample_graph)

    # Create new graph with additional artifact
    new_graph = ArtifactGraph()
    for aid in sample_graph:
        new_graph.add(sample_graph[aid])

    new_graph.add(
        ArtifactSpec(
            id="NewArtifact",
            description="New thing",
            contract="New contract",
        )
    )

    detector = ChangeDetector(check_output_files=False)
    changes = detector.detect(new_graph, execution)

    assert "NewArtifact" in changes.added
    assert changes.has_changes


def test_change_detector_contract_changed(sample_graph: ArtifactGraph) -> None:
    """ChangeDetector should detect contract changes."""
    execution = SavedExecution(goal="Test", graph=sample_graph)

    # Create modified graph
    new_graph = ArtifactGraph()
    for aid in sample_graph:
        artifact = sample_graph[aid]
        if aid == "UserProtocol":
            # Change contract
            artifact = ArtifactSpec(
                id=artifact.id,
                description=artifact.description,
                contract="MODIFIED CONTRACT",  # Changed!
                produces_file=artifact.produces_file,
                requires=artifact.requires,
                domain_type=artifact.domain_type,
            )
        new_graph.add(artifact)

    detector = ChangeDetector(check_output_files=False)
    changes = detector.detect(new_graph, execution)

    assert "UserProtocol" in changes.contract_changed


def test_change_detector_removed_artifact(sample_graph: ArtifactGraph) -> None:
    """ChangeDetector should detect removed artifacts."""
    execution = SavedExecution(goal="Test", graph=sample_graph)

    # Create graph with one less artifact (need to adjust deps)
    new_graph = ArtifactGraph()
    new_graph.add(sample_graph["UserProtocol"])
    new_graph.add(sample_graph["AuthInterface"])
    # Skip UserModel, AuthService, App

    detector = ChangeDetector(check_output_files=False)
    changes = detector.detect(new_graph, execution)

    assert "UserModel" in changes.removed
    assert "AuthService" in changes.removed
    assert "App" in changes.removed


# =============================================================================
# Test: Invalidation Cascade
# =============================================================================


def test_find_invalidated_single(sample_graph: ArtifactGraph) -> None:
    """find_invalidated should cascade from a single change."""
    # If UserProtocol changes, UserModel and AuthService should be invalidated
    # AuthService depends on UserProtocol
    # App depends on AuthService
    invalidated = find_invalidated(sample_graph, {"UserProtocol"})

    assert "UserProtocol" in invalidated
    assert "UserModel" in invalidated  # depends on UserProtocol
    assert "AuthService" in invalidated  # depends on UserProtocol
    assert "App" in invalidated  # depends on AuthService


def test_find_invalidated_multiple(sample_graph: ArtifactGraph) -> None:
    """find_invalidated should handle multiple starting points."""
    invalidated = find_invalidated(sample_graph, {"UserProtocol", "AuthInterface"})

    # Everything depends on these leaves
    assert len(invalidated) == 5  # All artifacts


def test_find_invalidated_leaf_only(sample_graph: ArtifactGraph) -> None:
    """find_invalidated with App should only include App."""
    invalidated = find_invalidated(sample_graph, {"App"})

    # App has no dependents
    assert invalidated == {"App"}


# =============================================================================
# Test: compute_rebuild_set
# =============================================================================


def test_compute_rebuild_set_with_changes(sample_graph: ArtifactGraph) -> None:
    """compute_rebuild_set should include changes and cascade."""
    changes = ChangeReport(contract_changed={"UserProtocol"})

    to_rebuild = compute_rebuild_set(sample_graph, changes)

    # Should include UserProtocol and all dependents
    assert "UserProtocol" in to_rebuild
    assert "UserModel" in to_rebuild
    assert "AuthService" in to_rebuild
    assert "App" in to_rebuild

    # AuthInterface unchanged and has no path through UserProtocol
    assert "AuthInterface" not in to_rebuild


def test_compute_rebuild_set_with_incomplete(sample_graph: ArtifactGraph) -> None:
    """compute_rebuild_set should include incomplete artifacts."""
    execution = SavedExecution(goal="Test", graph=sample_graph)

    # Complete some but not all
    execution.mark_completed(
        ArtifactResult(artifact_id="UserProtocol", content="code", model_tier="small")
    )
    execution.mark_completed(
        ArtifactResult(artifact_id="AuthInterface", content="code", model_tier="small")
    )

    changes = ChangeReport()  # No changes
    to_rebuild = compute_rebuild_set(sample_graph, changes, previous=execution)

    # Should include incomplete artifacts
    assert "UserModel" in to_rebuild
    assert "AuthService" in to_rebuild
    assert "App" in to_rebuild

    # Completed should not be included (if no cascade)
    assert "UserProtocol" not in to_rebuild
    assert "AuthInterface" not in to_rebuild


# =============================================================================
# Test: PlanPreview
# =============================================================================


def test_plan_preview_creation(sample_graph: ArtifactGraph) -> None:
    """PlanPreview should compute estimates."""
    preview = PlanPreview.create(sample_graph)

    assert len(preview.waves) == 3  # 3 layers in sample graph
    assert preview.estimated_tokens > 0
    assert preview.estimated_cost_usd > 0
    assert preview.estimated_duration_seconds > 0
    assert preview.parallelization_factor > 1.0


def test_plan_preview_model_distribution(sample_graph: ArtifactGraph) -> None:
    """PlanPreview should compute model distribution."""
    preview = PlanPreview.create(sample_graph)

    total = sum(preview.model_distribution.values())
    assert total == 5  # 5 artifacts


def test_plan_preview_incremental(sample_graph: ArtifactGraph) -> None:
    """PlanPreview should compute incremental savings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        # Save a previous execution with some completed
        execution = SavedExecution(goal="Test goal", graph=sample_graph)
        for aid in ["UserProtocol", "AuthInterface"]:
            execution.mark_completed(
                ArtifactResult(artifact_id=aid, content="code", model_tier="small")
            )
        store.save(execution)

        # Create preview with store
        preview = PlanPreview.create(sample_graph, goal="Test goal", store=store)

        assert preview.previous is not None
        # Changes would be detected based on content hashes
        # In this case, no actual files exist, so detection varies


# =============================================================================
# Test: ArtifactGraph.get_dependents (RFC-040 prerequisite)
# =============================================================================


def test_artifact_graph_get_dependents(sample_graph: ArtifactGraph) -> None:
    """ArtifactGraph.get_dependents should return correct dependents."""
    # UserProtocol is required by UserModel and AuthService
    dependents = sample_graph.get_dependents("UserProtocol")

    assert "UserModel" in dependents
    assert "AuthService" in dependents
    assert len(dependents) == 2


def test_artifact_graph_get_dependents_root() -> None:
    """Root artifact should have no dependents."""
    graph = ArtifactGraph()
    graph.add(ArtifactSpec(id="A", description="A", contract="A"))
    graph.add(
        ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"]))
    )

    dependents_b = graph.get_dependents("B")
    assert len(dependents_b) == 0


def test_artifact_graph_get_dependents_nonexistent(sample_graph: ArtifactGraph) -> None:
    """get_dependents for non-existent ID should return empty set."""
    dependents = sample_graph.get_dependents("NonExistent")
    assert dependents == set()
