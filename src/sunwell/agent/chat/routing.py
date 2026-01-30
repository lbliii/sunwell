"""DAG classification routing for the unified chat loop.

Routes user input based on intent classification to appropriate handlers.
Integrates adaptive trust system for progressive autonomy.
"""

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
from sunwell.agent.intent import (
    IntentClassification,
    IntentNode,
    format_path,
    requires_approval,
)

if TYPE_CHECKING:
    from sunwell.agent.background import BackgroundManager
    from sunwell.agent.rewind import SnapshotManager
    from sunwell.agent.trust import ApprovalTracker, AutoApproveConfig
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor

# Type aliases for callback functions
GenerateResponseFn = Callable[[str], Coroutine[Any, Any, str]]
ExecuteGoalFn = Callable[
    [str], AsyncIterator[tuple[LoopState, str | ChatCheckpoint | AgentEvent]]
]

logger = logging.getLogger(__name__)

# Threshold for offering background execution (in seconds)
BACKGROUND_THRESHOLD_SECONDS = 120


def estimate_task_duration(goal: str, path: IntentPath) -> int | None:
    """Estimate task duration based on goal complexity.

    Uses simple heuristics based on goal length and action type.
    Returns estimated duration in seconds, or None if quick task.

    Args:
        goal: The goal description
        path: The intent DAG path

    Returns:
        Estimated duration in seconds, or None if estimated < threshold
    """
    # Base duration based on action type
    base_duration = 30  # Default 30 seconds

    terminal = path[-1] if path else IntentNode.CONVERSATION

    # Adjust based on action type
    if terminal == IntentNode.CREATE:
        base_duration = 60
    elif terminal == IntentNode.MODIFY:
        base_duration = 45
    elif terminal == IntentNode.DELETE:
        base_duration = 20

    # Adjust based on goal complexity (rough heuristic)
    words = len(goal.split())
    if words > 50:
        base_duration *= 3
    elif words > 20:
        base_duration *= 2
    elif words > 10:
        base_duration *= 1.5

    # Check for indicators of complex tasks
    complex_indicators = [
        "refactor",
        "migrate",
        "implement",
        "build",
        "create API",
        "database",
        "authentication",
        "multiple files",
        "across",
    ]
    for indicator in complex_indicators:
        if indicator.lower() in goal.lower():
            base_duration *= 1.5

    estimated = int(base_duration)

    # Only return if above threshold
    if estimated >= BACKGROUND_THRESHOLD_SECONDS:
        return estimated
    return None


def ensure_checkpoint_response(
    value: str | CheckpointResponse | None,
) -> CheckpointResponse:
    """Convert value to CheckpointResponse, handling various input types."""
    if isinstance(value, CheckpointResponse):
        return value
    if value is None:
        return CheckpointResponse(choice="")
    return CheckpointResponse(choice=str(value))


