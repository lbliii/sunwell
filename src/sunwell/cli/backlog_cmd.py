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
from rich.console import Console
from rich.table import Table

from sunwell.backlog.manager import BacklogManager

if TYPE_CHECKING:
    pass

console = Console()


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

    # Human-readable table
    table = Table(title="📋 Project Backlog")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Priority", justify="right")
    table.add_column("Category", style="yellow")
    table.add_column("Complexity", style="green")
    table.add_column("Status", style="magenta")

    execution_order = backlog.execution_order()
    if not execution_order:
        console.print("📋 No goals in backlog")
        return

    for goal in execution_order[:20]:  # Show top 20
        status = "✓" if goal.id in backlog.completed else "⏳" if goal.id == backlog.in_progress else "□"
        if goal.id in backlog.blocked:
            status = "🚫"

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
    from sunwell.cli.helpers import resolve_model
    from sunwell.config import get_config
    from sunwell.execution import ExecutionManager, StdoutEmitter
    from sunwell.naaru.planners import ArtifactPlanner
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

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
            console.print(f"[yellow]⚠️  Goal already completed: {goal_id}[/yellow]")
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
            console.print(f"[yellow]🚫 Goal is blocked: {reason}[/yellow]")
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
                console.print(f"[yellow]⏳ Dependency not met: {dep_id}[/yellow]")
            return

    if not json_output:
        console.print(f"\n🎯 [bold]Running goal:[/bold] {goal.title}")
        console.print(f"   ID: {goal_id}")
        console.print(f"   Category: {goal.category}")
        console.print(f"   Complexity: {goal.estimated_complexity}")
        console.print()

    # Build the goal description for the agent
    goal_text = goal.description or goal.title

    if dry_run:
        if not json_output:
            console.print(f"[yellow]Dry run - would execute: {goal_text}[/yellow]")
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
            console.print(f"[red]❌ Failed to load model: {e}[/red]")
        return

    # Create planner
    planner = ArtifactPlanner(model=synthesis_model)

    # Create tool executor
    trust_level = ToolTrust.from_string(trust)
    executor = ToolExecutor(
        workspace=root,
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
            console.print(f"[red]❌ Failed: {result.error}[/red]")

    except Exception as e:
        if json_output:
            import json as json_module
            print(json_module.dumps({
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": __import__("time").time(),
            }))
        else:
            console.print(f"[red]❌ Execution failed: {e}[/red]")


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
        console.print("⚠️  Full execution loop requires model/agent setup")
        console.print("For parallel execution, use: sunwell backlog execute --workers 4")
        console.print("For single goals, use: sunwell agent run <goal>")


async def _execute_parallel(num_workers: int, auto: bool, dry_run: bool) -> None:
    """Execute backlog with parallel workers."""
    # Import here to avoid circular imports
    from sunwell.cli.workers_cmd import _start_workers

    await _start_workers(num_workers, category=None, dry_run=dry_run, auto=auto)


@backlog.command()
@click.option(
    "--trust",
    type=click.Choice(["conservative", "guarded", "supervised", "full"]),
    default="guarded",
    help="Trust level for guardrails (default: guarded)",
)
@click.option("--max-files", type=int, default=None, help="Override max files per goal")
@click.option("--max-lines", type=int, default=None, help="Override max lines per goal")
@click.option("--max-goals", type=int, default=None, help="Override max goals per session")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.pass_context
def autonomous(
    ctx,
    trust: str,
    max_files: int | None,
    max_lines: int | None,
    max_goals: int | None,
    dry_run: bool,
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
    """
    asyncio.run(_run_autonomous(trust, max_files, max_lines, max_goals, dry_run))


async def _run_autonomous(
    trust: str,
    max_files: int | None,
    max_lines: int | None,
    max_goals: int | None,
    dry_run: bool,
) -> None:
    """Run autonomous backlog with guardrails."""
    from sunwell.guardrails import (
        GuardrailConfig,
        GuardrailSystem,
        ScopeLimits,
        TrustLevel,
        load_config,
    )

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

    # Show configuration
    console.print("\n🛡️ [bold]Guardrails: {trust.upper()} mode[/bold]")
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
    manager = BacklogManager(root=root)
    backlog = await manager.refresh()
    goals = backlog.execution_order()

    if not goals:
        console.print("\n📋 No goals in backlog")
        return

    # Categorize goals
    auto_count = 0
    escalate_count = 0
    for goal in goals:
        if await guardrails.can_auto_approve(goal):
            auto_count += 1
        else:
            escalate_count += 1

    console.print(f"\n📋 [bold]Backlog:[/bold] {len(goals)} goals found")
    console.print(f"   ✅ {auto_count} auto-approvable (safe + simple)")
    console.print(f"   ⚠️ {escalate_count} require approval (complex or protected paths)")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes will be made[/yellow]")

        # Show what would happen
        table = Table(title="Goals that would be processed")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Auto")

        for goal in goals[:20]:
            can_auto = await guardrails.can_auto_approve(goal)
            table.add_row(
                goal.id[:8],
                goal.title[:50],
                "✅" if can_auto else "⚠️",
            )

        console.print(table)
        return

    # Start session
    try:
        session = await guardrails.start_session()
        console.print(f"\n🏷️ Session tagged: [cyan]{session.tag}[/cyan]")
    except Exception as e:
        console.print(f"\n[red]❌ Cannot start session: {e}[/red]")
        return

    console.print("\n" + "━" * 60 + "\n")

    # Process goals
    completed = 0
    skipped = 0

    for i, goal in enumerate(goals, 1):
        console.print(f"[{i}/{len(goals)}] [bold]{goal.title}[/bold]")
        console.print(f"      Category: {goal.category} | Complexity: {goal.estimated_complexity}")

        can_auto = await guardrails.can_auto_approve(goal)

        if can_auto:
            console.print("      ✅ Auto-approved")
            # In a real implementation, we'd execute the goal here
            console.print("      [dim]Execution not yet wired up[/dim]")
            completed += 1
        else:
            console.print("      ⚠️ Requires approval - skipping in demo")
            skipped += 1

        console.print()

        # Check if we can continue
        can_continue = guardrails.can_continue()
        if not can_continue.passed:
            console.print(f"[yellow]Session limit reached: {can_continue.reason}[/yellow]")
            break

    # Session complete
    console.print("━" * 60)
    stats = guardrails.get_session_stats()
    console.print("\n📊 [bold]Session Complete[/bold]")
    console.print(f"   Goals: {completed} completed, {skipped} skipped")
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

    console.print("🔄 Refreshing backlog from signals...")
    backlog = await manager.refresh()
    console.print(f"✅ Found {len(backlog.goals)} goals")


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
        console.print(f"✅ Added goal: {goals[0].title}")


@backlog.command()
@click.argument("goal_id")
@click.pass_context
def skip(ctx, goal_id: str) -> None:
    """Skip a goal."""
    manager = BacklogManager(root=Path.cwd())
    manager._load()

    if goal_id in manager.backlog.goals:
        asyncio.run(manager.block_goal(goal_id, "User skipped"))
        console.print(f"⏭️  Skipped goal: {goal_id}")
    else:
        console.print(f"❌ Goal not found: {goal_id}")


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
        console.print(f"🚫 Blocked goal: {goal_id} - {reason}")
    else:
        console.print(f"❌ Goal not found: {goal_id}")


@backlog.command()
@click.pass_context
def history(ctx) -> None:
    """View completed goals history."""
    root = Path.cwd()
    history_path = root / ".sunwell" / "backlog" / "completed.jsonl"

    if not history_path.exists():
        console.print("No completed goals yet")
        return

    table = Table(title="📜 Completed Goals")
    table.add_column("Goal ID", style="cyan")
    table.add_column("Success", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Files Changed", style="yellow")

    with history_path.open() as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                table.add_row(
                    entry.get("goal_id", "")[:8],
                    "✓" if entry.get("success") else "✗",
                    f"{entry.get('duration_seconds', 0):.1f}s",
                    str(len(entry.get("files_changed", []))),
                )

    console.print(table)
