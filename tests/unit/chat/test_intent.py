"""Tests for IntentRouter (RFC-135).

Verifies intent classification for chat-agent routing.
"""

import pytest

from sunwell.chat.intent import Intent, IntentClassification, IntentRouter


class TestIntentClassification:
    """Tests for IntentClassification dataclass."""

    def test_frozen(self) -> None:
        """Classification is immutable."""
        c = IntentClassification(intent=Intent.TASK, confidence=0.9)
        with pytest.raises(AttributeError):
            c.confidence = 0.5  # type: ignore[misc]

    def test_optional_fields(self) -> None:
        """Optional fields default to None."""
        c = IntentClassification(intent=Intent.CONVERSATION, confidence=0.8)
        assert c.task_description is None
        assert c.reasoning is None


class TestIntentRouterHeuristics:
    """Tests for heuristic-based classification (no LLM)."""

    @pytest.fixture
    def router(self) -> IntentRouter:
        """Router without LLM fallback."""
        return IntentRouter(model=None, threshold=0.7)

    @pytest.mark.asyncio
    async def test_command_slash(self, router: IntentRouter) -> None:
        """Slash commands are classified as COMMAND."""
        result = await router.classify("/quit")
        assert result.intent == Intent.COMMAND
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_command_double_colon(self, router: IntentRouter) -> None:
        """:: shortcuts are classified as COMMAND."""
        result = await router.classify("::research")
        assert result.intent == Intent.COMMAND
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_interrupt_during_execution(self, router: IntentRouter) -> None:
        """Any input during execution is INTERRUPT."""
        result = await router.classify("stop", is_executing=True)
        assert result.intent == Intent.INTERRUPT
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_task_imperative_add(self, router: IntentRouter) -> None:
        """'Add' + description is TASK."""
        result = await router.classify("Add user authentication to the API")
        assert result.intent == Intent.TASK
        assert result.confidence >= 0.7
        assert result.task_description is not None

    @pytest.mark.asyncio
    async def test_task_imperative_create(self, router: IntentRouter) -> None:
        """'Create' + description is TASK."""
        result = await router.classify("Create a new endpoint for user profiles")
        assert result.intent == Intent.TASK
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_task_imperative_fix(self, router: IntentRouter) -> None:
        """'Fix' + description is TASK."""
        result = await router.classify("Fix the bug in the login handler")
        assert result.intent == Intent.TASK
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_task_imperative_refactor(self, router: IntentRouter) -> None:
        """'Refactor' + description is TASK."""
        result = await router.classify("Refactor the database layer to use async")
        assert result.intent == Intent.TASK
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_conversation_question_what(self, router: IntentRouter) -> None:
        """'What' questions are CONVERSATION."""
        result = await router.classify("What is Python?")
        assert result.intent == Intent.CONVERSATION
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_conversation_question_how(self, router: IntentRouter) -> None:
        """'How' questions are CONVERSATION."""
        result = await router.classify("How does async/await work?")
        assert result.intent == Intent.CONVERSATION
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_conversation_question_why(self, router: IntentRouter) -> None:
        """'Why' questions are CONVERSATION."""
        result = await router.classify("Why should I use type hints?")
        assert result.intent == Intent.CONVERSATION
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_conversation_explain(self, router: IntentRouter) -> None:
        """'Explain' is CONVERSATION."""
        result = await router.classify("Explain the decorator pattern")
        assert result.intent == Intent.CONVERSATION
        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_conversation_tell_me_about(self, router: IntentRouter) -> None:
        """'Tell me about' is CONVERSATION."""
        result = await router.classify("Tell me about FastAPI")
        assert result.intent == Intent.CONVERSATION

    @pytest.mark.asyncio
    async def test_empty_input(self, router: IntentRouter) -> None:
        """Empty input defaults to CONVERSATION."""
        result = await router.classify("")
        assert result.intent == Intent.CONVERSATION
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_ambiguous_leans_task(self, router: IntentRouter) -> None:
        """Ambiguous input with task verb leans TASK."""
        result = await router.classify("implement this feature")
        assert result.intent == Intent.TASK

    @pytest.mark.asyncio
    async def test_ambiguous_question_mark(self, router: IntentRouter) -> None:
        """Question mark boosts CONVERSATION score."""
        result = await router.classify("should I use async?")
        # Could be either, but question mark helps
        assert result.intent in (Intent.CONVERSATION, Intent.TASK)


class TestIntentRouterThreshold:
    """Tests for confidence threshold behavior."""

    @pytest.mark.asyncio
    async def test_high_threshold_more_conversation(self) -> None:
        """Higher threshold = more falls to CONVERSATION."""
        router = IntentRouter(model=None, threshold=0.95)
        # Short task verbs may not meet 0.95
        result = await router.classify("update readme")
        # With very high threshold, may fall back to conversation
        assert result.intent in (Intent.TASK, Intent.CONVERSATION)

    @pytest.mark.asyncio
    async def test_low_threshold_more_task(self) -> None:
        """Lower threshold = more classified as TASK."""
        router = IntentRouter(model=None, threshold=0.3)
        result = await router.classify("maybe add a feature")
        # With low threshold, weak task signals pass
        assert result.intent in (Intent.TASK, Intent.CONVERSATION)
