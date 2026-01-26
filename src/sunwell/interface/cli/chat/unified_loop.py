"""RFC-135: Unified Chat-Agent Loop.

Provides seamless transitions between conversation and execution modes:
- Intent classification routes input to chat or agent
- Checkpoints enable user control at key decision points
- Progress events stream execution status to UI
"""

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown

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
) -> None:
    """Run the unified chat-agent loop (RFC-135).

    Provides seamless transitions between conversation and execution modes:
    - Intent classification routes input to chat or agent
    - Checkpoints enable user control at key decision points
    - Progress events stream execution status to UI
    """
    from sunwell.agent.chat import (
        ChatCheckpoint,
        UnifiedChatLoop,
    )
    from sunwell.agent.events import AgentEvent
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    # Set up tool executor
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

    # Create unified loop
    loop = UnifiedChatLoop(
        model=model,
        tool_executor=tool_executor,
        workspace=workspace,
        auto_confirm=auto_confirm,
        stream_progress=stream_progress,
    )

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

            if not user_input:
                continue

            # Handle quit commands directly
            if user_input.lower() in ("/quit", "/exit", "/q"):
                break

            # Send input to the loop
            result = await gen.asend(user_input)

            # Process results until we need more input
            while result is not None:
                if isinstance(result, str):
                    # Conversation response
                    _render_response(result, lens)
                    if dag:
                        dag.add_user_message(user_input)
                        dag.add_assistant_message(result, model=str(model))
                    result = None  # Wait for next user input

                elif isinstance(result, ChatCheckpoint):
                    # Handle checkpoint
                    response = _handle_checkpoint(result)
                    if response is None:
                        # User aborted
                        break
                    result = await gen.asend(response)

                elif isinstance(result, AgentEvent):
                    # Render progress event
                    _render_agent_event(result)
                    # Get next event
                    result = await gen.asend(None)

                else:
                    # Unknown result type
                    result = None

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
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.FAILURE:
        console.print(f"[red]✗ {checkpoint.message}[/red]")
        if checkpoint.error:
            console.print(f"[dim]{checkpoint.error}[/dim]")
        if checkpoint.recovery_options:
            console.print(
                f"[yellow]Recovery options: {', '.join(checkpoint.recovery_options)}[/yellow]"
            )
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
        return CheckpointResponse("done")

    elif checkpoint.type == ChatCheckpointType.INTERRUPTION:
        console.print(f"[yellow]⚡ Paused:[/yellow] {checkpoint.message}")
        if checkpoint.options:
            console.print(f"[dim]Options: {', '.join(checkpoint.options)}[/dim]")
        default = checkpoint.default or "continue"
        choice = console.input(f"[bold]Action?[/bold] [{default}] ").strip() or default
        return CheckpointResponse(choice)

    elif checkpoint.type == ChatCheckpointType.CLARIFICATION:
        console.print(f"[cyan]? {checkpoint.message}[/cyan]")
        user_input = console.input("[bold]Your response:[/bold] ").strip()
        return CheckpointResponse("respond", additional_input=user_input)

    else:
        # Unknown checkpoint type - default to continue
        return CheckpointResponse("continue")


def _render_agent_event(event: AgentEvent) -> None:
    """Render an AgentEvent for the CLI.

    Uses minimal output for streaming updates, with detailed info
    for significant events like task completion or failures.
    """
    from sunwell.agent.events import EventType

    if event.type == EventType.TASK_START:
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
