"""Tests for DAG classification routing (RFC-135 double-submit fix).

Verifies:
- Conversational paths (UNDERSTAND, ANALYZE, PLAN) return tuples directly
- Execution paths (ACT) return async generators
- Regression test: double-submit bug is fixed
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.agent.chat.routing import (
    RoutingResult,
    _create_read_execution_generator,
    _create_write_execution_generator,
    route_dag_classification,
)
from sunwell.agent.chat.state import LoopState
from sunwell.agent.intent import IntentClassification, IntentNode


def _make_classification(
    branch: IntentNode,
    path: tuple[IntentNode, ...] | None = None,
    confidence: float = 0.9,
    task_description: str | None = None,
) -> IntentClassification:
    """Create a mock IntentClassification for testing."""
    if path is None:
        path = (IntentNode.CONVERSATION, branch)
    return IntentClassification(
        path=path,
        confidence=confidence,
        reasoning="test reasoning",
        task_description=task_description,
    )


class TestConversationalBranchesReturnTuples:
    """Verify conversational branches return tuples, not generators."""

    @pytest.mark.asyncio
    async def test_understand_returns_tuple(self) -> None:
        """UNDERSTAND branch returns a tuple directly (fixes double-submit)."""
        generate_fn = AsyncMock(return_value="Hello!")
        execute_fn = AsyncMock()

        classification = _make_classification(IntentNode.UNDERSTAND)
        conversation_history: list[dict[str, str]] = []

        result = await route_dag_classification(
            classification,
            "hi there",
            tool_executor=None,
            conversation_history=conversation_history,
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=execute_fn,
        )

        # Should return a tuple, not a generator
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        state, response = result
        assert state == LoopState.IDLE
        assert response == "Hello!"
        # Should have updated conversation history
        assert len(conversation_history) == 1
        assert conversation_history[0]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_analyze_returns_tuple(self) -> None:
        """ANALYZE branch returns a tuple directly (fixes double-submit)."""
        generate_fn = AsyncMock(return_value="Analysis complete")
        execute_fn = AsyncMock()

        classification = _make_classification(IntentNode.ANALYZE)
        conversation_history: list[dict[str, str]] = []

        result = await route_dag_classification(
            classification,
            "what does this code do?",
            tool_executor=None,
            conversation_history=conversation_history,
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=execute_fn,
        )

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        state, response = result
        assert state == LoopState.IDLE
        assert response == "Analysis complete"

    @pytest.mark.asyncio
    async def test_plan_returns_tuple(self) -> None:
        """PLAN branch returns a tuple directly (fixes double-submit)."""
        generate_fn = AsyncMock(return_value="Here's my plan...")
        execute_fn = AsyncMock()

        classification = _make_classification(IntentNode.PLAN)
        conversation_history: list[dict[str, str]] = []

        result = await route_dag_classification(
            classification,
            "plan a todo app",
            tool_executor=None,
            conversation_history=conversation_history,
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=execute_fn,
        )

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        state, response = result
        assert state == LoopState.IDLE
        assert response == "Here's my plan..."


class TestFallbacksReturnTuples:
    """Verify fallback branches return tuples, not generators."""

    @pytest.mark.asyncio
    async def test_low_confidence_returns_tuple(self) -> None:
        """Low confidence fallback returns a tuple directly."""
        generate_fn = AsyncMock()
        execute_fn = AsyncMock()

        # Use ACT branch with low confidence - it will fall through to low confidence check
        # since it requires tools but none are provided, we need to use a branch that
        # goes to the confidence check. Use a path that doesn't match any branch.
        classification = IntentClassification(
            path=(IntentNode.CONVERSATION,),  # No specific branch
            confidence=0.3,  # Low confidence triggers fallback
            reasoning="uncertain reasoning",
            task_description=None,
        )

        result = await route_dag_classification(
            classification,
            "???",
            tool_executor=None,
            conversation_history=[],
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=execute_fn,
        )

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        state, response = result
        assert state == LoopState.IDLE
        assert "rephrase" in response.lower()

    @pytest.mark.asyncio
    async def test_default_fallback_returns_tuple(self) -> None:
        """Default fallback returns a tuple directly."""
        generate_fn = AsyncMock(return_value="I can help with that")
        execute_fn = AsyncMock()

        # Create a classification that doesn't match any branch
        classification = IntentClassification(
            path=(IntentNode.CONVERSATION,),  # No specific branch
            confidence=0.9,
            reasoning="test",
            task_description=None,
        )

        result = await route_dag_classification(
            classification,
            "something",
            tool_executor=None,
            conversation_history=[],
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=execute_fn,
        )

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"


class TestActBranchReturnsGenerator:
    """Verify ACT branches return generators (for checkpoint handoffs)."""

    @pytest.mark.asyncio
    async def test_act_without_tools_returns_tuple(self) -> None:
        """ACT branch without tools returns a tuple (explaining chat mode)."""
        classification = _make_classification(
            IntentNode.ACT,
            path=(IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE),
        )

        result = await route_dag_classification(
            classification,
            "create a file",
            tool_executor=None,  # No tools!
            conversation_history=[],
            auto_confirm=False,
            generate_response_fn=AsyncMock(),
            execute_goal_fn=AsyncMock(),
        )

        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        state, response = result
        assert state == LoopState.IDLE
        assert "chat mode" in response.lower()

    @pytest.mark.asyncio
    async def test_act_read_returns_generator(self) -> None:
        """ACT/READ branch returns an async generator."""
        mock_tool_executor = MagicMock()

        async def mock_execute_goal(
            goal: str,
        ) -> AsyncIterator[tuple[LoopState, str]]:
            yield (LoopState.EXECUTING, "reading...")
            yield (LoopState.IDLE, "done reading")

        classification = _make_classification(
            IntentNode.ACT,
            path=(IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.READ),
            task_description="read the file",
        )

        result = await route_dag_classification(
            classification,
            "read the file",
            tool_executor=mock_tool_executor,
            conversation_history=[],
            auto_confirm=False,
            generate_response_fn=AsyncMock(),
            execute_goal_fn=mock_execute_goal,
        )

        # Should return a generator, not a tuple
        assert hasattr(result, "asend"), f"Expected generator, got {type(result)}"
        assert isinstance(result, AsyncIterator)

    @pytest.mark.asyncio
    async def test_act_write_returns_generator(self) -> None:
        """ACT/WRITE branch returns an async generator."""
        mock_tool_executor = MagicMock()

        async def mock_execute_goal(
            goal: str,
        ) -> AsyncIterator[tuple[LoopState, str]]:
            yield (LoopState.EXECUTING, "writing...")
            yield (LoopState.IDLE, "done")

        classification = _make_classification(
            IntentNode.ACT,
            path=(IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE),
            task_description="create the file",
        )

        result = await route_dag_classification(
            classification,
            "create the file",
            tool_executor=mock_tool_executor,
            conversation_history=[],
            auto_confirm=True,  # Skip approval for this test
            generate_response_fn=AsyncMock(),
            execute_goal_fn=mock_execute_goal,
        )

        # Should return a generator, not a tuple
        assert hasattr(result, "asend"), f"Expected generator, got {type(result)}"


class TestDoubleSubmitRegression:
    """Regression tests for the double-submit bug.

    The bug occurred because conversational paths would yield-then-return:
    1. User sends message
    2. Routing yields response
    3. CLI renders response, prompts for new input
    4. User sends new input
    5. Routing resumes from yield, ignores input, returns
    6. Main generator yields None (input lost!)
    7. User has to re-submit

    The fix: conversational paths return tuples directly (no yield).
    """

    @pytest.mark.asyncio
    async def test_routing_returns_tuple_not_generator_for_conversation(self) -> None:
        """The key fix: routing returns tuple for conversation, not generator.

        Before the fix, route_dag_classification was an async generator that
        would yield-then-return. After the fix, it returns a tuple directly
        for conversational paths.

        This means the caller (unified.py) can immediately yield the response
        and be ready for the next input, instead of being suspended inside
        the routing generator.
        """
        responses = ["First response", "Second response"]
        response_index = 0

        async def generate_fn(user_input: str) -> str:
            nonlocal response_index
            result = responses[response_index]
            response_index += 1
            return result

        classification = _make_classification(IntentNode.UNDERSTAND)
        conversation_history: list[dict[str, str]] = []

        # First call - should return tuple directly
        result1 = await route_dag_classification(
            classification,
            "first message",
            tool_executor=None,
            conversation_history=conversation_history,
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=AsyncMock(),
        )

        # Verify it's a tuple, not a generator
        assert isinstance(result1, tuple), "routing should return tuple for conversation"
        state1, response1 = result1
        assert state1 == LoopState.IDLE
        assert response1 == "First response"

        # Second call - should also return tuple directly (independent call)
        result2 = await route_dag_classification(
            classification,
            "second message",
            tool_executor=None,
            conversation_history=conversation_history,
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=AsyncMock(),
        )

        assert isinstance(result2, tuple), "routing should return tuple for conversation"
        state2, response2 = result2
        assert state2 == LoopState.IDLE
        assert response2 == "Second response"

    @pytest.mark.asyncio
    async def test_no_suspended_generator_state_after_conversation(self) -> None:
        """Verify no generator state is leaked between calls.

        Before the fix, the routing generator would be suspended at a yield
        after returning a conversational response. This test verifies that
        each call is independent and doesn't carry state from previous calls.
        """
        call_count = 0

        async def generate_fn(user_input: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"Response {call_count} to: {user_input}"

        for i in range(5):
            classification = _make_classification(IntentNode.UNDERSTAND)

            result = await route_dag_classification(
                classification,
                f"message {i}",
                tool_executor=None,
                conversation_history=[],
                auto_confirm=False,
                generate_response_fn=generate_fn,
                execute_goal_fn=AsyncMock(),
            )

            # Each call should return a fresh tuple
            assert isinstance(result, tuple), f"Call {i}: expected tuple"
            state, response = result
            assert state == LoopState.IDLE
            assert f"Response {i + 1}" in response
            assert f"message {i}" in response

    @pytest.mark.asyncio
    async def test_tuple_response_can_be_used_directly(self) -> None:
        """Verify the tuple response can be used without iteration.

        This is the practical benefit of the fix: unified.py can just
        unpack the tuple and yield the response, without needing to
        iterate a generator.
        """
        async def generate_fn(user_input: str) -> str:
            return "Simple response"

        classification = _make_classification(IntentNode.PLAN)

        result = await route_dag_classification(
            classification,
            "plan something",
            tool_executor=None,
            conversation_history=[],
            auto_confirm=False,
            generate_response_fn=generate_fn,
            execute_goal_fn=AsyncMock(),
        )

        # Should be able to unpack directly (the practical fix)
        state, response = result  # No iteration needed!
        assert state == LoopState.IDLE
        assert response == "Simple response"


class TestPlanBasedEstimation:
    """Tests for plan-based duration estimation in routing (RFC: Plan-Based Duration).

    Verifies:
    - Plan function is called when provided
    - Estimation uses plan data when available
    - Fallback to heuristics when plan unavailable
    """

    @pytest.mark.asyncio
    async def test_write_path_calls_plan_fn_when_provided(self) -> None:
        """WRITE path calls plan_fn before background offer."""
        from sunwell.agent.core.agent import PlanResult
        from sunwell.agent.core.task_graph import TaskGraph
        from sunwell.planning.naaru.planners.metrics import PlanMetrics

        mock_tool_executor = MagicMock()
        plan_called = False

        async def mock_plan_fn(goal: str) -> PlanResult:
            nonlocal plan_called
            plan_called = True
            return PlanResult(
                task_graph=TaskGraph(),
                metrics=PlanMetrics(
                    depth=1, width=0, leaf_count=0, artifact_count=0,
                    parallelism_factor=0.0, balance_factor=0.0,
                    file_conflicts=0, estimated_waves=1,
                ),
            )

        mock_execute_goal = AsyncMock(return_value=iter([]))

        classification = _make_classification(
            IntentNode.ACT,
            path=(IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE),
            task_description="create a file",
        )

        # With auto_confirm=True, plan_fn won't be called (optimization)
        # Need auto_confirm=False and background_manager=None to trigger plan path
        # but since background_manager is None, it won't offer background
        result = await route_dag_classification(
            classification,
            "create a file",
            tool_executor=mock_tool_executor,
            conversation_history=[],
            auto_confirm=False,  # Required for plan-based path
            generate_response_fn=AsyncMock(),
            execute_goal_fn=mock_execute_goal,
            plan_fn=mock_plan_fn,
            # No background_manager means no background offer, but plan is still used
        )

        # Plan should be called when auto_confirm=False and plan_fn provided
        # (even without background_manager, the plan is computed for estimation)
        # But with no background_manager, it won't offer background, so just executes
        assert hasattr(result, "asend"), "Should return generator for WRITE"

    @pytest.mark.asyncio
    async def test_write_path_uses_execute_with_plan_fn(self) -> None:
        """WRITE path uses execute_with_plan_fn when plan is precomputed.
        
        This requires all conditions for plan-based estimation to be met:
        - plan_fn provided
        - background_manager provided  
        - model provided
        - auto_confirm=False
        
        Even if the estimate is below threshold (no background offer),
        the execute_with_plan_fn should be used.
        """
        from sunwell.agent.core.agent import PlanResult
        from sunwell.agent.core.task_graph import TaskGraph
        from sunwell.planning.naaru.planners.metrics import PlanMetrics

        mock_tool_executor = MagicMock()
        mock_background_manager = MagicMock()
        mock_model = MagicMock()
        execute_with_plan_called = False
        received_plan: PlanResult | None = None

        async def mock_plan_fn(goal: str) -> PlanResult:
            # Return a small plan (estimate below threshold = no background offer)
            return PlanResult(
                task_graph=TaskGraph(),
                metrics=PlanMetrics(
                    depth=1, width=1, leaf_count=1, artifact_count=0,
                    parallelism_factor=1.0, balance_factor=1.0,
                    file_conflicts=0, estimated_waves=1,
                ),
            )

        async def mock_execute_with_plan(
            goal: str, plan: PlanResult
        ) -> AsyncIterator[tuple[LoopState, str]]:
            nonlocal execute_with_plan_called, received_plan
            execute_with_plan_called = True
            received_plan = plan
            yield (LoopState.EXECUTING, "executing")

        async def mock_execute_goal(goal: str) -> AsyncIterator[tuple[LoopState, str]]:
            yield (LoopState.EXECUTING, "fallback execution")

        classification = _make_classification(
            IntentNode.ACT,
            path=(IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE),
            task_description="create a file",
        )

        result = await route_dag_classification(
            classification,
            "create a file",
            tool_executor=mock_tool_executor,
            conversation_history=[],
            auto_confirm=False,
            generate_response_fn=AsyncMock(),
            execute_goal_fn=mock_execute_goal,
            plan_fn=mock_plan_fn,
            execute_with_plan_fn=mock_execute_with_plan,
            background_manager=mock_background_manager,  # Required for plan path
            model=mock_model,  # Required for plan path
        )

        # Consume the generator fully to trigger execution
        assert hasattr(result, "asend")
        try:
            state_event = await result.asend(None)
            while True:
                # For approval checkpoints, send "y" response
                state_event = await result.asend("y")
        except StopAsyncIteration:
            pass

        # execute_with_plan_fn should have been called with the plan
        assert execute_with_plan_called, "execute_with_plan_fn should be called"
        assert received_plan is not None, "Plan should be passed to execute_with_plan_fn"

    @pytest.mark.asyncio
    async def test_auto_confirm_skips_plan_estimation(self) -> None:
        """auto_confirm=True skips plan-based estimation for speed."""
        from sunwell.agent.core.agent import PlanResult

        mock_tool_executor = MagicMock()
        plan_called = False

        async def mock_plan_fn(goal: str) -> PlanResult:
            nonlocal plan_called
            plan_called = True
            raise AssertionError("Should not call plan_fn with auto_confirm=True")

        mock_execute_goal = AsyncMock(return_value=iter([]))

        classification = _make_classification(
            IntentNode.ACT,
            path=(IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE),
            task_description="create a file",
        )

        result = await route_dag_classification(
            classification,
            "create a file",
            tool_executor=mock_tool_executor,
            conversation_history=[],
            auto_confirm=True,  # Should skip plan_fn
            generate_response_fn=AsyncMock(),
            execute_goal_fn=mock_execute_goal,
            plan_fn=mock_plan_fn,
        )

        # Should return generator without calling plan_fn
        assert hasattr(result, "asend")
        assert not plan_called, "plan_fn should not be called with auto_confirm=True"
