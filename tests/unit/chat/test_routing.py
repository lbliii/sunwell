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
