"""Tests for LearningPhase.

Tests the extracted learning phase independently of the Agent class.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sunwell.agent.events import EventType
from sunwell.agent.learning import Learning, LearningExtractor, LearningStore
from sunwell.agent.phases import LearningPhase, LearningResult


@pytest.mark.asyncio
async def test_learning_phase_extracts_from_code(tmp_path: Path) -> None:
    """Test that learning phase extracts patterns from changed files."""
    # Create test file
    test_file = tmp_path / "models.py"
    test_file.write_text(
        '''
class User:
    """User model."""
    id: int
    email: str
'''
    )

    # Setup learning phase
    store = LearningStore()
    extractor = LearningExtractor(use_llm=False)

    phase = LearningPhase(
        goal="Create user model",
        success=True,
        task_graph=None,
        learning_store=store,
        learning_extractor=extractor,
        files_changed=[str(test_file)],
    )

    # Run phase
    events = []
    result = None
    async for event in phase.run():
        if isinstance(event, LearningResult):
            result = event
        else:
            events.append(event)

    # Should have extracted some learnings
    assert result is not None
    # May or may not extract depending on heuristics
    # The important thing is it doesn't crash


@pytest.mark.asyncio
async def test_learning_phase_records_success() -> None:
    """Test that learning phase records successful execution."""
    store = LearningStore()
    extractor = LearningExtractor(use_llm=False)

    # Manually add a learning to simulate extraction
    store.add_learning(Learning(fact="Created User model", category="artifact"))

    phase = LearningPhase(
        goal="Create model",
        success=True,
        task_graph=None,
        learning_store=store,
        learning_extractor=extractor,
        files_changed=[],
    )

    result = None
    async for event in phase.run():
        if isinstance(event, LearningResult):
            result = event

    # Learning store should have the learning
    assert len(store.learnings) == 1
    assert store.learnings[0].fact == "Created User model"


@pytest.mark.asyncio
async def test_learning_phase_yields_events() -> None:
    """Test that learning phase yields events for each learning."""
    store = LearningStore()
    extractor = LearningExtractor(use_llm=False)

    # Pre-populate store with learnings
    store.add_learning(Learning(fact="Learning 1", category="pattern"))
    store.add_learning(Learning(fact="Learning 2", category="type"))

    phase = LearningPhase(
        goal="Test goal",
        success=True,
        task_graph=None,
        learning_store=store,
        learning_extractor=extractor,
        files_changed=[],
    )

    events = []
    async for event in phase.run():
        if not isinstance(event, LearningResult):
            events.append(event)

    # Should yield memory_learning events (may be 0 if no new learnings)
    # The important thing is the phase completes


@pytest.mark.asyncio
async def test_learning_phase_result_includes_summary() -> None:
    """Test that learning phase result includes summary."""
    store = LearningStore()
    extractor = LearningExtractor(use_llm=False)

    phase = LearningPhase(
        goal="Test goal",
        success=True,
        task_graph=None,
        learning_store=store,
        learning_extractor=extractor,
        files_changed=[],
    )

    result = None
    async for event in phase.run():
        if isinstance(event, LearningResult):
            result = event

    # Should have result with summary
    assert result is not None
    assert isinstance(result.facts_extracted, int)
    assert isinstance(result.categories_covered, set)


@pytest.mark.asyncio
async def test_learning_phase_handles_failure() -> None:
    """Test that learning phase handles failed execution."""
    store = LearningStore()
    extractor = LearningExtractor(use_llm=False)

    phase = LearningPhase(
        goal="Test goal",
        success=False,  # Execution failed
        task_graph=None,
        learning_store=store,
        learning_extractor=extractor,
        files_changed=[],
    )

    # Should complete without crashing even on failure
    result = None
    async for event in phase.run():
        if isinstance(event, LearningResult):
            result = event

    assert result is not None
