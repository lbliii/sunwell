"""CLI commands for Autonomous Backlog (RFC-046).

Provides:
- sunwell backlog: View prioritized backlog
- sunwell backlog run <id>: Execute a specific goal by ID (RFC-056)
- sunwell backlog --execute: Execute in supervised mode
- sunwell backlog --autonomous: Execute with guardrails (RFC-048)
- sunwell backlog refresh: Force refresh from signals
- sunwell backlog add "goal": Add explicit goal
- sunwell backlog skip <id>: Skip a goal
- sunwell backlog block <id> "reason": Block a goal
- sunwell backlog history: View completed goals
"""


import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.table import Table

from sunwell.features.backlog.manager import BacklogManager
from sunwell.interface.cli.core.theme import create_sunwell_console

if TYPE_CHECKING:
    from sunwell.agent.execution import ExecutionManager, ExecutionResult
    from sunwell.features.backlog.goals import Goal
    from sunwell.planning.naaru.planners import ArtifactPlanner
    from sunwell.quality.guardrails import GuardrailSystem
    from sunwell.tools.execution import ToolExecutor

console = create_sunwell_console()


# =============================================================================
# Execution Helpers
# =============================================================================


async def _execute_goal_with_guardrails(
    goal: Goal,
    manager: ExecutionManager,
    planner: ArtifactPlanner,
    executor: ToolExecutor,
    guardrails: GuardrailSystem | None = None,
    verbose: bool = False,
) -> ExecutionResult | None:
    """Execute a single goal with optional guardrail integration.

    This is the core execution helper used by both `backlog run` and
    `backlog autonomous` commands.

    Args:
        goal: The goal to execute
        manager: ExecutionManager for backlog lifecycle
        planner: ArtifactPlanner for discovering artifacts
        executor: ToolExecutor for running tools
        guardrails: Optional GuardrailSystem for checkpointing
        verbose: Whether to show verbose output

    Returns:
        ExecutionResult if successful, None if execution failed
    """
    from sunwell.quality.guardrails.types import FileChange

    goal_text = goal.description or goal.title

    try:
        # Execute via ExecutionManager
        result = await manager.run_goal(
            goal=goal_text,
            planner=planner,
            executor=executor,
            goal_id=goal.id,
            verbose=verbose,
        )

        # Record checkpoint with guardrails if provided
        if guardrails and result.success:
            changes = [
                FileChange(path=Path(p))
                for p in result.artifacts_created
            ]
            await guardrails.checkpoint_goal(goal, changes)

        return result

    except Exception as e:
        console.print(f"[void.purple]✗ Execution failed: {e}[/void.purple]")
        return None


@click.group()
def backlog() -> None:
    """Autonomous Backlog — Self-directed goal generation.

    Sunwell continuously observes project state and identifies what should
    exist but doesn't — applying artifact-first decomposition to goal selection.

    Examples:

        sunwell backlog                    # View prioritized backlog
        sunwell backlog --execute          # Execute in supervised mode
        sunwell backlog refresh            # Force refresh from signals
        sunwell backlog add "Fix auth bug" # Add explicit goal
        sunwell backlog skip 3             # Skip a goal
        sunwell backlog history            # View completed goals
    """
    pass


@backlog.command()
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.option("--mermaid", is_flag=True, help="Export dependency graph as Mermaid")
@click.pass_context
def show(ctx, json_output: bool, mermaid: bool) -> None:
    """Show prioritized backlog."""
    asyncio.run(_show_backlog(json_output, mermaid))


