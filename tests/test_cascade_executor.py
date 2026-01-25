"""Tests for CascadeExecutor functionality (RFC-069).

Tests cover:
- CascadeArtifactBuilder spec generation
- CascadeExecutor wave-by-wave execution
- Event emission during execution
- Contract verification
- WaveResult handling
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.quality.weakness.cascade import CascadeEngine, CascadeExecution, CascadePreview
from sunwell.quality.weakness.executor import (
    CascadeArtifactBuilder,
    CascadeExecutor,
    WaveResult,
)
from sunwell.quality.weakness.types import (
    ExtractedContract,
    WaveConfidence,
    WeaknessScore,
    WeaknessSignal,
    WeaknessType,
)

# =============================================================================
# Mock Classes
# =============================================================================


class MockModel:
    """Mock model for testing without actual LLM calls."""

    def __init__(self, response: str = ""):
        self.response = response
        self.calls: list[str] = []

    async def generate(self, prompt: str, options=None):
        """Mock generate that records calls and returns preset response."""
        self.calls.append(prompt)

        class MockResult:
            def __init__(self, content: str):
                self.content = content
                self.text = content

        return MockResult(self.response)


class MockToolExecutor:
    """Mock tool executor for testing."""

    def __init__(self, success: bool = True):
        self.success = success
        self.calls: list[dict] = []

    async def execute(self, tool_call):
        """Mock execute that records calls."""
        self.calls.append({"name": tool_call.name, "arguments": tool_call.arguments})

        class MockResult:
            def __init__(self, success: bool):
                self.success = success
                self.output = "OK" if success else "Failed"

        return MockResult(self.success)


class MockPlanner:
    """Mock planner for testing."""

    def __init__(self, content: str = "# Generated code\npass"):
        self.content = content
        self.calls: list[ArtifactSpec] = []

    async def create_artifact(self, artifact: ArtifactSpec, context: dict | None = None) -> str:
        """Mock create_artifact that records calls."""
        self.calls.append(artifact)
        return self.content


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_graph() -> ArtifactGraph:
    """Create a sample artifact graph for testing."""
    graph = ArtifactGraph()

    # Add a weak node and its dependents
    graph.add(
        ArtifactSpec(
            id="src/auth.py",
            description="Authentication module",
            contract="Auth functions",
            produces_file="src/auth.py",
            requires=frozenset(),
        )
    )
    graph.add(
        ArtifactSpec(
            id="src/user.py",
            description="User module",
            contract="User model",
            produces_file="src/user.py",
            requires=frozenset(["src/auth.py"]),
        )
    )
    graph.add(
        ArtifactSpec(
            id="src/api.py",
            description="API routes",
            contract="REST endpoints",
            produces_file="src/api.py",
            requires=frozenset(["src/user.py"]),
        )
    )

    return graph


@pytest.fixture
def sample_weakness() -> WeaknessScore:
    """Create a sample weakness score."""
    return WeaknessScore(
        artifact_id="src/auth.py",
        file_path=Path("src/auth.py"),
        signals=(
            WeaknessSignal(
                artifact_id="src/auth.py",
                file_path=Path("src/auth.py"),
                weakness_type=WeaknessType.LOW_COVERAGE,
                severity=0.7,
            ),
        ),
        fan_out=2,
        depth=0,
    )


@pytest.fixture
def sample_preview(sample_weakness: WeaknessScore) -> CascadePreview:
    """Create a sample cascade preview."""
    return CascadePreview(
        weak_node="src/auth.py",
        weakness_score=sample_weakness,
        direct_dependents=frozenset(["src/user.py"]),
        transitive_dependents=frozenset(["src/api.py"]),
        total_impacted=3,
        estimated_effort="small",
        files_touched=("src/auth.py", "src/user.py", "src/api.py"),
        waves=(("src/auth.py",), ("src/user.py",), ("src/api.py",)),
        risk_assessment="Low risk",
    )


@pytest.fixture
def sample_contracts() -> dict[str, ExtractedContract]:
    """Create sample extracted contracts."""
    return {
        "src/auth.py": ExtractedContract(
            artifact_id="src/auth.py",
            file_path=Path("src/auth.py"),
            functions=("def authenticate(username, password)",),
            classes=(),
            exports=(),
            type_signatures=(),
            interface_hash="abc123",
        ),
    }


@pytest.fixture
def mock_engine(sample_graph: ArtifactGraph) -> CascadeEngine:
    """Create a mock cascade engine."""
    engine = CascadeEngine(graph=sample_graph, project_root=Path("/tmp/test"))
    return engine


# =============================================================================
# Test: WaveResult
# =============================================================================


def test_wave_result_success() -> None:
    """WaveResult should track successful wave execution."""
    result = WaveResult(
        wave_num=0,
        completed={"artifact1": "content1"},
        success=True,
        error=None,
    )

    assert result.wave_num == 0
    assert result.success is True
    assert result.error is None
    assert "artifact1" in result.completed


def test_wave_result_failure() -> None:
    """WaveResult should track failed wave execution."""
    result = WaveResult(
        wave_num=1,
        completed={},
        success=False,
        error="Generation failed",
    )

    assert result.success is False
    assert result.error == "Generation failed"


# =============================================================================
# Test: CascadeArtifactBuilder
# =============================================================================


def test_cascade_artifact_builder_creation(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
    sample_contracts: dict[str, ExtractedContract],
) -> None:
    """CascadeArtifactBuilder should be creatable."""
    builder = CascadeArtifactBuilder(
        engine=mock_engine,
        preview=sample_preview,
        contracts=sample_contracts,
    )

    assert builder.engine is mock_engine
    assert builder.preview is sample_preview


def test_cascade_artifact_builder_build_wave_graph(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
    sample_contracts: dict[str, ExtractedContract],
) -> None:
    """build_wave_graph should create artifact graph for a wave."""
    builder = CascadeArtifactBuilder(
        engine=mock_engine,
        preview=sample_preview,
        contracts=sample_contracts,
    )

    # Build graph for wave 0
    wave_graph = builder.build_wave_graph(0)

    assert len(wave_graph) == 1
    # Should have cascade-prefixed ID
    assert "cascade-src/auth.py" in wave_graph


def test_cascade_artifact_builder_regenerate_description(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
    sample_contracts: dict[str, ExtractedContract],
) -> None:
    """Wave 0 artifacts should have regenerate description."""
    builder = CascadeArtifactBuilder(
        engine=mock_engine,
        preview=sample_preview,
        contracts=sample_contracts,
    )

    wave_graph = builder.build_wave_graph(0)
    artifact = wave_graph["cascade-src/auth.py"]

    assert "Regenerate" in artifact.description
    assert "low_coverage" in artifact.description


def test_cascade_artifact_builder_update_description(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
    sample_contracts: dict[str, ExtractedContract],
) -> None:
    """Wave 1+ artifacts should have update description."""
    builder = CascadeArtifactBuilder(
        engine=mock_engine,
        preview=sample_preview,
        contracts=sample_contracts,
    )

    wave_graph = builder.build_wave_graph(1)
    artifact = wave_graph["cascade-src/user.py"]

    assert "Update" in artifact.description
    assert "compatible" in artifact.description


def test_cascade_artifact_builder_includes_contract(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
    sample_contracts: dict[str, ExtractedContract],
) -> None:
    """Artifacts should include contract constraints."""
    builder = CascadeArtifactBuilder(
        engine=mock_engine,
        preview=sample_preview,
        contracts=sample_contracts,
    )

    wave_graph = builder.build_wave_graph(0)
    artifact = wave_graph["cascade-src/auth.py"]

    # Contract should be included
    assert "Interface Contract" in artifact.contract
    assert "authenticate" in artifact.contract


# =============================================================================
# Test: CascadeExecutor
# =============================================================================


def test_cascade_executor_creation(
    mock_engine: CascadeEngine,
) -> None:
    """CascadeExecutor should be creatable."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    assert executor.engine is mock_engine
    assert executor.planner is planner


