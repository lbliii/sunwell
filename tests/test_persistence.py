"""Tests for RFC-040/RFC-074 Plan Persistence and Incremental Execution.

Tests cover:
- SavedExecution creation and serialization
- PlanStore save/load/list operations
- Content hashing
- RFC-074 v2 ExecutionCache operations
- RFC-074 v2 IncrementalExecutor skip logic
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.agent.incremental import (
    ExecutionCache,
    ExecutionPlan,
    IncrementalExecutor,
    SkipDecision,
    SkipReason,
)
from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.naaru.executor import ArtifactResult
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
# Test: RFC-074 v2 ExecutionCache
# =============================================================================


def test_execution_cache_goal_tracking(sample_graph: ArtifactGraph) -> None:
    """ExecutionCache should track goal→artifacts mapping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")

        # Record a goal execution
        artifact_ids = ["UserProtocol", "AuthInterface", "UserModel"]
        cache.record_goal_execution("goal_abc123", artifact_ids, execution_time_ms=1500.0)

        # Retrieve it
        result = cache.get_artifacts_for_goal("goal_abc123")
        assert set(result) == set(artifact_ids)

        # Get full details
        details = cache.get_goal_execution("goal_abc123")
        assert details is not None
        assert details["goal_hash"] == "goal_abc123"
        assert details["execution_time_ms"] == 1500.0


def test_execution_cache_goal_not_found(sample_graph: ArtifactGraph) -> None:
    """ExecutionCache should return None for unknown goals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")

        result = cache.get_artifacts_for_goal("unknown_goal")
        assert result is None


# =============================================================================
# Test: RFC-074 v2 IncrementalExecutor plan_execution
# =============================================================================


def test_incremental_executor_plan_no_cache(sample_graph: ArtifactGraph) -> None:
    """IncrementalExecutor should plan full execution when no cache exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")
        executor = IncrementalExecutor(graph=sample_graph, cache=cache)

        plan = executor.plan_execution()

        # All artifacts should be scheduled for execution
        assert len(plan.to_execute) == 5  # 5 artifacts in sample_graph
        assert len(plan.to_skip) == 0


def test_incremental_executor_skip_decisions(sample_graph: ArtifactGraph) -> None:
    """IncrementalExecutor should provide skip decisions with reasons."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")
        executor = IncrementalExecutor(graph=sample_graph, cache=cache)

        plan = executor.plan_execution()

        # All decisions should have NO_CACHE reason (fresh cache)
        for artifact_id, decision in plan.decisions.items():
            assert decision.artifact_id == artifact_id
            assert not decision.can_skip
            assert decision.reason == SkipReason.NO_CACHE
            assert decision.current_hash  # Hash should be computed


def test_incremental_executor_force_rerun(sample_graph: ArtifactGraph) -> None:
    """IncrementalExecutor should respect force_rerun parameter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")

        # First, simulate a successful execution by setting cache entries
        from sunwell.incremental.cache import ExecutionStatus
        from sunwell.incremental.hasher import compute_input_hash
        for artifact_id in sample_graph:
            spec = sample_graph[artifact_id]
            input_hash = compute_input_hash(spec, {})
            cache.set(artifact_id, input_hash, ExecutionStatus.COMPLETED, result={"content": "test"})

        executor = IncrementalExecutor(graph=sample_graph, cache=cache)

        # Plan with force_rerun on specific artifacts
        plan = executor.plan_execution(force_rerun={"UserProtocol"})

        # UserProtocol should be scheduled (force)
        assert "UserProtocol" in plan.to_execute
        decision = plan.decisions["UserProtocol"]
        assert not decision.can_skip
        assert decision.reason == SkipReason.FORCE_RERUN


# =============================================================================
# Test: RFC-074 v2 ExecutionPlan properties
# =============================================================================


def test_execution_plan_properties(sample_graph: ArtifactGraph) -> None:
    """ExecutionPlan should compute derived properties correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")
        executor = IncrementalExecutor(graph=sample_graph, cache=cache)

        plan = executor.plan_execution()

        assert plan.total == 5
        assert plan.skip_percentage == 0.0  # All need execution

        # Verify to_dict() works
        plan_dict = plan.to_dict()
        assert plan_dict["total_artifacts"] == 5
        assert plan_dict["to_execute"] == 5
        assert plan_dict["to_skip"] == 0


# =============================================================================
# Test: RFC-074 v2 Provenance (from cache)
# =============================================================================


def test_execution_cache_provenance(sample_graph: ArtifactGraph) -> None:
    """ExecutionCache should track provenance from graph structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = ExecutionCache(Path(tmpdir) / "cache.db")
        executor = IncrementalExecutor(graph=sample_graph, cache=cache)

        # Planning syncs provenance to cache
        executor.plan_execution()

        # UserProtocol has dependents: UserModel, AuthService
        dependents = cache.get_direct_dependents("UserProtocol")
        assert "UserModel" in dependents
        assert "AuthService" in dependents

        # Get downstream (transitive)
        downstream = cache.get_downstream("UserProtocol")
        assert "UserModel" in downstream
        assert "AuthService" in downstream
        assert "App" in downstream  # Transitive through AuthService


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


# =============================================================================
# Test: Fresh Project (No .sunwell directory) - Regression tests
# =============================================================================


def test_plan_store_creates_directory_on_init() -> None:
    """PlanStore should create directory structure on initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a nested path that doesn't exist
        base_path = Path(tmpdir) / ".sunwell" / "plans"
        assert not base_path.exists()

        # Creating PlanStore should create the directory
        store = PlanStore(base_path=base_path)

        assert base_path.exists()
        assert base_path.is_dir()


def test_plan_store_load_nonexistent_returns_none() -> None:
    """PlanStore.load should return None for non-existent plans, not error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        # Should return None, not raise exception
        result = store.load("nonexistent_hash")
        assert result is None


def test_plan_store_find_by_goal_nonexistent_returns_none() -> None:
    """PlanStore.find_by_goal should return None for non-existent goals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        result = store.find_by_goal("This goal does not exist")
        assert result is None


def test_plan_store_list_recent_empty() -> None:
    """PlanStore.list_recent should return empty list for empty store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        recent = store.list_recent()
        assert recent == []


def test_plan_store_exists_empty_store() -> None:
    """PlanStore.exists should return False in empty store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PlanStore(base_path=Path(tmpdir))

        assert store.exists("any_hash") is False
