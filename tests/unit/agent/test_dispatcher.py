"""Tests for TaskDispatcher parallel task execution."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.events import AgentEvent, EventType
from sunwell.agent.execution.dispatcher import (
    TaskDispatcher,
    should_use_parallel_dispatch,
)
from sunwell.agent.loop.config import LoopConfig
from sunwell.planning.naaru.types import Task, TaskMode, TaskStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session(tmp_path: Path) -> MagicMock:
    """Create a mock SessionContext."""
    session = MagicMock()
    session.cwd = tmp_path
    session.session_id = "test-session-123"
    return session


@pytest.fixture
def mock_config() -> LoopConfig:
    """Create a LoopConfig for testing."""
    return LoopConfig(
        enable_parallel_tasks=True,
        max_parallel_tasks=4,
        enable_worktree_isolation=True,
        enable_content_validation=True,
    )


@pytest.fixture
def sample_tasks() -> list[Task]:
    """Create sample tasks with parallel_group assignments."""
    return [
        Task(
            id="task1",
            description="Create file 1",
            mode=TaskMode.GENERATE,
            target_path="src/file1.py",
            parallel_group="implementations",
            modifies=frozenset(["src/file1.py"]),
            status=TaskStatus.PENDING,
        ),
        Task(
            id="task2",
            description="Create file 2",
            mode=TaskMode.GENERATE,
            target_path="src/file2.py",
            parallel_group="implementations",
            modifies=frozenset(["src/file2.py"]),
            status=TaskStatus.PENDING,
        ),
        Task(
            id="task3",
            description="Create test file",
            mode=TaskMode.GENERATE,
            target_path="tests/test_main.py",
            parallel_group="tests",
            modifies=frozenset(["tests/test_main.py"]),
            requires=frozenset(["task1", "task2"]),
            status=TaskStatus.PENDING,
        ),
    ]


# =============================================================================
# Tests
# =============================================================================


class TestShouldUseParallelDispatch:
    """Tests for the should_use_parallel_dispatch helper."""

    def test_returns_true_when_parallel_groups_exist(
        self, sample_tasks: list[Task]
    ) -> None:
        """Should return True when TaskGraph has parallelizable groups."""
        from sunwell.agent.core.task_graph import TaskGraph

        graph = TaskGraph(tasks=sample_tasks)
        config = LoopConfig(enable_parallel_tasks=True)

        result = should_use_parallel_dispatch(graph, config)

        assert result is True

    def test_returns_false_when_parallel_disabled(
        self, sample_tasks: list[Task]
    ) -> None:
        """Should return False when parallel tasks are disabled."""
        from sunwell.agent.core.task_graph import TaskGraph

        graph = TaskGraph(tasks=sample_tasks)
        config = LoopConfig(enable_parallel_tasks=False)

        result = should_use_parallel_dispatch(graph, config)

        assert result is False

    def test_returns_false_for_single_task(self) -> None:
        """Should return False when only one task exists."""
        from sunwell.agent.core.task_graph import TaskGraph

        single_task = Task(
            id="task1",
            description="Single task",
            mode=TaskMode.GENERATE,
            parallel_group="implementations",
            status=TaskStatus.PENDING,
        )
        graph = TaskGraph(tasks=[single_task])
        config = LoopConfig(enable_parallel_tasks=True)

        result = should_use_parallel_dispatch(graph, config)

        # Single task in a group doesn't benefit from parallelization
        assert result is False


class TestTaskDispatcher:
    """Tests for TaskDispatcher class."""

    @pytest.mark.asyncio
    async def test_dispatcher_creates_with_workspace_readiness(
        self,
        mock_session: MagicMock,
        mock_config: LoopConfig,
        tmp_path: Path,
    ) -> None:
        """Dispatcher should check workspace readiness on init."""
        dispatcher = TaskDispatcher(
            workspace=tmp_path,
            session=mock_session,
            config=mock_config,
        )

        # Should have workspace readiness info
        assert dispatcher._workspace_readiness is not None
        # tmp_path is not a git repo
        assert dispatcher._workspace_readiness.is_git_repo is False

    @pytest.mark.asyncio
    async def test_dispatcher_emits_start_and_complete_events(
        self,
        mock_session: MagicMock,
        mock_config: LoopConfig,
        sample_tasks: list[Task],
        tmp_path: Path,
    ) -> None:
        """Dispatcher should emit PARALLEL_DISPATCH_START/COMPLETE events."""
        from sunwell.agent.core.task_graph import TaskGraph

        graph = TaskGraph(tasks=sample_tasks)

        dispatcher = TaskDispatcher(
            workspace=tmp_path,
            session=mock_session,
            config=mock_config,
        )

        # Mock sequential execution to just emit task complete
        async def mock_sequential(task: Task):
            yield AgentEvent(
                type=EventType.TASK_COMPLETE,
                data={"task_id": task.id, "success": True},
            )

        events = []
        async for event in dispatcher.execute_graph(graph, mock_sequential):
            events.append(event)

        # Should have dispatch start and complete events
        event_types = [e.type for e in events]
        assert EventType.PARALLEL_DISPATCH_START in event_types
        assert EventType.PARALLEL_DISPATCH_COMPLETE in event_types

    @pytest.mark.asyncio
    async def test_dispatcher_emits_parallel_group_events(
        self,
        mock_session: MagicMock,
        mock_config: LoopConfig,
        tmp_path: Path,
    ) -> None:
        """Dispatcher should emit PARALLEL_GROUP_START/COMPLETE for parallel groups."""
        from sunwell.agent.coordination.parallel_executor import (
            ParallelGroupResult,
            TaskResult,
        )
        from sunwell.agent.core.task_graph import TaskGraph

        # Create tasks that can be parallelized
        tasks = [
            Task(
                id="task1",
                description="Task 1",
                mode=TaskMode.GENERATE,
                parallel_group="wave1",
                modifies=frozenset(["file1.py"]),
                status=TaskStatus.PENDING,
            ),
            Task(
                id="task2",
                description="Task 2",
                mode=TaskMode.GENERATE,
                parallel_group="wave1",
                modifies=frozenset(["file2.py"]),
                status=TaskStatus.PENDING,
            ),
        ]
        graph = TaskGraph(tasks=tasks)

        # Create dispatcher with mocked parallel executor
        dispatcher = TaskDispatcher(
            workspace=tmp_path,
            session=mock_session,
            config=mock_config,
        )

        # Mock the parallel executor's execute_parallel_group method
        mock_exec = MagicMock()
        mock_exec.execute_parallel_group = AsyncMock(
            return_value=ParallelGroupResult(
                group_name="wave1",
                task_results=[
                    TaskResult(task_id="task1", success=True),
                    TaskResult(task_id="task2", success=True),
                ],
                total_duration_ms=100,
            )
        )
        dispatcher._parallel_executor = mock_exec

        async def mock_sequential(task: Task):
            yield AgentEvent(
                type=EventType.TASK_COMPLETE,
                data={"task_id": task.id, "success": True},
            )

        events = []
        async for event in dispatcher.execute_graph(graph, mock_sequential):
            events.append(event)

        # Check for parallel group events
        event_types = [e.type for e in events]
        assert EventType.PARALLEL_GROUP_START in event_types
        assert EventType.PARALLEL_GROUP_COMPLETE in event_types

    @pytest.mark.asyncio
    async def test_dispatcher_falls_back_to_sequential_when_disabled(
        self,
        mock_session: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dispatcher should execute sequentially when parallel is disabled."""
        from sunwell.agent.core.task_graph import TaskGraph

        # Create tasks without dependencies for simpler test
        tasks = [
            Task(
                id="task1",
                description="Task 1",
                mode=TaskMode.GENERATE,
                parallel_group="implementations",
                modifies=frozenset(["file1.py"]),
                status=TaskStatus.PENDING,
            ),
            Task(
                id="task2",
                description="Task 2",
                mode=TaskMode.GENERATE,
                parallel_group="implementations",
                modifies=frozenset(["file2.py"]),
                status=TaskStatus.PENDING,
            ),
        ]
        config = LoopConfig(enable_parallel_tasks=False)
        graph = TaskGraph(tasks=tasks)

        dispatcher = TaskDispatcher(
            workspace=tmp_path,
            session=mock_session,
            config=config,
        )

        executed_tasks = []

        async def mock_sequential(task: Task):
            executed_tasks.append(task.id)
            yield AgentEvent(
                type=EventType.TASK_COMPLETE,
                data={"task_id": task.id, "success": True},
            )

        events = []
        async for event in dispatcher.execute_graph(graph, mock_sequential):
            events.append(event)

        # All tasks should be executed via sequential path
        assert len(executed_tasks) == len(tasks)
        # Should not have parallel group events
        event_types = [e.type for e in events]
        assert EventType.PARALLEL_GROUP_START not in event_types

    @pytest.mark.asyncio
    async def test_dispatcher_emits_isolation_warning_for_non_git(
        self,
        mock_session: MagicMock,
        mock_config: LoopConfig,
        sample_tasks: list[Task],
        tmp_path: Path,
    ) -> None:
        """Dispatcher should emit ISOLATION_WARNING for non-git workspaces."""
        from sunwell.agent.core.task_graph import TaskGraph

        graph = TaskGraph(tasks=sample_tasks)

        dispatcher = TaskDispatcher(
            workspace=tmp_path,
            session=mock_session,
            config=mock_config,
        )

        async def mock_sequential(task: Task):
            yield AgentEvent(
                type=EventType.TASK_COMPLETE,
                data={"task_id": task.id, "success": True},
            )

        events = []
        async for event in dispatcher.execute_graph(graph, mock_sequential):
            events.append(event)

        # Should have isolation warning since tmp_path is not a git repo
        event_types = [e.type for e in events]
        assert EventType.ISOLATION_WARNING in event_types