@pytest.mark.asyncio
async def test_cascade_executor_execute_basic(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should run through all waves."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    # Mock verification methods to pass
    with (
        patch.object(executor, "_run_tests", return_value=True),
        patch.object(executor, "_run_type_check", return_value=True),
        patch.object(executor, "_run_lint", return_value=True),
    ):
        execution = await executor.execute(
            preview=sample_preview,
            auto_approve=True,
        )

    # Should have attempted all waves
    assert len(planner.calls) == 3  # 3 artifacts across 3 waves
    assert execution.completed or execution.current_wave >= 0


@pytest.mark.asyncio
async def test_cascade_executor_emits_events(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should emit events when callback provided."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    events: list[dict] = []

    def capture_event(event):
        events.append(event.to_dict())

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
        on_event=capture_event,
    )

    with (
        patch.object(executor, "_run_tests", return_value=True),
        patch.object(executor, "_run_type_check", return_value=True),
        patch.object(executor, "_run_lint", return_value=True),
    ):
        await executor.execute(
            preview=sample_preview,
            auto_approve=True,
        )

    # Should have emitted events
    assert len(events) > 0

    # Should have task_start event
    event_types = [e["type"] for e in events]
    assert "task_start" in event_types


@pytest.mark.asyncio
async def test_cascade_executor_on_wave_complete_callback(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should call on_wave_complete after each wave."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    wave_completions: list[WaveConfidence] = []

    async def on_wave_complete(confidence: WaveConfidence) -> bool:
        wave_completions.append(confidence)
        return True  # Continue

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    with (
        patch.object(executor, "_run_tests", return_value=True),
        patch.object(executor, "_run_type_check", return_value=True),
        patch.object(executor, "_run_lint", return_value=True),
    ):
        await executor.execute(
            preview=sample_preview,
            auto_approve=True,
            on_wave_complete=on_wave_complete,
        )

    # Should have called callback for each wave
    assert len(wave_completions) == 3


@pytest.mark.asyncio
async def test_cascade_executor_abort_on_callback_false(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should abort if on_wave_complete returns False."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    async def on_wave_complete(confidence: WaveConfidence) -> bool:
        return False  # Abort after first wave

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    with (
        patch.object(executor, "_run_tests", return_value=True),
        patch.object(executor, "_run_type_check", return_value=True),
        patch.object(executor, "_run_lint", return_value=True),
    ):
        execution = await executor.execute(
            preview=sample_preview,
            auto_approve=True,
            on_wave_complete=on_wave_complete,
        )

    assert execution.aborted is True
    assert execution.abort_reason == "User cancelled"


@pytest.mark.asyncio
async def test_cascade_executor_handles_planner_error(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should handle planner errors gracefully."""

    class FailingPlanner:
        async def create_artifact(self, artifact, context=None):
            raise RuntimeError("Planner failed")

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=FailingPlanner(),
        tool_executor=MockToolExecutor(),
        project_root=Path("/tmp/test"),
    )

    execution = await executor.execute(
        preview=sample_preview,
        auto_approve=True,
    )

    # Should have aborted due to error
    assert execution.aborted is True
    assert "failed" in execution.abort_reason.lower()


@pytest.mark.asyncio
async def test_cascade_executor_handles_tool_error(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should handle tool executor errors."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor(success=False)

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    execution = await executor.execute(
        preview=sample_preview,
        auto_approve=True,
    )

    # Should have aborted due to tool failure
    assert execution.aborted is True


@pytest.mark.asyncio
async def test_cascade_executor_confidence_threshold(
    mock_engine: CascadeEngine,
    sample_preview: CascadePreview,
) -> None:
    """execute() should pause when confidence drops below threshold."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    # Mock tests failing to lower confidence
    with (
        patch.object(executor, "_run_tests", return_value=False),
        patch.object(executor, "_run_type_check", return_value=True),
        patch.object(executor, "_run_lint", return_value=True),
    ):
        execution = await executor.execute(
            preview=sample_preview,
            auto_approve=False,  # Don't auto-approve
            confidence_threshold=0.7,
        )

    # Should be paused for approval (tests failed = low confidence)
    assert execution.paused_for_approval is True


# =============================================================================
# Test: Verification Methods
# =============================================================================


@pytest.mark.asyncio
async def test_verify_contracts_compatible(
    mock_engine: CascadeEngine,
    sample_contracts: dict[str, ExtractedContract],
) -> None:
    """_verify_contracts should return True for compatible contracts."""
    planner = MockPlanner()
    tool_executor = MockToolExecutor()

    executor = CascadeExecutor(
        engine=mock_engine,
        planner=planner,
        tool_executor=tool_executor,
        project_root=Path("/tmp/test"),
    )

    # Mock extract_contract to return same contract (compatible)
    with patch.object(
        mock_engine,
        "extract_contract",
        return_value=sample_contracts["src/auth.py"],
    ):
        result = await executor._verify_contracts(
            original_contracts=sample_contracts,
            wave_artifacts=("src/auth.py",),
        )

    assert result is True


# =============================================================================
# Test: Integration with CascadeExecution
# =============================================================================


def test_cascade_execution_records_wave_completion() -> None:
    """CascadeExecution should properly record wave completions."""
    weakness = WeaknessScore(
        artifact_id="test",
        file_path=Path("test.py"),
        signals=(),
        fan_out=0,
        depth=0,
    )

    preview = CascadePreview(
        weak_node="test",
        weakness_score=weakness,
        direct_dependents=frozenset(),
        transitive_dependents=frozenset(),
        total_impacted=1,
        estimated_effort="small",
        files_touched=("test.py",),
        waves=(("test",),),
        risk_assessment="Low",
    )

    execution = CascadeExecution(
        preview=preview,
        auto_approve=True,
        confidence_threshold=0.7,
    )

    # Record wave completion
    confidence = WaveConfidence.compute(
        wave_num=0,
        artifacts=("test",),
        test_result=True,
        type_result=True,
        lint_result=True,
        contract_result=True,
    )

    execution.record_wave_completion(confidence)

    assert len(execution.wave_confidences) == 1
    assert execution.overall_confidence == 1.0
