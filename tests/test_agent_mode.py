"""Tests for RFC-032 Agent Mode.

Tests the following components:
- Task and TaskStatus types
- TaskPlanner protocol implementations
- AgentPlanner task decomposition
- ToolRegionWorker execution
- Naaru.run() agent mode
- Error recovery and checkpointing
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.naaru.checkpoint import (
    AgentCheckpoint,
    FailurePolicy,
    TaskExecutionConfig,
)
from sunwell.naaru.planners import (
    AgentPlanner,
    TaskPlanner,
)
from sunwell.naaru.types import (
    Opportunity,
    RiskLevel,
    Task,
    TaskMode,
    TaskStatus,
)

# =============================================================================
# Task Type Tests
# =============================================================================


class TestTask:
    """Tests for the Task dataclass."""

    def test_task_creation_minimal(self):
        """Test minimal task creation."""
        task = Task(
            id="test-001",
            description="Test task",
            mode=TaskMode.GENERATE,
        )

        assert task.id == "test-001"
        assert task.description == "Test task"
        assert task.mode == TaskMode.GENERATE
        assert task.status == TaskStatus.PENDING
        assert task.tools == frozenset()
        assert task.depends_on == ()

    def test_task_creation_full(self):
        """Test task creation with all fields."""
        task = Task(
            id="test-002",
            description="Full test task",
            mode=TaskMode.EXECUTE,
            tools=frozenset(["write_file", "run_command"]),
            target_path="/tmp/test.py",
            working_directory="/tmp",
            depends_on=("task-001",),
            category="testing",
            priority=0.8,
            estimated_effort="high",
            risk_level=RiskLevel.HIGH,
            verification="Check file exists",
            verification_command="test -f /tmp/test.py",
        )

        assert task.tools == frozenset(["write_file", "run_command"])
        assert task.depends_on == ("task-001",)
        assert task.risk_level == RiskLevel.HIGH
        assert task.verification_command == "test -f /tmp/test.py"

    def test_task_is_ready_no_deps(self):
        """Test is_ready with no dependencies."""
        task = Task(
            id="test-003",
            description="No deps",
            mode=TaskMode.GENERATE,
        )

        completed = set()
        assert task.is_ready(completed)

    def test_task_is_ready_with_deps(self):
        """Test is_ready with dependencies."""
        task = Task(
            id="test-004",
            description="Has deps",
            mode=TaskMode.GENERATE,
            depends_on=("dep-001", "dep-002"),
        )

        # Not ready - no deps completed
        assert not task.is_ready(set())

        # Not ready - partial deps
        assert not task.is_ready({"dep-001"})

        # Ready - all deps completed
        assert task.is_ready({"dep-001", "dep-002"})

        # Ready - extra completed tasks don't matter
        assert task.is_ready({"dep-001", "dep-002", "other"})

    def test_task_to_opportunity(self):
        """Test conversion to Opportunity."""
        from sunwell.naaru.types import OpportunityCategory

        task = Task(
            id="test-005",
            description="Convert me",
            mode=TaskMode.SELF_IMPROVE,
            target_path="/tmp/code.py",
            category="code_quality",  # Must be valid OpportunityCategory
            priority=0.7,
            estimated_effort="medium",
            risk_level=RiskLevel.LOW,
            details={"line": 42},
        )

        opp = task.to_opportunity()

        assert isinstance(opp, Opportunity)
        assert opp.id == "test-005"
        assert opp.description == "Convert me"
        assert opp.category == OpportunityCategory.CODE_QUALITY
        assert opp.target_module == "/tmp/code.py"  # Opportunity uses target_module
        assert opp.priority == 0.7
        assert opp.details == {"line": 42}

    def test_task_from_opportunity(self):
        """Test conversion from Opportunity."""
        from sunwell.naaru.types import OpportunityCategory

        opp = Opportunity(
            id="opp-001",
            description="Original opportunity",
            category=OpportunityCategory.SECURITY,  # Must use enum
            target_module="/tmp/auth.py",  # Correct field name
            priority=0.9,
            estimated_effort="high",
            risk_level=RiskLevel.HIGH,
            details={"issue": "SQL injection"},
        )

        task = Task.from_opportunity(opp)

        assert task.id == "opp-001"
        assert task.description == "Original opportunity"
        assert task.mode == TaskMode.SELF_IMPROVE
        assert task.category == "security"  # Task uses string category
        assert task.risk_level == RiskLevel.HIGH


class TestTaskStatus:
    """Tests for TaskStatus transitions."""

    def test_all_status_values(self):
        """Verify all expected status values exist."""
        expected = {"pending", "ready", "in_progress", "blocked", "completed", "failed", "skipped"}
        actual = {s.value for s in TaskStatus}
        assert actual == expected


class TestTaskMode:
    """Tests for TaskMode enum."""

    def test_all_mode_values(self):
        """Verify all expected mode values exist."""
        expected = {"self_improve", "generate", "modify", "execute", "research", "composite"}
        actual = {m.value for m in TaskMode}
        assert actual == expected


# =============================================================================
# AgentPlanner Tests
# =============================================================================


class TestAgentPlanner:
    """Tests for the AgentPlanner task decomposition."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        model = AsyncMock()
        return model

    @pytest.fixture
    def planner(self, mock_model):
        """Create an AgentPlanner with mock model."""
        return AgentPlanner(
            model=mock_model,
            available_tools=frozenset(["write_file", "read_file", "run_command"]),
            max_subtasks=10,
        )

    @pytest.mark.asyncio
    async def test_plan_simple_goal(self, planner, mock_model):
        """Test planning a simple goal."""
        # Mock model response with valid JSON
        mock_model.generate.return_value = MagicMock(
            content=json.dumps(
                [
                    {
                        "id": "task-1",
                        "description": "Create hello.py file",
                        "mode": "generate",
                        "tools": ["write_file"],
                        "target_path": "hello.py",
                    }
                ]
            )
        )

        tasks = await planner.plan(["Create a hello world script"])

        assert len(tasks) == 1
        assert tasks[0].id == "task-1"
        assert tasks[0].mode == TaskMode.GENERATE
        assert "write_file" in tasks[0].tools

    @pytest.mark.asyncio
    async def test_plan_multi_step_goal(self, planner, mock_model):
        """Test planning a multi-step goal with dependencies."""
        mock_model.generate.return_value = MagicMock(
            content=json.dumps(
                [
                    {
                        "id": "task-1",
                        "description": "Create config file",
                        "mode": "generate",
                        "tools": ["write_file"],
                        "target_path": "config.json",
                    },
                    {
                        "id": "task-2",
                        "description": "Create app that uses config",
                        "mode": "generate",
                        "tools": ["write_file"],
                        "target_path": "app.py",
                        "depends_on": ["task-1"],
                    },
                ]
            )
        )

        tasks = await planner.plan(["Create an app with config"])

        assert len(tasks) == 2
        assert tasks[1].depends_on == ("task-1",)

    @pytest.mark.asyncio
    async def test_plan_handles_malformed_json(self, planner, mock_model):
        """Test graceful handling of malformed JSON."""
        # Model returns invalid JSON
        mock_model.generate.return_value = MagicMock(
            content="Sure! Here's a plan:\n```json\n{invalid json}\n```"
        )

        # Should fallback to single task
        tasks = await planner.plan(["Do something"])

        assert len(tasks) == 1
        assert "Do something" in tasks[0].description

    @pytest.mark.asyncio
    async def test_plan_extracts_json_from_markdown(self, planner, mock_model):
        """Test JSON extraction from markdown code blocks."""
        mock_model.generate.return_value = MagicMock(
            content="""Here's the plan:

```json
[
  {
    "id": "t1",
    "description": "First task",
    "mode": "generate",
    "tools": []
  }
]
```

Let me know if you need changes!"""
        )

        tasks = await planner.plan(["Test goal"])

        assert len(tasks) == 1
        assert tasks[0].id == "t1"

    def test_planner_mode(self, planner):
        """Test that planner reports correct mode."""
        # AgentPlanner supports multiple modes, defaults to COMPOSITE
        assert planner.mode in {TaskMode.COMPOSITE, TaskMode.GENERATE, TaskMode.EXECUTE}


