"""Unit tests for trinket base types."""

from pathlib import Path

import pytest

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
    TurnResult,
)


class TestTrinketSection:
    """Tests for TrinketSection dataclass."""

    def test_create_minimal(self) -> None:
        """Should create section with minimal args."""
        section = TrinketSection(
            name="test",
            content="Hello",
            placement=TrinketPlacement.SYSTEM,
        )
        assert section.name == "test"
        assert section.content == "Hello"
        assert section.placement == TrinketPlacement.SYSTEM
        assert section.priority == 50  # Default
        assert section.cacheable is False  # Default

    def test_create_full(self) -> None:
        """Should create section with all args."""
        section = TrinketSection(
            name="test",
            content="Hello",
            placement=TrinketPlacement.CONTEXT,
            priority=10,
            cacheable=True,
        )
        assert section.priority == 10
        assert section.cacheable is True

    def test_frozen(self) -> None:
        """Should be immutable."""
        section = TrinketSection(
            name="test",
            content="Hello",
            placement=TrinketPlacement.SYSTEM,
        )
        with pytest.raises(AttributeError):
            section.name = "changed"  # type: ignore[misc]


class TestTrinketContext:
    """Tests for TrinketContext dataclass."""

    def test_create_minimal(self) -> None:
        """Should create context with minimal args."""
        ctx = TrinketContext(
            task="Build API",
            workspace=Path("/project"),
        )
        assert ctx.task == "Build API"
        assert ctx.workspace == Path("/project")
        assert ctx.turn == 0  # Default
        assert ctx.tools == ()  # Default
        assert ctx.extra == {}  # Default

    def test_create_full(self) -> None:
        """Should create context with all args."""
        ctx = TrinketContext(
            task="Build API",
            workspace=Path("/project"),
            turn=5,
            tools=("read_file", "write_file"),
            extra={"key": "value"},
        )
        assert ctx.turn == 5
        assert ctx.tools == ("read_file", "write_file")
        assert ctx.extra == {"key": "value"}

    def test_frozen(self) -> None:
        """Should be immutable."""
        ctx = TrinketContext(task="test", workspace=Path("."))
        with pytest.raises(AttributeError):
            ctx.task = "changed"  # type: ignore[misc]


class TestTurnResult:
    """Tests for TurnResult dataclass."""

    def test_create_success(self) -> None:
        """Should create success result."""
        result = TurnResult(
            turn=1,
            tool_calls=("read_file", "write_file"),
            success=True,
        )
        assert result.turn == 1
        assert result.tool_calls == ("read_file", "write_file")
        assert result.success is True
        assert result.error is None

    def test_create_failure(self) -> None:
        """Should create failure result."""
        result = TurnResult(
            turn=2,
            success=False,
            error="Tool execution failed",
        )
        assert result.success is False
        assert result.error == "Tool execution failed"


class TestTrinketPlacement:
    """Tests for TrinketPlacement enum."""

    def test_values(self) -> None:
        """Should have expected values."""
        assert TrinketPlacement.SYSTEM.value == "system"
        assert TrinketPlacement.CONTEXT.value == "context"
        assert TrinketPlacement.NOTIFICATION.value == "notification"


class TestBaseTrinket:
    """Tests for BaseTrinket abstract class."""

    def test_is_abstract(self) -> None:
        """Should not be instantiable directly."""
        with pytest.raises(TypeError):
            BaseTrinket()  # type: ignore[abstract]

    def test_concrete_implementation(self) -> None:
        """Should be implementable."""

        class ConcreteTrinket(BaseTrinket):
            def get_section_name(self) -> str:
                return "concrete"

            async def generate(self, context: TrinketContext) -> TrinketSection:
                return TrinketSection(
                    name="concrete",
                    content="test",
                    placement=TrinketPlacement.SYSTEM,
                )

        trinket = ConcreteTrinket()
        assert trinket.get_section_name() == "concrete"

    def test_optional_hooks_have_defaults(self) -> None:
        """Optional hooks should have default implementations."""

        class MinimalTrinket(BaseTrinket):
            def get_section_name(self) -> str:
                return "minimal"

            async def generate(self, context: TrinketContext) -> TrinketSection | None:
                return None

        trinket = MinimalTrinket()
        # Should not raise - defaults exist
        trinket.on_turn_complete(TurnResult(turn=1))
        trinket.on_tool_executed("read_file", success=True)
