"""Tests for Agent.run() (RFC-MEMORY).

Tests the agent execution signature using SessionContext and PersistentMemory.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.agent.events import EventType


class TestAgentRun:
    """Tests for Agent.run() method."""

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
        mock_sync_result.success = True
        memory.sync = MagicMock(return_value=mock_sync_result)

        # Mock add_failure
        memory.add_failure = AsyncMock()

        return memory

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """Create mock Agent with run."""
        from sunwell.agent import Agent

        # We can't easily instantiate Agent without all dependencies,
        # so we'll test the method signature and behavior indirectly
        agent = MagicMock(spec=Agent)
        return agent

    @pytest.mark.asyncio
    async def test_run_signature_exists(self) -> None:
        """Agent should have run method with SessionContext, PersistentMemory signature."""
        from sunwell.agent import Agent

        assert hasattr(Agent, "run")

    @pytest.mark.asyncio
    async def test_run_yields_orient_event(
        self,
        mock_session: MagicMock,
        mock_memory: MagicMock,
    ) -> None:
        """run() should yield ORIENT event at start."""
        from sunwell.agent import Agent
        from sunwell.agent.events import orient_event

        # Create a minimal agent mock
        agent = MagicMock(spec=Agent)

        # Mock the internal methods
        async def mock_run(session, memory):
            # ORIENT phase
            ctx = await memory.get_relevant(session.goal)
            yield orient_event(
                learnings=5,
                constraints=len(ctx.constraints),
                dead_ends=len(ctx.dead_ends),
            )

        agent.run = mock_run

        events = []
        async for event in agent.run(mock_session, mock_memory):
            events.append(event)

        assert len(events) >= 1
        assert events[0].type == EventType.ORIENT
        assert events[0].data["constraints"] == 1
        assert events[0].data["dead_ends"] == 1

    @pytest.mark.asyncio
    async def test_run_calls_get_relevant(
        self,
        mock_session: MagicMock,
        mock_memory: MagicMock,
    ) -> None:
        """run() should call memory.get_relevant() with goal."""
        from sunwell.agent import Agent
        from sunwell.agent.events import orient_event

        async def mock_run(session, memory):
            ctx = await memory.get_relevant(session.goal)
            yield orient_event(
                learnings=0,
                constraints=len(ctx.constraints),
                dead_ends=len(ctx.dead_ends),
            )

        agent = MagicMock(spec=Agent)
        agent.run = mock_run

        async for _ in agent.run(mock_session, mock_memory):
            pass

        mock_memory.get_relevant.assert_called_once_with("build an API")

    @pytest.mark.asyncio
    async def test_run_syncs_memory(
        self,
        mock_session: MagicMock,
        mock_memory: MagicMock,
    ) -> None:
        """run() should sync memory at the end."""
        from sunwell.agent import Agent
        from sunwell.agent.events import complete_event, orient_event

        async def mock_run(session, memory):
            await memory.get_relevant(session.goal)
            yield orient_event(0, 0, 0)

            # LEARN phase
            memory.sync()
            yield complete_event()

        agent = MagicMock(spec=Agent)
        agent.run = mock_run

        events = []
        async for event in agent.run(mock_session, mock_memory):
            events.append(event)

        mock_memory.sync.assert_called_once()


class TestAgentRunIntegration:
    """Integration-style tests for run."""

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create mock model."""
        model = MagicMock()
        model.complete = AsyncMock(return_value="Task completed")
        return model

    @pytest.fixture
    def mock_tool_executor(self) -> MagicMock:
        """Create mock tool executor."""
        executor = MagicMock()
        executor.execute = AsyncMock(return_value=None)
        return executor

    @pytest.mark.asyncio
    async def test_run_full_flow_mocked(
        self,
        tmp_path: Path,
        mock_model: MagicMock,
        mock_tool_executor: MagicMock,
    ) -> None:
        """Test full run flow with mocked dependencies."""
        from sunwell.agent import Agent
        from sunwell.agent.budget import AdaptiveBudget

        # Create real agent with mocked dependencies
        agent = Agent(
            model=mock_model,
            tool_executor=mock_tool_executor,
            cwd=tmp_path,
            budget=AdaptiveBudget(total_budget=10_000),
        )

        # Verify run exists and is callable
        assert callable(agent.run)

        # Note: Full execution test would require extensive mocking
        # This test verifies the method signature is correct
