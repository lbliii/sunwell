"""RFC-135: Unified Chat-Agent Loop.

Provides seamless transitions between conversation and execution modes:
- Intent classification routes input to chat or agent
- Checkpoints enable user control at key decision points
- Progress events stream execution status to UI

Holy Light aesthetic (RFC-131): Golden accents radiating from the void.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markdown import Markdown

from sunwell.interface.cli.core.events import live_session, render_agent_event
from sunwell.interface.cli.core.render_context import reset_render_context
from sunwell.interface.cli.core.theme import (
    CHARS_CIRCLES,
    CHARS_DIAMONDS,
    CHARS_MISC,
    CHARS_STARS,
    create_sunwell_console,
    render_alert,
    render_countdown,
    render_error,
    render_quote,
    render_separator,
    should_reduce_motion,
    Sparkle,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sunwell.agent.chat import ChatCheckpoint, CheckpointResponse
    from sunwell.agent.events import AgentEvent
    from sunwell.foundation.core.lens import Lens
    from sunwell.interface.cli.notifications import BatchedNotifier, Notifier
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.models import ModelProtocol


# Holy Light themed console
console = create_sunwell_console()


async def run_unified_loop(
    model: ModelProtocol,
    workspace: Path,
    trust_level: str = "workspace",
    auto_confirm: bool = False,
    stream_progress: bool = True,
    dag: ConversationDAG | None = None,
    store: SimulacrumStore | None = None,
    memory_path: Path | None = None,
    lens: Lens | None = None,
    tools_enabled: bool = True,
    verbose: bool = False,
    show_status: bool = False,
) -> None:
    """Run the unified chat-agent loop (RFC-135).

    Provides seamless transitions between conversation and execution modes:
    - Intent classification routes input to chat or agent
    - Checkpoints enable user control at key decision points
    - Progress events stream execution status to UI

    Args:
        tools_enabled: If False, tool_executor won't be created and TASK intents
                      will get a friendly message to enable tools.
        verbose: If True, show detailed progress including model thinking,
                token metrics, and execution timeline.
        show_status: If True, show live StatusBar with session metrics
                    (tokens, cost, elapsed time).
    """
    from sunwell.agent.chat import (
        ChatCheckpoint,
        UnifiedChatLoop,
    )
    from sunwell.agent.events import AgentEvent
    from sunwell.interface.cli.hooks import register_user_hooks, unregister_user_hooks
    from sunwell.interface.cli.notifications import create_notifier
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    # Reset render context for fresh hierarchical display
    reset_render_context()

    # Load user-configurable hooks from .sunwell/hooks.toml
    hook_count = register_user_hooks(workspace)

    # Create notifier with history and optional batching (from config)
    notifier = create_notifier(workspace)
    
    # Set module-level notifier for checkpoint handlers
    global _notifier
    _notifier = notifier
    if hook_count > 0:
        logger.info("Loaded %d user hooks from .sunwell/hooks.toml", hook_count)

    # Set up tool executor only if tools are enabled
    tool_executor = None
    if tools_enabled:
        try:
            project = resolve_project(cwd=workspace)
        except ProjectResolutionError:
            project = create_project_from_workspace(workspace)

        policy = ToolPolicy(trust_level=ToolTrust.from_string(trust_level))
        tool_executor = ToolExecutor(
            project=project,
            policy=policy,
        )
        logger.debug("Tool executor created with trust_level=%s", trust_level)
    else:
        logger.debug("Tools disabled, running in chat-only mode")

    # Create unified loop
    loop = UnifiedChatLoop(
        model=model,
        tool_executor=tool_executor,
        workspace=workspace,
        trust_level=trust_level,
        auto_confirm=auto_confirm,
        stream_progress=stream_progress,
    )

    # Set notifier on background manager for completion notifications
    if hasattr(loop, '_background_manager') and loop._background_manager is not None:
        loop._background_manager.notifier = notifier

    # Start the generator
    gen = loop.run()
    await gen.asend(None)  # Initialize

    # Wrap execution with optional live status display
    with live_session(console, enable_status=show_status):
        try:
            while True:
                # Get user input with Holy Light styling
                state_indicator = ""
                if loop.is_executing:
                    state_indicator = f" [holy.gold]({CHARS_STARS['progress']} executing)[/holy.gold]"
                user_input = console.input(f"\n[holy.radiant]{CHARS_STARS['radiant']} You:{state_indicator}[/holy.radiant] ").strip()

                logger.debug("CLI received input: %r (len=%d)", user_input[:50] if user_input else "", len(user_input) if user_input else 0)

                if not user_input:
                    logger.debug("Empty input, prompting again")
                    continue

                # Handle quit commands directly
                if user_input.lower() in ("/quit", "/exit", "/q"):
                    logger.debug("Quit command received")
                    break

                # Handle /tools on|off commands
                if user_input.lower().startswith("/tools"):
                    parts = user_input.lower().split()
                    if len(parts) >= 2:
                        if parts[1] == "on":
                            if loop.tool_executor is None:
                                # Create tool executor
                                try:
                                    project = resolve_project(cwd=workspace)
                                except ProjectResolutionError:
                                    project = create_project_from_workspace(workspace)
                                policy = ToolPolicy(trust_level=ToolTrust.from_string(trust_level))
                                loop.tool_executor = ToolExecutor(project=project, policy=policy)
                                console.print(f"[holy.success]{CHARS_STARS['complete']} Tools enabled[/holy.success]")
                            else:
                                console.print("[neutral.dim]Tools already enabled[/neutral.dim]")
                            continue
                        elif parts[1] == "off":
                            if loop.tool_executor is not None:
                                loop.tool_executor = None
                                console.print(f"[holy.gold]{CHARS_STARS['progress']} Tools disabled[/holy.gold]")
                            else:
                                console.print("[neutral.dim]Tools already disabled[/neutral.dim]")
                            continue
                    console.print("[neutral.dim]Usage: /tools on | /tools off[/neutral.dim]")
                    continue

                # Send input to the loop
                logger.debug("Sending to generator: %r", user_input[:50])
                result = await gen.asend(user_input)
                logger.debug("Generator returned: type=%s, value=%r", type(result).__name__, str(result)[:100] if result else None)

                # Process results until we need more input
                while result is not None:
                    logger.debug("Processing result: type=%s", type(result).__name__)

                    if isinstance(result, str):
                        # Conversation response
                        logger.debug("Rendering string response (%d chars)", len(result))
                        _render_response(result, lens)
                        if dag:
                            dag.add_user_message(user_input)
                            dag.add_assistant_message(result, model=str(model))
                        # Small yield to let terminal I/O settle before next input
                        await asyncio.sleep(0.01)
                        result = None  # Wait for next user input

                    elif isinstance(result, ChatCheckpoint):
                        # Handle checkpoint
                        logger.debug("Handling checkpoint: type=%s, message=%r", result.type, result.message[:50] if result.message else None)
                        response = _handle_checkpoint(result)
                        if response is None:
                            # User aborted
                            logger.debug("User aborted checkpoint")
                            break
                        logger.debug("Checkpoint response: %r", response)
                        result = await gen.asend(response)
                        logger.debug("After checkpoint, generator returned: type=%s", type(result).__name__)

                    elif isinstance(result, AgentEvent):
                        # Render progress event
                        logger.debug("Rendering agent event: type=%s", result.type)
                        render_agent_event(result, console, verbose=verbose)

                        # Periodic checkpoint: save SimulacrumStore after task completion
                        # This ensures conversation/learning state survives interruption
                        if store and result.type.value == "task_complete":
                            store.save_session()
                            logger.debug("Checkpoint: saved SimulacrumStore after task completion")

                        # Get next event
                        result = await gen.asend(None)
                        logger.debug("After event, generator returned: type=%s", type(result).__name__ if result else "None")

                    else:
                        # Unknown result type
                        logger.warning("Unknown result type: %s, value=%r", type(result).__name__, result)
                        result = None

                logger.debug("Result loop ended, waiting for next input")

        except KeyboardInterrupt:
            console.print(f"\n[void.indigo]{CHARS_STARS['progress']} Interrupted. Saving session...[/void.indigo]")
            # Save immediately on interrupt to capture current state
            if store:
                store.save_session()
                console.print(f"[holy.success]{CHARS_STARS['complete']} Session saved[/holy.success]")
                session_id = store.session_id
                console.print(f"  [neutral.dim]Resume with: sunwell chat --resume {session_id}[/neutral.dim]")
        except EOFError:
            pass
        except GeneratorExit:
            pass
        finally:
            # Clean up
            try:
                await gen.aclose()
            except Exception:
                pass

            # Save session (may be redundant if already saved in KeyboardInterrupt, but safe)
            if store:
                store.save_session()

            # Extract awareness patterns from session (fire and forget)
            try:
                from sunwell.awareness.hooks import extract_awareness_end_of_session
                patterns_count = extract_awareness_end_of_session(workspace)
                if patterns_count > 0:
                    logger.debug("Extracted %d awareness patterns", patterns_count)
            except Exception as e:
                # Awareness extraction should never block session exit
                logger.debug("Awareness extraction failed: %s", e)

            # Unregister user hooks on session end
            unregister_user_hooks()


def _handle_checkpoint(checkpoint: ChatCheckpoint) -> CheckpointResponse | None:
    """Handle a ChatCheckpoint by prompting user for decision.

    Holy Light aesthetic: golden for positive, void spectrum for warnings/errors.

    Returns:
        CheckpointResponse with user's choice, or None to abort
    """
    from sunwell.agent.chat import ChatCheckpointType, CheckpointResponse

    # Display checkpoint message
    console.print()

    if checkpoint.type == ChatCheckpointType.CONFIRMATION:
        # Use alert box for confirmations requiring user attention
        render_alert(console, checkpoint.message, severity="info", title="Confirmation")
        if checkpoint.options:
            console.print(f"[neutral.dim]Options: {', '.join(checkpoint.options)}[/neutral.dim]")
        default = checkpoint.default or "Y"
        choice = console.input(f"[sunwell.heading]Proceed?[/sunwell.heading] [{default}] ").strip() or default
        resp = CheckpointResponse(choice)
        logger.debug("CONFIRMATION: choice=%r proceed=%s", choice, resp.proceed)
        return resp

    elif checkpoint.type == ChatCheckpointType.FAILURE:
        # Use render_error for proper Holy Light error display
        suggestion = None
        if checkpoint.recovery_options:
            suggestion = f"Options: {', '.join(checkpoint.recovery_options)}"
        render_error(
            console,
            checkpoint.message,
            details=checkpoint.error,
            suggestion=suggestion,
        )
        # Send error notification
        _send_error_notification(checkpoint.message, checkpoint.error or "")
        default = checkpoint.default or "abort"
        choice = console.input(f"[sunwell.heading]Action?[/sunwell.heading] [{default}] ").strip() or default
        if choice.lower() in ("q", "quit", "abort"):
            return None
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.COMPLETION:
        # Use sparkle for completion celebration
        console.print(f"\n[holy.success]{CHARS_STARS['complete']} {checkpoint.message}[/holy.success]")
        if checkpoint.summary:
            console.print(f"[neutral.dim]{checkpoint.summary}[/neutral.dim]")
        if checkpoint.files_changed:
            console.print(f"[neutral.dim]Files: {', '.join(checkpoint.files_changed[:5])}[/neutral.dim]")
        # Sparkle burst animation (fire and forget, respects reduced motion)
        if not should_reduce_motion():
            asyncio.create_task(Sparkle.burst("", duration=0.3))
        # Send completion notification (fire and forget)
        _send_completion_notification(checkpoint.summary or checkpoint.message)
        return CheckpointResponse("done")

    elif checkpoint.type == ChatCheckpointType.INTERRUPTION:
        console.print(f"[holy.gold]{CHARS_STARS['progress']} Paused:[/holy.gold] {checkpoint.message}")
        if checkpoint.options:
            console.print(f"[neutral.dim]Options: {', '.join(checkpoint.options)}[/neutral.dim]")
        # Send waiting notification
        _send_waiting_notification(checkpoint.message)
        default = checkpoint.default or "continue"
        choice = console.input(f"[sunwell.heading]Action?[/sunwell.heading] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.CLARIFICATION:
        # Waiting state with hollow diamond indicator
        console.print(f"\n[holy.radiant]{CHARS_DIAMONDS['hollow']} {checkpoint.message}[/holy.radiant]")
        user_input = console.input(f"[sunwell.heading]{CHARS_MISC['input']} Your response:[/sunwell.heading] ").strip()
        # Echo user's response with quote block
        if user_input:
            render_quote(console, user_input, attribution="User")
        return CheckpointResponse("respond", additional_input=user_input)

    # ═══════════════════════════════════════════════════════════════════════════
    # Adaptive Trust Checkpoints (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    elif checkpoint.type == ChatCheckpointType.TRUST_UPGRADE:
        # Use alert box for trust upgrade prompt
        render_alert(console, checkpoint.message, severity="info", title="Trust Upgrade Available")
        if checkpoint.options:
            console.print(f"[neutral.dim]Options: {', '.join(checkpoint.options)}[/neutral.dim]")
        default = checkpoint.default or "no"
        choice = console.input(f"[sunwell.heading]Auto-approve?[/sunwell.heading] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    # ═══════════════════════════════════════════════════════════════════════════
    # Background Task Checkpoints (Next-Level Chat UX)
    # RFC: Plan-Based Duration Estimation - Enhanced display
    # ═══════════════════════════════════════════════════════════════════════════

    elif checkpoint.type == ChatCheckpointType.BACKGROUND_OFFER:
        # RFC: Show plan summary if available (plan-based estimation)
        if checkpoint.plan_summary:
            console.print(f"[sunwell.info]{CHARS_MISC['insight']} {checkpoint.plan_summary}[/sunwell.info]")
            console.print()
        
        # Use alert box for long-running task offer
        title = "Long-Running Task"
        if checkpoint.task_count:
            title = f"Long-Running Task ({checkpoint.task_count} tasks)"
        render_alert(console, checkpoint.message, severity="info", title=title)
        
        if checkpoint.estimated_duration_seconds:
            # Show estimate with confidence range if available
            from sunwell.agent.estimation import format_duration
            time_str = format_duration(checkpoint.estimated_duration_seconds)
            
            if checkpoint.confidence_range:
                low, high = checkpoint.confidence_range
                low_str = format_duration(low)
                high_str = format_duration(high)
                console.print(
                    f"[neutral.dim]Estimated: {time_str} "
                    f"(typically {low_str}-{high_str})[/neutral.dim]"
                )
            else:
                # Fallback to countdown-style for heuristic estimates
                render_countdown(console, checkpoint.estimated_duration_seconds)
            console.print()  # Clear the line after display
            
        if checkpoint.options:
            console.print(f"[neutral.dim]Options: {', '.join(checkpoint.options)}[/neutral.dim]")
        default = checkpoint.default or "wait"
        choice = console.input(f"[sunwell.heading]Run in background?[/sunwell.heading] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    # ═══════════════════════════════════════════════════════════════════════════
    # Ambient Intelligence Checkpoints (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    elif checkpoint.type == ChatCheckpointType.AMBIENT_ALERT:
        # Use render_alert for consistent severity-based display
        severity = checkpoint.severity or "info"
        title = checkpoint.alert_type or "Alert"
        
        # Build message with suggestion if available
        message = checkpoint.message
        if checkpoint.suggested_fix:
            message += f"\n\n{CHARS_MISC['insight']} Suggestion: {checkpoint.suggested_fix}"
        
        render_alert(console, message, severity=severity, title=title)
        
        if checkpoint.options:
            console.print(f"[neutral.dim]Options: {', '.join(checkpoint.options)}[/neutral.dim]")
        default = checkpoint.default or "ignore"
        choice = console.input(f"[sunwell.heading]Action?[/sunwell.heading] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    else:
        # Unknown checkpoint type - default to continue
        return CheckpointResponse("continue")


def _render_response(response: str, lens=None) -> None:
    """Render a conversational response with Holy Light styling."""
    lens_name = lens.metadata.name if lens and hasattr(lens, "metadata") else "Sunwell"
    console.print(f"\n[holy.radiant]{CHARS_STARS['complete']} {lens_name}:[/holy.radiant]")
    console.print(Markdown(response))
    # Add separator after response for visual break
    render_separator(console, style="mote")
    # Flush to ensure terminal is ready for next input
    sys.stdout.flush()


# =============================================================================
# Notification Helpers (Conversational DAG Architecture)
# =============================================================================

# Module-level notifier (set by run_unified_loop)
# Can be either Notifier or BatchedNotifier depending on config
_notifier: "Notifier | BatchedNotifier | None" = None


def _send_completion_notification(summary: str) -> None:
    """Send a completion notification (fire and forget).
    
    Args:
        summary: Completion summary message
    """
    import asyncio
    
    if _notifier is None:
        return
    
    try:
        # Fire and forget - don't wait for notification
        asyncio.create_task(_notifier.send_complete(summary))
    except Exception:
        # Notifications should never break the main flow
        pass


def _send_error_notification(message: str, details: str = "") -> None:
    """Send an error notification (fire and forget).
    
    Args:
        message: Error message
        details: Additional details
    """
    import asyncio
    
    if _notifier is None:
        return
    
    try:
        asyncio.create_task(_notifier.send_error(message, details=details))
    except Exception:
        pass


def _send_waiting_notification(message: str = "Input needed") -> None:
    """Send a waiting-for-input notification (fire and forget).
    
    Args:
        message: Waiting message
    """
    import asyncio
    
    if _notifier is None:
        return
    
    try:
        asyncio.create_task(_notifier.send_waiting(message))
    except Exception:
        pass
    sys.stderr.flush()
