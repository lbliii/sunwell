"""Tests for smart-to-dumb model delegation (RFC-137).

Tests the ephemeral lens integration, delegation flow, and wire-up.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sunwell.agent.ephemeral_lens import (
    _parse_lens_json,
    create_ephemeral_lens,
    should_use_delegation,
)
from sunwell.agent.events import (
    EventType,
    delegation_started_event,
    ephemeral_lens_created_event,
)
from sunwell.agent.loop import AgentLoop, LoopConfig
from sunwell.agent.request import RunOptions
from sunwell.context.session import SessionContext
from sunwell.core.lens import EphemeralLens
from sunwell.models.protocol import ModelProtocol


class TestShouldUseDelegation:
    """Tests for the delegation decision function."""

    @pytest.mark.asyncio
    async def test_delegation_triggered_for_large_tasks(self) -> None:
        """Delegation starts when task exceeds threshold."""
        result = await should_use_delegation(
            task="Generate CRUD endpoints for 5 entities",
            estimated_tokens=5000,  # Above default threshold of 2000
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_delegation_triggered_for_low_budget(self) -> None:
        """Delegation starts when budget is limited."""
        result = await should_use_delegation(
            task="Simple task",
            estimated_tokens=1000,  # Below threshold
            budget_remaining=2000,  # Very limited budget
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_delegation_triggered_for_multi_file(self) -> None:
        """Delegation starts for multi-file generation."""
        result = await should_use_delegation(
            task="Generate components for the dashboard",
            estimated_tokens=1000,  # Below threshold
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_delegation_skipped_for_small_tasks(self) -> None:
        """Small tasks use normal execution path."""
        result = await should_use_delegation(
            task="Fix the typo in line 42",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is False


class TestParseLensJson:
    """Tests for JSON parsing from model responses."""

    def test_parse_clean_json(self) -> None:
        """Parse clean JSON directly."""
        content = '{"heuristics": ["h1"], "patterns": ["p1"]}'
        result = _parse_lens_json(content)
        assert result == {"heuristics": ["h1"], "patterns": ["p1"]}

    def test_parse_json_with_markdown_fence(self) -> None:
        """Parse JSON wrapped in markdown code fence."""
        content = """```json
{"heuristics": ["h1"], "patterns": ["p1"]}
```"""
        result = _parse_lens_json(content)
        assert result == {"heuristics": ["h1"], "patterns": ["p1"]}

    def test_parse_json_embedded_in_text(self) -> None:
        """Parse JSON embedded in other text."""
        content = """Here is the lens:
{"heuristics": ["h1"], "patterns": ["p1"]}
That's it."""
        result = _parse_lens_json(content)
        assert result == {"heuristics": ["h1"], "patterns": ["p1"]}

    def test_parse_invalid_json_returns_empty(self) -> None:
        """Invalid JSON returns empty dict."""
        content = "This is not JSON at all"
        result = _parse_lens_json(content)
        assert result == {}


class TestEphemeralLensCreation:
    """Tests for ephemeral lens creation."""

    def test_ephemeral_lens_to_context(self) -> None:
        """EphemeralLens.to_context() produces valid context string."""
        lens = EphemeralLens(
            heuristics=("Use type hints", "Add docstrings"),
            patterns=("dataclass for models",),
            anti_patterns=("global state",),
            constraints=("Python 3.10+",),
            task_scope="User authentication API",
            generated_by="claude-3-opus",
        )
        context = lens.to_context()

        assert "type hints" in context.lower() or "Type hints" in context
        assert "docstrings" in context.lower() or "Docstrings" in context
        assert "User authentication API" in context or "authentication" in context.lower()


class TestDelegationEvents:
    """Tests for delegation event factories."""

    def test_delegation_started_event(self) -> None:
        """Delegation started event has correct structure."""
        event = delegation_started_event(
            task_description="Generate API endpoints",
            smart_model="claude-3-opus",
            delegation_model="claude-3-haiku",
            reason="Task exceeds threshold",
            estimated_tokens=5000,
        )

        assert event.type == EventType.DELEGATION_STARTED
        assert event.data["smart_model"] == "claude-3-opus"
        assert event.data["delegation_model"] == "claude-3-haiku"
        assert event.data["estimated_tokens"] == 5000

    def test_ephemeral_lens_created_event(self) -> None:
        """Ephemeral lens created event has correct structure."""
        event = ephemeral_lens_created_event(
            task_scope="User authentication",
            heuristics_count=5,
            patterns_count=3,
            generated_by="claude-3-opus",
            anti_patterns_count=2,
            constraints_count=1,
        )

        assert event.type == EventType.EPHEMERAL_LENS_CREATED
        assert event.data["heuristics_count"] == 5
        assert event.data["patterns_count"] == 3
        assert event.data["generated_by"] == "claude-3-opus"


