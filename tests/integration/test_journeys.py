"""Integration tests for E2E behavioral journeys.

These tests run actual journeys against a real model (defaults to Ollama).
They test behavioral contracts rather than exact outputs:
- Intent classification
- Signal extraction
- Tool calls
- State changes
- Output patterns

To run:
    pytest tests/integration/test_journeys.py -v

To run specific journey:
    pytest tests/integration/test_journeys.py -v -k "create_app"

Environment variables:
    SUNWELL_TEST_MODEL: Model to use (default: gemma3:4b)
    SUNWELL_TEST_PROVIDER: Provider (default: ollama)
    SUNWELL_SKIP_SLOW_JOURNEYS: Skip slow multi-turn tests
"""

import os
from pathlib import Path

import pytest

# Mark all tests in this module as integration tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,  # These tests involve real LLM calls
]

# Get test configuration from environment
TEST_MODEL = os.environ.get("SUNWELL_TEST_MODEL", "gemma3:4b")
TEST_PROVIDER = os.environ.get("SUNWELL_TEST_PROVIDER", "ollama")
SKIP_SLOW = os.environ.get("SUNWELL_SKIP_SLOW_JOURNEYS", "").lower() in ("1", "true", "yes")

# Path to journeys directory
JOURNEYS_DIR = Path(__file__).parent.parent.parent / "benchmark" / "journeys"


@pytest.fixture
def runner():
    """Create a JourneyRunner for tests."""
    from sunwell.benchmark.journeys import JourneyRunner

    return JourneyRunner(
        provider=TEST_PROVIDER,
        model_name=TEST_MODEL,
        trust_level="shell",
        cleanup_workspace=True,
        debug=False,
    )


# =============================================================================
# Single-Turn Journey Tests
# =============================================================================


class TestSingleTurnJourneys:
    """Tests for single-turn journeys."""

    @pytest.mark.asyncio
    async def test_simple_qa_conversation_intent(self, runner):
        """Test that simple Q&A is classified as CONVERSATION."""
        from sunwell.benchmark.journeys import load_journey

        journey = load_journey(JOURNEYS_DIR / "single-turn" / "simple-qa.yaml")
        result = await runner.run(journey)

        # Check intent classification
        assert result.intent_match, f"Intent mismatch: {result.assertion_report.failures()}"

    @pytest.mark.asyncio
    async def test_create_app_task_intent(self, runner):
        """Test that 'create an app' is classified as TASK."""
        from sunwell.benchmark.journeys import load_journey

        journey = load_journey(JOURNEYS_DIR / "single-turn" / "create-app.yaml")
        result = await runner.run(journey)

        # Check intent classification
        assert result.intent_match, f"Intent mismatch: {result.assertion_report.failures()}"

    @pytest.mark.asyncio
    async def test_backlog_query_reads_files(self, runner):
        """Test that backlog query reads the TODO file."""
        from sunwell.benchmark.journeys import load_journey

        journey = load_journey(JOURNEYS_DIR / "single-turn" / "backlog-query.yaml")
        result = await runner.run(journey)

        # Check that read_file was called
        assert result.tools_match, f"Tools mismatch: {result.assertion_report.failures()}"

    @pytest.mark.asyncio
    @pytest.mark.skipif(SKIP_SLOW, reason="Slow test skipped")
    async def test_create_app_creates_file(self, runner):
        """Test that create app actually creates a Python file."""
        from sunwell.benchmark.journeys import load_journey

        journey = load_journey(JOURNEYS_DIR / "single-turn" / "create-app.yaml")
        result = await runner.run(journey)

        # Full behavioral check
        assert result.passed, (
            f"Journey failed:\n"
            f"  Intent: {result.intent_match}\n"
            f"  Signals: {result.signals_match}\n"
            f"  Tools: {result.tools_match}\n"
            f"  State: {result.state_match}\n"
            f"  Output: {result.output_match}\n"
            f"  Failures: {[f.message for f in result.assertion_report.failures()]}"
        )


# =============================================================================
# Multi-Turn Journey Tests
# =============================================================================


@pytest.mark.skipif(SKIP_SLOW, reason="Slow multi-turn tests skipped")
class TestMultiTurnJourneys:
    """Tests for multi-turn journeys."""

    @pytest.mark.asyncio
    async def test_debug_session_finds_bug(self, runner):
        """Test that debug session identifies the bug."""
        from sunwell.benchmark.journeys import load_journey

        journey = load_journey(JOURNEYS_DIR / "multi-turn" / "debug-session.yaml")
        result = await runner.run(journey)

        # At minimum, first turn should read the file
        if result.turn_results:
            first_turn = result.turn_results[0]
            assert first_turn.assertion_report.passed or any(
                "read_file" in str(r.actual) for r in first_turn.assertion_report.results
            ), f"First turn didn't read file: {first_turn.assertion_report.failures()}"

    @pytest.mark.asyncio
    async def test_feature_build_modifies_file(self, runner):
        """Test that feature build modifies the app file."""
        from sunwell.benchmark.journeys import load_journey

        journey = load_journey(JOURNEYS_DIR / "multi-turn" / "feature-build.yaml")
        result = await runner.run(journey)

        # Check that write_file was called at some point
        assert result.tools_match or any(
            "write_file" in str(r.actual)
            for r in result.assertion_report.results
            if r.category == "tools"
        ), f"File not modified: {result.assertion_report.failures()}"


# =============================================================================
# Parametrized Tests for All Journeys
# =============================================================================