class TestTaskDispatcherIntegration:
    """Integration tests for TaskDispatcher with real components."""

    @pytest.mark.asyncio
    async def test_end_to_end_sequential_execution(
        self,
        mock_session: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test end-to-end execution with sequential tasks."""
        from sunwell.agent.core.task_graph import TaskGraph

        # Create independent sequential tasks (no parallel groups, no dependencies)
        tasks = [
            Task(
                id="setup",
                description="Setup task",
                mode=TaskMode.GENERATE,
                status=TaskStatus.PENDING,
            ),
            Task(
                id="main",
                description="Main task",
                mode=TaskMode.GENERATE,
                status=TaskStatus.PENDING,
            ),
        ]
        graph = TaskGraph(tasks=tasks)
        config = LoopConfig(enable_parallel_tasks=True)

        dispatcher = TaskDispatcher(
            workspace=tmp_path,
            session=mock_session,
            config=config,
        )

        execution_order = []

        async def track_execution(task: Task):
            execution_order.append(task.id)
            yield AgentEvent(
                type=EventType.TASK_COMPLETE,
                data={"task_id": task.id, "success": True},
            )

        async for _ in dispatcher.execute_graph(graph, track_execution):
            pass

        # All tasks should be executed
        assert len(execution_order) == 2
        assert set(execution_order) == {"setup", "main"}