class TestLoopConfig:
    """Tests for LoopConfig delegation options."""

    def test_delegation_disabled_by_default(self) -> None:
        """Delegation is disabled by default."""
        config = LoopConfig()
        assert config.enable_delegation is False
        assert config.delegation_threshold_tokens == 2000

    def test_delegation_can_be_enabled(self) -> None:
        """Delegation can be enabled via config."""
        config = LoopConfig(enable_delegation=True, delegation_threshold_tokens=3000)
        assert config.enable_delegation is True
        assert config.delegation_threshold_tokens == 3000


class TestAgentLoopDelegation:
    """Tests for AgentLoop delegation integration."""

    def test_estimate_output_tokens_small_task(self) -> None:
        """Small tasks get reasonable token estimates."""
        loop = AgentLoop(
            model=MagicMock(),
            executor=MagicMock(),
        )
        estimate = loop._estimate_output_tokens("Fix the typo")
        assert 500 <= estimate <= 2000

    def test_estimate_output_tokens_large_task(self) -> None:
        """Large tasks with indicators get multiplied estimates."""
        loop = AgentLoop(
            model=MagicMock(),
            executor=MagicMock(),
        )
        # Short task with indicator: 10 words * 10 = 100, * 2 for "complete" = 200, min 500
        estimate = loop._estimate_output_tokens(
            "Generate a complete implementation of user authentication with all endpoints"
        )
        assert estimate >= 500  # Minimum cap applies

        # Longer task to actually trigger multiplier above min
        # 30 words * 10 = 300, * 2 for "complete" = 600 > 500
        estimate_long = loop._estimate_output_tokens(
            "Generate a complete implementation of the user authentication system "
            "including login logout registration password reset email verification "
            "and session management with all the necessary database models and API endpoints"
        )
        assert estimate_long > 500  # Should exceed minimum due to length + multiplier

    def test_delegation_fields_initialized(self) -> None:
        """AgentLoop has delegation fields."""
        loop = AgentLoop(
            model=MagicMock(),
            executor=MagicMock(),
        )
        assert loop.smart_model is None
        assert loop.delegation_model is None
        assert loop._in_delegation is False

    def test_delegation_models_can_be_set(self) -> None:
        """AgentLoop accepts smart_model and delegation_model."""
        smart = MagicMock(spec=ModelProtocol)
        cheap = MagicMock(spec=ModelProtocol)

        loop = AgentLoop(
            model=MagicMock(),
            executor=MagicMock(),
            smart_model=smart,
            delegation_model=cheap,
        )

        assert loop.smart_model is smart
        assert loop.delegation_model is cheap


class TestRunOptionsDelegation:
    """Tests for RunOptions delegation fields."""

    def test_delegation_disabled_by_default(self) -> None:
        """Delegation is disabled by default in RunOptions."""
        options = RunOptions()

        assert options.enable_delegation is False
        assert options.delegation_threshold_tokens == 2000
        assert options.smart_model is None
        assert options.delegation_model is None

    def test_delegation_can_be_enabled(self) -> None:
        """Delegation can be enabled with model names."""
        options = RunOptions(
            enable_delegation=True,
            delegation_threshold_tokens=3000,
            smart_model="claude-3-opus-20240229",
            delegation_model="claude-3-haiku-20240307",
        )

        assert options.enable_delegation is True
        assert options.delegation_threshold_tokens == 3000
        assert options.smart_model == "claude-3-opus-20240229"
        assert options.delegation_model == "claude-3-haiku-20240307"

    def test_delegation_accepts_model_instances(self) -> None:
        """Delegation accepts ModelProtocol instances."""
        smart = MagicMock(spec=ModelProtocol)
        cheap = MagicMock(spec=ModelProtocol)

        options = RunOptions(
            enable_delegation=True,
            smart_model=smart,
            delegation_model=cheap,
        )

        assert options.smart_model is smart
        assert options.delegation_model is cheap


class TestSessionContextOptions:
    """Tests for SessionContext options storage."""

    def test_session_stores_options(self) -> None:
        """SessionContext stores full RunOptions."""
        import tempfile

        options = RunOptions(
            enable_delegation=True,
            smart_model="claude-3-opus-20240229",
            delegation_model="claude-3-haiku-20240307",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            session = SessionContext.build(
                cwd=Path(tmpdir),
                goal="test goal",
                options=options,
            )

            assert session.options is options
            assert session.options.enable_delegation is True
            assert session.options.smart_model == "claude-3-opus-20240229"

    def test_session_default_options(self) -> None:
        """SessionContext creates default options if not provided."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            session = SessionContext.build(
                cwd=Path(tmpdir),
                goal="test goal",
            )

            assert session.options is not None
            assert session.options.enable_delegation is False
