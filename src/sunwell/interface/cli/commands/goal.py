"""Goal execution command for CLI.

Single-shot goal execution that delegates to UnifiedChatLoop.
This is essentially an alias for a single-turn conversation.

The goal command now goes through the same path as `sunwell chat`,
ensuring all UI features (intent classification, progress display,
notifications) work consistently.
"""

from pathlib import Path

import click

from sunwell.interface.cli.core.async_runner import async_command
from sunwell.interface.cli.core.theme import console, print_banner
from sunwell.interface.cli.helpers import resolve_model
from sunwell.interface.cli.helpers.project import extract_project_name
from sunwell.interface.cli.workspace_prompt import resolve_workspace_interactive


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
    from sunwell.interface.cli.notifications import Notifier, load_notification_config
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

    # Load user hooks
    hook_count = register_user_hooks(workspace)
    if hook_count > 0 and verbose:
        console.print(f"  [dim]Loaded {hook_count} user hooks[/]")

    # Load notification config
    notification_config = load_notification_config(workspace)
    notifier = Notifier(config=notification_config)

    # Create model
    try:
        synthesis_model = resolve_model(provider_override, model_override)
    except Exception as e:
        console.print(f"  [void.purple]✗[/] [sunwell.error]Failed to load model:[/] {e}")
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
        except KeyboardInterrupt:
            print('{"type": "error", "data": {"message": "Interrupted by user"}}')
        return

    # Interactive mode - use RichRenderer for events
    from rich.markdown import Markdown
    
    try:
        gen = loop.run()
        await gen.asend(None)  # Initialize
        result = await gen.asend(goal)
        
        # Process results until completion
        while result is not None:
            if isinstance(result, str):
                # Conversational response (for UNDERSTAND intents)
                console.print()
                console.print(Markdown(result))
                # Send completion notification
                await notifier.send_complete("Response generated")
                result = None
                
            elif isinstance(result, ChatCheckpoint):
                # Handle checkpoint (should auto-confirm, but handle display)
                if result.type == ChatCheckpointType.COMPLETION:
                    # Show completion summary
                    console.print(f"\n[green]★ {result.message}[/green]")
                    if result.summary:
                        console.print(f"[dim]{result.summary}[/dim]")
                    if result.files_changed:
                        console.print(f"[dim]Files: {', '.join(result.files_changed[:5])}[/dim]")
                    await notifier.send_complete(result.summary or result.message)
                    result = None
                elif result.type == ChatCheckpointType.FAILURE:
                    console.print(f"\n[red]✗ {result.message}[/red]")
                    if result.error:
                        console.print(f"[dim]{result.error}[/dim]")
                    await notifier.send_error(result.message, details=result.error or "")
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
                
    except KeyboardInterrupt:
        console.print("\n  [neutral.dim]◈ Paused by user[/]")
    except Exception as e:
        console.print(f"\n  [void.purple]✗[/] [sunwell.error]Error:[/] {e}")
        if verbose:
            import traceback
            console.print(f"[neutral.dim]{traceback.format_exc()}[/]")


