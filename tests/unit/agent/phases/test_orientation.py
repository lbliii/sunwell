"""Tests for OrientationPhase.

Tests the extracted orientation phase independently of the Agent class.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.agent.events import EventType
from sunwell.agent.phases import OrientationPhase, OrientationResult


@pytest.fixture
def mock_memory() -> MagicMock:
    """Create a mock PersistentMemory."""
    from sunwell.agent.learning import Learning
    from sunwell.memory.core.types import MemoryContext

    memory = MagicMock()
    memory.get_relevant = AsyncMock(
        return_value=MemoryContext(
            learnings=(Learning(fact="Test fact", category="pattern"),),
            constraints=(),
            dead_ends=(),
        )
    )
    return memory


@pytest.mark.asyncio
async def test_orientation_phase_loads_memory_context(
    mock_memory: MagicMock,
) -> None:
    """Test that orientation phase loads memory context."""
    phase = OrientationPhase(
        goal="Build REST API",
        memory=mock_memory,
    )

    results = []
    async for event in phase.run():
        results.append(event)

    # Should have orient event and final result
    assert len(results) >= 2

    # First event should be orient event
    orient = results[0]
    assert hasattr(orient, "type")
    assert orient.type == EventType.ORIENT

    # Last event should be OrientationResult
    result = results[-1]
    assert isinstance(result, OrientationResult)
    assert result.memory_ctx is not None
    assert len(result.memory_ctx.learnings) == 1


@pytest.mark.asyncio
async def test_orientation_phase_uses_provided_lens() -> None:
    """Test that orientation phase uses provided lens."""
    from sunwell.foundation.core.lens import Lens, LensMetadata
    from sunwell.memory.core.types import MemoryContext

    mock_memory = MagicMock()
    mock_memory.get_relevant = AsyncMock(
        return_value=MemoryContext(learnings=(), constraints=(), dead_ends=())
    )

    provided_lens = Lens(metadata=LensMetadata(name="test", version="1.0.0"))

    phase = OrientationPhase(
        goal="Build API",
        memory=mock_memory,
        provided_lens=provided_lens,
    )

    result = None
    async for event in phase.run():
        if isinstance(event, OrientationResult):
            result = event

    assert result is not None
    assert result.lens == provided_lens


@pytest.mark.asyncio
async def test_orientation_phase_includes_briefing() -> None:
    """Test that orientation phase includes briefing if provided."""
    from sunwell.memory.briefing import Briefing, BriefingStatus
    from sunwell.memory.core.types import MemoryContext

    mock_memory = MagicMock()
    mock_memory.get_relevant = AsyncMock(
        return_value=MemoryContext(learnings=(), constraints=(), dead_ends=())
    )

    briefing = Briefing(
        mission="Test mission",
        status=BriefingStatus.NOT_STARTED,
        progress="Just started",
        last_action="Initialized project",
        hazards=(),
    )

    phase = OrientationPhase(
        goal="Build API",
        memory=mock_memory,
        briefing=briefing,
    )

    events = []
    async for event in phase.run():
        events.append(event)

    # Should have briefing_loaded event
    briefing_events = [e for e in events if hasattr(e, "type") and e.type == EventType.BRIEFING_LOADED]
    assert len(briefing_events) == 1

    # Result should include briefing
    result = events[-1]
    assert isinstance(result, OrientationResult)
    assert result.briefing == briefing


@pytest.mark.asyncio
async def test_orientation_phase_without_auto_lens() -> None:
    """Test that orientation phase doesn't auto-select lens when disabled."""
    from sunwell.memory.core.types import MemoryContext

    mock_memory = MagicMock()
    mock_memory.get_relevant = AsyncMock(
        return_value=MemoryContext(learnings=(), constraints=(), dead_ends=())
    )

    phase = OrientationPhase(
        goal="Build API",
        memory=mock_memory,
        auto_lens=False,
    )

    result = None
    async for event in phase.run():
        if isinstance(event, OrientationResult):
            result = event

    assert result is not None
    assert result.lens is None