async def _show_backlog(json_output: bool, mermaid: bool) -> None:
    """Show backlog."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    backlog = await manager.refresh()

    if json_output:
        data = {
            "goals": [
                {
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "priority": g.priority,
                    "category": g.category,
                    "complexity": g.estimated_complexity,
                    "auto_approvable": g.auto_approvable,
                    "requires": list(g.requires),
                }
                for g in backlog.goals.values()
            ],
            "completed": list(backlog.completed),
            "in_progress": backlog.in_progress,
            "blocked": backlog.blocked,
        }
        console.print(json.dumps(data, indent=2))
        return

    if mermaid:
        console.print(backlog.to_mermaid())
        return

    # Human-readable table (RFC-131: Holy Light styling)
    table = Table(title="≡ Project Backlog")
    table.add_column("ID", style="holy.radiant")
    table.add_column("Title")
    table.add_column("Priority", justify="right")
    table.add_column("Category", style="holy.gold")
    table.add_column("Complexity", style="holy.success")
    table.add_column("Status")

    execution_order = backlog.execution_order()
    if not execution_order:
        console.print("[neutral.dim]≡ No goals in backlog[/neutral.dim]")
        return

    for goal in execution_order[:20]:  # Show top 20
        if goal.id in backlog.completed:
            status = "[holy.success]★[/]"
        elif goal.id == backlog.in_progress:
            status = "[holy.radiant]◎[/]"
        elif goal.id in backlog.blocked:
            status = "[void.purple]✗[/]"
        else:
            status = "[neutral.dim]◇[/]"

        table.add_row(
            goal.id[:8],
            goal.title[:50],
            f"{goal.priority:.2f}",
            goal.category,
            goal.estimated_complexity,
            status,
        )

    console.print(table)

    if len(execution_order) > 20:
        console.print(f"\n... and {len(execution_order) - 20} more goals")


@backlog.command("run")
@click.argument("goal_id")
@click.option(
    "--provider", "-p",
    type=click.Choice(["openai", "anthropic", "ollama"]),
    default=None,
    help="Model provider (default: from config)",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override model selection",
)
@click.option(
    "--time", "-t",
    default=300,
    help="Max execution time in seconds (default: 300)",
)
@click.option(
    "--trust",
    type=click.Choice(["read_only", "workspace", "shell"]),
    default="workspace",
    help="Tool trust level",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Plan only, don't execute",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output NDJSON events for programmatic consumption (RFC-056)",
)
@click.pass_context
def run_goal(
    ctx,
    goal_id: str,
    provider: str | None,
    model: str | None,
    time: int,
    trust: str,
    dry_run: bool,
    verbose: bool,
    json_output: bool,
) -> None:
    """Execute a specific backlog goal by ID (RFC-056).

    This runs a goal from the existing backlog, preserving the goal's
    metadata and marking it as in_progress/completed.

    \b
    Examples:
        sunwell backlog run add-auth
        sunwell backlog run user-model --dry-run
        sunwell backlog run fix-bug --json  # For Studio integration
        sunwell backlog run auth --provider openai  # Use OpenAI

    Use 'sunwell backlog show' to see available goal IDs.
    """
    asyncio.run(_run_backlog_goal(
        goal_id, provider, model, time, trust, dry_run, verbose, json_output
    ))


async def _run_backlog_goal(
    goal_id: str,
    provider_override: str | None,
    model_override: str | None,
    time: int,
    trust: str,
    dry_run: bool,
    verbose: bool,
    json_output: bool,
) -> None:
    """Execute a specific backlog goal via ExecutionManager (RFC-094)."""
    from sunwell.agent.execution import ExecutionManager, StdoutEmitter
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.planning.naaru.planners import ArtifactPlanner
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    root = Path.cwd()
    emitter = StdoutEmitter(json_output=json_output)
    manager = ExecutionManager(root=root, emitter=emitter)

    # Find the goal
    goal = manager.backlog.backlog.goals.get(goal_id)

    # Also try partial match if exact match not found
    if goal is None:
        for gid, g in manager.backlog.backlog.goals.items():
            if gid.startswith(goal_id) or goal_id in gid:
                goal = g
                goal_id = gid
                break

    if goal is None:
        if json_output:
            import json as json_module
            print(json_module.dumps({
                "type": "error",
                "data": {"message": f"Goal not found: {goal_id}"},
                "timestamp": __import__("time").time(),
            }))
        else:
            console.print(f"[red]❌ Goal not found: {goal_id}[/red]")
            console.print("\nAvailable goals:")
            for gid in list(manager.backlog.backlog.goals.keys())[:10]:
                console.print(f"  - {gid}")
        return

    # Check if goal is already completed
    if goal_id in manager.backlog.backlog.completed:
        if json_output:
            import json as json_module
            print(json_module.dumps({
                "type": "error",
                "data": {"message": f"Goal already completed: {goal_id}"},
                "timestamp": __import__("time").time(),
            }))
        else:
            console.print(f"[holy.gold]△ Goal already completed: {goal_id}[/holy.gold]")
        return

    # Check if blocked
    if goal_id in manager.backlog.backlog.blocked:
        reason = manager.backlog.backlog.blocked[goal_id]
        if json_output:
            import json as json_module
            print(json_module.dumps({
                "type": "error",
                "data": {"message": f"Goal is blocked: {reason}"},
                "timestamp": __import__("time").time(),
            }))
        else:
            console.print(f"[void.purple]✗ Goal is blocked: {reason}[/void.purple]")
        return

    # Check dependencies
    for dep_id in goal.requires:
        if dep_id not in manager.backlog.backlog.completed:
            if json_output:
                import json as json_module
                print(json_module.dumps({
                    "type": "error",
                    "data": {"message": f"Dependency not met: {dep_id}"},
                    "timestamp": __import__("time").time(),
                }))
            else:
                console.print(f"[holy.gold]◇ Dependency not met: {dep_id}[/holy.gold]")
            return

    if not json_output:
        console.print(f"\n[sunwell.heading]◆ Running goal:[/] {goal.title}")
        console.print(f"   ID: {goal_id}")
        console.print(f"   Category: {goal.category}")
        console.print(f"   Complexity: {goal.estimated_complexity}")
        console.print()

    # Build the goal description for the agent
    goal_text = goal.description or goal.title

    if dry_run:
        if not json_output:
            console.print(f"[holy.gold]Dry run - would execute: {goal_text}[/holy.gold]")
        return

    # Load config and create agent
    config = get_config()

    try:
        synthesis_model = resolve_model(provider_override, model_override)
        if verbose:
            provider = provider_override or (config.model.default_provider if config else "ollama")
            model_name = model_override or (config.model.default_model if config else "gemma3:4b")
            console.print(f"[dim]Using model: {provider}:{model_name}[/dim]")
    except Exception as e:
        if json_output:
            import json as json_module
            print(json_module.dumps({
                "type": "error",
                "data": {"message": f"Failed to load model: {e}"},
                "timestamp": __import__("time").time(),
            }))
        else:
            console.print(f"[void.purple]✗ Failed to load model: {e}[/void.purple]")
        return

    # Create planner
    planner = ArtifactPlanner(model=synthesis_model)

    # RFC-117: Try to resolve project context
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )

    try:
        project = resolve_project(project_root=root)
    except ProjectResolutionError:
        project = create_project_from_workspace(root)

    # Create tool executor
    trust_level = ToolTrust.from_string(trust)
    executor = ToolExecutor(
        project=project,
        policy=ToolPolicy(trust_level=trust_level),
    )

    # Execute via ExecutionManager (RFC-094)
    # All backlog state management (claim, complete, events) is handled internally
    try:
        result = await manager.run_goal(
            goal=goal_text,
            planner=planner,
            executor=executor,
            goal_id=goal_id,
        )

        if not result.success and not json_output:
            console.print(f"[void.purple]✗ Failed: {result.error}[/void.purple]")

    except Exception as e:
        if json_output:
            import json as json_module
            print(json_module.dumps({
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": __import__("time").time(),
            }))
        else:
            console.print(f"[void.purple]✗ Execution failed: {e}[/void.purple]")


@backlog.command()
@click.option("--approve", help="Comma-separated goal IDs to pre-approve")
@click.option("--workers", "-n", "num_workers", type=int, default=None,
              help="Number of parallel workers (RFC-051)")
@click.option("--auto", is_flag=True, help="Auto-detect optimal worker count")
@click.option("--dry-run", is_flag=True, help="Show what would happen")
@click.pass_context
def execute(
    ctx,
    approve: str | None,
    num_workers: int | None,
    auto: bool,
    dry_run: bool,
) -> None:
    """Execute backlog in supervised mode.

    Use --workers for parallel execution (RFC-051):

        sunwell backlog execute --workers 4    # Use 4 workers
        sunwell backlog execute --workers auto # Auto-detect count
        sunwell backlog execute --dry-run      # Preview only

    For serial execution, use 'sunwell agent run' for individual goals.
    """
    if num_workers is not None or auto:
        # Delegate to parallel workers command
        asyncio.run(_execute_parallel(num_workers or 4, auto, dry_run))
    else:
        console.print("[holy.gold]△ Full execution loop requires model/agent setup[/holy.gold]")
        console.print("For parallel execution: sunwell backlog execute --workers 4")
        console.print("For single goals: sunwell agent run <goal>")


async def _execute_parallel(num_workers: int, auto: bool, dry_run: bool) -> None:
    """Execute backlog with parallel workers."""
    # Import here to avoid circular imports
    from sunwell.interface.cli.commands.workers_cmd import _start_workers

    await _start_workers(num_workers, category=None, dry_run=dry_run, auto=auto)


@backlog.command()
@click.option(
    "--trust",
    type=click.Choice(["conservative", "guarded", "supervised", "full"]),
    default="guarded",
    help="Trust level for guardrails (default: guarded)",
)
@click.option(
    "--provider", "-p",
    type=click.Choice(["openai", "anthropic", "ollama"]),
    default=None,
    help="Model provider (default: from config)",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override model selection",
)
@click.option("--max-files", type=int, default=None, help="Override max files per goal")
@click.option("--max-lines", type=int, default=None, help="Override max lines per goal")
@click.option("--max-goals", type=int, default=None, help="Override max goals per session")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Auto-approve all escalations (use with caution)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def autonomous(
    ctx,
    trust: str,
    provider: str | None,
    model: str | None,
    max_files: int | None,
    max_lines: int | None,
    max_goals: int | None,
    dry_run: bool,
    yes: bool,
    verbose: bool,
) -> None:
    """Execute backlog autonomously with guardrails (RFC-048).

    Guardrails ensure safe unsupervised operation:
    - Actions are classified by risk level
    - Scope limits prevent runaway changes
    - Each goal creates a git checkpoint
    - Session can be rolled back if needed

    Examples:

        sunwell backlog autonomous                    # Run with defaults
        sunwell backlog autonomous --trust supervised # Ask for dangerous only
        sunwell backlog autonomous --max-files 20     # Override file limit
        sunwell backlog autonomous --dry-run          # Preview without executing
        sunwell backlog autonomous --yes              # Auto-approve all (dangerous)
    """
    asyncio.run(_run_autonomous(
        trust, provider, model, max_files, max_lines, max_goals, dry_run, yes, verbose
    ))


async def _run_autonomous(
    trust: str,
    provider: str | None,
    model: str | None,
    max_files: int | None,
    max_lines: int | None,
    max_goals: int | None,
    dry_run: bool,
    yes: bool,
    verbose: bool,
) -> None:
    """Run autonomous backlog with guardrails."""
    from sunwell.agent.execution import ExecutionManager, StdoutEmitter
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.helpers import CLIEscalationUI, resolve_model
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )
    from sunwell.planning.naaru.planners import ArtifactPlanner
    from sunwell.quality.guardrails import (
        GuardrailConfig,
        GuardrailSystem,
        ScopeLimits,
        TrustLevel,
        load_config,
    )
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    root = Path.cwd()

    # Load config with overrides
    config = load_config(root)

    # Apply trust level
    config = GuardrailConfig(
        trust_level=TrustLevel(trust),
        scope=ScopeLimits(
            max_files_per_goal=max_files or config.scope.max_files_per_goal,
            max_lines_changed_per_goal=max_lines or config.scope.max_lines_changed_per_goal,
            max_goals_per_session=max_goals or config.scope.max_goals_per_session,
            max_files_per_session=config.scope.max_files_per_session,
            max_lines_per_session=config.scope.max_lines_per_session,
            max_duration_per_session_hours=config.scope.max_duration_per_session_hours,
            require_tests_for_source_changes=config.scope.require_tests_for_source_changes,
            require_git_clean_start=config.scope.require_git_clean_start,
            commit_after_each_goal=config.scope.commit_after_each_goal,
        ),
        verification=config.verification,
        trust_zones=config.trust_zones,
        auto_approve_categories=config.auto_approve_categories,
        auto_approve_complexity=config.auto_approve_complexity,
    )

    # Create guardrail system
    guardrails = GuardrailSystem(repo_path=root, config=config)

    # Configure CLI escalation UI
    cli_ui = CLIEscalationUI(console=console)
    guardrails.escalation_handler.ui = cli_ui

    # If --yes flag, configure auto-response
    if yes:
        console.print("\n[yellow]⚠ Warning: --yes flag set. All escalations will be auto-approved.[/yellow]")
        guardrails.escalation_handler.auto_response = "approve"

    # Show configuration
    console.print(f"\n🛡️ [bold]Guardrails: {trust.upper()} mode[/bold]")
    console.print(f"   Trust zones: {len(config.trust_zones) + 7} (includes defaults)")
    scope = config.scope
    console.print(
        f"   Scope limits: {scope.max_files_per_goal} files/goal, "
        f"{scope.max_lines_changed_per_goal} lines/goal, "
        f"{scope.max_goals_per_session} goals/session"
    )
    console.print(
        f"   Verification: {config.verification.safe_threshold:.0%} (safe), "
        f"{config.verification.moderate_threshold:.0%} (moderate)"
    )

    # Refresh backlog
    backlog_manager = BacklogManager(root=root)
    backlog = await backlog_manager.refresh()
    goals = backlog.execution_order()

    if not goals:
        console.print("\n[neutral.dim]≡ No goals in backlog[/neutral.dim]")
        return

    # Categorize goals
    auto_count = 0
    escalate_count = 0
    for goal in goals:
        if await guardrails.can_auto_approve(goal):
            auto_count += 1
        else:
            escalate_count += 1

    console.print(f"\n[sunwell.heading]≡ Backlog:[/] {len(goals)} goals found")
    console.print(f"   [holy.success]★[/] {auto_count} auto-approvable (safe + simple)")
    console.print(f"   [holy.gold]△[/] {escalate_count} require approval")

    if dry_run:
        console.print("\n[holy.gold]Dry run - no changes will be made[/holy.gold]")

        # Show what would happen
        table = Table(title="Goals that would be processed")
        table.add_column("ID", style="holy.radiant")
        table.add_column("Title")
        table.add_column("Auto")

        for goal in goals[:20]:
            can_auto = await guardrails.can_auto_approve(goal)
            table.add_row(
                goal.id[:8],
                goal.title[:50],
                "[holy.success]★[/]" if can_auto else "[holy.gold]△[/]",
            )

        console.print(table)
        return

    # ==========================================================================
    # Setup execution infrastructure
    # ==========================================================================

    # Load model
    app_config = get_config()
    try:
        synthesis_model = resolve_model(provider, model)
        if verbose:
            provider_name = provider or (app_config.model.default_provider if app_config else "ollama")
            model_name = model or (app_config.model.default_model if app_config else "gemma3:4b")
            console.print(f"[dim]Using model: {provider_name}:{model_name}[/dim]")
    except Exception as e:
        console.print(f"[void.purple]✗ Failed to load model: {e}[/void.purple]")
        return

    # Create planner
    planner = ArtifactPlanner(model=synthesis_model)

    # Resolve project context
    try:
        project = resolve_project(project_root=root)
    except ProjectResolutionError:
        project = create_project_from_workspace(root)

    # Create tool executor
    trust_level = ToolTrust.from_string("workspace")  # Default for autonomous
    executor = ToolExecutor(
        project=project,
        policy=ToolPolicy(trust_level=trust_level),
    )

    # Create execution manager
    emitter = StdoutEmitter(json_output=False)
    exec_manager = ExecutionManager(root=root, emitter=emitter)

    # ==========================================================================
    # Start session
    # ==========================================================================

    try:
        session = await guardrails.start_session()
        console.print(f"\n[sunwell.heading]◆ Session tagged:[/] {session.tag}")
    except Exception as e:
        console.print(f"\n[void.purple]✗ Cannot start session: {e}[/void.purple]")
        return

    console.print("\n" + "━" * 60 + "\n")

    # ==========================================================================
    # Process goals
    # ==========================================================================

    completed = 0
    skipped = 0
    failed = 0
    artifacts_created = 0
    skip_all_escalations = False

    for i, goal in enumerate(goals, 1):
        console.print(f"[{i}/{len(goals)}] [sunwell.heading]{goal.title}[/]")
        console.print(f"      Category: {goal.category} | Complexity: {goal.estimated_complexity}")

        can_auto = await guardrails.can_auto_approve(goal)

        should_execute = False

        if can_auto:
            console.print("      [holy.success]★ Auto-approved[/holy.success]")
            should_execute = True
        elif skip_all_escalations:
            console.print("      [holy.gold]△ Skipped (skip-all mode)[/holy.gold]")
            skipped += 1
        else:
            # Escalate to user
            console.print("      [holy.gold]△ Requires approval[/holy.gold]")
            resolution = await guardrails.escalate_goal(goal)

            if resolution.action == "approve":
                should_execute = True
            elif resolution.action == "skip_all":
                skip_all_escalations = True
                skipped += 1
                console.print("      [dim]Skipping all remaining escalations[/dim]")
            elif resolution.action == "abort":
                console.print("\n[holy.gold]Session aborted by user[/holy.gold]")
                break
            else:
                skipped += 1
                console.print("      [dim]Skipped[/dim]")

        # Execute if approved
        if should_execute:
            result = await _execute_goal_with_guardrails(
                goal=goal,
                manager=exec_manager,
                planner=planner,
                executor=executor,
                guardrails=guardrails,
                verbose=verbose,
            )

            if result and result.success:
                completed += 1
                artifacts_created += len(result.artifacts_created)
                console.print(
                    f"      [holy.success]✓ Completed[/] "
                    f"({len(result.artifacts_created)} artifacts, {result.duration_ms}ms)"
                )
            else:
                failed += 1
                error_msg = result.error if result else "Unknown error"
                console.print(f"      [void.purple]✗ Failed: {error_msg}[/void.purple]")

        console.print()

        # Check if we can continue
        can_continue = guardrails.can_continue()
        if not can_continue.passed:
            console.print(f"[holy.gold]Session limit reached: {can_continue.reason}[/holy.gold]")
            break

    # ==========================================================================
    # Session complete
    # ==========================================================================

    console.print("━" * 60)
    stats = guardrails.get_session_stats()
    remaining = len(goals) - completed - skipped - failed

    console.print("\n[sunwell.heading]◆ Session Complete[/sunwell.heading]")
    console.print(f"   Goals: {completed} completed, {failed} failed, {skipped} skipped, {remaining} remaining")
    console.print(f"   Artifacts: {artifacts_created} created")
    console.print(f"   Duration: {stats['duration_minutes']:.1f} minutes")
    console.print(f"\n   To rollback: sunwell guardrails rollback {session.tag}")


@backlog.command()
@click.pass_context
def refresh(ctx) -> None:
    """Force refresh backlog from signals."""
    asyncio.run(_refresh_backlog())


async def _refresh_backlog() -> None:
    """Refresh backlog."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    console.print("[holy.radiant]↻ Refreshing backlog from signals...[/holy.radiant]")
    backlog = await manager.refresh()
    console.print(f"[holy.success]★ Found {len(backlog.goals)} goals[/holy.success]")


