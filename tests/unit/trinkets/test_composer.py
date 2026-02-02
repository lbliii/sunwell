"""Unit tests for TrinketComposer."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
    TurnResult,
)
from sunwell.agent.trinkets.composer import ComposedPrompt, TrinketComposer


class MockTrinket(BaseTrinket):
    """Mock trinket for testing."""

    def __init__(
        self,
        name: str,
        content: str,
        placement: TrinketPlacement = TrinketPlacement.SYSTEM,
        priority: int = 50,
        cacheable: bool = False,
        should_fail: bool = False,
        return_none: bool = False,
    ):
        self._name = name
        self._content = content
        self._placement = placement
        self._priority = priority
        self._cacheable = cacheable
        self._should_fail = should_fail
        self._return_none = return_none
        self.turn_complete_called = False
        self.tool_executed_calls: list[tuple[str, bool]] = []

    def get_section_name(self) -> str:
        return self._name

    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        if self._should_fail:
            raise RuntimeError(f"Trinket {self._name} failed")
        if self._return_none:
            return None
        return TrinketSection(
            name=self._name,
            content=self._content,
            placement=self._placement,
            priority=self._priority,
            cacheable=self._cacheable,
        )

    def on_turn_complete(self, result: TurnResult) -> None:
        self.turn_complete_called = True

    def on_tool_executed(self, tool_name: str, success: bool) -> None:
        self.tool_executed_calls.append((tool_name, success))


class TestComposedPrompt:
    """Tests for ComposedPrompt dataclass."""

    def test_has_system_true(self) -> None:
        """Should return True when system has content."""
        prompt = ComposedPrompt(system="Hello", context="", notification="")
        assert prompt.has_system is True

    def test_has_system_false(self) -> None:
        """Should return False when system is empty."""
        prompt = ComposedPrompt(system="", context="World", notification="")
        assert prompt.has_system is False

    def test_has_system_whitespace_only(self) -> None:
        """Should return False when system is whitespace only."""
        prompt = ComposedPrompt(system="   \n  ", context="", notification="")
        assert prompt.has_system is False

    def test_has_context_true(self) -> None:
        """Should return True when context has content."""
        prompt = ComposedPrompt(system="", context="World", notification="")
        assert prompt.has_context is True

    def test_has_notification_true(self) -> None:
        """Should return True when notification has content."""
        prompt = ComposedPrompt(system="", context="", notification="Now")
        assert prompt.has_notification is True


class TestTrinketComposerRegistration:
    """Tests for trinket registration."""

    def test_register_trinket(self) -> None:
        """Should register a trinket."""
        composer = TrinketComposer()
        trinket = MockTrinket("test", "content")

        composer.register(trinket)

        assert len(composer.trinkets) == 1
        assert composer.registered_names == ["test"]

    def test_register_multiple(self) -> None:
        """Should register multiple trinkets."""
        composer = TrinketComposer()
        composer.register(MockTrinket("one", "1"))
        composer.register(MockTrinket("two", "2"))

        assert len(composer.trinkets) == 2
        assert composer.registered_names == ["one", "two"]

    def test_unregister_trinket(self) -> None:
        """Should unregister a trinket by name."""
        composer = TrinketComposer()
        composer.register(MockTrinket("one", "1"))
        composer.register(MockTrinket("two", "2"))

        result = composer.unregister("one")

        assert result is True
        assert len(composer.trinkets) == 1
        assert composer.registered_names == ["two"]

    def test_unregister_nonexistent(self) -> None:
        """Should return False for nonexistent trinket."""
        composer = TrinketComposer()

        result = composer.unregister("nonexistent")

        assert result is False


class TestTrinketComposerComposition:
    """Tests for trinket composition."""

    @pytest.fixture
    def context(self) -> TrinketContext:
        """Create test context."""
        return TrinketContext(task="Build API", workspace=Path("/project"))

    @pytest.mark.asyncio
    async def test_compose_empty(self, context: TrinketContext) -> None:
        """Should return empty prompt when no trinkets."""
        composer = TrinketComposer()

        result = await composer.compose(context)

        assert result.system == ""
        assert result.context == ""
        assert result.notification == ""

    @pytest.mark.asyncio
    async def test_compose_single_system(self, context: TrinketContext) -> None:
        """Should compose single system trinket."""
        composer = TrinketComposer()
        composer.register(MockTrinket("test", "Hello", TrinketPlacement.SYSTEM))

        result = await composer.compose(context)

        assert result.system == "Hello"
        assert result.context == ""
        assert result.notification == ""

    @pytest.mark.asyncio
    async def test_compose_multiple_placements(self, context: TrinketContext) -> None:
        """Should compose trinkets into correct placements."""
        composer = TrinketComposer()
        composer.register(MockTrinket("sys", "System", TrinketPlacement.SYSTEM))
        composer.register(MockTrinket("ctx", "Context", TrinketPlacement.CONTEXT))
        composer.register(MockTrinket("notif", "Notif", TrinketPlacement.NOTIFICATION))

        result = await composer.compose(context)

        assert result.system == "System"
        assert result.context == "Context"
        assert result.notification == "Notif"

    @pytest.mark.asyncio
    async def test_compose_priority_ordering(self, context: TrinketContext) -> None:
        """Should sort sections by priority within placement."""
        composer = TrinketComposer()
        composer.register(MockTrinket("high", "High", priority=100))
        composer.register(MockTrinket("low", "Low", priority=10))
        composer.register(MockTrinket("mid", "Mid", priority=50))

        result = await composer.compose(context)

        # Lower priority = earlier, so Low first, then Mid, then High
        assert result.system == "Low\n\nMid\n\nHigh"

    @pytest.mark.asyncio
    async def test_compose_skips_none(self, context: TrinketContext) -> None:
        """Should skip trinkets that return None."""
        composer = TrinketComposer()
        composer.register(MockTrinket("visible", "Visible"))
        composer.register(MockTrinket("hidden", "", return_none=True))

        result = await composer.compose(context)

        assert result.system == "Visible"

    @pytest.mark.asyncio
    async def test_compose_skips_empty_content(self, context: TrinketContext) -> None:
        """Should skip trinkets with empty content."""
        composer = TrinketComposer()
        composer.register(MockTrinket("visible", "Visible"))
        # Empty content trinket - needs custom implementation
        empty_trinket = MockTrinket("empty", "")
        # Override to return section with empty content
        async def generate_empty(ctx):
            return TrinketSection(
                name="empty", content="", placement=TrinketPlacement.SYSTEM
            )
        empty_trinket.generate = generate_empty  # type: ignore[method-assign]
        composer.register(empty_trinket)

        result = await composer.compose(context)

        assert result.system == "Visible"

    @pytest.mark.asyncio
    async def test_compose_graceful_degradation(self, context: TrinketContext) -> None:
        """Should continue if a trinket fails."""
        composer = TrinketComposer()
        composer.register(MockTrinket("before", "Before", priority=10))
        composer.register(MockTrinket("fail", "", should_fail=True, priority=20))
        composer.register(MockTrinket("after", "After", priority=30))

        result = await composer.compose(context)

        # Should have both non-failing trinkets
        assert "Before" in result.system
        assert "After" in result.system


class TestTrinketComposerCaching:
    """Tests for section caching."""

    @pytest.fixture
    def context(self) -> TrinketContext:
        """Create test context."""
        return TrinketContext(task="Build API", workspace=Path("/project"))

    @pytest.mark.asyncio
    async def test_cache_cacheable_section(self, context: TrinketContext) -> None:
        """Should cache cacheable sections."""
        composer = TrinketComposer()
        trinket = MockTrinket("cached", "Content", cacheable=True)
        composer.register(trinket)

        await composer.compose(context)

        assert "cached" in composer.cached_names

    @pytest.mark.asyncio
    async def test_no_cache_non_cacheable(self, context: TrinketContext) -> None:
        """Should not cache non-cacheable sections."""
        composer = TrinketComposer()
        trinket = MockTrinket("dynamic", "Content", cacheable=False)
        composer.register(trinket)

        await composer.compose(context)

        assert "dynamic" not in composer.cached_names

    @pytest.mark.asyncio
    async def test_use_cached_on_recompose(self, context: TrinketContext) -> None:
        """Should use cached section on subsequent compose."""
        composer = TrinketComposer()
        call_count = 0

        class CountingTrinket(BaseTrinket):
            def get_section_name(self) -> str:
                return "counting"

            async def generate(self, ctx: TrinketContext) -> TrinketSection:
                nonlocal call_count
                call_count += 1
                return TrinketSection(
                    name="counting",
                    content=f"Call {call_count}",
                    placement=TrinketPlacement.SYSTEM,
                    cacheable=True,
                )

        composer.register(CountingTrinket())

        result1 = await composer.compose(context)
        result2 = await composer.compose(context)

        # generate() should only be called once due to caching
        assert call_count == 1
        assert result1.system == "Call 1"
        assert result2.system == "Call 1"

    def test_clear_cache(self, context: TrinketContext) -> None:
        """Should clear cached sections."""
        composer = TrinketComposer()
        composer._cache["test"] = TrinketSection(
            name="test", content="cached", placement=TrinketPlacement.SYSTEM
        )

        composer.clear_cache()

        assert len(composer._cache) == 0


class TestTrinketComposerNotifications:
    """Tests for turn and tool notifications."""

    def test_notify_turn_complete(self) -> None:
        """Should notify all trinkets of turn completion."""
        composer = TrinketComposer()
        trinket1 = MockTrinket("one", "1")
        trinket2 = MockTrinket("two", "2")
        composer.register(trinket1)
        composer.register(trinket2)

        composer.notify_turn_complete(TurnResult(turn=1, success=True))

        assert trinket1.turn_complete_called is True
        assert trinket2.turn_complete_called is True

    def test_notify_tool_executed(self) -> None:
        """Should notify all trinkets of tool execution."""
        composer = TrinketComposer()
        trinket = MockTrinket("test", "content")
        composer.register(trinket)

        composer.notify_tool_executed("read_file", success=True)
        composer.notify_tool_executed("write_file", success=False)

        assert trinket.tool_executed_calls == [
            ("read_file", True),
            ("write_file", False),
        ]

    def test_notify_graceful_on_error(self) -> None:
        """Should continue notifying if one trinket fails."""
        composer = TrinketComposer()

        class FailingTrinket(BaseTrinket):
            def get_section_name(self) -> str:
                return "failing"

            async def generate(self, ctx: TrinketContext) -> TrinketSection | None:
                return None

            def on_turn_complete(self, result: TurnResult) -> None:
                raise RuntimeError("Notification failed")

        trinket_ok = MockTrinket("ok", "content")
        composer.register(FailingTrinket())
        composer.register(trinket_ok)

        # Should not raise
        composer.notify_turn_complete(TurnResult(turn=1, success=True))

        # Second trinket should still be notified
        assert trinket_ok.turn_complete_called is True