def _render_event(event: AgentEvent, verbose: bool = False) -> None:
    """Render an AgentEvent to the console.
    
    Uses the same rendering logic as the unified loop but optimized
    for single-shot execution (no Live display needed).
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
            console.print(f"  [holy.gold]→[/] Intent: {path_text}")
            
            if verbose or requires_approval:
                console.print(f"     [dim]confidence: {confidence:.0%}[/]")
                if tool_scope:
                    console.print(f"     [dim]scope: {tool_scope}[/]")
                if requires_approval:
                    console.print(f"     [void.indigo]⊗ requires approval[/]")
        
        case EventType.NODE_TRANSITION:
            from_node = event.data.get("from_node", "?")
            to_node = event.data.get("to_node", "?")
            reason = event.data.get("reason", "")
            console.print(
                f"  [dim]◇ {from_node} → [/][holy.gold]{to_node}[/]"
                + (f" [dim]({reason})[/]" if reason else "")
            )
        
        # Signal extraction
        case EventType.SIGNAL:
            if event.data.get("status") == "extracting":
                console.print("[holy.radiant]✦[/] Understanding goal...", end="\r")
            elif event.data.get("signals"):
                signals = event.data["signals"]
                console.print()
                console.print("[holy.radiant]✦[/] Understanding goal...")
                console.print(f"   [holy.gold]├─[/] complexity: {signals.get('complexity', '?')}")
                console.print(f"   [holy.gold]├─[/] needs_tools: {signals.get('needs_tools', '?')}")
                conf = signals.get("effective_confidence", 0)
                console.print(f"   [holy.gold]├─[/] confidence: {conf:.0%}")
                console.print(f"   [holy.gold]└─[/] route: {signals.get('planning_route', '?')}")
        
        # Planning
        case EventType.PLAN_START:
            technique = event.data.get("technique", "unknown")
            console.print(f"[holy.radiant]✦[/] Illuminating ({technique})...")
        
        case EventType.PLAN_CANDIDATE_GENERATED:
            prog = event.data.get("progress", 1)
            total = event.data.get("total_candidates", 5)
            style = event.data.get("variance_config", {}).get("prompt_style", "?")
            artifacts = event.data.get("artifact_count", 0)
            console.print(f"   [holy.gold]✧[/] [{prog}/{total}] {style}: {artifacts} artifacts")
        
        case EventType.PLAN_WINNER:
            tasks = event.data.get("tasks", 0)
            gates = event.data.get("gates", 0)
            technique = event.data.get("technique", "unknown")
            selected = event.data.get("selected_candidate_id", "?")
            score = event.data.get("score", 0)
            console.print(f"   [holy.success]★[/] Selected: {selected} (score: {score:.1f})")
            console.print(f"\n[holy.success]★[/] [sunwell.heading]Plan ready[/] ({technique})")
            console.print(f"   [holy.gold]├─[/] {tasks} tasks")
            console.print(f"   [holy.gold]└─[/] {gates} validation gates")
        
        # Task execution
        case EventType.TASK_START:
            task_id = event.data.get("task_id", "task")
            console.print(f"[cyan]→[/] {task_id}")
        
        case EventType.TASK_COMPLETE:
            duration_ms = event.data.get("duration_ms", 0)
            console.print(f"[green]✓[/] Done ({duration_ms}ms)")
        
        # Model inference
        case EventType.MODEL_COMPLETE:
            total = event.data.get("total_tokens", 0)
            duration = event.data.get("duration_s", 0)
            tps = event.data.get("tokens_per_second", 0)
            ttft = event.data.get("time_to_first_token_ms")
            ttft_str = f", TTFT: {ttft}ms" if ttft else ""
            console.print(
                f"   [holy.success]✓[/] Generated {total} tokens "
                f"in {duration:.1f}s ({tps:.1f} tok/s{ttft_str})"
            )
        
        # Learning
        case EventType.MEMORY_LEARNING:
            fact = event.data.get("fact", "")
            console.print(f"   [holy.gold.dim]≡[/] Learned: {fact[:50]}...")
        
        # Gates
        case EventType.GATE_START:
            gate_id = event.data.get("gate_id", "gate")
            console.print(f"\n  [holy.gold]{'═' * 54}[/]")
            console.print(f"  [sunwell.phase]GATE: {gate_id}[/]")
            console.print(f"  [holy.gold]{'═' * 54}[/]")
        
        case EventType.GATE_STEP:
            step = event.data.get("step", "?")
            passed = event.data.get("passed", False)
            icon = "✧" if passed else "✗"
            color = "holy.success" if passed else "void.purple"
            console.print(f"    ├─ {step.ljust(12)} [{color}]{icon}[/]")
        
        case EventType.GATE_PASS:
            duration = event.data.get("duration_ms", 0)
            console.print(f"    └─ [holy.success]✧ PASSED[/] ({duration}ms)")
        
        case EventType.GATE_FAIL:
            failed_step = event.data.get("failed_step", "unknown")
            console.print(f"    └─ [void.purple]✗ FAILED[/] at {failed_step}")
        
        # Fixing
        case EventType.FIX_START:
            console.print("\n  [void.indigo]⚙[/] Auto-fixing...")
        
        case EventType.FIX_PROGRESS:
            stage = event.data.get("stage", "?")
            detail = event.data.get("detail", "")
            console.print(f"   [holy.gold]├─[/] {stage}: {detail}")
        
        case EventType.FIX_COMPLETE:
            console.print("   └─ [holy.success]✓[/] Fix applied")
        
        # Escalation
        case EventType.ESCALATE:
            reason = event.data.get("reason", "unknown")
            message = event.data.get("message", "")
            console.print("\n  [void.indigo]△[/] [sunwell.warning]Escalating to user[/]")
            console.print(f"    Reason: {reason}")
            if message:
                console.print(f"    {message}")
        
        # Completion
        case EventType.COMPLETE:
            tasks = event.data.get("tasks_completed", 0)
            duration = event.data.get("duration_s", 0)
            learnings = event.data.get("learnings", 0)
            
            console.print()
            console.print(f"┌{'─' * 53}┐")
            console.print(f"│  [holy.success]★ Complete[/]{'':44}│")
            console.print(f"└{'─' * 53}┘")
            console.print()
            console.print(f"  [holy.radiant]✦[/] {tasks} tasks completed in {duration:.1f}s")
            if learnings > 0:
                console.print(f"  [holy.gold.dim]≡[/] Extracted {learnings} learnings")
            console.print()
            console.print("  [holy.radiant]✦✧✦[/] Goal achieved")
            console.print()
        
        # Errors
        case EventType.ERROR:
            message = event.data.get("message", "Unknown error")
            console.print(f"\n  [void.purple]✗[/] [sunwell.error]Error:[/] {message}")
