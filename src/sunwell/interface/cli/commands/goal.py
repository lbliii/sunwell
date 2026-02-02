"""Goal execution command for CLI.

Single-shot goal execution that delegates to UnifiedChatLoop.
This is essentially an alias for a single-turn conversation.

The goal command now goes through the same path as `sunwell chat`,
ensuring all UI features (intent classification, progress display,
notifications) work consistently.

Session Tracking:
- Creates a SessionState at goal start (status=RUNNING)
- Saves as PAUSED on KeyboardInterrupt
- Sets COMPLETED/FAILED on exit
- Enables `sunwell resume` to continue interrupted goals
"""

import uuid
from datetime import datetime
from pathlib import Path

import click

from sunwell.interface.cli.core.async_runner import async_command
from sunwell.interface.cli.core.events import render_agent_event
from sunwell.interface.cli.core.render_context import reset_render_context
from sunwell.interface.cli.core.theme import (
    CHARS_DIAMONDS,
    CHARS_STARS,
    console,
    print_banner,
    render_collapsible,
    render_error,
    render_separator,
    should_reduce_motion,
    Sparkle,
)
from sunwell.interface.cli.helpers import resolve_model
from sunwell.interface.cli.helpers.project import extract_project_name
from sunwell.interface.cli.workspace_prompt import resolve_workspace_interactive


def _generate_session_id() -> str:
    """Generate a short unique session ID."""
    return uuid.uuid4().hex[:12]


def _create_goal_session(goal: str, workspace: Path) -> str:
    """Create and register a new session for goal-first execution.

    Args:
        goal: The goal being executed
        workspace: The workspace path

    Returns:
        The session ID
    """
    from sunwell.planning.naaru.session_store import SessionStore
    from sunwell.planning.naaru.types import SessionConfig, SessionState, SessionStatus

    session_id = _generate_session_id()
    config = SessionConfig(goals=(goal,))
    state = SessionState(
        session_id=session_id,
        config=config,
        status=SessionStatus.RUNNING,
        started_at=datetime.now(),
    )

    store = SessionStore()
    store.save(state)
    store.set_metadata(session_id, workspace_id=str(workspace))

    return session_id


def _update_session_status(
    session_id: str,
    status: str,
    reason: str | None = None,
) -> None:
    """Update the session status.

    Args:
        session_id: The session to update
        status: New status (completed, failed, paused)
        reason: Optional reason for the status change
    """
    from sunwell.planning.naaru.session_store import SessionStore
    from sunwell.planning.naaru.types import SessionStatus

    status_map = {
        "completed": SessionStatus.COMPLETED,
        "failed": SessionStatus.FAILED,
        "paused": SessionStatus.PAUSED,
        "running": SessionStatus.RUNNING,
    }

    store = SessionStore()
    store.update_status(session_id, status_map[status], reason)


@click.command(name="_run", hidden=True)
@click.argument("goal")
@click.option("--dry-run", is_flag=True)
@click.option("--open", "open_studio", is_flag=True, help="Open plan in Studio (with --plan)")
@click.option("--json-output", is_flag=True)
@click.option("--provider", "-p", default=None)
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--time", "-t", default=300)
@click.option("--trust", default="workspace")
@click.option("--workspace", "-w", default=None)
@click.option("--converge/--no-converge", default=False,
              help="Enable convergence loops (iterate until lint/types pass)")
@click.option("--converge-gates", default="lint,type",
              help="Gates for convergence (comma-separated: lint,type,test)")
@click.option("--converge-max", default=5, type=int,
              help="Maximum convergence iterations")
@async_command
async def run_goal(
    goal: str,
    dry_run: bool,
    open_studio: bool,
    json_output: bool,
    provider: str | None,
    model: str | None,
    verbose: bool,
    time: int,
    trust: str,
    workspace: str | None,
    converge: bool,
    converge_gates: str,
    converge_max: int,
) -> None:
    """Execute a goal (single-turn through unified loop)."""
    workspace_path = Path(workspace) if workspace else None
    
    await run_goal_unified(
        goal=goal,
        workspace_path=workspace_path,
        trust_level=trust,
        provider_override=provider,
        model_override=model,
        verbose=verbose,
        dry_run=dry_run,
        json_output=json_output,
    )


