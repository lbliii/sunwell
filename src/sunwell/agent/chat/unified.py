"""Unified chat-agent loop (RFC-135).

The UnifiedChatLoop manages seamless transitions between conversation and
agent execution modes. It uses an async generator pattern for checkpoint-based
handoffs between the loop and the UI.

Key responsibilities:
1. Intent classification (conversation vs task)
2. Conversation response generation
3. Agent planning and execution with checkpoints
4. Mid-execution interruption handling
5. Graceful error recovery
6. Adaptive trust management (progressive autonomy)

Usage:
    >>> loop = UnifiedChatLoop(model, tool_executor, workspace)
    >>> gen = loop.run()
    >>> await gen.asend(None)  # Initialize
    >>> result = await gen.asend("Add user auth")
    >>> while isinstance(result, ChatCheckpoint):
    ...     response = handle_checkpoint(result)
    ...     result = await gen.asend(response)

Thread Safety:
    Not thread-safe. Use one loop per conversation.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.chat.checkpoint import (
    ChatCheckpoint,
    ChatCheckpointType,
    CheckpointResponse,
)
from sunwell.agent.chat.commands import (
    handle_background_command,
    handle_command,
    handle_resume_command,
    handle_rewind_command,
    handle_session_command,
    handle_tools_command,
)
from sunwell.agent.chat.conversation import (
    generate_response,
    get_conversation_context,
)
from sunwell.agent.chat.execution import GoalExecutor
from sunwell.agent.chat.routing import route_dag_classification
from sunwell.agent.chat.state import LoopState, MAX_HISTORY_SIZE
from sunwell.agent.events import AgentEvent
from sunwell.agent.intent import (
    DAGClassifier,
    IntentNode,
    format_path,
)
from sunwell.agent.background import BackgroundManager
from sunwell.agent.rewind import SnapshotManager
from sunwell.agent.trust import ApprovalTracker, AutoApproveConfig

if TYPE_CHECKING:
    from sunwell.agent.context.session import SessionContext
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor

logger = logging.getLogger(__name__)


class UnifiedChatLoop:
    """Unified chat-agent experience with seamless transitions.

    Manages the state machine between conversation and agent modes,
    yielding user-facing ChatCheckpoints at handoff points.

    The loop uses an async generator pattern:
    - Yields responses, checkpoints, and progress events
    - Receives user input via asend()
    - Handles interruptions during execution

    Example:
        >>> loop = UnifiedChatLoop(model, executor, workspace)
        >>> gen = loop.run()
        >>> await gen.asend(None)  # Initialize
        >>> result = await gen.asend("What is Python?")
        >>> # result is a string (conversation response)
        >>> result = await gen.asend("Create a hello.py file")
        >>> # result is ChatCheckpoint(type=CONFIRMATION, ...)
    """

    def __init__(
        self,
        model: ModelProtocol,
        tool_executor: ToolExecutor | None,
        workspace: Path,
        *,
        trust_level: str = "workspace",
        auto_confirm: bool = False,
        stream_progress: bool = True,
    ) -> None:
        """Initialize the unified chat loop.

        Args:
            model: LLM for generation
            tool_executor: Executor for tools (file I/O, commands, etc.)
            workspace: Working directory
            trust_level: Trust level for tool execution (default "workspace")
            auto_confirm: Skip confirmation checkpoints (for testing/CI)
            stream_progress: Yield AgentEvents during execution
        """
        self.model = model
        self.tool_executor = tool_executor
        self.workspace = Path(workspace).resolve()
        self.trust_level = trust_level
        self.auto_confirm = auto_confirm
        self.stream_progress = stream_progress

        # DAG classifier (RFC: Conversational DAG Architecture)
        self.classifier = DAGClassifier(model=model)

        # Shared state (survives mode switches)
        self.conversation_history: list[dict[str, str]] = []
        self.session: SessionContext | None = None
        self.memory: PersistentMemory | None = None

        # Current DAG path (for display and navigation)
        self._current_dag_path: tuple[IntentNode, ...] | None = None
        self._previous_dag_path: tuple[IntentNode, ...] | None = None

        # Execution state
        self._state = LoopState.IDLE
        self._pending_input: asyncio.Queue[str] = asyncio.Queue()
        self._goal_executor: GoalExecutor | None = None
        self._cancel_requested = False

        # Adaptive trust system (progressive autonomy)
        self._approval_tracker = ApprovalTracker(workspace=self.workspace)
        self._auto_approve_config = AutoApproveConfig(workspace=self.workspace)

        # Code state rewind system
        self._snapshot_manager = SnapshotManager(workspace=self.workspace)
        self._snapshot_taken_this_turn = False  # Track if we've already snapshotted

        # Background task manager
        self._background_manager = BackgroundManager(workspace=self.workspace)

    @property
    def is_executing(self) -> bool:
        """True if agent is currently executing tasks."""
        return self._state in (LoopState.PLANNING, LoopState.EXECUTING)

    @property
    def state(self) -> LoopState:
        """Current loop state (for UI display)."""
        return self._state

    def request_cancel(self) -> None:
        """Request graceful cancellation of current execution."""
        self._cancel_requested = True
        if self._goal_executor:
            self._goal_executor.request_cancel()

    def _clear_pending_input(self) -> None:
        """Clear any pending input from the queue."""
        while not self._pending_input.empty():
            try:
                self._pending_input.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _trim_history(self) -> None:
        """Trim conversation history to prevent unbounded growth."""
        if len(self.conversation_history) > MAX_HISTORY_SIZE:
            self.conversation_history = self.conversation_history[-MAX_HISTORY_SIZE:]

    async def _generate_response(
        self,
        user_input: str,
        execution_context: dict[str, Any] | None = None,
    ) -> str:
        """Generate conversational response."""
        return await generate_response(
            self.model,
            user_input,
            self.conversation_history,
            self.workspace,
            execution_context,
        )

    async def _execute_goal(
        self,
        goal: str,
    ) -> AsyncIterator[str | ChatCheckpoint | AgentEvent]:
        """Execute a goal with checkpoints and optional progress streaming."""
        from sunwell.agent.context.session import SessionContext

        if self.tool_executor is None:
            logger.warning("No tool executor available for goal execution")
            yield (
                "I understand you want me to do something, but I'm in **chat mode** "
                "(tools disabled). Use `/tools on` to enable agent mode, or rephrase "
                "as a question."
            )
            return

        self._state = LoopState.PLANNING

        # Create goal executor
        self._goal_executor = GoalExecutor(
            model=self.model,
            tool_executor=self.tool_executor,
            workspace=self.workspace,
            auto_confirm=self.auto_confirm,
            stream_progress=self.stream_progress,
        )

        # Create session
        self.session = SessionContext.build(self.workspace, goal, None)

        try:
            # Execute goal and forward events
            gen = self._goal_executor.execute(
                goal,
                self.session,
                self.memory,
                self.conversation_history,
                self._generate_response,
            )

            try:
                result = await gen.asend(None)
                while True:
                    state, event = result
                    self._state = state
                    # Single-yield protocol: yield event, receive response, forward to executor
                    response = yield event
                    result = await gen.asend(response)
            except StopAsyncIteration:
                pass

        finally:
            self._goal_executor = None
            self._state = LoopState.IDLE

    def _handle_command(self, command: str) -> tuple[str | None, str | None]:
        """Handle /slash commands."""
        response, goal = handle_command(
            command,
            self._state,
            self.tool_executor,
            self.conversation_history,
            self.request_cancel,
            self._snapshot_manager,
        )

        # Handle special /tools command
        if response and response.startswith("__TOOLS_COMMAND__:"):
            arg = response.split(":", 1)[1]
            msg, new_executor = handle_tools_command(
                arg,
                self.workspace,
                self.trust_level,
                self.tool_executor,
            )
            self.tool_executor = new_executor
            return (msg, None)

        # Handle special /rewind command
        if response and response.startswith("__REWIND_COMMAND__:"):
            arg = response.split(":", 1)[1]
            msg = handle_rewind_command(
                arg,
                self._snapshot_manager,
                self.conversation_history,
            )
            return (msg, None)

        # Handle special /background command
        if response and response.startswith("__BACKGROUND_COMMAND__:"):
            arg = response.split(":", 1)[1]
            msg = handle_background_command(arg, self._background_manager)
            return (msg, None)

        # Handle special /resume command
        if response and response.startswith("__RESUME_COMMAND__:"):
            arg = response.split(":", 1)[1]
            msg = handle_resume_command(arg, self._background_manager)
            return (msg, None)

        # Handle special /session command
        if response and response.startswith("__SESSION_COMMAND__:"):
            arg = response.split(":", 1)[1]
            msg = handle_session_command(arg, self)
            return (msg, None)

        return (response, goal)

    async def run(
        self,
    ) -> AsyncIterator[str | ChatCheckpoint | AgentEvent]:
        """Main loop - yields responses, checkpoints, and optionally progress events.

        This is an async generator. Initialize with asend(None), then send user
        input via asend(user_input). The generator yields:
        - str: Conversational response
        - ChatCheckpoint: User decision point (confirmation, failure, etc.)
        - AgentEvent: Progress event (if stream_progress=True)

        Usage:
            gen = loop.run()
            await gen.asend(None)  # Initialize

            while True:
                result = await gen.asend(user_input)
                if isinstance(result, ChatCheckpoint):
                    response = get_user_choice(result)
                    result = await gen.asend(response)
                elif isinstance(result, AgentEvent):
                    display_progress(result)
                else:
                    display_response(result)

        Yields:
            str: Conversational response
            ChatCheckpoint: User decision point
            AgentEvent: Progress event (if stream_progress=True)

        Raises:
            GeneratorExit: On aclose() call
        """
        from sunwell.agent.context.session import SessionContext
        from sunwell.memory import PersistentMemory

        # Initialize session and memory
        self.session = SessionContext.build(self.workspace, "", None)
        self.memory = PersistentMemory.load(self.workspace)
        self._state = LoopState.IDLE

        try:
            while True:
                # Get user input (via asend)
                user_input: str | CheckpointResponse | None = yield
                logger.debug(
                    "Loop received input: type=%s, value=%r",
                    type(user_input).__name__,
                    user_input[:50] if isinstance(user_input, str) else user_input,
                )

                # Handle None (initialization or continue after event)
                if user_input is None:
                    logger.debug("Input is None, continuing")
                    continue

                # Handle CheckpointResponse (from checkpoint interaction)
                if isinstance(user_input, CheckpointResponse):
                    logger.debug("Received CheckpointResponse, continuing")
                    continue

                # Handle empty/whitespace input
                if not user_input or not user_input.strip():
                    logger.debug("Empty or whitespace input, skipping")
                    continue

                # Handle cancellation request
                if self._cancel_requested:
                    logger.debug("Cancellation requested, resetting")
                    self._cancel_requested = False
                    self._state = LoopState.IDLE
                    yield "Execution cancelled."
                    continue

                # Add to conversation history (with size limit)
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input,
                })
                self._trim_history()

                # Handle input during execution (interruption)
                if self.is_executing:
                    logger.debug("Input during execution, queueing as interrupt")
                    await self._pending_input.put(user_input)
                    continue

                # Check for explicit /command first
                if user_input.strip().startswith("/") or user_input.strip().startswith(
                    "::"
                ):
                    response, agent_goal = self._handle_command(user_input)
                    if agent_goal:
                        # Manual iteration to forward checkpoint responses
                        goal_gen = self._execute_goal(agent_goal)
                        try:
                            event = await goal_gen.asend(None)
                            while True:
                                resp = yield event
                                event = await goal_gen.asend(resp)
                        except StopAsyncIteration:
                            pass
                    elif response:
                        yield response
                    self._state = LoopState.IDLE
                    continue

                # Classify intent using DAG classifier
                self._state = LoopState.CLASSIFYING
                logger.debug("Classifying intent for: %r", user_input[:100])

                result = await self.classifier.classify(
                    user_input,
                    context=get_conversation_context(self.conversation_history),
                )
                # Track path change for NODE_TRANSITION events
                old_path = self._current_dag_path
                self._previous_dag_path = old_path
                self._current_dag_path = result.path

                logger.debug(
                    "DAG classification: path=%s (confidence=%.2f, reason=%s)",
                    format_path(result.path),
                    result.confidence,
                    result.reasoning,
                )

                # Emit hook for intent classification
                from sunwell.agent.hooks import HookEvent, emit_hook_sync

                emit_hook_sync(
                    HookEvent.INTENT_CLASSIFIED,
                    path=[n.value for n in result.path],
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    user_input=user_input,
                )

                # Emit NODE_TRANSITION if path changed
                if old_path is not None and old_path != result.path:
                    from_node = old_path[-1].value if old_path else "idle"
                    to_node = result.path[-1].value if result.path else "idle"
                    emit_hook_sync(
                        HookEvent.NODE_TRANSITION,
                        from_node=from_node,
                        to_node=to_node,
                        old_path=[n.value for n in old_path],
                        new_path=[n.value for n in result.path],
                    )

                # Increment conversation turn for snapshot tracking
                conversation_turn = self._snapshot_manager.increment_turn()
                self._snapshot_taken_this_turn = False

                # Route based on DAG path
                route_gen = route_dag_classification(
                    result,
                    user_input,
                    tool_executor=self.tool_executor,
                    conversation_history=self.conversation_history,
                    auto_confirm=self.auto_confirm,
                    generate_response_fn=self._generate_response,
                    execute_goal_fn=self._execute_goal_wrapped,
                    workspace=self.workspace,
                    approval_tracker=self._approval_tracker,
                    auto_approve_config=self._auto_approve_config,
                    snapshot_manager=self._snapshot_manager,
                    conversation_turn=conversation_turn,
                    background_manager=self._background_manager,
                    model=self.model,
                    memory=self.memory,
                )
                try:
                    route_result = await route_gen.asend(None)
                    while True:
                        state, event = route_result
                        self._state = state
                        # Single-yield protocol: yield event, receive response, forward to routing
                        response = yield event
                        route_result = await route_gen.asend(response)
                except StopAsyncIteration:
                    pass
                self._state = LoopState.IDLE

        except GeneratorExit:
            # Graceful shutdown via aclose()
            self._state = LoopState.IDLE
            if self.memory:
                self.memory.sync()
        except Exception as e:
            self._state = LoopState.ERROR
            logger.exception("UnifiedChatLoop error")
            yield ChatCheckpoint(
                type=ChatCheckpointType.FAILURE,
                message=f"Unexpected error: {e}",
                error=str(e),
                recovery_options=("retry", "abort"),
                default="abort",
            )

    async def _execute_goal_wrapped(
        self,
        goal: str,
    ) -> AsyncIterator[tuple[LoopState, str | ChatCheckpoint | AgentEvent]]:
        """Wrapped goal execution that yields (state, event) tuples for routing.
        
        Uses manual iteration to properly forward checkpoint responses.
        async for doesn't support asend(), so we iterate manually.
        """
        goal_gen = self._execute_goal(goal)
        try:
            event = await goal_gen.asend(None)
            while True:
                # Yield event with current state, receive response
                response = yield (self._state, event)
                # Forward response to inner generator
                event = await goal_gen.asend(response)
        except StopAsyncIteration:
            pass
