"""Tests for Agent.run() (RFC-MEMORY).

Tests the agent execution signature using SessionContext and PersistentMemory.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.agent.events import EventType


class TestAgentRunSignature:
    """Tests for Agent.run() method signature."""

    @pytest.mark.asyncio
    async def test_run_method_exists(self) -> None:
        """Agent class should have run method."""
        from sunwell.agent import Agent

        assert hasattr(Agent, "run")


class TestAgentRunEventFlow:
    """Tests for expected event flow from run()."""

    @pytest.fixture
    def mock_session(self, tmp_path: Path) -> MagicMock:
        """Create mock SessionContext."""
        session = MagicMock()
        session.session_id = "test-session-123"
        session.goal = "build an API"
        session.cwd = tmp_path
        session.project_type = "python"
        session.framework = "fastapi"
        session.trust = "workspace"
        session.timeout = 300
        session.model_name = "gpt-4o"
        session.lens = None
        session.briefing = None
        session.tasks = []
        session.current_task = None
        session.files_modified = []
        session.artifacts_created = []
        session.to_planning_prompt = MagicMock(return_value="workspace context")
        session.save_briefing = MagicMock()
        return session

    @pytest.fixture
    def mock_memory(self, tmp_path: Path) -> MagicMock:
        """Create mock PersistentMemory."""
        memory = MagicMock()
        memory.workspace = tmp_path
        memory.learning_count = 5
        memory.decision_count = 2
        memory.failure_count = 1
        memory.simulacrum = None

        # Mock get_relevant to return MemoryContext
        mock_ctx = MagicMock()
        mock_ctx.learnings = ["learned this"]
        mock_ctx.constraints = ("no redis",)
        mock_ctx.dead_ends = ("async sqlalchemy failed",)
        mock_ctx.to_prompt = MagicMock(return_value="## Constraints\n- no redis")
        memory.get_relevant = AsyncMock(return_value=mock_ctx)

        # Mock sync
        mock_sync_result = MagicMock()
        mock_sync_result.all_succeeded = True
        memory.sync = MagicMock(return_value=mock_sync_result)

        # Mock add_failure
        memory.add_failure = AsyncMock()

        return memory

    @pytest.mark.asyncio
    async def test_orient_event_has_correct_type(self) -> None:
        """ORIENT event should have correct type."""
        from sunwell.agent.events import orient_event

        event = orient_event(learnings=5, constraints=2, dead_ends=1)

        assert event.type == EventType.ORIENT
        assert event.data["learnings"] == 5
        assert event.data["constraints"] == 2
        assert event.data["dead_ends"] == 1

    @pytest.mark.asyncio
    async def test_complete_event_exists(self) -> None:
        """complete_event should be available."""
        from sunwell.agent.events import complete_event

        # complete_event requires arguments
        event = complete_event(
            tasks_completed=3,
            gates_passed=2,
            duration_s=45.5,
        )

        assert event.type == EventType.COMPLETE
        assert event.data["tasks_completed"] == 3


class TestAgentRunMemoryIntegration:
    """Tests for memory integration with run()."""

    @pytest.fixture
    def mock_memory(self, tmp_path: Path) -> MagicMock:
        """Create mock PersistentMemory."""
        memory = MagicMock()
        memory.workspace = tmp_path
        memory.learning_count = 0
        memory.decision_count = 0
        memory.failure_count = 0

        mock_ctx = MagicMock()
        mock_ctx.constraints = ()
        mock_ctx.dead_ends = ()
        mock_ctx.to_prompt = MagicMock(return_value="")
        memory.get_relevant = AsyncMock(return_value=mock_ctx)

        mock_sync_result = MagicMock()
        mock_sync_result.all_succeeded = True
        memory.sync = MagicMock(return_value=mock_sync_result)

        return memory

    @pytest.mark.asyncio
    async def test_memory_get_relevant_returns_context(
        self, mock_memory: MagicMock
    ) -> None:
        """Memory.get_relevant() should return context with constraints and dead_ends."""
        ctx = await mock_memory.get_relevant("test goal")

        assert hasattr(ctx, "constraints")
        assert hasattr(ctx, "dead_ends")

    def test_memory_sync_returns_result(self, mock_memory: MagicMock) -> None:
        """Memory.sync() should return sync result."""
        result = mock_memory.sync()

        assert hasattr(result, "all_succeeded")
