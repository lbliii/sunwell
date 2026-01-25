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
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.chat.checkpoint import (
    ChatCheckpoint,
    ChatCheckpointType,
    CheckpointResponse,
)
from sunwell.agent.chat.intent import Intent, IntentRouter

if TYPE_CHECKING:
    from sunwell.agent import Agent
    from sunwell.agent.events import AgentEvent
    from sunwell.agent.context.session import SessionContext
    from sunwell.memory import PersistentMemory
    from sunwell.models.protocol import ModelProtocol
    from sunwell.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


class LoopState(Enum):
    """State machine for the unified loop."""

    IDLE = "idle"
    """Waiting for user input."""

    CLASSIFYING = "classifying"
    """Analyzing intent."""

    CONVERSING = "conversing"
    """Generating chat response."""

    PLANNING = "planning"
    """Agent creating plan."""

    CONFIRMING = "confirming"
    """Awaiting user confirmation."""

    EXECUTING = "executing"
    """Running tasks."""

    INTERRUPTED = "interrupted"
    """User input during execution."""

    COMPLETED = "completed"
    """Goal finished."""

    ERROR = "error"
    """Unrecoverable error."""


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
        intent_router: IntentRouter | None = None,
        auto_confirm: bool = False,
        stream_progress: bool = True,
    ) -> None:
        """Initialize the unified chat loop.

        Args:
            model: LLM for generation
            tool_executor: Executor for tools (file I/O, commands, etc.)
            workspace: Working directory
            intent_router: Custom intent router (created with model if None)
            auto_confirm: Skip confirmation checkpoints (for testing/CI)
            stream_progress: Yield AgentEvents during execution
        """
        self.model = model
        self.tool_executor = tool_executor
        self.workspace = Path(workspace).resolve()
        self.intent_router = intent_router or IntentRouter(model)
        self.auto_confirm = auto_confirm
        self.stream_progress = stream_progress

        # Shared state (survives mode switches)
        self.conversation_history: list[dict[str, str]] = []
        self.session: SessionContext | None = None
        self.memory: PersistentMemory | None = None

        # Execution state
        self._state = LoopState.IDLE
        self._pending_input: asyncio.Queue[str] = asyncio.Queue()
        self._current_agent: Agent | None = None
        self._cancel_requested = False

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
                # Handle None (initialization or continue after event)
                if user_input is None:
                    continue

                # Handle CheckpointResponse (from checkpoint interaction)
                if isinstance(user_input, CheckpointResponse):
                    # Checkpoint responses are handled in _execute_goal
                    continue

                # Handle cancellation request
                if self._cancel_requested:
                    self._cancel_requested = False
                    self._state = LoopState.IDLE
                    yield "Execution cancelled."
                    continue

                # Add to conversation history
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input,
                })

                # Handle input during execution (interruption)
                if self.is_executing:
                    await self._pending_input.put(user_input)
                    continue

                # Classify intent
                self._state = LoopState.CLASSIFYING
                classification = await self.intent_router.classify(
                    user_input,
                    context=self._get_conversation_context(),
                    is_executing=self.is_executing,
                )

                # Route based on intent
                if classification.intent == Intent.COMMAND:
                    response, agent_goal = self._handle_command(user_input)
                    if agent_goal:
                        # /agent command - execute the goal
                        async for event in self._execute_goal(agent_goal):
                            yield event
                    elif response:
                        yield response
                    self._state = LoopState.IDLE

                elif classification.intent == Intent.TASK:
                    # Transition to agent mode
                    async for event in self._execute_goal(
                        classification.task_description or user_input
                    ):
                        yield event
                    self._state = LoopState.IDLE

                else:  # CONVERSATION
                    self._state = LoopState.CONVERSING
                    response = await self._generate_response(user_input)
                    self._state = LoopState.IDLE
                    yield response
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response,
                    })

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

    async def _execute_goal(
        self,
        goal: str,
    ) -> AsyncIterator[str | ChatCheckpoint | AgentEvent]:
        """Execute a goal with checkpoints and optional progress streaming.

        Flow:
            1. PLANNING: Generate plan via agent.plan()
            2. CONFIRMING: Yield ChatCheckpoint for user approval (unless auto_confirm)
            3. EXECUTING: Run agent.run(), streaming AgentEvents if stream_progress=True
            4. Handle interruptions, failures, completion via ChatCheckpoints
        """
        from sunwell.agent import Agent
        from sunwell.agent.events import AgentEvent, EventType
        from sunwell.agent.context.session import SessionContext

        self._state = LoopState.PLANNING

        # Create agent
        self._current_agent = Agent(
            model=self.model,
            tool_executor=self.tool_executor,
            cwd=self.workspace,
            stream_inference=self.stream_progress,
        )

        try:
            # Update session with goal
            self.session = SessionContext.build(self.workspace, goal, None)

            # Plan first (stream planning events if enabled)
            plan_data: dict[str, Any] | None = None
            async for event in self._current_agent.plan(self.session, self.memory):
                if self.stream_progress:
                    yield event
                if event.type == EventType.PLAN_WINNER:
                    plan_data = event.data

            if not plan_data:
                yield "I couldn't create a plan for that goal."
                return

            # Checkpoint: Confirmation
            self._state = LoopState.CONFIRMING
            if not self.auto_confirm:
                checkpoint = ChatCheckpoint(
                    type=ChatCheckpointType.CONFIRMATION,
                    message=self._format_plan_summary(plan_data),
                    options=("Y", "n", "edit"),
                    default="Y",
                    agent_checkpoint_id=f"plan-{self.session.session_id}",
                    context={"plan": plan_data},
                )
                response: CheckpointResponse = yield checkpoint

                if response.abort:
                    yield "Cancelled."
                    return

                if not response.proceed:
                    yield "Okay, let me know if you'd like to try a different approach."
                    return

            # Execute with checkpoint handling
            self._state = LoopState.EXECUTING
            async for event in self._current_agent.run(self.session, self.memory):
                # Check for cancellation
                if self._cancel_requested:
                    self._cancel_requested = False
                    task_graph = self._current_agent._task_graph
                    completed = len(task_graph.completed_ids) if task_graph else 0
                    yield ChatCheckpoint(
                        type=ChatCheckpointType.COMPLETION,
                        message="Execution cancelled by user",
                        summary=f"Completed {completed} tasks before cancel",
                    )
                    return

                # Check for pending user input (interruption)
                if not self._pending_input.empty():
                    pending_text = await self._pending_input.get()
                    self._state = LoopState.INTERRUPTED

                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.INTERRUPTION,
                        message=f"You said: {pending_text}",
                        options=("respond", "continue", "abort"),
                        default="respond",
                    )
                    response = yield checkpoint

                    if response.abort:
                        yield "Execution aborted."
                        return

                    if response.choice == "respond":
                        # Answer the question with execution context
                        answer = await self._generate_response(
                            pending_text,
                            execution_context=event.data,
                        )
                        yield answer

                    self._state = LoopState.EXECUTING

                # Stream progress events to UI
                if self.stream_progress and event.type in (
                    EventType.TASK_START,
                    EventType.TASK_COMPLETE,
                    EventType.MODEL_TOKENS,
                    EventType.GATE_START,
                    EventType.GATE_PASS,
                ):
                    yield event

                # Handle agent events that require user interaction
                if event.type == EventType.GATE_FAIL:
                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.FAILURE,
                        message="Validation failed",
                        error=event.data.get("error_message"),
                        recovery_options=("auto-fix", "skip", "manual", "retry", "abort"),
                        default="auto-fix",
                    )
                    response = yield checkpoint

                    if response.abort:
                        yield "Execution aborted due to validation failure."
                        return

                    # Agent handles auto-fix internally via Compound Eye

                elif event.type == EventType.TASK_COMPLETE and not self.stream_progress:
                    # Yield progress update (only if not streaming all events)
                    yield self._format_task_complete(event.data)

                elif event.type == EventType.COMPLETE:
                    # Checkpoint: Completion
                    self._state = LoopState.COMPLETED

                    # Build summary from actual event data
                    tasks_done = event.data.get("tasks_completed", 0)
                    gates_done = event.data.get("gates_passed", 0)
                    duration = event.data.get("duration_s", 0)
                    learnings = event.data.get("learnings", 0)

                    summary = f"{tasks_done} tasks, {gates_done} gates passed"
                    if duration:
                        summary += f" ({duration:.1f}s)"
                    if learnings:
                        summary += f", {learnings} learnings"

                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.COMPLETION,
                        message="Execution complete",
                        summary=summary,
                        files_changed=tuple(event.data.get("files_changed", [])),
                    )
                    yield checkpoint

                    # Add completion to conversation
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": f"Done! {summary}",
                    })

        except Exception as e:
            self._state = LoopState.ERROR
            logger.exception("Goal execution error")
            yield ChatCheckpoint(
                type=ChatCheckpointType.FAILURE,
                message=f"Execution error: {e}",
                error=str(e),
                recovery_options=("retry", "abort"),
                default="abort",
            )
        finally:
            self._current_agent = None

    async def _generate_response(
        self,
        user_input: str,
        execution_context: dict[str, Any] | None = None,
    ) -> str:
        """Generate conversational response."""
        messages = self._build_messages(user_input)

        if execution_context:
            # Add execution context for mid-execution questions
            messages.insert(-1, {
                "role": "system",
                "content": f"Current execution context: {execution_context}",
            })

        # Convert to message tuples for model
        from sunwell.models.protocol import Message

        structured = tuple(
            Message(role=m["role"], content=m["content"])
            for m in messages
        )

        # Check if model supports streaming
        if hasattr(self.model, "generate_stream"):
            response_parts: list[str] = []
            async for chunk in self.model.generate_stream(structured):
                response_parts.append(chunk)
            return "".join(response_parts)

        # Fallback to non-streaming
        result = await self.model.generate(structured)
        return result.text or ""

    def _build_messages(self, user_input: str) -> list[dict[str, str]]:
        """Build message list with conversation history."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]

        # Add recent conversation history (last 20 messages = 10 turns)
        messages.extend(self.conversation_history[-20:])

        # Add current input if not already there
        if not messages or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})

        return messages

    def _get_conversation_context(self) -> str:
        """Get recent conversation as context string for intent classification."""
        recent = self.conversation_history[-6:]
        return "\n".join(
            f"{m['role']}: {m['content'][:200]}"
            for m in recent
        )

    def _format_plan_summary(self, plan_data: dict[str, Any]) -> str:
        """Format plan for confirmation checkpoint."""
        # Get task count (int) and optional task details (list)
        task_count = plan_data.get("tasks", 0)
        task_list = plan_data.get("task_list", [])
        gate_count = plan_data.get("gates", 0)
        gate_list = plan_data.get("gate_list", [])

        # Use counts if no detail list provided
        if not task_list:
            task_count = task_count or len(task_list)
        if not gate_list:
            gate_count = gate_count or len(gate_list)

        lines = [
            f"★ Plan ready ({task_count or len(task_list)} tasks, {gate_count or len(gate_list)} validation gates)",
            "",
        ]

        # Show task details if available
        for i, task in enumerate(task_list[:10], 1):
            desc = task.get("description", "") if isinstance(task, dict) else str(task)
            lines.append(f"   {i}. {desc[:60]}")

        if len(task_list) > 10:
            lines.append(f"   ... and {len(task_list) - 10} more")

        lines.append("")
        lines.append("Proceed?")

        return "\n".join(lines)

    def _format_task_complete(self, data: dict[str, Any]) -> str:
        """Format task completion message."""
        task_num = data.get("task_index", 0) + 1
        total = data.get("total_tasks", 0)
        desc = data.get("description", "")

        return f"[{task_num}/{total}] ✓ {desc}"

    @property
    def _system_prompt(self) -> str:
        """Build system prompt for conversation mode."""
        return f"""You are Sunwell, an AI assistant for software development.

You can both:
1. Answer questions and have conversations
2. Execute coding tasks (create files, modify code, etc.)

When the user asks you to DO something (create, add, fix, refactor),
you'll transition to execution mode with a plan.

When the user asks questions, explain or discuss freely.

Current workspace: {self.workspace}"""

    def _handle_command(self, command: str) -> tuple[str | None, str | None]:
        """Handle /slash commands.

        Supports:
        - /agent [goal]: Force agent mode for explicit task (returns goal)
        - /chat: Stay in conversation mode
        - /abort: Cancel current execution
        - /status: Show current state

        Returns:
            Tuple of (response_message, agent_goal). If agent_goal is set,
            caller should execute that goal. Otherwise, return response_message.
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/agent" and arg:
            # Force agent mode - return the goal to execute
            return (None, arg)
        elif cmd == "/chat":
            return ("Staying in conversation mode. I won't execute tasks unless you use /agent.", None)
        elif cmd == "/abort":
            if self.is_executing:
                self.request_cancel()
                return ("Cancellation requested...", None)
            return ("No execution in progress.", None)
        elif cmd == "/status":
            return (f"State: {self._state.value}, History: {len(self.conversation_history)} messages", None)
        else:
            return (f"Unknown command: {cmd}", None)