@backlog.command()
@click.argument("goal")
@click.pass_context
def add(ctx, goal: str) -> None:
    """Add explicit goal to backlog."""
    asyncio.run(_add_goal(goal))


async def _add_goal(goal: str) -> None:
    """Add goal."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    # Generate goal from explicit text
    goals = await manager.goal_generator.generate(
        observable_signals=[],
        intelligence_signals=[],
        explicit_goals=[goal],
    )

    if goals:
        # Add to backlog
        manager.backlog.goals[goals[0].id] = goals[0]
        manager._save()
        console.print(f"[holy.success]★ Added goal: {goals[0].title}[/holy.success]")


@backlog.command()
@click.argument("goal_id")
@click.pass_context
def skip(ctx, goal_id: str) -> None:
    """Skip a goal."""
    manager = BacklogManager(root=Path.cwd())
    manager._load()

    if goal_id in manager.backlog.goals:
        asyncio.run(manager.block_goal(goal_id, "User skipped"))
        console.print(f"[neutral.dim]◇ Skipped goal: {goal_id}[/neutral.dim]")
    else:
        console.print(f"[void.purple]✗ Goal not found: {goal_id}[/void.purple]")


@backlog.command()
@click.argument("goal_id")
@click.argument("reason")
@click.pass_context
def block(ctx, goal_id: str, reason: str) -> None:
    """Block a goal with reason."""
    manager = BacklogManager(root=Path.cwd())
    manager._load()

    if goal_id in manager.backlog.goals:
        asyncio.run(manager.block_goal(goal_id, reason))
        console.print(f"[void.purple]✗ Blocked goal: {goal_id} - {reason}[/void.purple]")
    else:
        console.print(f"[void.purple]✗ Goal not found: {goal_id}[/void.purple]")


@backlog.command()
@click.pass_context
def history(ctx) -> None:
    """View completed goals history."""
    root = Path.cwd()
    history_path = root / ".sunwell" / "backlog" / "completed.jsonl"

    if not history_path.exists():
        console.print("[neutral.dim]No completed goals yet[/neutral.dim]")
        return

    table = Table(title="≡ Completed Goals")
    table.add_column("Goal ID", style="holy.radiant")
    table.add_column("Success", style="holy.success")
    table.add_column("Duration", justify="right")
    table.add_column("Files Changed", style="holy.gold")

    with history_path.open() as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                table.add_row(
                    entry.get("goal_id", "")[:8],
                    "★" if entry.get("success") else "✗",
                    f"{entry.get('duration_seconds', 0):.1f}s",
                    str(len(entry.get("files_changed", []))),
                )

    console.print(table)
