"""Unit tests for Naaru planners."""

from unittest.mock import AsyncMock, Mock

import pytest

from sunwell.planning.naaru.planners.agent import AgentPlanner
from sunwell.planning.naaru.planners.protocol import PlanningError, PlanningStrategy, TaskPlanner
from sunwell.planning.naaru.types import Task, TaskMode, TaskStatus


class TestTaskPlannerProtocol:
    """Test TaskPlanner protocol."""

    def test_task_planner_is_protocol(self) -> None:
        """Test TaskPlanner is a Protocol."""
        # Protocol types can't be instantiated directly
        assert hasattr(TaskPlanner, "__protocol_methods__") or callable(getattr(TaskPlanner, "plan", None))


class TestPlanningStrategy:
    """Test PlanningStrategy enum."""

    def test_planning_strategy_values(self) -> None:
        """Test PlanningStrategy has expected values."""
        assert PlanningStrategy.SEQUENTIAL.value == "sequential"
        assert PlanningStrategy.CONTRACT_FIRST.value == "contract_first"
        assert PlanningStrategy.RESOURCE_AWARE.value == "resource_aware"
        assert PlanningStrategy.ARTIFACT_FIRST.value == "artifact_first"
        assert PlanningStrategy.HARMONIC.value == "harmonic"

    def test_planning_strategy_from_string(self) -> None:
        """Test PlanningStrategy can be created from string."""
        assert PlanningStrategy("sequential") == PlanningStrategy.SEQUENTIAL
        assert PlanningStrategy("contract_first") == PlanningStrategy.CONTRACT_FIRST


class TestPlanningError:
    """Test PlanningError exception."""

    def test_planning_error_creation(self) -> None:
        """Test PlanningError can be created."""
        error = PlanningError("Test planning error")
        assert str(error) == "Test planning error"
        assert isinstance(error, Exception)

    def test_planning_error_with_context(self) -> None:
        """Test PlanningError can be created with message."""
        error = PlanningError("Planning failed")
        assert "Planning failed" in str(error)
        assert isinstance(error, Exception)


class TestAgentPlanner:
    """Test AgentPlanner."""

    def test_agent_planner_creation(self) -> None:
        """Test AgentPlanner can be created."""
        mock_model = Mock()
        planner = AgentPlanner(
            model=mock_model,
            available_tools=frozenset(["write_file"]),
            strategy=PlanningStrategy.SEQUENTIAL,
        )
        assert planner.model == mock_model
        assert "write_file" in planner.available_tools
        assert planner.strategy == PlanningStrategy.SEQUENTIAL

    def test_agent_planner_defaults(self) -> None:
        """Test AgentPlanner default values."""
        mock_model = Mock()
        planner = AgentPlanner(model=mock_model)
        
        assert planner.max_subtasks == 20
        assert planner.max_planning_attempts == 3
        assert planner.strategy == PlanningStrategy.CONTRACT_FIRST  # RFC-034 default

    @pytest.mark.asyncio
    async def test_agent_planner_plan_method_exists(self) -> None:
        """Test AgentPlanner has plan method."""
        mock_model = Mock()
        planner = AgentPlanner(model=mock_model)
        
        # Verify plan method exists and is async
        assert hasattr(planner, "plan")
        assert callable(planner.plan)
        
        # Method should be async (can't easily test without full implementation)
        import inspect
        assert inspect.iscoroutinefunction(planner.plan)

    def test_agent_planner_with_tool_definitions(self) -> None:
        """Test AgentPlanner with tool definitions."""
        mock_model = Mock()
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        
        planner = AgentPlanner(
            model=mock_model,
            tool_definitions=(mock_tool,),
        )
        assert len(planner.tool_definitions) == 1
        assert planner.tool_definitions[0].name == "test_tool"
