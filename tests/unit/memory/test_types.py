"""Tests for memory types (RFC: Architecture Proposal).

Tests for MemoryContext and TaskMemoryContext data classes.
"""

import pytest

from sunwell.memory.types import MemoryContext, TaskMemoryContext


class TestMemoryContext:
    """Tests for MemoryContext dataclass."""

    def test_create_empty(self) -> None:
        """MemoryContext should create with default empty values."""
        ctx = MemoryContext()

        assert ctx.learnings == ()
        assert ctx.facts == ()
        assert ctx.constraints == ()
        assert ctx.dead_ends == ()
        assert ctx.team_decisions == ()
        assert ctx.patterns == ()

    def test_create_with_values(self) -> None:
        """MemoryContext should accept all fields."""
        ctx = MemoryContext(
            constraints=("no redis - too complex",),
            dead_ends=("async sqlalchemy failed",),
            team_decisions=("use pydantic v2",),
            patterns=("snake_case for functions",),
        )

        assert ctx.constraints == ("no redis - too complex",)
        assert ctx.dead_ends == ("async sqlalchemy failed",)
        assert ctx.team_decisions == ("use pydantic v2",)
        assert ctx.patterns == ("snake_case for functions",)

    def test_frozen(self) -> None:
        """MemoryContext should be immutable (frozen)."""
        ctx = MemoryContext(constraints=("no redis",))

        with pytest.raises(AttributeError):
            ctx.constraints = ("different",)  # type: ignore

    def test_to_prompt_empty(self) -> None:
        """to_prompt() should return empty string for empty context."""
        ctx = MemoryContext()
        assert ctx.to_prompt() == ""

    def test_to_prompt_constraints(self) -> None:
        """to_prompt() should include constraints section."""
        ctx = MemoryContext(constraints=("no redis - too complex for scale",))

        prompt = ctx.to_prompt()

        assert "## Constraints (DO NOT violate)" in prompt
        assert "no redis - too complex for scale" in prompt

    def test_to_prompt_dead_ends(self) -> None:
        """to_prompt() should include dead ends section."""
        ctx = MemoryContext(dead_ends=("async sqlalchemy caused pool issues",))

        prompt = ctx.to_prompt()

        assert "## Known Dead Ends (DO NOT repeat)" in prompt
        assert "async sqlalchemy caused pool issues" in prompt

    def test_to_prompt_team_decisions(self) -> None:
        """to_prompt() should include team decisions section."""
        ctx = MemoryContext(team_decisions=("use pydantic v2 for models",))

        prompt = ctx.to_prompt()

        assert "## Team Decisions (follow these)" in prompt
        assert "use pydantic v2 for models" in prompt

    def test_to_prompt_combined(self) -> None:
        """to_prompt() should combine all sections."""
        ctx = MemoryContext(
            constraints=("constraint 1",),
            dead_ends=("dead end 1",),
            team_decisions=("team decision 1",),
        )

        prompt = ctx.to_prompt()

        assert "Constraints" in prompt
        assert "Dead Ends" in prompt
        assert "Team Decisions" in prompt

    def test_to_prompt_limits_learnings(self) -> None:
        """to_prompt() should limit learnings to top 10."""
        # Create mock learnings
        from unittest.mock import MagicMock

        learnings = tuple(
            MagicMock(category=f"cat-{i}", fact=f"fact {i}")
            for i in range(15)
        )

        ctx = MemoryContext(learnings=learnings)
        prompt = ctx.to_prompt()

        # Should have "Known Facts" section
        assert "## Known Facts" in prompt
        # Should only show 10 (limited)
        assert "fact 9" in prompt
        assert "fact 10" not in prompt  # Limited to 10


class TestTaskMemoryContext:
    """Tests for TaskMemoryContext dataclass."""

    def test_create_empty(self) -> None:
        """TaskMemoryContext should create with default empty values."""
        ctx = TaskMemoryContext()

        assert ctx.constraints == ()
        assert ctx.hazards == ()
        assert ctx.patterns == ()

    def test_create_with_values(self) -> None:
        """TaskMemoryContext should accept all fields."""
        ctx = TaskMemoryContext(
            constraints=("max 100 chars per line",),
            hazards=("previous race condition in this file",),
            patterns=("use dataclasses for models",),
        )

        assert ctx.constraints == ("max 100 chars per line",)
        assert ctx.hazards == ("previous race condition in this file",)
        assert ctx.patterns == ("use dataclasses for models",)

    def test_frozen(self) -> None:
        """TaskMemoryContext should be immutable (frozen)."""
        ctx = TaskMemoryContext(constraints=("constraint",))

        with pytest.raises(AttributeError):
            ctx.constraints = ("different",)  # type: ignore

    def test_to_prompt_empty(self) -> None:
        """to_prompt() should return empty string for empty context."""
        ctx = TaskMemoryContext()
        assert ctx.to_prompt() == ""

    def test_to_prompt_constraints(self) -> None:
        """to_prompt() should include constraints section."""
        ctx = TaskMemoryContext(constraints=("max 100 chars per line",))

        prompt = ctx.to_prompt()

        assert "CONSTRAINTS for this task:" in prompt
        assert "max 100 chars per line" in prompt

    def test_to_prompt_hazards(self) -> None:
        """to_prompt() should include hazards section."""
        ctx = TaskMemoryContext(hazards=("race condition here before",))

        prompt = ctx.to_prompt()

        assert "HAZARDS (past failures with similar tasks):" in prompt
        assert "race condition here before" in prompt

    def test_to_prompt_patterns(self) -> None:
        """to_prompt() should include patterns section."""
        ctx = TaskMemoryContext(patterns=("use dataclasses",))

        prompt = ctx.to_prompt()

        assert "PATTERNS to follow:" in prompt
        assert "use dataclasses" in prompt

    def test_to_prompt_combined(self) -> None:
        """to_prompt() should combine all sections."""
        ctx = TaskMemoryContext(
            constraints=("constraint 1",),
            hazards=("hazard 1",),
            patterns=("pattern 1",),
        )

        prompt = ctx.to_prompt()

        assert "CONSTRAINTS" in prompt
        assert "HAZARDS" in prompt
        assert "PATTERNS" in prompt
