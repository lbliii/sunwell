"""Unit tests for trinket implementations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sunwell.agent.trinkets.base import (
    TrinketContext,
    TrinketPlacement,
    TurnResult,
)
from sunwell.agent.trinkets.implementations.time import TimeTrinket
from sunwell.agent.trinkets.implementations.briefing import BriefingTrinket
from sunwell.agent.trinkets.implementations.learning import LearningTrinket
from sunwell.agent.trinkets.implementations.tool_guidance import ToolGuidanceTrinket
from sunwell.agent.trinkets.implementations.memory import MemoryTrinket


@pytest.fixture
def context() -> TrinketContext:
    """Create test context."""
    return TrinketContext(task="Build API", workspace=Path("/project"))


class TestTimeTrinket:
    """Tests for TimeTrinket."""

    def test_section_name(self) -> None:
        """Should return 'time' as section name."""
        trinket = TimeTrinket()
        assert trinket.get_section_name() == "time"

    @pytest.mark.asyncio
    async def test_generate_returns_section(self, context: TrinketContext) -> None:
        """Should generate time section."""
        trinket = TimeTrinket()

        result = await trinket.generate(context)

        assert result is not None
        assert result.name == "time"
        assert result.placement == TrinketPlacement.NOTIFICATION
        assert result.priority == 0  # First
        assert result.cacheable is False
        assert "Current time:" in result.content

    @pytest.mark.asyncio
    async def test_uses_absolute_timestamp(self, context: TrinketContext) -> None:
        """Should use absolute timestamp format."""
        trinket = TimeTrinket()

        result = await trinket.generate(context)

        # Should contain date like "On Feb 2" not relative like "today"
        assert result is not None
        assert "On " in result.content


class TestBriefingTrinket:
    """Tests for BriefingTrinket."""

    def test_section_name(self) -> None:
        """Should return 'briefing' as section name."""
        trinket = BriefingTrinket(briefing=None)
        assert trinket.get_section_name() == "briefing"

    @pytest.mark.asyncio
    async def test_generate_none_when_no_briefing(
        self, context: TrinketContext
    ) -> None:
        """Should return None when no briefing."""
        trinket = BriefingTrinket(briefing=None)

        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_with_briefing(self, context: TrinketContext) -> None:
        """Should generate briefing section."""
        mock_briefing = MagicMock()
        mock_briefing.to_prompt.return_value = "## Briefing\nMission: Build API"

        trinket = BriefingTrinket(briefing=mock_briefing)

        result = await trinket.generate(context)

        assert result is not None
        assert result.name == "briefing"
        assert result.placement == TrinketPlacement.SYSTEM
        assert result.priority == 10  # Early
        assert result.cacheable is True
        assert "Briefing" in result.content

    def test_update_briefing(self) -> None:
        """Should allow updating briefing."""
        trinket = BriefingTrinket(briefing=None)

        new_briefing = MagicMock()
        trinket.update_briefing(new_briefing)

        assert trinket.briefing is new_briefing


class TestLearningTrinket:
    """Tests for LearningTrinket."""

    def test_section_name(self) -> None:
        """Should return 'learnings' as section name."""
        trinket = LearningTrinket(learning_store=None)
        assert trinket.get_section_name() == "learnings"

    @pytest.mark.asyncio
    async def test_generate_none_when_no_store(self, context: TrinketContext) -> None:
        """Should return None when no learning store."""
        trinket = LearningTrinket(learning_store=None)

        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_none_when_no_learnings(
        self, context: TrinketContext
    ) -> None:
        """Should return None when no relevant learnings."""
        mock_store = MagicMock()
        mock_store.get_relevant.return_value = []
        mock_store.format_tool_suggestions.return_value = None

        trinket = LearningTrinket(learning_store=mock_store)

        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_with_learnings(self, context: TrinketContext) -> None:
        """Should generate learnings section."""
        mock_learning = MagicMock()
        mock_learning.fact = "Use pytest for testing"
        mock_learning._first_person_prefix.return_value = "I know:"

        mock_store = MagicMock()
        mock_store.get_relevant.return_value = [mock_learning]
        mock_store.format_tool_suggestions.return_value = None

        trinket = LearningTrinket(learning_store=mock_store)

        result = await trinket.generate(context)

        assert result is not None
        assert result.name == "learnings"
        assert result.placement == TrinketPlacement.SYSTEM
        assert result.priority == 30
        assert result.cacheable is False
        assert "I know:" in result.content or "What I've Learned" in result.content

    @pytest.mark.asyncio
    async def test_generate_with_tool_suggestions(
        self, context: TrinketContext
    ) -> None:
        """Should include tool suggestions when enabled."""
        mock_store = MagicMock()
        mock_store.get_relevant.return_value = []
        mock_store.format_tool_suggestions.return_value = "For code tasks: read_file"

        trinket = LearningTrinket(learning_store=mock_store, enable_tool_learning=True)

        result = await trinket.generate(context)

        assert result is not None
        assert "read_file" in result.content

    @pytest.mark.asyncio
    async def test_graceful_on_error(self, context: TrinketContext) -> None:
        """Should return None on error (graceful degradation)."""
        mock_store = MagicMock()
        mock_store.get_relevant.side_effect = RuntimeError("Store error")

        trinket = LearningTrinket(learning_store=mock_store)

        result = await trinket.generate(context)

        assert result is None


class TestToolGuidanceTrinket:
    """Tests for ToolGuidanceTrinket."""

    def test_section_name(self) -> None:
        """Should return 'tool_guidance' as section name."""
        trinket = ToolGuidanceTrinket(executor=None)
        assert trinket.get_section_name() == "tool_guidance"

    @pytest.mark.asyncio
    async def test_generate_none_when_no_executor(
        self, context: TrinketContext
    ) -> None:
        """Should return None when no executor."""
        trinket = ToolGuidanceTrinket(executor=None)

        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_none_when_no_registry(
        self, context: TrinketContext
    ) -> None:
        """Should return None when executor has no registry."""
        mock_executor = MagicMock()
        mock_executor._registry = None

        trinket = ToolGuidanceTrinket(executor=mock_executor)

        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_with_guidance(self, context: TrinketContext) -> None:
        """Should generate tool guidance section."""
        mock_registry = MagicMock()
        mock_executor = MagicMock()
        mock_executor._registry = mock_registry

        # Mock the build_tool_context function (imported inside generate())
        with patch(
            "sunwell.tools.registry.context.build_tool_context"
        ) as mock_build:
            mock_build.return_value = "<available_tools>...</available_tools>"

            trinket = ToolGuidanceTrinket(executor=mock_executor)
            result = await trinket.generate(context)

            assert result is not None
            assert result.name == "tool_guidance"
            assert result.placement == TrinketPlacement.SYSTEM
            assert result.priority == 50
            assert result.cacheable is False

    def test_on_tool_executed(self) -> None:
        """Should track executed tools."""
        trinket = ToolGuidanceTrinket(executor=None)

        trinket.on_tool_executed("read_file", success=True)
        trinket.on_tool_executed("write_file", success=False)

        assert "read_file" in trinket._tools_executed
        assert "write_file" in trinket._tools_executed

    def test_on_turn_complete(self) -> None:
        """Should track tools from turn result."""
        trinket = ToolGuidanceTrinket(executor=None)

        trinket.on_turn_complete(
            TurnResult(turn=1, tool_calls=("edit_file", "run_command"))
        )

        assert "edit_file" in trinket._tools_executed
        assert "run_command" in trinket._tools_executed


class TestMemoryTrinket:
    """Tests for MemoryTrinket."""

    def test_section_name(self) -> None:
        """Should return 'memory' as section name."""
        trinket = MemoryTrinket(store=None)
        assert trinket.get_section_name() == "memory"

    @pytest.mark.asyncio
    async def test_generate_none_when_no_store(self, context: TrinketContext) -> None:
        """Should return None when no store."""
        trinket = MemoryTrinket(store=None)

        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_with_context_assembler(
        self, context: TrinketContext
    ) -> None:
        """Should use context assembler when available."""
        mock_assembler = MagicMock()
        mock_assembler.get_context_for_prompt_async = MagicMock(
            return_value=MagicMock()
        )
        # Make it an async mock
        import asyncio

        async def async_get_context(*args, **kwargs):
            return "## History\nUser asked about auth"

        mock_assembler.get_context_for_prompt_async = async_get_context

        mock_store = MagicMock()
        mock_store._context_assembler = mock_assembler

        trinket = MemoryTrinket(store=mock_store)
        result = await trinket.generate(context)

        assert result is not None
        assert result.name == "memory"
        assert result.placement == TrinketPlacement.CONTEXT
        assert result.priority == 70
        assert result.cacheable is False

    @pytest.mark.asyncio
    async def test_generate_none_when_no_context(
        self, context: TrinketContext
    ) -> None:
        """Should return None when no context available."""
        mock_store = MagicMock()
        mock_store._context_assembler = None
        # Remove _hot_dag attribute
        del mock_store._hot_dag

        trinket = MemoryTrinket(store=mock_store)
        result = await trinket.generate(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_graceful_on_error(self, context: TrinketContext) -> None:
        """Should return None on error (graceful degradation)."""
        mock_store = MagicMock()
        mock_store._context_assembler = MagicMock()
        mock_store._context_assembler.get_context_for_prompt_async = MagicMock(
            side_effect=RuntimeError("Retrieval failed")
        )

        trinket = MemoryTrinket(store=mock_store)
        result = await trinket.generate(context)

        assert result is None