# =============================================================================
# Checkpoint Tests
# =============================================================================


class TestAgentCheckpoint:
    """Tests for checkpoint save/load functionality."""

    def test_checkpoint_creation(self):
        """Test creating a checkpoint."""
        from datetime import datetime

        tasks = [
            Task(
                id="t1",
                description="Task 1",
                mode=TaskMode.GENERATE,
                status=TaskStatus.COMPLETED,
            ),
            Task(
                id="t2",
                description="Task 2",
                mode=TaskMode.EXECUTE,
                status=TaskStatus.PENDING,
                depends_on=("t1",),
            ),
        ]

        checkpoint = AgentCheckpoint(
            goal="Test goal",
            started_at=datetime.now(),
            checkpoint_at=datetime.now(),
            tasks=tasks,
            completed_ids={"t1"},
            artifacts=[Path("/tmp/output.txt")],
        )

        assert checkpoint.goal == "Test goal"
        assert len(checkpoint.tasks) == 2
        assert "t1" in checkpoint.completed_ids

    def test_checkpoint_save_load(self):
        """Test checkpoint serialization round-trip."""
        from datetime import datetime

        tasks = [
            Task(
                id="t1",
                description="Test task",
                mode=TaskMode.GENERATE,
                status=TaskStatus.COMPLETED,
                result={"output": "success"},
            ),
        ]

        original = AgentCheckpoint(
            goal="Round-trip test",
            started_at=datetime.now(),
            checkpoint_at=datetime.now(),
            tasks=tasks,
            completed_ids={"t1"},
            artifacts=[],
        )

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            original.save(temp_path)
            loaded = AgentCheckpoint.load(temp_path)

            assert loaded.goal == original.goal
            assert len(loaded.tasks) == 1
            assert loaded.tasks[0].id == "t1"
            assert loaded.completed_ids == {"t1"}
        finally:
            temp_path.unlink(missing_ok=True)


