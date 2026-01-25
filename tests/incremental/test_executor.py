"""Tests for RFC-074 IncrementalExecutor."""

from pathlib import Path

import pytest

from sunwell.incremental.cache import ExecutionCache, ExecutionStatus
from sunwell.incremental.executor import (
    ExecutionPlan,
    IncrementalExecutor,
    SkipDecision,
    SkipReason,
    should_skip,
)
from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec


@pytest.fixture
def cache(tmp_path: Path) -> ExecutionCache:
    """Create a test cache."""
    return ExecutionCache(tmp_path / "test_cache.db")


@pytest.fixture
def simple_graph() -> ArtifactGraph:
    """Create a simple test graph: A → B → C."""
    graph = ArtifactGraph()
    graph.add(ArtifactSpec(id="A", description="Artifact A", contract="Contract A"))
    graph.add(
        ArtifactSpec(
            id="B",
            description="Artifact B",
            contract="Contract B",
            requires=frozenset(["A"]),
        )
    )
    graph.add(
        ArtifactSpec(
            id="C",
            description="Artifact C",
            contract="Contract C",
            requires=frozenset(["B"]),
        )
    )
    return graph


class TestShouldSkip:
    """Tests for should_skip function."""

    def test_skip_unchanged_artifact(self, cache: ExecutionCache) -> None:
        """Unchanged artifacts are skipped."""
        spec = ArtifactSpec(id="artifact_a", description="test", contract="test")

        # Cache a completed execution with matching hash
        from sunwell.incremental.hasher import compute_input_hash

        input_hash = compute_input_hash(spec, {})
        cache.set("artifact_a", input_hash, ExecutionStatus.COMPLETED, {"output": "value"})

        decision = should_skip(spec, cache, {})

        assert decision.can_skip is True
        assert decision.reason == SkipReason.UNCHANGED_SUCCESS
        assert decision.cached_result == {"output": "value"}

    def test_execute_when_no_cache(self, cache: ExecutionCache) -> None:
        """Artifacts with no cache entry must execute."""
        spec = ArtifactSpec(id="artifact_a", description="test", contract="test")

        decision = should_skip(spec, cache, {})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.NO_CACHE

    def test_execute_when_hash_changed(self, cache: ExecutionCache) -> None:
        """Artifacts with changed hash must execute."""
        spec = ArtifactSpec(id="artifact_a", description="test", contract="test")

        # Cache with different hash
        cache.set("artifact_a", "old_hash", ExecutionStatus.COMPLETED)

        decision = should_skip(spec, cache, {})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.HASH_CHANGED
        assert decision.previous_hash == "old_hash"

    def test_execute_when_previous_failed(self, cache: ExecutionCache) -> None:
        """Artifacts that previously failed must execute."""
        spec = ArtifactSpec(id="artifact_a", description="test", contract="test")

        from sunwell.incremental.hasher import compute_input_hash

        input_hash = compute_input_hash(spec, {})
        cache.set("artifact_a", input_hash, ExecutionStatus.FAILED)

        decision = should_skip(spec, cache, {})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.PREVIOUS_FAILED

    def test_execute_when_force_rerun(self, cache: ExecutionCache) -> None:
        """Force rerun overrides caching."""
        spec = ArtifactSpec(id="artifact_a", description="test", contract="test")

        from sunwell.incremental.hasher import compute_input_hash

        input_hash = compute_input_hash(spec, {})
        cache.set("artifact_a", input_hash, ExecutionStatus.COMPLETED)

        decision = should_skip(spec, cache, {}, force_rerun=True)

        assert decision.can_skip is False
        assert decision.reason == SkipReason.FORCE_RERUN


