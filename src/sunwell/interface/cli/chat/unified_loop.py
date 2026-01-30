"""RFC-135: Unified Chat-Agent Loop.

Provides seamless transitions between conversation and execution modes:
- Intent classification routes input to chat or agent
- Checkpoints enable user control at key decision points
- Progress events stream execution status to UI
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sunwell.agent.chat import ChatCheckpoint, CheckpointResponse
    from sunwell.agent.events import AgentEvent
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.models import ModelProtocol


console = Console()


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
) -> None:
    """Run the unified chat-agent loop (RFC-135).

    Provides seamless transitions between conversation and execution modes:
    - Intent classification routes input to chat or agent
    - Checkpoints enable user control at key decision points
    - Progress events stream execution status to UI

    Args:
        tools_enabled: If False, tool_executor won't be created and TASK intents
                      will get a friendly message to enable tools.
    """
    from sunwell.agent.chat import (
        ChatCheckpoint,
        UnifiedChatLoop,
    )
    from sunwell.agent.events import AgentEvent
    from sunwell.interface.cli.hooks import register_user_hooks, unregister_user_hooks
    from sunwell.interface.cli.notifications import (
        Notifier,
        load_notification_config,
    )
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    # Load user-configurable hooks from .sunwell/hooks.toml
    hook_count = register_user_hooks(workspace)

    # Load notification config from .sunwell/config.toml
    notification_config = load_notification_config(workspace)
    notifier = Notifier(config=notification_config)
    
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
            sandbox=None,
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

    try:
        while True:
            # Get user input
            state_indicator = ""
            if loop.is_executing:
                state_indicator = " [yellow](executing)[/yellow]"
            user_input = console.input(f"\n[bold cyan]You:{state_indicator}[/bold cyan] ").strip()

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
                            console.print("[green]✓ Tools enabled[/green]")
                        else:
                            console.print("[dim]Tools already enabled[/dim]")
                        continue
                    elif parts[1] == "off":
                        if loop.tool_executor is not None:
                            loop.tool_executor = None
                            console.print("[yellow]✓ Tools disabled[/yellow]")
                        else:
                            console.print("[dim]Tools already disabled[/dim]")
                        continue
                console.print("[dim]Usage: /tools on | /tools off[/dim]")
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
                    _render_agent_event(result)
                    # Get next event
                    result = await gen.asend(None)
                    logger.debug("After event, generator returned: type=%s", type(result).__name__ if result else "None")

                else:
                    # Unknown result type
                    logger.warning("Unknown result type: %s, value=%r", type(result).__name__, result)
                    result = None

            logger.debug("Result loop ended, waiting for next input")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Saving session...[/yellow]")
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

        # Save session
        if store:
            store.save_session()
            console.print("[green]✓ Session saved[/green]")


def _handle_checkpoint(checkpoint: ChatCheckpoint) -> CheckpointResponse | None:
    """Handle a ChatCheckpoint by prompting user for decision.

    Returns:
        CheckpointResponse with user's choice, or None to abort
    """
    from sunwell.agent.chat import ChatCheckpointType, CheckpointResponse

    # Display checkpoint message
    console.print()

    if checkpoint.type == ChatCheckpointType.CONFIRMATION:
        console.print(f"[cyan]{checkpoint.message}[/cyan]")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "Y"
        choice = console.input(f"[bold]Proceed?[/bold] [{default}] ").strip() or default
        resp = CheckpointResponse(choice)
        logger.debug("CONFIRMATION: choice=%r proceed=%s", choice, resp.proceed)
        return resp

    elif checkpoint.type == ChatCheckpointType.FAILURE:
        console.print(f"[red]✗ {checkpoint.message}[/red]")
        if checkpoint.error:
            console.print(f"[dim]{checkpoint.error}[/dim]")
        if checkpoint.recovery_options:
            console.print(
                f"[yellow]Recovery options: {', '.join(checkpoint.recovery_options)}[/yellow]"
            )
        # Send error notification
        _send_error_notification(checkpoint.message, checkpoint.error or "")
        default = checkpoint.default or "abort"
        choice = console.input(f"[bold]Action?[/bold] [{default}] ").strip() or default
        if choice.lower() in ("q", "quit", "abort"):
            return None
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.COMPLETION:
        console.print(f"[green]★ {checkpoint.message}[/green]")
        if checkpoint.summary:
            console.print(f"[dim]{checkpoint.summary}[/dim]")
        if checkpoint.files_changed:
            console.print(f"[dim]Files: {', '.join(checkpoint.files_changed[:5])}[/dim]")
        # Send completion notification (fire and forget)
        _send_completion_notification(checkpoint.summary or checkpoint.message)
        return CheckpointResponse("done")

    elif checkpoint.type == ChatCheckpointType.INTERRUPTION:
        console.print(f"[yellow]⚡ Paused:[/yellow] {checkpoint.message}")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        # Send waiting notification
        _send_waiting_notification(checkpoint.message)
        default = checkpoint.default or "continue"
        choice = console.input(f"[bold]Action?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.CLARIFICATION:
        console.print(f"[cyan]? {checkpoint.message}[/cyan]")
        user_input = console.input("[bold]Your response:[/bold] ").strip()
        return CheckpointResponse("respond", additional_input=user_input)

    # ═══════════════════════════════════════════════════════════════════════════
    # Adaptive Trust Checkpoints (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    elif checkpoint.type == ChatCheckpointType.TRUST_UPGRADE:
        console.print(f"\n[cyan]🔓 Trust Upgrade Available[/cyan]")
        console.print(f"[white]{checkpoint.message}[/white]")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "no"
        choice = console.input(f"[bold]Auto-approve?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    # ═══════════════════════════════════════════════════════════════════════════
    # Background Task Checkpoints (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    elif checkpoint.type == ChatCheckpointType.BACKGROUND_OFFER:
        console.print(f"\n[cyan]⏱️ Long-Running Task[/cyan]")
        console.print(f"[white]{checkpoint.message}[/white]")
        if checkpoint.estimated_duration_seconds:
            minutes = checkpoint.estimated_duration_seconds // 60
            seconds = checkpoint.estimated_duration_seconds % 60
            if minutes > 0:
                console.print(f"[dim]Estimated time: {minutes}m {seconds}s[/dim]")
            else:
                console.print(f"[dim]Estimated time: {seconds}s[/dim]")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "wait"
        choice = console.input(f"[bold]Run in background?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    # ═══════════════════════════════════════════════════════════════════════════
    # Ambient Intelligence Checkpoints (Next-Level Chat UX)
    # ═══════════════════════════════════════════════════════════════════════════

    elif checkpoint.type == ChatCheckpointType.AMBIENT_ALERT:
        # Color based on severity
        severity = checkpoint.severity or "info"
        if severity == "error":
            color = "red"
            icon = "🚨"
        elif severity == "warning":
            color = "yellow"
            icon = "⚠️"
        else:
            color = "cyan"
            icon = "💡"

        console.print(f"\n[{color}]{icon} {checkpoint.alert_type or 'Alert'}[/{color}]")
        console.print(f"[white]{checkpoint.message}[/white]")
        if checkpoint.suggested_fix:
            console.print(f"[dim]Suggested fix: {checkpoint.suggested_fix}[/dim]")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "ignore"
        choice = console.input(f"[bold]Action?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    else:
        # Unknown checkpoint type - default to continue
        return CheckpointResponse("continue")


def _render_agent_event(event: AgentEvent) -> None:
    """Render an AgentEvent for the CLI.

    Uses minimal output for streaming updates, with detailed info
    for significant events like task completion or failures.
    """
    from sunwell.agent.events import EventType

    if event.type == EventType.SIGNAL:
        status = event.data.get("status", "")
        if status == "extracting":
            console.print("[dim]⚡ Analyzing request...[/dim]", end="\r")
        elif status == "extracted":
            console.print("[dim]⚡ Analysis complete    [/dim]")

    elif event.type == EventType.PLAN_START:
        technique = event.data.get("technique", "planning")
        console.print(f"[cyan]📋 Planning ({technique})...[/cyan]")

    elif event.type == EventType.SIGNAL_ROUTE:
        planning = event.data.get("planning", "")
        confidence = event.data.get("confidence", 0)
        console.print(f"[dim]   Route: {planning} (confidence: {confidence:.0%})[/dim]")

    elif event.type == EventType.TASK_START:
        task_desc = event.data.get("description", "Working...")[:60]
        console.print(f"[cyan]→[/cyan] {task_desc}")

    elif event.type == EventType.TASK_COMPLETE:
        duration_ms = event.data.get("duration_ms", 0)
        duration_note = f" ({duration_ms}ms)" if duration_ms else ""
        console.print(f"[green]✓[/green] Done{duration_note}")

    elif event.type == EventType.GATE_START:
        gate_name = event.data.get("gate_name", "Validation")
        console.print(f"[dim]  Checking: {gate_name}...[/dim]", end="\r")

    elif event.type == EventType.GATE_PASS:
        gate_name = event.data.get("gate_name", "Validation")
        console.print(f"[green]  ✓ {gate_name}[/green]     ")

    elif event.type == EventType.GATE_FAIL:
        error = event.data.get("error_message", "Validation failed")
        console.print(f"[red]  ✗ {error}[/red]")

    elif event.type == EventType.MODEL_TOKENS:
        # Minimal token count display (overwrite line)
        tokens = event.data.get("total_tokens", 0)
        console.print(f"[dim]  Tokens: {tokens}[/dim]", end="\r")

    elif event.type == EventType.PLAN_WINNER:
        tasks = event.data.get("tasks", 0)
        gates = event.data.get("gates", 0)
        technique = event.data.get("technique", "")
        technique_note = f" ({technique})" if technique else ""
        console.print(
            f"[cyan]★ Plan ready:[/cyan] {tasks} tasks, {gates} validation gates{technique_note}"
        )

    elif event.type == EventType.COMPLETE:
        tasks_done = event.data.get("tasks_completed", 0)
        gates_done = event.data.get("gates_passed", 0)
        duration = event.data.get("duration_s", 0)
        summary = f"{tasks_done} tasks, {gates_done} gates"
        if duration:
            summary += f" ({duration:.1f}s)"
        console.print(f"\n[green]★ Complete:[/green] {summary}")


def _render_response(response: str, lens=None) -> None:
    """Render a conversational response."""
    lens_name = lens.metadata.name if lens and hasattr(lens, "metadata") else "Sunwell"
    console.print(f"\n[bold green]{lens_name}:[/bold green]")
    console.print(Markdown(response))
    # Flush to ensure terminal is ready for next input
    sys.stdout.flush()


# =============================================================================
# Notification Helpers (Conversational DAG Architecture)
# =============================================================================

# Module-level notifier (set by run_unified_loop)
_notifier: "Notifier | None" = None


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
