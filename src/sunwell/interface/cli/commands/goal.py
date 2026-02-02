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
from sunwell.interface.cli.core.theme import (
    CHARS_CHECKS,
    CHARS_DIAMONDS,
    CHARS_MISC,
    CHARS_PROGRESS,
    CHARS_STARS,
    console,
    print_banner,
    render_alert,
    render_collapsible,
    render_complete,
    render_confidence,
    render_decision,
    render_error,
    render_gate_header,
    render_learning,
    render_metrics,
    render_phase_header,
    render_separator,
    render_step_progress,
    render_validation,
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
                _render_event(result, verbose)
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


def _render_event(event: AgentEvent, verbose: bool = False) -> None:
    """Render an AgentEvent to the console.
    
    Uses Holy Light components for consistent styling with the chat interface.
    """
    from sunwell.agent.events import EventType
    from sunwell.interface.cli.progress.dag_path import format_dag_path
    
    match event.type:
        # Intent classification (Conversational DAG Architecture)
        case EventType.INTENT_CLASSIFIED:
            path_parts = event.data.get("path", [])
            confidence = event.data.get("confidence", 0)
            requires_approval = event.data.get("requires_approval", False)
            tool_scope = event.data.get("tool_scope")
            
            path_text = format_dag_path(path_parts) if path_parts else event.data.get("path_formatted", "")
            
            console.print()
            console.print(f"  [holy.gold]{CHARS_PROGRESS['arrow']}[/] Intent: {path_text}")
            
            if verbose or requires_approval:
                render_confidence(console, confidence, label="confidence")
                if tool_scope:
                    console.print(f"     [neutral.dim]scope: {tool_scope}[/]")
                if requires_approval:
                    console.print(f"     [void.indigo]{CHARS_MISC['approval']} requires approval[/]")
        
        case EventType.NODE_TRANSITION:
            from_node = event.data.get("from_node", "?")
            to_node = event.data.get("to_node", "?")
            reason = event.data.get("reason", "")
            console.print(
                f"  [neutral.dim]{CHARS_DIAMONDS['hollow']} {from_node} → [/][holy.gold]{to_node}[/]"
                + (f" [neutral.dim]({reason})[/]" if reason else "")
            )
        
        # Signal extraction
        case EventType.SIGNAL:
            if event.data.get("status") == "extracting":
                render_phase_header(console, "understanding")
            elif event.data.get("signals"):
                signals = event.data["signals"]
                console.print(f"  [holy.radiant]{CHARS_STARS['radiant']}[/] Understanding goal...")
                console.print(f"   [holy.gold]├─[/] complexity: {signals.get('complexity', '?')}")
                console.print(f"   [holy.gold]├─[/] needs_tools: {signals.get('needs_tools', '?')}")
                conf = signals.get("effective_confidence", 0)
                render_confidence(console, conf, label="confidence")
                console.print(f"   [holy.gold]└─[/] route: {signals.get('planning_route', '?')}")
        
        # Planning
        case EventType.PLAN_START:
            technique = event.data.get("technique", "unknown")
            render_phase_header(console, "illuminating")
            console.print(f"  [neutral.dim]Technique: {technique}[/]")
        
        case EventType.PLAN_CANDIDATE_GENERATED:
            prog = event.data.get("progress", 1)
            total = event.data.get("total_candidates", 5)
            style = event.data.get("variance_config", {}).get("prompt_style", "?")
            artifacts = event.data.get("artifact_count", 0)
            render_step_progress(console, prog, total, description=f"{style}: {artifacts} artifacts")
        
        case EventType.PLAN_WINNER:
            tasks = event.data.get("tasks", 0)
            gates = event.data.get("gates", 0)
            technique = event.data.get("technique", "unknown")
            rationale = event.data.get("rationale", "")
            console.print()
            render_decision(
                console,
                f"Plan selected: {tasks} tasks, {gates} gates",
                rationale=rationale or technique,
            )
        
        # Task execution
        case EventType.TASK_START:
            task_id = event.data.get("task_id", "task")
            task_num = event.data.get("task_number", 0)
            total_tasks = event.data.get("total_tasks", 0)
            description = event.data.get("description", task_id)[:60]
            
            if event.data.get("first_task") or task_id == "1":
                render_phase_header(console, "crafting")
            
            if task_num > 0 and total_tasks > 0:
                render_step_progress(console, task_num, total_tasks, description=description)
            else:
                console.print(f"  [holy.gold]{CHARS_DIAMONDS['hollow']}[/] {description}")
        
        case EventType.TASK_COMPLETE:
            duration_ms = event.data.get("duration_ms", 0)
            render_validation(console, "Task", passed=True, details=f"{duration_ms}ms")
        
        # Model inference
        case EventType.MODEL_COMPLETE:
            total = event.data.get("total_tokens", 0)
            duration = event.data.get("duration_s", 0)
            tps = event.data.get("tokens_per_second", 0)
            ttft = event.data.get("time_to_first_token_ms")
            render_metrics(console, {
                "total_tokens": total,
                "duration_s": duration,
                "tokens_per_second": tps,
                "time_to_first_token_ms": ttft,
            })
        
        # Learning
        case EventType.MEMORY_LEARNING:
            fact = event.data.get("fact", "")
            source = event.data.get("source", "")
            render_learning(console, fact, source)
        
        # Gates
        case EventType.GATE_START:
            gate_id = event.data.get("gate_id", "gate")
            render_phase_header(console, "verifying")
            render_gate_header(console, gate_id)
        
        case EventType.GATE_STEP:
            step = event.data.get("step", "?")
            passed = event.data.get("passed", False)
            render_validation(console, step, passed=passed)
        
        case EventType.GATE_PASS:
            gate_name = event.data.get("gate_name", "Validation")
            duration = event.data.get("duration_ms", 0)
            render_validation(console, gate_name, passed=True, details=f"{duration}ms")
        
        case EventType.GATE_FAIL:
            gate_name = event.data.get("gate_name", "Validation")
            failed_step = event.data.get("failed_step", "unknown")
            error_trace = event.data.get("error_trace", [])
            render_validation(console, gate_name, passed=False, details=f"at {failed_step}")
            
            # Show collapsible error trace if available
            if error_trace:
                render_collapsible(
                    console,
                    "Error trace",
                    error_trace,
                    expanded=False,
                    item_count=len(error_trace),
                )
        
        # Fixing
        case EventType.FIX_START:
            console.print(f"\n  [void.indigo]{CHARS_MISC['gear']}[/] Auto-fixing...")
        
        case EventType.FIX_PROGRESS:
            stage = event.data.get("stage", "?")
            detail = event.data.get("detail", "")
            console.print(f"   [holy.gold]├─[/] {stage}: {detail}")
        
        case EventType.FIX_COMPLETE:
            render_validation(console, "Fix", passed=True)
        
        # Escalation
        case EventType.ESCALATE:
            reason = event.data.get("reason", "unknown")
            message = event.data.get("message", "")
            render_alert(
                console,
                f"Reason: {reason}\n{message}" if message else f"Reason: {reason}",
                severity="warning",
                title="Escalating to user",
            )
        
        # Completion
        case EventType.COMPLETE:
            tasks = event.data.get("tasks_completed", 0)
            gates = event.data.get("gates_passed", 0)
            duration = event.data.get("duration_s", 0)
            learnings = event.data.get("learnings_extracted", 0)
            files_created = event.data.get("files_created", [])
            files_modified = event.data.get("files_modified", [])
            
            render_complete(
                console,
                tasks_completed=tasks,
                gates_passed=gates,
                duration_s=duration,
                learnings=learnings,
                files_created=files_created,
                files_modified=files_modified,
            )
            
            # Sparkle celebration
            if not should_reduce_motion():
                import asyncio
                asyncio.create_task(Sparkle.burst("Goal achieved", duration=0.3))
        
        # Errors
        case EventType.ERROR:
            message = event.data.get("message", "Unknown error")
            details = event.data.get("details")
            render_error(console, message, details=details)