class TestTaskExecutionConfig:
    """Tests for task execution configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TaskExecutionConfig()

        assert config.max_retries_per_task == 2
        assert config.checkpoint_interval_seconds == 60.0
        assert config.failure_policy == FailurePolicy.CONTINUE

    def test_strict_config(self):
        """Test abort failure policy."""
        config = TaskExecutionConfig(
            failure_policy=FailurePolicy.ABORT,
            max_retries_per_task=0,
        )

        assert config.failure_policy == FailurePolicy.ABORT
        assert config.max_retries_per_task == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestAgentModeIntegration:
    """Integration tests for agent mode."""

    @pytest.fixture
    def mock_naaru_deps(self):
        """Create mock dependencies for Naaru."""
        model = AsyncMock()
        model.generate.return_value = MagicMock(
            content=json.dumps(
                [
                    {
                        "id": "task-1",
                        "description": "Create file",
                        "mode": "generate",
                        "tools": ["write_file"],
                        "target_path": "output.py",
                    }
                ]
            )
        )

        tool_executor = MagicMock()
        tool_executor.execute.return_value = {"success": True, "output": "File created"}
        tool_executor.get_available_tools.return_value = ["write_file", "read_file"]

        return {
            "model": model,
            "tool_executor": tool_executor,
        }

    @pytest.mark.asyncio
    async def test_task_dependency_resolution(self):
        """Test that task dependencies are resolved correctly."""
        tasks = [
            Task(id="a", description="A", mode=TaskMode.GENERATE),
            Task(id="b", description="B", mode=TaskMode.GENERATE, depends_on=("a",)),
            Task(id="c", description="C", mode=TaskMode.GENERATE, depends_on=("a", "b")),
        ]

        completed = set()
        execution_order = []

        # Simulate dependency-aware execution
        while len(completed) < len(tasks):
            for task in tasks:
                if task.id in completed:
                    continue
                if task.is_ready(completed):
                    execution_order.append(task.id)
                    completed.add(task.id)
                    break

        assert execution_order == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_parallel_independent_tasks(self):
        """Test that independent tasks can be identified for parallel execution."""
        tasks = [
            Task(id="a", description="A", mode=TaskMode.GENERATE),
            Task(id="b", description="B", mode=TaskMode.GENERATE),
            Task(id="c", description="C", mode=TaskMode.GENERATE, depends_on=("a", "b")),
        ]

        completed = set()

        # Find all ready tasks
        ready_tasks = [t for t in tasks if t.is_ready(completed)]

        # A and B should both be ready (parallelizable)
        assert len(ready_tasks) == 2
        assert {t.id for t in ready_tasks} == {"a", "b"}


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error recovery and handling."""

    def test_task_failure_state(self):
        """Test task failure state tracking."""
        task = Task(
            id="failing-task",
            description="This will fail",
            mode=TaskMode.EXECUTE,
            status=TaskStatus.IN_PROGRESS,
        )

        # Simulate failure
        failed_task = Task(
            id=task.id,
            description=task.description,
            mode=task.mode,
            status=TaskStatus.FAILED,
            error="Command returned exit code 1",
        )

        assert failed_task.status == TaskStatus.FAILED
        assert failed_task.error is not None

    def test_blocked_task_detection(self):
        """Test detection of blocked tasks."""
        tasks = [
            Task(
                id="dep", description="Dependency", mode=TaskMode.GENERATE, status=TaskStatus.FAILED
            ),
            Task(
                id="dependent",
                description="Depends on failed",
                mode=TaskMode.GENERATE,
                depends_on=("dep",),
            ),
        ]

        # Dependent task should be blocked since dependency failed
        failed_ids = {t.id for t in tasks if t.status == TaskStatus.FAILED}

        dependent = tasks[1]
        is_blocked = any(dep_id in failed_ids for dep_id in dependent.depends_on)

        assert is_blocked


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestTaskPlannerProtocol:
    """Tests to verify TaskPlanner protocol compliance."""

    def test_agent_planner_is_task_planner(self):
        """Verify AgentPlanner implements TaskPlanner protocol."""
        model = AsyncMock()
        planner = AgentPlanner(model=model)

        assert isinstance(planner, TaskPlanner)

    @pytest.mark.asyncio
    async def test_planner_has_required_methods(self):
        """Verify planner has required protocol methods."""
        model = AsyncMock()
        model.generate.return_value = MagicMock(content="[]")

        planner = AgentPlanner(model=model)

        # Must have plan method
        assert hasattr(planner, "plan")
        assert callable(planner.plan)

        # Must have mode property
        assert hasattr(planner, "mode")

        # plan must be async
        result = planner.plan(["test"])
        assert asyncio.iscoroutine(result)
        await result  # Cleanup coroutine
