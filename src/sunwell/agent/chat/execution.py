"""Goal execution for the unified chat loop.

Handles agent planning, confirmation, and task execution with checkpoints.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.chat.checkpoint import (
    ChatCheckpoint,
    ChatCheckpointType,
    CheckpointResponse,
)
from sunwell.agent.chat.state import LoopState, MAX_HISTORY_SIZE
from sunwell.agent.events import AgentEvent

if TYPE_CHECKING:
    from sunwell.agent import Agent
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.recovery.manager import RecoveryManager
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor

# Type alias for async response generator function
GenerateResponseFn = Callable[
    [str, dict[str, Any] | None], Coroutine[Any, Any, str]
]

logger = logging.getLogger(__name__)


def format_plan_summary(plan_data: dict[str, Any]) -> str:
    """Format plan for confirmation checkpoint.

    Args:
        plan_data: Plan data from agent planning

    Returns:
        Formatted plan summary string
    """
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
        f"★ Plan ready ({task_count or len(task_list)} tasks, "
        f"{gate_count or len(gate_list)} validation gates)",
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


def format_task_complete(data: dict[str, Any]) -> str:
    """Format task completion message.

    Args:
        data: Task completion event data

    Returns:
        Formatted completion message
    """
    task_num = data.get("task_index", 0) + 1
    total = data.get("total_tasks", 0)
    desc = data.get("description", "")

    return f"[{task_num}/{total}] ✓ {desc}"


def ensure_checkpoint_response(
    value: str | CheckpointResponse | None,
) -> CheckpointResponse:
    """Convert value to CheckpointResponse, handling various input types.

    Args:
        value: Input value (string, CheckpointResponse, or None)

    Returns:
        CheckpointResponse instance
    """
    if isinstance(value, CheckpointResponse):
        return value
    if value is None:
        return CheckpointResponse(choice="")
    return CheckpointResponse(choice=str(value))


class GoalExecutor:
    """Handles goal execution with checkpoints and progress streaming.

    This class encapsulates the execution logic to keep the main loop slim.
    It manages the state transitions and checkpoint handling during goal execution.
    """

    def __init__(
        self,
        model: ModelProtocol,
        tool_executor: ToolExecutor,
        workspace: Path,
        *,
        auto_confirm: bool = False,
        stream_progress: bool = True,
        recovery_manager: RecoveryManager | None = None,
    ) -> None:
        """Initialize the goal executor.

        Args:
            model: LLM for generation
            tool_executor: Executor for tools
            workspace: Working directory
            auto_confirm: Skip confirmation checkpoints
            stream_progress: Yield AgentEvents during execution
            recovery_manager: Manager for persisting recovery state on failures
        """
        self.model = model
        self.tool_executor = tool_executor
        self.workspace = workspace
        self.auto_confirm = auto_confirm
        self.stream_progress = stream_progress
        self.recovery_manager = recovery_manager

        # Execution state
        self._current_agent: Agent | None = None
        self._pending_input: asyncio.Queue[str] = asyncio.Queue()
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Request graceful cancellation of current execution."""
        self._cancel_requested = True

    def clear_pending_input(self) -> None:
        """Clear any pending input from the queue."""
        while not self._pending_input.empty():
            try:
                self._pending_input.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def queue_input(self, text: str) -> None:
        """Queue user input during execution (for interruptions).

        Args:
            text: User input text
        """
        await self._pending_input.put(text)

    async def execute(
        self,
        goal: str,
        session: SessionContext,
        memory: PersistentMemory | None,
        conversation_history: list[dict[str, str]],
        generate_response_fn: GenerateResponseFn,
    ) -> AsyncIterator[tuple[LoopState, str | ChatCheckpoint | AgentEvent]]:
        """Execute a goal with checkpoints and optional progress streaming.

        ⚠️ BIDIRECTIONAL GENERATOR: This generator expects responses via asend().
        Do NOT consume with ``async for`` - it will break checkpoint responses.
        Use manual iteration instead::

            gen = executor.execute(...)
            try:
                result = await gen.asend(None)
                while True:
                    response = yield result  # or handle checkpoint
                    result = await gen.asend(response)
            except StopAsyncIteration:
                pass

        Flow:
            1. PLANNING: Generate plan via agent.plan()
            2. CONFIRMING: Yield ChatCheckpoint for user approval (unless auto_confirm)
            3. EXECUTING: Run agent.run(), streaming AgentEvents if stream_progress=True
            4. Handle interruptions, failures, completion via ChatCheckpoints

        Args:
            goal: The goal to execute
            session: Session context
            memory: Persistent memory or None
            conversation_history: Conversation history for updates
            generate_response_fn: Function to generate responses for interruptions

        Yields:
            Tuples of (state, event) where event is str, ChatCheckpoint, or AgentEvent
        """
        from sunwell.agent import Agent
        from sunwell.agent.context.session import SessionContext
        from sunwell.agent.events import EventType

        logger.debug("GoalExecutor.execute starting for: %r", goal[:100])

        # Create agent
        logger.debug(
            "Creating agent with tool_executor=%s",
            type(self.tool_executor).__name__,
        )
        self._current_agent = Agent(
            model=self.model,
            tool_executor=self.tool_executor,
            cwd=self.workspace,
            stream_inference=self.stream_progress,
        )

        try:
            # Update session with goal
            session = SessionContext.build(self.workspace, goal, None)
            logger.debug("Session created: %s", session.session_id)

            # Plan first (stream planning events if enabled)
            logger.debug("Starting agent.plan()")
            plan_data: dict[str, Any] | None = None
            event_count = 0
            async for event in self._current_agent.plan(session, memory):
                event_count += 1
                logger.debug("Plan event %d: type=%s", event_count, event.type)
                if self.stream_progress:
                    yield (LoopState.PLANNING, event)
                if event.type == EventType.PLAN_WINNER:
                    plan_data = event.data
                    logger.debug(
                        "Plan winner received with %d tasks",
                        plan_data.get("tasks", 0) if plan_data else 0,
                    )

            logger.debug(
                "Planning complete: %d events, plan_data=%s",
                event_count,
                "yes" if plan_data else "no",
            )

            if not plan_data:
                logger.warning("No plan data after planning phase")
                yield (LoopState.IDLE, "I couldn't create a plan for that goal.")
                return

            # Checkpoint: Confirmation
            if not self.auto_confirm:
                checkpoint = ChatCheckpoint(
                    type=ChatCheckpointType.CONFIRMATION,
                    message=format_plan_summary(plan_data),
                    options=("Y", "n", "edit"),
                    default="Y",
                    agent_checkpoint_id=f"plan-{session.session_id}",
                    context={"plan": plan_data},
                )
                # Single-yield: send checkpoint AND receive response
                raw_response = yield (LoopState.CONFIRMING, checkpoint)
                response = ensure_checkpoint_response(raw_response)

                if response.abort:
                    self.clear_pending_input()
                    yield (LoopState.IDLE, "Cancelled.")
                    return

                if not response.proceed:
                    yield (
                        LoopState.IDLE,
                        "Okay, let me know if you'd like to try a different approach.",
                    )
                    return

            # Execute with checkpoint handling
            completed_tasks = 0
            async for event in self._current_agent.run(session, memory):
                # Track task completions
                if event.type == EventType.TASK_COMPLETE:
                    completed_tasks += 1

                # Check for cancellation
                if self._cancel_requested:
                    self._cancel_requested = False
                    self.clear_pending_input()
                    yield (
                        LoopState.COMPLETED,
                        ChatCheckpoint(
                            type=ChatCheckpointType.COMPLETION,
                            message="Execution cancelled by user",
                            summary=f"Completed {completed_tasks} tasks before cancel",
                        ),
                    )
                    return

                # Check for pending user input (interruption)
                if not self._pending_input.empty():
                    pending_text = await self._pending_input.get()

                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.INTERRUPTION,
                        message=f"You said: {pending_text}",
                        options=("respond", "continue", "abort"),
                        default="respond",
                    )
                    # Single-yield: send checkpoint AND receive response
                    raw_response = yield (LoopState.INTERRUPTED, checkpoint)
                    response = ensure_checkpoint_response(raw_response)

                    if response.abort:
                        self.clear_pending_input()
                        yield (LoopState.IDLE, "Execution aborted.")
                        return

                    if response.choice == "respond":
                        # Answer the question with execution context
                        answer = await generate_response_fn(
                            pending_text,
                            execution_context=event.data,
                        )
                        yield (LoopState.EXECUTING, answer)

                # Stream progress events to UI
                if self.stream_progress and event.type in (
                    EventType.TASK_START,
                    EventType.TASK_COMPLETE,
                    EventType.MODEL_TOKENS,
                    EventType.GATE_START,
                    EventType.GATE_PASS,
                ):
                    yield (LoopState.EXECUTING, event)

                # Handle agent events that require user interaction
                if event.type == EventType.GATE_FAIL:
                    checkpoint = ChatCheckpoint(
                        type=ChatCheckpointType.FAILURE,
                        message="Validation failed",
                        error=event.data.get("error_message"),
                        recovery_options=(
                            "auto-fix",
                            "skip",
                            "manual",
                            "retry",
                            "abort",
                        ),
                        default="auto-fix",
                    )
                    # Single-yield: send checkpoint AND receive response
                    raw_response = yield (LoopState.EXECUTING, checkpoint)
                    response = ensure_checkpoint_response(raw_response)

                    if response.abort:
                        self.clear_pending_input()
                        yield (
                            LoopState.IDLE,
                            "Execution aborted due to validation failure.",
                        )
                        return

                    # Agent handles auto-fix internally via Compound Eye

                elif event.type == EventType.TASK_COMPLETE and not self.stream_progress:
                    # Yield progress update (only if not streaming all events)
                    yield (LoopState.EXECUTING, format_task_complete(event.data))

                elif event.type == EventType.COMPLETE:
                    # Checkpoint: Completion
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
                    yield (LoopState.COMPLETED, checkpoint)

                    # Add completion to conversation
                    conversation_history.append({
                        "role": "assistant",
                        "content": f"Done! {summary}",
                    })
                    if len(conversation_history) > MAX_HISTORY_SIZE:
                        del conversation_history[: -MAX_HISTORY_SIZE]

        except Exception as e:
            logger.exception("Goal execution error")
            yield (
                LoopState.ERROR,
                ChatCheckpoint(
                    type=ChatCheckpointType.FAILURE,
                    message=f"Execution error: {e}",
                    error=str(e),
                    recovery_options=("retry", "abort"),
                    default="abort",
                ),
            )
        finally:
            self._current_agent = None