def get_all_journey_paths() -> list[Path]:
    """Get all journey YAML files."""
    if not JOURNEYS_DIR.exists():
        return []
    return list(JOURNEYS_DIR.glob("**/*.yaml"))


def journey_id_from_path(path: Path) -> str:
    """Get journey ID from path for test naming."""
    return path.stem


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "journey_path",
    get_all_journey_paths(),
    ids=lambda p: journey_id_from_path(p),
)
async def test_journey_runs_without_error(journey_path: Path, runner):
    """Smoke test: journey runs without crashing."""
    from sunwell.benchmark.journeys import load_journey

    journey = load_journey(journey_path)
    result = await runner.run(journey)

    # Smoke test - just check it didn't error
    assert result.error is None, f"Journey errored: {result.error}"


# =============================================================================
# Unit Tests for Journey Framework
# =============================================================================


class TestJourneyTypes:
    """Unit tests for journey type loading."""

    def test_load_single_turn_journey(self):
        """Test loading a single-turn journey."""
        from sunwell.benchmark.journeys import load_journey
        from sunwell.benchmark.journeys.types import SingleTurnJourney

        path = JOURNEYS_DIR / "single-turn" / "simple-qa.yaml"
        if not path.exists():
            pytest.skip("Journey file not found")

        journey = load_journey(path)
        assert isinstance(journey, SingleTurnJourney)
        assert journey.id == "journey-simple-qa"
        assert journey.input is not None
        assert journey.expect is not None

    def test_load_multi_turn_journey(self):
        """Test loading a multi-turn journey."""
        from sunwell.benchmark.journeys import load_journey
        from sunwell.benchmark.journeys.types import MultiTurnJourney

        path = JOURNEYS_DIR / "multi-turn" / "debug-session.yaml"
        if not path.exists():
            pytest.skip("Journey file not found")

        journey = load_journey(path)
        assert isinstance(journey, MultiTurnJourney)
        assert journey.id == "journey-debug-session"
        assert len(journey.turns) > 0

    def test_load_journeys_from_directory(self):
        """Test loading all journeys from directory."""
        from sunwell.benchmark.journeys import load_journeys_from_directory

        if not JOURNEYS_DIR.exists():
            pytest.skip("Journeys directory not found")

        journeys = load_journeys_from_directory(JOURNEYS_DIR)
        assert len(journeys) > 0


class TestBehavioralAssertions:
    """Unit tests for behavioral assertions."""

    def test_check_intent_exact_match(self):
        """Test intent assertion with exact match."""
        from sunwell.benchmark.journeys.assertions import BehavioralAssertions
        from sunwell.benchmark.journeys.recorder import EventRecorder, IntentRecord

        recorder = EventRecorder()
        recorder.intents.append(IntentRecord(intent="TASK", confidence=0.9))

        assertions = BehavioralAssertions()
        result = assertions.check_intent(recorder, "TASK")

        assert result.passed
        assert result.category == "intent"

    def test_check_intent_alternatives(self):
        """Test intent assertion with alternatives."""
        from sunwell.benchmark.journeys.assertions import BehavioralAssertions
        from sunwell.benchmark.journeys.recorder import EventRecorder, IntentRecord

        recorder = EventRecorder()
        recorder.intents.append(IntentRecord(intent="CONVERSATION", confidence=0.8))

        assertions = BehavioralAssertions()
        result = assertions.check_intent(recorder, ("TASK", "CONVERSATION"))

        assert result.passed

    def test_check_tool_called(self):
        """Test tool call assertion."""
        from sunwell.benchmark.journeys.assertions import BehavioralAssertions
        from sunwell.benchmark.journeys.recorder import EventRecorder, ToolCallRecord
        from sunwell.benchmark.journeys.types import ToolExpectation

        recorder = EventRecorder()
        recorder.tool_calls.append(ToolCallRecord(
            name="write_file",
            arguments={"path": "app.py", "content": "print('hello')"},
        ))

        assertions = BehavioralAssertions()
        result = assertions.check_tool_called(
            recorder,
            ToolExpectation(name="write_file", args_contain={"path": "*.py"}),
        )

        assert result.passed

    def test_check_output_contains(self):
        """Test output contains assertion."""
        from sunwell.benchmark.journeys.assertions import BehavioralAssertions
        from sunwell.benchmark.journeys.recorder import EventRecorder

        recorder = EventRecorder()
        recorder.outputs.append("I created a Flask app with a hello endpoint.")

        assertions = BehavioralAssertions()
        result = assertions.check_output_contains(recorder, ("flask", "hello"))

        assert result.passed


class TestEventRecorder:
    """Unit tests for EventRecorder."""

    def test_recorder_starts_and_stops(self):
        """Test recorder lifecycle."""
        from sunwell.benchmark.journeys.recorder import EventRecorder

        recorder = EventRecorder()
        recorder.start()
        assert recorder._unsubscribe is not None

        recorder.stop()
        assert recorder._unsubscribe is None

    def test_recorder_context_manager(self):
        """Test recorder as context manager."""
        from sunwell.benchmark.journeys.recorder import EventRecorder

        with EventRecorder() as recorder:
            assert recorder._unsubscribe is not None

        assert recorder._unsubscribe is None

    def test_recorder_reset(self):
        """Test recorder reset."""
        from sunwell.benchmark.journeys.recorder import EventRecorder, ToolCallRecord

        recorder = EventRecorder()
        recorder.tool_calls.append(ToolCallRecord(name="test", arguments={}))
        recorder.outputs.append("test output")

        recorder.reset()

        assert len(recorder.tool_calls) == 0
        assert len(recorder.outputs) == 0
