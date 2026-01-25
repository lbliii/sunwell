"""CLI commands for Autonomy Guardrails (RFC-048).

Provides:
- sunwell guardrails show: Show current guardrail configuration
- sunwell guardrails check: Validate goals against guardrails
- sunwell guardrails history: View session history
- sunwell guardrails rollback: Rollback session or goal
"""


import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def guardrails() -> None:
    """Autonomy Guardrails — Safe unsupervised operation.

    Guardrails define what Sunwell can do autonomously and what requires
    human approval. The system classifies actions by risk level and
    enforces scope limits.

    Examples:

        sunwell guardrails show              # Show current configuration
        sunwell guardrails check             # Validate goals against guardrails
        sunwell guardrails history           # View session history
        sunwell guardrails rollback <id>     # Rollback a session
    """
    pass


@guardrails.command()
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def show(ctx, json_output: bool) -> None:
    """Show current guardrail configuration."""
    from sunwell.guardrails import load_config

    root = Path.cwd()
    config = load_config(root)

    if json_output:
        import json as json_lib

        data = {
            "trust_level": config.trust_level.value,
            "scope": {
                "max_files_per_goal": config.scope.max_files_per_goal,
                "max_lines_per_goal": config.scope.max_lines_changed_per_goal,
                "max_goals_per_session": config.scope.max_goals_per_session,
                "max_files_per_session": config.scope.max_files_per_session,
                "require_tests_for_source": config.scope.require_tests_for_source_changes,
            },
            "verification": {
                "safe_threshold": config.verification.safe_threshold,
                "moderate_threshold": config.verification.moderate_threshold,
            },
            "auto_approve": {
                "categories": list(config.auto_approve_categories),
                "complexity": list(config.auto_approve_complexity),
            },
        }
        console.print(json_lib.dumps(data, indent=2))
        return

    # Human-readable output
    console.print("\n🛡️ [bold]Autonomy Guardrails Configuration[/bold]\n")

    # Trust level
    level_colors = {
        "conservative": "red",
        "guarded": "yellow",
        "supervised": "green",
        "full": "cyan",
    }
    color = level_colors.get(config.trust_level.value, "white")
    level = config.trust_level.value.upper()
    console.print(f"[bold]Trust Level:[/bold] [{color}]{level}[/{color}]")

    # Scope limits
    console.print("\n[bold]Scope Limits:[/bold]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Limit", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Max files per goal", str(config.scope.max_files_per_goal))
    table.add_row("Max lines per goal", str(config.scope.max_lines_changed_per_goal))
    table.add_row("Max goals per session", str(config.scope.max_goals_per_session))
    table.add_row("Max files per session", str(config.scope.max_files_per_session))
    table.add_row("Max session duration", f"{config.scope.max_duration_per_session_hours}h")
    req_tests = "✓" if config.scope.require_tests_for_source_changes else "✗"
    table.add_row("Require tests for source", req_tests)
    console.print(table)

    # Verification thresholds
    console.print("\n[bold]Verification Thresholds:[/bold]")
    console.print(f"  SAFE actions: {config.verification.safe_threshold:.0%}")
    console.print(f"  MODERATE actions: {config.verification.moderate_threshold:.0%}")

    # Auto-approve policy
    console.print("\n[bold]Auto-Approve Policy:[/bold]")
    console.print(f"  Categories: {', '.join(sorted(config.auto_approve_categories))}")
    console.print(f"  Complexity: {', '.join(sorted(config.auto_approve_complexity))}")

    # Trust zones
    if config.trust_zones:
        console.print(f"\n[bold]Custom Trust Zones:[/bold] {len(config.trust_zones)}")
        for zone in config.trust_zones[:5]:
            risk = zone.risk_override.value if zone.risk_override else "default"
            console.print(f"  {zone.pattern} → {risk}")
        if len(config.trust_zones) > 5:
            console.print(f"  ... and {len(config.trust_zones) - 5} more")


@guardrails.command()
@click.pass_context
def check(ctx) -> None:
    """Validate current backlog goals against guardrails."""
    asyncio.run(_check_goals())


async def _check_goals() -> None:
    """Check goals against guardrails."""
    from sunwell.backlog.manager import BacklogManager
    from sunwell.guardrails import GuardrailSystem

    root = Path.cwd()
    manager = BacklogManager(root=root)
    guardrails = GuardrailSystem(repo_path=root)

    console.print("🔍 Checking backlog goals against guardrails...\n")

    backlog = await manager.refresh()
    goals = backlog.execution_order()

    if not goals:
        console.print("📋 No goals in backlog")
        return

    table = Table(title="Goal Guardrail Check")
    table.add_column("Goal ID", style="cyan")
    table.add_column("Title")
    table.add_column("Risk", justify="center")
    table.add_column("Scope", justify="center")
    table.add_column("Auto", justify="center")

    auto_count = 0
    escalate_count = 0

    for goal in goals:
        can_auto = await guardrails.can_auto_approve(goal)
        passed, reason, classification, scope_check = await guardrails.check_goal(goal)

        risk_str = "✅"
        if classification:
            risk_map = {"safe": "🟢", "moderate": "🟡", "dangerous": "🟠", "forbidden": "🔴"}
            risk_str = risk_map.get(classification.risk.value, "⚪")

        scope_str = "✅" if (scope_check is None or scope_check.passed) else "❌"
        auto_str = "✅" if can_auto else "⚠️"

        if can_auto:
            auto_count += 1
        else:
            escalate_count += 1

        table.add_row(
            goal.id[:8],
            goal.title[:40],
            risk_str,
            scope_str,
            auto_str,
        )

    console.print(table)
    console.print(f"\n✅ {auto_count} auto-approvable | ⚠️ {escalate_count} require approval")


@guardrails.command()
@click.pass_context
def history(ctx) -> None:
    """View guardrail session history."""
    root = Path.cwd()

    # Look for session tags
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "tag", "-l", "sunwell-session-*"],
            capture_output=True,
            text=True,
        )
        tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
    except Exception:
        tags = []

    if not tags:
        console.print("📜 No guardrail sessions found")
        return

    console.print("\n📜 [bold]Guardrail Session History[/bold]\n")

    table = Table()
    table.add_column("Session Tag", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Status")

    for tag in sorted(tags, reverse=True)[:10]:
        # Extract date from tag name
        parts = tag.replace("sunwell-session-", "").split("_")
        if len(parts) >= 2:
            date_str = f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]}"
            time_str = f"{parts[1][:2]}:{parts[1][2:4]}:{parts[1][4:]}"
            date_display = f"{date_str} {time_str}"
        else:
            date_display = "unknown"

        table.add_row(tag, date_display, "completed")

    console.print(table)
    console.print(f"\nShowing {min(10, len(tags))} of {len(tags)} sessions")
    console.print("\nTo rollback: sunwell guardrails rollback <session-tag>")