class TestIncrementalExecutor:
    """Tests for IncrementalExecutor."""

    def test_plan_execution_all_new(
        self, simple_graph: ArtifactGraph, cache: ExecutionCache
    ) -> None:
        """All artifacts execute when cache is empty."""
        executor = IncrementalExecutor(simple_graph, cache)

        plan = executor.plan_execution()

        assert set(plan.to_execute) == {"A", "B", "C"}
        assert plan.to_skip == []
        assert plan.skip_percentage == 0.0

    def test_plan_execution_with_cache_hits(
        self, simple_graph: ArtifactGraph, cache: ExecutionCache
    ) -> None:
        """Cached artifacts are skipped."""
        executor = IncrementalExecutor(simple_graph, cache)

        # Pre-populate cache for A with correct hash
        spec_a = simple_graph.get("A")
        assert spec_a is not None
        from sunwell.incremental.hasher import compute_input_hash

        hash_a = compute_input_hash(spec_a, {})
        cache.set("A", hash_a, ExecutionStatus.COMPLETED)

        plan = executor.plan_execution()

        assert "A" in plan.to_skip
        assert "B" in plan.to_execute
        assert "C" in plan.to_execute

    def test_plan_execution_force_rerun(
        self, simple_graph: ArtifactGraph, cache: ExecutionCache
    ) -> None:
        """Force rerun executes specific artifacts."""
        executor = IncrementalExecutor(simple_graph, cache)

        # Cache all artifacts
        for artifact_id in ["A", "B", "C"]:
            spec = simple_graph.get(artifact_id)
            assert spec is not None
            from sunwell.incremental.hasher import compute_input_hash

            dep_hashes = {}
            if artifact_id == "B":
                dep_hashes = {"A": compute_input_hash(simple_graph.get("A"), {})}
            elif artifact_id == "C":
                dep_hashes = {
                    "B": compute_input_hash(
                        simple_graph.get("B"),
                        {"A": compute_input_hash(simple_graph.get("A"), {})},
                    )
                }
            hash_val = compute_input_hash(spec, dep_hashes)
            cache.set(artifact_id, hash_val, ExecutionStatus.COMPLETED)

        plan = executor.plan_execution(force_rerun={"B"})

        assert "B" in plan.to_execute
        assert plan.decisions["B"].reason == SkipReason.FORCE_RERUN

    def test_impact_analysis(self, simple_graph: ArtifactGraph, cache: ExecutionCache) -> None:
        """Impact analysis shows downstream artifacts."""
        executor = IncrementalExecutor(simple_graph, cache)

        impact = executor.impact_analysis("A")

        assert impact["artifact"] == "A"
        assert "B" in impact["transitive_dependents"]
        assert "C" in impact["transitive_dependents"]

    @pytest.mark.asyncio
    async def test_execute_basic(self, simple_graph: ArtifactGraph, cache: ExecutionCache) -> None:
        """Basic execution creates all artifacts."""
        executor = IncrementalExecutor(simple_graph, cache)

        async def create_fn(spec: ArtifactSpec) -> str:
            return f"Content for {spec.id}"

        result = await executor.execute(create_fn)

        assert result.success
        assert len(result.completed) == 3
        assert len(result.skipped) == 0
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_execute_with_skips(
        self, simple_graph: ArtifactGraph, cache: ExecutionCache
    ) -> None:
        """Execution skips cached artifacts."""
        executor = IncrementalExecutor(simple_graph, cache)

        # Pre-cache A
        spec_a = simple_graph.get("A")
        assert spec_a is not None
        from sunwell.incremental.hasher import compute_input_hash

        hash_a = compute_input_hash(spec_a, {})
        cache.set("A", hash_a, ExecutionStatus.COMPLETED, {"output": "cached"})

        async def create_fn(spec: ArtifactSpec) -> str:
            return f"Content for {spec.id}"

        result = await executor.execute(create_fn)

        assert result.success
        assert "A" in result.skipped
        assert "B" in result.completed
        assert "C" in result.completed

    @pytest.mark.asyncio
    async def test_execute_with_failure(
        self, simple_graph: ArtifactGraph, cache: ExecutionCache
    ) -> None:
        """Failed artifacts are recorded."""
        executor = IncrementalExecutor(simple_graph, cache)

        async def create_fn(spec: ArtifactSpec) -> str:
            if spec.id == "B":
                raise ValueError("B failed!")
            return f"Content for {spec.id}"

        result = await executor.execute(create_fn)

        assert not result.success
        assert "A" in result.completed
        assert "B" in result.failed
        assert "B failed!" in result.failed["B"]


class TestExecutionPlan:
    """Tests for ExecutionPlan dataclass."""

    def test_to_dict(self) -> None:
        """ExecutionPlan converts to dict."""
        plan = ExecutionPlan(
            to_execute=["A", "B"],
            to_skip=["C"],
            decisions={
                "A": SkipDecision(
                    artifact_id="A",
                    can_skip=False,
                    reason=SkipReason.NO_CACHE,
                    current_hash="hash_a",
                ),
                "B": SkipDecision(
                    artifact_id="B",
                    can_skip=False,
                    reason=SkipReason.HASH_CHANGED,
                    current_hash="hash_b",
                    previous_hash="old_hash_b",
                ),
                "C": SkipDecision(
                    artifact_id="C",
                    can_skip=True,
                    reason=SkipReason.UNCHANGED_SUCCESS,
                    current_hash="hash_c",
                    previous_hash="hash_c",
                ),
            },
            computed_hashes={"A": "hash_a", "B": "hash_b", "C": "hash_c"},
        )

        result = plan.to_dict()

        assert result["total_artifacts"] == 3
        assert result["to_execute"] == 2
        assert result["to_skip"] == 1
        assert abs(result["skip_percentage"] - 33.33) < 0.1