async def run_goal_unified(
    goal: str,
    workspace_path: Path | None = None,
    trust_level: str = "workspace",
    provider_override: str | None = None,
    model_override: str | None = None,
    verbose: bool = False,
    dry_run: bool = False,
    json_output: bool = False,
) -> None:
    """Execute a goal through the unified chat loop (single turn).
    
    This is the main entry point for goal execution. It delegates to
    UnifiedChatLoop with auto_confirm=True for a single-turn execution.
    
    Session tracking:
    - Creates a SessionState at start (status=RUNNING)
    - Saves as PAUSED on KeyboardInterrupt (resume with `sunwell resume`)
    - Sets COMPLETED/FAILED on exit
    
    Args:
        goal: The goal to execute
        workspace_path: Explicit workspace path
        trust_level: Trust level (read_only, workspace, shell)
        provider_override: Override provider selection
        model_override: Override model selection
        verbose: Show verbose output
        dry_run: If True, only plan without executing
        json_output: Output as JSON (uses JSONRenderer)
    """
    from sunwell.agent.chat import ChatCheckpoint, ChatCheckpointType, UnifiedChatLoop
    from sunwell.agent.events import AgentEvent
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.hooks import register_user_hooks
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

    # Show banner (except in JSON mode)
    if not json_output:
        print_banner(console, version="0.3.0", small=True)

    # Load config
    _ = get_config()

    # Resolve workspace
    project_name = extract_project_name(goal)
    workspace = resolve_workspace_interactive(
        explicit=workspace_path,
        project_name=project_name,
        quiet=not verbose,
    )

    # Create session for tracking (enables `sunwell resume`)
    session_id: str | None = None
    if not dry_run:
        try:
            session_id = _create_goal_session(goal, workspace)
        except Exception:
            # Session tracking is optional, don't fail the goal
            pass

    # Load user hooks
    hook_count = register_user_hooks(workspace)
    if hook_count > 0 and verbose:
        console.print(f"  [dim]Loaded {hook_count} user hooks[/]")

    # Create notifier with history and optional batching (from config)
    notifier = create_notifier(workspace)

    # Create model
    try:
        synthesis_model = resolve_model(provider_override, model_override)
    except Exception as e:
        render_error(console, "Failed to load model", details=str(e))
        if session_id:
            _update_session_status(session_id, "failed", str(e))
        return

    # Create tool executor
    trust_map = {
        "read_only": ToolTrust.READ_ONLY,
        "workspace": ToolTrust.WORKSPACE,
        "shell": ToolTrust.SHELL,
    }
    tool_trust = trust_map.get(trust_level, ToolTrust.WORKSPACE)
    policy = ToolPolicy(trust_level=tool_trust)

    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError:
        project = create_project_from_workspace(workspace)

    tool_executor = ToolExecutor(project=project, policy=policy)

    # Create unified loop with auto_confirm for single-shot execution
    loop = UnifiedChatLoop(
        model=synthesis_model,
        tool_executor=tool_executor,
        workspace=workspace,
        trust_level=trust_level,
        auto_confirm=True,  # No checkpoints for single-shot
        stream_progress=True,
    )

    # Create renderer based on output mode
    from sunwell.agent import create_renderer
    renderer_mode = "json" if json_output else "interactive"
    
    # For JSON output, use JSONRenderer directly
    if json_output:
        from sunwell.agent.utils.renderer import JSONRenderer
        
        async def run_json():
            gen = loop.run()
            await gen.asend(None)  # Initialize
            result = await gen.asend(goal)
            
            # Process all results
            while result is not None:
                if isinstance(result, AgentEvent):
                    import json
                    print(json.dumps(result.to_dict()))
                    result = await gen.asend(None)
                elif isinstance(result, ChatCheckpoint):
                    # Auto-confirm checkpoints
                    from sunwell.agent.chat import CheckpointResponse
                    result = await gen.asend(CheckpointResponse("y"))
                elif isinstance(result, str):
                    import json
                    print(json.dumps({"type": "response", "data": {"text": result}}))
                    result = None
                else:
                    result = None
        
        try:
            await run_json()
            if session_id:
                _update_session_status(session_id, "completed")
        except KeyboardInterrupt:
            print('{"type": "error", "data": {"message": "Interrupted by user"}}')
            if session_id:
                _update_session_status(session_id, "paused", "Interrupted by user")
        return

    # Interactive mode - use RichRenderer for events
    from rich.markdown import Markdown
    
    goal_completed = False
    goal_failed = False
    try:
        gen = loop.run()
        await gen.asend(None)  # Initialize
        result = await gen.asend(goal)
        
        # Process results until completion
        while result is not None:
            if isinstance(result, str):
                # Conversational response (for UNDERSTAND intents)
                console.print()
                console.print(f"[holy.radiant]{CHARS_STARS['complete']} Sunwell:[/holy.radiant]")
                console.print(Markdown(result))
                render_separator(console, style="mote")
                # Send completion notification
                await notifier.send_complete("Response generated")
                goal_completed = True
                result = None
                
            elif isinstance(result, ChatCheckpoint):
                # Handle checkpoint (should auto-confirm, but handle display)
                if result.type == ChatCheckpointType.COMPLETION:
                    # Show completion summary with Holy Light styling
                    console.print()
                    console.print(f"  [holy.success]{CHARS_STARS['complete']} {result.message}[/holy.success]")
                    if result.summary:
                        console.print(f"  [neutral.dim]{result.summary}[/neutral.dim]")
                    if result.files_changed:
                        console.print(f"  [neutral.dim]Files: {', '.join(result.files_changed[:5])}[/neutral.dim]")
                    # Sparkle celebration
                    if not should_reduce_motion():
                        import asyncio
                        asyncio.create_task(Sparkle.burst("", duration=0.3))
                    await notifier.send_complete(result.summary or result.message)
                    goal_completed = True
                    result = None
                elif result.type == ChatCheckpointType.FAILURE:
                    # Use render_error for proper Holy Light error display
                    render_error(
                        console,
                        result.message,
                        details=result.error,
                    )
                    await notifier.send_error(result.message, details=result.error or "")
                    goal_failed = True
                    if session_id:
                        _update_session_status(session_id, "failed", result.error or result.message)
                    result = None
                else:
                    # Auto-confirm other checkpoints
                    from sunwell.agent.chat import CheckpointResponse
                    result = await gen.asend(CheckpointResponse("y"))
                    
            elif isinstance(result, AgentEvent):
                # Render event using the event helpers
                render_agent_event(result, console, verbose)
                result = await gen.asend(None)
            else:
                result = None
        
        # Mark session as completed if we got here without failure
        if session_id and goal_completed and not goal_failed:
            _update_session_status(session_id, "completed")
                
    except KeyboardInterrupt:
        # Save session as PAUSED so it can be resumed
        if session_id:
            _update_session_status(session_id, "paused", "Interrupted by user")
        console.print(f"\n  [neutral.dim]{CHARS_DIAMONDS['inset']} Goal paused[/]")
        console.print(f"  [neutral.dim]Resume with: [holy.gold]sunwell resume[/holy.gold][/]")
    except Exception as e:
        if session_id:
            _update_session_status(session_id, "failed", str(e))
        if verbose:
            import traceback
            trace_lines = traceback.format_exc().strip().split("\n")
            render_error(console, str(e))
            render_collapsible(
                console,
                "Full traceback",
                trace_lines,
                expanded=False,
                item_count=len(trace_lines),
            )
        else:
            render_error(console, str(e))