@guardrails.command()
@click.argument("target")
@click.option("--goal", is_flag=True, help="Rollback a specific goal instead of session")
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def rollback(ctx, target: str, goal: bool, force: bool) -> None:
    """Rollback a session or goal.

    TARGET is either a session tag (sunwell-session-*) or a goal ID with --goal.

    Examples:

        sunwell guardrails rollback sunwell-session-20260119_143022
        sunwell guardrails rollback goal-123 --goal
    """
    if not force:
        if goal:
            msg = f"Rollback goal {target}? This will create a revert commit."
        else:
            msg = f"Rollback session {target}? This will RESET to the session start."
        if not click.confirm(msg):
            console.print("Cancelled")
            return

    asyncio.run(_rollback(target, goal))


async def _rollback(target: str, is_goal: bool) -> None:
    """Perform rollback."""
    from sunwell.guardrails import RecoveryManager

    root = Path.cwd()
    recovery = RecoveryManager(root)

    if is_goal:
        console.print(f"🔄 Rolling back goal: {target}")
        result = await recovery.rollback_goal(target)
    else:
        # Set the session tag
        recovery.session_tag = target
        console.print(f"🔄 Rolling back session: {target}")
        result = await recovery.rollback_session()

    if result.success:
        console.print("✅ Rollback successful")
        if result.goals_reverted:
            console.print(f"   Reverted {result.goals_reverted} goal(s)")
    else:
        console.print(f"❌ Rollback failed: {result.reason}")


@guardrails.command()
@click.argument("path")
@click.pass_context
def classify(ctx, path: str) -> None:
    """Classify a file path by risk level.

    Useful for understanding how guardrails will treat specific files.

    Examples:

        sunwell guardrails classify src/auth/login.py
        sunwell guardrails classify tests/test_utils.py
    """
    from sunwell.guardrails import Action, ActionClassifier

    classifier = ActionClassifier()
    result = classifier.classify(
        Action(action_type="file_write", path=path)
    )

    risk_colors = {
        "safe": "green",
        "moderate": "yellow",
        "dangerous": "red",
        "forbidden": "bright_red",
    }
    color = risk_colors.get(result.risk.value, "white")

    console.print(f"\n📁 [bold]{path}[/bold]")
    console.print(f"   Risk: [{color}]{result.risk.value.upper()}[/{color}]")
    console.print(f"   Reason: {result.reason}")
    console.print(f"   Escalation required: {'Yes' if result.escalation_required else 'No'}")
    if result.blocking_rule:
        console.print(f"   Blocking rule: {result.blocking_rule}")