async def route_dag_classification(
    classification: IntentClassification,
    user_input: str,
    *,
    tool_executor: ToolExecutor | None,
    conversation_history: list[dict[str, str]],
    auto_confirm: bool,
    generate_response_fn: GenerateResponseFn,
    execute_goal_fn: ExecuteGoalFn,
    workspace: Path | None = None,
    approval_tracker: ApprovalTracker | None = None,
    auto_approve_config: AutoApproveConfig | None = None,
    snapshot_manager: SnapshotManager | None = None,
    conversation_turn: int = 0,
    background_manager: BackgroundManager | None = None,
    model: ModelProtocol | None = None,
    memory: PersistentMemory | None = None,
) -> AsyncIterator[tuple[LoopState, str | ChatCheckpoint | AgentEvent | None]]:
    """Route based on DAG classification path.

    Maps DAG paths to actions:
    - UNDERSTAND branch → Conversation (no tools)
    - ANALYZE branch → Read-only tools
    - PLAN branch → Read-only tools, may lead to action
    - ACT/READ branch → Read-only tools
    - ACT/WRITE branch → Write tools with approval

    Integrates adaptive trust system:
    - Checks auto-approve config before requiring confirmation
    - Tracks approval decisions for pattern learning
    - Suggests trust upgrades after consistent approvals

    Args:
        classification: DAG classification result
        user_input: Original user input
        tool_executor: Tool executor or None
        conversation_history: Conversation history
        auto_confirm: Whether to skip confirmations
        generate_response_fn: Function to generate conversation response
        execute_goal_fn: Function to execute a goal
        workspace: Workspace path for trust storage (optional)
        approval_tracker: ApprovalTracker instance for recording decisions (optional)
        auto_approve_config: AutoApproveConfig for checking auto-approve rules (optional)
        snapshot_manager: SnapshotManager for code state snapshots (optional)
        conversation_turn: Current conversation turn for snapshot labeling
        background_manager: BackgroundManager for background task execution (optional)
        model: Model for background execution (optional, required for background tasks)
        memory: PersistentMemory for background execution (optional)

    Yields:
        Tuples of (state, event)
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
        response = await generate_response_fn(user_input)
        yield (LoopState.IDLE, response)
        conversation_history.append({
            "role": "assistant",
            "content": response,
        })
        if len(conversation_history) > MAX_HISTORY_SIZE:
            del conversation_history[: -MAX_HISTORY_SIZE]
        return

    # ANALYZE branch - conversation with optional read-only context
    if branch == IntentNode.ANALYZE:
        # For now, treat as conversation - future: could use read-only tools
        response = await generate_response_fn(user_input)
        yield (LoopState.IDLE, response)
        conversation_history.append({
            "role": "assistant",
            "content": response,
        })
        if len(conversation_history) > MAX_HISTORY_SIZE:
            del conversation_history[: -MAX_HISTORY_SIZE]
        return

    # PLAN branch - may show a plan but not execute
    if branch == IntentNode.PLAN:
        # For now, treat as conversation about planning
        response = await generate_response_fn(user_input)
        yield (LoopState.IDLE, response)
        conversation_history.append({
            "role": "assistant",
            "content": response,
        })
        if len(conversation_history) > MAX_HISTORY_SIZE:
            del conversation_history[: -MAX_HISTORY_SIZE]
        return

    # ACT branch - requires tools
    if branch == IntentNode.ACT:
        # Check if tools are available
        if tool_executor is None:
            yield (
                LoopState.IDLE,
                f"I understand you want me to {terminal.value} something, "
                f"but I'm in **chat mode** (tools disabled). "
                f"Use `/tools on` to enable agent mode.",
            )
            return

        # READ sub-branch - read-only tools
        if IntentNode.READ in path and IntentNode.WRITE not in path:
            # Execute with read-only scope
            goal = classification.task_description or user_input
            logger.debug("Routing to read-only agent: %r", goal[:100])
            # Manual iteration to forward checkpoint responses (async for doesn't support asend)
            goal_gen = execute_goal_fn(goal)
            try:
                result = await goal_gen.asend(None)
                while True:
                    response = yield result
                    result = await goal_gen.asend(response)
            except StopAsyncIteration:
                pass
            return

        # WRITE sub-branch - write tools with approval
        if IntentNode.WRITE in path:
            goal = classification.task_description or user_input

            # Check if approval is needed
            needs_approval = requires_approval(path) and not auto_confirm

            # Check if this path is auto-approved (adaptive trust)
            is_auto_approved = False
            if needs_approval and auto_approve_config is not None:
                is_auto_approved = auto_approve_config.should_auto_approve(path)
                if is_auto_approved:
                    logger.debug("Path %s is auto-approved by user preference", path)

            # Show path and get approval if needed (and not auto-approved)
            if needs_approval and not is_auto_approved:
                path_display = format_path(path)
                checkpoint = ChatCheckpoint(
                    type=ChatCheckpointType.CONFIRMATION,
                    message=f"Path: {path_display}\n\nThis will modify files. Proceed?",
                    options=("Y", "n"),
                    default="Y",
                    context={"dag_path": [n.value for n in path]},
                )
                # Single-yield: send checkpoint AND receive response in one operation
                raw_response = yield (LoopState.CONFIRMING, checkpoint)
                response = ensure_checkpoint_response(raw_response)
                logger.debug(
                    "DAG checkpoint response: raw=%r, choice=%r, proceed=%s",
                    raw_response,
                    response.choice,
                    response.proceed,
                )

                # Record the approval decision for adaptive trust
                if approval_tracker is not None:
                    approval_tracker.record_decision(path, approved=response.proceed)

                if not response.proceed:
                    yield (LoopState.IDLE, "Okay, no changes made.")
                    return

                # Check if we should suggest trust upgrade
                if approval_tracker is not None and auto_approve_config is not None:
                    if (
                        approval_tracker.should_suggest_upgrade(path)
                        and not auto_approve_config.has_rule(path)
                    ):
                        # Get approval pattern for context
                        pattern = approval_tracker.get_pattern(path)
                        approval_count = pattern.approval_count if pattern else 0

                        path_key = tuple(n.value for n in path)
                        trust_checkpoint = ChatCheckpoint(
                            type=ChatCheckpointType.TRUST_UPGRADE,
                            message=(
                                f"You've approved **{path_key[-1]}** operations "
                                f"{approval_count} times.\n\n"
                                f"Would you like to auto-approve this type in the future?"
                            ),
                            options=("yes", "no", "never"),
                            default="no",
                            intent_path=path_key,
                            approval_count=approval_count,
                        )
                        # Single-yield: send checkpoint AND receive response
                        raw_trust_response = yield (LoopState.CONFIRMING, trust_checkpoint)
                        trust_response = ensure_checkpoint_response(raw_trust_response)

                        if trust_response.enable_auto_approve:
                            auto_approve_config.add_rule(path, approval_count)
                            yield (
                                LoopState.IDLE,
                                f"✓ Auto-approve enabled for **{path_key[-1]}** operations.",
                            )
                            # Don't return - continue to execute the goal

            # Check if this is a long-running task and offer background execution
            estimated_duration = estimate_task_duration(goal, path)
            if (
                estimated_duration is not None
                and background_manager is not None
                and model is not None
                and tool_executor is not None
                and not auto_confirm
            ):
                mins = estimated_duration // 60
                secs = estimated_duration % 60
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

                bg_checkpoint = ChatCheckpoint(
                    type=ChatCheckpointType.BACKGROUND_OFFER,
                    message=(
                        f"This task may take approximately **{time_str}**.\n\n"
                        f"Would you like to run it in the background? "
                        f"You'll be notified when it completes."
                    ),
                    options=("background", "wait", "cancel"),
                    default="wait",
                    estimated_duration_seconds=estimated_duration,
                )
                raw_bg_response = yield (LoopState.CONFIRMING, bg_checkpoint)
                bg_response = ensure_checkpoint_response(raw_bg_response)

                if bg_response.run_background:
                    # Spawn background task
                    session = await background_manager.spawn(
                        goal=goal,
                        model=model,
                        tool_executor=tool_executor,
                        memory=memory,
                        estimated_duration=estimated_duration,
                    )
                    yield (
                        LoopState.IDLE,
                        f"✓ Task started in background: `{session.session_id}`\n\n"
                        f"Use `/background` to check status or `/resume {session.session_id}` "
                        f"to see results when complete.",
                    )
                    return

                if bg_response.abort:
                    yield (LoopState.IDLE, "Task cancelled.")
                    return

                # User chose to wait - continue with foreground execution

            # Take snapshot before write operations (code state rewind)
            if snapshot_manager is not None:
                try:
                    snapshot = snapshot_manager.take_snapshot(
                        conversation_turn=conversation_turn,
                        label=f"Before: {goal[:50]}",
                    )
                    logger.debug("Created pre-write snapshot: %s", snapshot.id)
                except Exception as e:
                    logger.warning("Failed to create snapshot: %s", e)

            logger.debug("Routing to write agent: %r", goal[:100])
            # Manual iteration to forward checkpoint responses (async for doesn't support asend)
            goal_gen = execute_goal_fn(goal)
            try:
                result = await goal_gen.asend(None)
                while True:
                    state, event = result
                    
                    # Take stable snapshot after completion
                    if (
                        isinstance(event, ChatCheckpoint)
                        and event.type == ChatCheckpointType.COMPLETION
                        and snapshot_manager is not None
                    ):
                        try:
                            stable_snapshot = snapshot_manager.take_snapshot(
                                conversation_turn=conversation_turn,
                                label=f"After: {goal[:50]}",
                                is_stable=True,
                            )
                            logger.debug("Created stable snapshot: %s", stable_snapshot.id)
                        except Exception as e:
                            logger.warning("Failed to create stable snapshot: %s", e)
                    
                    # Yield event and forward response to executor
                    response = yield (state, event)
                    result = await goal_gen.asend(response)
            except StopAsyncIteration:
                pass
            return

    # Fallback - low confidence or unknown path
    if classification.confidence < 0.5:
        yield (
            LoopState.IDLE,
            f"I'm not sure what you'd like me to do. "
            f"Could you rephrase that?\n\n"
            f"_({classification.reasoning})_",
        )
        return

    # Default to conversation
    response = await generate_response_fn(user_input)
    yield (LoopState.IDLE, response)
    conversation_history.append({
        "role": "assistant",
        "content": response,
    })
    if len(conversation_history) > MAX_HISTORY_SIZE:
        del conversation_history[: -MAX_HISTORY_SIZE]
