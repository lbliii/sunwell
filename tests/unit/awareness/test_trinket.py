"""Tests for AwarenessTrinket."""

from pathlib import Path

import pytest

from sunwell.agent.trinkets import AwarenessTrinket, TrinketContext, TrinketPlacement
from sunwell.awareness.patterns import AwarenessPattern, PatternType
from sunwell.awareness.store import AwarenessStore


@pytest.fixture
def awareness_dir(tmp_path: Path) -> Path:
    """Create awareness directory with test patterns."""
    awareness_dir = tmp_path / ".sunwell" / "awareness"
    awareness_dir.mkdir(parents=True)

    store = AwarenessStore(awareness_dir)

    # Add a significant pattern
    store.add_pattern(AwarenessPattern(
        pattern_type=PatternType.CONFIDENCE,
        observation="I overstate confidence on refactoring tasks",
        metric=0.20,
        sample_size=10,
        context="refactoring",
    ))

    # Add an insignificant pattern (will be filtered out)
    store.add_pattern(AwarenessPattern(
        pattern_type=PatternType.CONFIDENCE,
        observation="minor pattern",
        metric=0.05,  # Below threshold
        sample_size=10,
        context="minor",
    ))

    store.save()
    return tmp_path


class TestAwarenessTrinket:
    """Tests for the AwarenessTrinket class."""

    @pytest.mark.asyncio
    async def test_generates_section_with_patterns(self, awareness_dir: Path) -> None:
        """Should generate section when significant patterns exist."""
        trinket = AwarenessTrinket(workspace=awareness_dir)
        context = TrinketContext(task="refactor auth module", workspace=awareness_dir)

        section = await trinket.generate(context)

        assert section is not None
        assert section.name == "awareness"
        assert section.placement == TrinketPlacement.SYSTEM
        assert section.priority == 35
        assert section.cacheable is True

        # Should include significant pattern
        assert "overstate confidence" in section.content
        # Should include header
        assert "Self-Observations" in section.content

    @pytest.mark.asyncio
    async def test_returns_none_when_no_patterns(self, tmp_path: Path) -> None:
        """Should return None when no awareness patterns exist."""
        empty_workspace = tmp_path / "empty"
        empty_workspace.mkdir()

        trinket = AwarenessTrinket(workspace=empty_workspace)
        context = TrinketContext(task="test", workspace=empty_workspace)

        section = await trinket.generate(context)

        assert section is None

    @pytest.mark.asyncio
    async def test_filters_insignificant_patterns(self, awareness_dir: Path) -> None:
        """Should filter out insignificant patterns."""
        trinket = AwarenessTrinket(workspace=awareness_dir)
        context = TrinketContext(task="test", workspace=awareness_dir)

        section = await trinket.generate(context)

        assert section is not None
        # Should not include insignificant pattern
        assert "minor pattern" not in section.content

    @pytest.mark.asyncio
    async def test_caches_patterns_on_first_call(self, awareness_dir: Path) -> None:
        """Patterns should be cached after first generate call."""
        trinket = AwarenessTrinket(workspace=awareness_dir)
        context = TrinketContext(task="test", workspace=awareness_dir)

        # First call loads patterns
        assert trinket._patterns is None
        await trinket.generate(context)
        assert trinket._patterns is not None

        # Patterns are now cached
        cached_patterns = trinket._patterns.copy()
        await trinket.generate(context)
        assert trinket._patterns == cached_patterns

    def test_refresh_clears_cache(self, awareness_dir: Path) -> None:
        """refresh_patterns should clear the pattern cache."""
        trinket = AwarenessTrinket(workspace=awareness_dir)
        trinket._patterns = []  # Simulate cached state

        trinket.refresh_patterns()

        assert trinket._patterns is None

    def test_section_name_is_awareness(self, awareness_dir: Path) -> None:
        """Section name should be 'awareness'."""
        trinket = AwarenessTrinket(workspace=awareness_dir)
        assert trinket.get_section_name() == "awareness"
