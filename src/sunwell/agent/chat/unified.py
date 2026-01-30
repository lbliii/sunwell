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
from sunwell.agent.intent import (
    DAGClassifier,
    IntentClassification,
    IntentNode,
    format_path,
    requires_approval,
)

if TYPE_CHECKING:
    from sunwell.agent import Agent
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.events import AgentEvent
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor

logger = logging.getLogger(__name__)

# Maximum conversation history entries (user + assistant messages)
# 50 entries = ~25 turns, enough context without unbounded growth
_MAX_HISTORY_SIZE = 50


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

    def _clear_pending_input(self) -> None:
        """Clear any pending input from the queue."""
        while not self._pending_input.empty():
            try:
                self._pending_input.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _trim_history(self) -> None:
        """Trim conversation history to prevent unbounded growth."""
        if len(self.conversation_history) > _MAX_HISTORY_SIZE:
            # Keep the most recent entries
            self.conversation_history = self.conversation_history[-_MAX_HISTORY_SIZE:]

    def _ensure_checkpoint_response(
        self, value: str | CheckpointResponse | None
    ) -> CheckpointResponse:
        """Convert value to CheckpointResponse, handling various input types."""
        if isinstance(value, CheckpointResponse):
            return value
        if value is None:
            return CheckpointResponse(choice="")
        return CheckpointResponse(choice=str(value))

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
                    # Checkpoint responses are handled in _execute_goal
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
                if user_input.strip().startswith("/") or user_input.strip().startswith("::"):
                    response, agent_goal = self._handle_command(user_input)
                    if agent_goal:
                        async for event in self._execute_goal(agent_goal):
                            yield event
                    elif response:
                        yield response
                    self._state = LoopState.IDLE
                    continue

                # Classify intent using DAG classifier
                self._state = LoopState.CLASSIFYING
                logger.debug("Classifying intent for: %r", user_input[:100])
                
                result = await self.classifier.classify(
                    user_input,
                    context=self._get_conversation_context(),
                )
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
                
                # Route based on DAG path
                async for event in self._route_dag_classification(result, user_input):
                    yield event

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
        from sunwell.agent.context.session import SessionContext
        from sunwell.agent.events import EventType

        logger.debug("_execute_goal starting for: %r", goal[:100])
        self._state = LoopState.PLANNING

        # Check if we have tool executor
        if self.tool_executor is None:
            logger.warning("No tool executor available for goal execution")
            yield (
                "I understand you want me to do something, but I'm in **chat mode** "
                "(tools disabled). Use `/tools on` to enable agent mode, or rephrase "
                "as a question."
            )
            return

        # Create agent
        logger.debug("Creating agent with tool_executor=%s", type(self.tool_executor).__name__)
        self._current_agent = Agent(
            model=self.model,
            tool_executor=self.tool_executor,
            cwd=self.workspace,
            stream_inference=self.stream_progress,
        )

        try:
            # Update session with goal
            self.session = SessionContext.build(self.workspace, goal, None)
            logger.debug("Session created: %s", self.session.session_id)

            # Plan first (stream planning events if enabled)
            logger.debug("Starting agent.plan()")
            plan_data: dict[str, Any] | None = None
            event_count = 0
            async for event in self._current_agent.plan(self.session, self.memory):
                event_count += 1
                logger.debug("Plan event %d: type=%s", event_count, event.type)
                if self.stream_progress:
                    yield event
                if event.type == EventType.PLAN_WINNER:
                    plan_data = event.data
                    logger.debug("Plan winner received with %d tasks", plan_data.get("tasks", 0) if plan_data else 0)

            logger.debug("Planning complete: %d events, plan_data=%s", event_count, "yes" if plan_data else "no")

            if not plan_data:
                logger.warning("No plan data after planning phase")
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
                raw_response = yield checkpoint
                response = self._ensure_checkpoint_response(raw_response)

                if response.abort:
                    self._clear_pending_input()
                    yield "Cancelled."
                    return

                if not response.proceed:
                    yield "Okay, let me know if you'd like to try a different approach."
                    return

            # Execute with checkpoint handling
            self._state = LoopState.EXECUTING
            completed_tasks = 0  # Track completed tasks via events (not private state)
            async for event in self._current_agent.run(self.session, self.memory):
                # Track task completions
                if event.type == EventType.TASK_COMPLETE:
                    completed_tasks += 1

                # Check for cancellation
                if self._cancel_requested:
                    self._cancel_requested = False
                    self._clear_pending_input()
                    yield ChatCheckpoint(
                        type=ChatCheckpointType.COMPLETION,
                        message="Execution cancelled by user",
                        summary=f"Completed {completed_tasks} tasks before cancel",
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
                    raw_response = yield checkpoint
                    response = self._ensure_checkpoint_response(raw_response)

                    if response.abort:
                        self._clear_pending_input()
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
                    raw_response = yield checkpoint
                    response = self._ensure_checkpoint_response(raw_response)

                    if response.abort:
                        self._clear_pending_input()
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
                    self._trim_history()

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
        from sunwell.models import Message

        structured = tuple(
            Message(role=m["role"], content=m["content"])
            for m in messages
        )

        logger.debug(
            "Calling model.generate with %d messages (model=%s)",
            len(structured),
            type(self.model).__name__,
        )

        # Check if model supports streaming
        if hasattr(self.model, "generate_stream"):
            logger.debug("Using streaming generation")
            response_parts: list[str] = []
            try:
                async for chunk in self.model.generate_stream(structured):
                    response_parts.append(chunk)
                response = "".join(response_parts)
                logger.debug("Streaming complete: %d chars", len(response))
                return response
            except Exception as e:
                logger.exception("Streaming generation failed")
                raise

        # Fallback to non-streaming
        logger.debug("Using non-streaming generation")
        try:
            result = await self.model.generate(structured)
            response = result.text or ""
            logger.debug("Generation complete: %d chars", len(response))
            return response
        except Exception as e:
            logger.exception("Generation failed")
            raise

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

        # Use list length if available, otherwise fall back to counts
        if task_list:
            task_count = len(task_list)
        if gate_list:
            gate_count = len(gate_list)

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
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).astimezone()
        current_time = now.strftime("%A, %B %d, %Y at %H:%M %Z")

        return f"""You are Sunwell, an AI assistant for software development.

You can both:
1. Answer questions and have conversations
2. Execute coding tasks (create files, modify code, etc.)

When the user asks you to DO something (create, add, fix, refactor),
you'll transition to execution mode with a plan.

When the user asks questions, explain or discuss freely.

Current date/time: {current_time}
Current workspace: {self.workspace}

Note: Your training data has a knowledge cutoff. For questions about current
events, recent releases, or time-sensitive information, acknowledge you may
not have the latest data and suggest the user verify from authoritative sources."""

    async def _route_dag_classification(
        self,
        classification: IntentClassification,
        user_input: str,
    ) -> AsyncIterator[str | ChatCheckpoint | AgentEvent]:
        """Route based on DAG classification path.
        
        Maps DAG paths to actions:
        - UNDERSTAND branch → Conversation (no tools)
        - ANALYZE branch → Read-only tools
        - PLAN branch → Read-only tools, may lead to action
        - ACT/READ branch → Read-only tools
        - ACT/WRITE branch → Write tools with approval
        
        Args:
            classification: DAG classification result
            user_input: Original user input
            
        Yields:
            Responses, checkpoints, and events
        """
        path = classification.path
        terminal = classification.terminal_node
        branch = classification.branch
        
        logger.debug(
            "DAG routing: terminal=%s, branch=%s, requires_tools=%s, requires_approval=%s",
            terminal,
            branch,
            classification.requires_tools,
            requires_approval(path),
        )
        
        # UNDERSTAND branch - pure conversation, no tools
        if branch == IntentNode.UNDERSTAND:
            self._state = LoopState.CONVERSING
            response = await self._generate_response(user_input)
            self._state = LoopState.IDLE
            yield response
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
            })
            self._trim_history()
            return
        
        # ANALYZE branch - conversation with optional read-only context
        if branch == IntentNode.ANALYZE:
            self._state = LoopState.CONVERSING
            # For now, treat as conversation - future: could use read-only tools
            response = await self._generate_response(user_input)
            self._state = LoopState.IDLE
            yield response
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
            })
            self._trim_history()
            return
        
        # PLAN branch - may show a plan but not execute
        if branch == IntentNode.PLAN:
            self._state = LoopState.CONVERSING
            # For now, treat as conversation about planning
            response = await self._generate_response(user_input)
            self._state = LoopState.IDLE
            yield response
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
            })
            self._trim_history()
            return
        
        # ACT branch - requires tools
        if branch == IntentNode.ACT:
            # Check if tools are available
            if self.tool_executor is None:
                yield (
                    f"I understand you want me to {terminal.value} something, "
                    f"but I'm in **chat mode** (tools disabled). "
                    f"Use `/tools on` to enable agent mode."
                )
                self._state = LoopState.IDLE
                return
            
            # READ sub-branch - read-only tools
            if IntentNode.READ in path and IntentNode.WRITE not in path:
                # Execute with read-only scope
                goal = classification.task_description or user_input
                logger.debug("Routing to read-only agent: %r", goal[:100])
                async for event in self._execute_goal(goal):
                    yield event
                self._state = LoopState.IDLE
                return
            
            # WRITE sub-branch - write tools with approval
            if IntentNode.WRITE in path:
                goal = classification.task_description or user_input
                
                # Show path and get approval if needed
                if requires_approval(path) and not self.auto_confirm:
                    path_display = format_path(path)
                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.CONFIRMATION,
                        message=f"Path: {path_display}\n\nThis will modify files. Proceed?",
                        options=("Y", "n"),
                        default="Y",
                        context={"dag_path": [n.value for n in path]},
                    )
                    raw_response = yield checkpoint
                    response = self._ensure_checkpoint_response(raw_response)
                    
                    if not response.proceed:
                        yield "Okay, no changes made."
                        self._state = LoopState.IDLE
                        return
                
                logger.debug("Routing to write agent: %r", goal[:100])
                async for event in self._execute_goal(goal):
                    yield event
                self._state = LoopState.IDLE
                return
        
        # Fallback - low confidence or unknown path
        if classification.confidence < 0.5:
            self._state = LoopState.IDLE
            yield (
                f"I'm not sure what you'd like me to do. "
                f"Could you rephrase that?\n\n"
                f"_({classification.reasoning})_"
            )
            return
        
        # Default to conversation
        self._state = LoopState.CONVERSING
        response = await self._generate_response(user_input)
        self._state = LoopState.IDLE
        yield response
        self.conversation_history.append({
            "role": "assistant",
            "content": response,
        })
        self._trim_history()

    def _handle_command(self, command: str) -> tuple[str | None, str | None]:
        """Handle /slash commands.

        Supports:
        - /agent [goal]: Force agent mode for explicit task (returns goal)
        - /chat: Stay in conversation mode
        - /abort: Cancel current execution
        - /status: Show current state
        - /tools on|off: Enable/disable tool execution

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
            tools_status = "enabled" if self.tool_executor else "disabled"
            return (
                f"State: {self._state.value}, History: {len(self.conversation_history)} messages, "
                f"Tools: {tools_status}",
                None,
            )
        elif cmd == "/tools":
            return self._handle_tools_command(arg)
        else:
            return (f"Unknown command: {cmd}", None)

    def _handle_tools_command(self, arg: str) -> tuple[str | None, str | None]:
        """Handle /tools on|off command to enable/disable tool execution."""
        from sunwell.knowledge.project import (
            ProjectResolutionError,
            create_project_from_workspace,
            resolve_project,
        )
        from sunwell.tools.core.types import ToolPolicy, ToolTrust
        from sunwell.tools.execution import ToolExecutor

        arg_lower = arg.lower()
        if arg_lower == "on":
            if self.tool_executor is not None:
                return ("Tools are already enabled.", None)

            # Create tool executor
            try:
                project = resolve_project(cwd=self.workspace)
            except ProjectResolutionError:
                project = create_project_from_workspace(self.workspace)

            policy = ToolPolicy(trust_level=ToolTrust.from_string(self.trust_level))
            self.tool_executor = ToolExecutor(
                project=project,
                sandbox=None,
                policy=policy,
            )
            logger.info("Tools enabled with trust_level=%s", self.trust_level)
            return ("✓ Tools enabled. I can now execute tasks.", None)

        elif arg_lower == "off":
            if self.tool_executor is None:
                return ("Tools are already disabled.", None)
            self.tool_executor = None
            logger.info("Tools disabled")
            return ("✓ Tools disabled. I'll only respond to questions.", None)

        else:
            status = "enabled" if self.tool_executor else "disabled"
            return (f"Tools are currently {status}. Use `/tools on` or `/tools off`.", None)
