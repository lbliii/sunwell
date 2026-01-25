"""Guard CLI commands for RFC-130 Adaptive Guards.

Commands for managing guardrail evolution and feedback.
"""

import asyncio
from pathlib import Path

import click
from rich.table import Table

from sunwell.cli.theme import create_sunwell_console

console = create_sunwell_console()


@click.group()
def guard() -> None:
    """Manage guardrails and adaptive learning (RFC-130)."""
    pass


@guard.command()
@click.option(
    "--min-confidence", "-c",
    default=0.7,
    type=float,
    help="Minimum confidence for suggestions (default: 0.7)",
)
@click.option(
    "--apply", "-a",
    is_flag=True,
    help="Apply suggested evolutions interactively",
)
def evolve(min_confidence: float, apply: bool) -> None:
    """Show and optionally apply guard evolution suggestions.

    Analyzes accumulated violations to suggest rule refinements
    that reduce false positives while maintaining security.

    Examples:

    \b
        sunwell guard evolve                    # Show suggestions
        sunwell guard evolve --min-confidence 0.8
        sunwell guard evolve --apply            # Apply interactively
    """
    asyncio.run(_evolve_guards(min_confidence, apply))


async def _evolve_guards(min_confidence: float, apply: bool) -> None:
    """Get and display guard evolution suggestions."""
    from sunwell.guardrails.classifier import SmartActionClassifier

    # Create classifier with learning enabled
    classifier = SmartActionClassifier(
        enable_learning=True,
        violation_store_path=Path(".sunwell/guard-violations"),
    )

    # Get suggestions
    evolutions = await classifier.suggest_evolutions()

    # Filter by confidence
    evolutions = [e for e in evolutions if e.confidence >= min_confidence]

    if not evolutions:
        console.print("[holy.success]✓ No evolution suggestions at this time[/holy.success]")
        console.print(
            f"[neutral.dim]Threshold: {min_confidence:.0%} confidence. "
            "Accumulate more violations for suggestions.[/neutral.dim]"
        )
        return

    # Display suggestions (RFC-131: Holy Light styling)
    console.print("\n[holy.radiant]≡ Guard Evolution Suggestions[/holy.radiant]\n")
    console.print(f"Found {len(evolutions)} suggestions (≥{min_confidence:.0%} confidence)\n")

    table = Table(show_header=True, header_style="sunwell.heading")
    table.add_column("#", style="neutral.dim", width=3)
    table.add_column("Rule", style="holy.radiant")
    table.add_column("Type", style="holy.gold")
    table.add_column("Confidence", justify="right")
    table.add_column("Description")
    table.add_column("Violations", justify="right")

    for i, evo in enumerate(evolutions, 1):
        if evo.confidence >= 0.85:
            conf_style = "holy.success"
        elif evo.confidence >= 0.7:
            conf_style = "holy.gold"
        else:
            conf_style = "void.purple"
        table.add_row(
            str(i),
            evo.rule_id[:20],
            evo.evolution_type.value,
            f"[{conf_style}]{evo.confidence:.0%}[/{conf_style}]",
            evo.description[:40] + "..." if len(evo.description) > 40 else evo.description,
            str(evo.supporting_violations),
        )

    console.print(table)

    # Show details for each
    console.print("\n[sunwell.heading]Details:[/sunwell.heading]\n")
    for i, evo in enumerate(evolutions, 1):
        console.print(f"[holy.radiant]{i}. {evo.rule_id}[/holy.radiant]")
        console.print(f"   Type: {evo.evolution_type.value}")
        console.print(f"   Reason: {evo.reason}")
        if evo.new_pattern:
            console.print(f"   New pattern: {evo.new_pattern}")
        if evo.new_trust_level:
            console.print(f"   New trust level: {evo.new_trust_level.value}")
        console.print()

    if apply:
        console.print("\n[holy.gold]△ Interactive mode not yet implemented.[/holy.gold]")
        console.print("[neutral.dim]Export to .sunwell/config.yaml and edit.[/neutral.dim]")


@guard.command()
@click.argument("rule_id")
@click.option(
    "--false-positive", "-fp",
    is_flag=True,
    help="Mark last violation as false positive",
)
@click.option(
    "--correct", "-c",
    is_flag=True,
    help="Mark last violation as correct (guard was right)",
)
@click.option(
    "--comment", "-m",
    default=None,
    help="Add comment to feedback",
)
def feedback(rule_id: str, false_positive: bool, correct: bool, comment: str | None) -> None:
    """Provide feedback on a guardrail decision.

    Use this to mark violations as false positives or confirm
    that the guard made the right call.

    Examples:

    \b
        sunwell guard feedback trust_zone --false-positive
        sunwell guard feedback forbidden_pattern --correct
        sunwell guard feedback scope_files --false-positive -m "Test file, should be allowed"
    """
    if not false_positive and not correct:
        console.print("[void.purple]✗ Must specify --false-positive or --correct[/void.purple]")
        return

    from sunwell.guardrails.classifier import SmartActionClassifier
    from sunwell.guardrails.types import GuardViolation, ViolationOutcome

    classifier = SmartActionClassifier(
        enable_learning=True,
        violation_store_path=Path(".sunwell/guard-violations"),
    )

    # Create violation record
    violation = GuardViolation(
        action_type="feedback",
        path=None,
        blocking_rule=rule_id,
        outcome=ViolationOutcome.FALSE_POSITIVE if false_positive else ViolationOutcome.BLOCKED,
        user_comment=comment,
    )

    classifier.record_violation(violation)

    if false_positive:
        console.print(f"[holy.success]✓ Recorded false positive: {rule_id}[/holy.success]")
    else:
        console.print(f"[holy.success]✓ Confirmed guard correct: {rule_id}[/holy.success]")

    if comment:
        console.print(f"[neutral.dim]Comment: {comment}[/neutral.dim]")


@guard.command()
@click.option(
    "--json", "-j",
    "as_json",
    is_flag=True,
    help="Output as JSON",
)
def stats(as_json: bool) -> None:
    """Show guardrail statistics and violation summary.

    Examples:

    \b
        sunwell guard stats
        sunwell guard stats --json
    """
    from sunwell.guardrails.classifier import SmartActionClassifier

    classifier = SmartActionClassifier(
        enable_learning=True,
        violation_store_path=Path(".sunwell/guard-violations"),
    )

    stats = classifier.get_violation_stats()

    if as_json:
        import json
        console.print(json.dumps(stats, indent=2))
        return

    console.print("\n[holy.radiant]≡ Guard Statistics[/holy.radiant]\n")

    total = stats["total_violations"]
    learn_icon = "✓" if stats["learning_enabled"] else "✗"
    console.print(f"[sunwell.heading]Violations:[/] {total}")
    console.print(f"[sunwell.heading]Learning:[/] {learn_icon}")

    if stats['by_outcome']:
        console.print("\n[sunwell.heading]By Outcome:[/sunwell.heading]")
        for outcome, count in stats['by_outcome'].items():
            if count > 0:
                icon = "⊘" if outcome == "blocked" else "△" if outcome == "overridden" else "✗"
                console.print(f"  {icon} {outcome}: {count}")

    if stats['by_rule']:
        console.print("\n[sunwell.heading]By Rule:[/sunwell.heading]")
        for rule, count in sorted(stats['by_rule'].items(), key=lambda x: -x[1]):
            console.print(f"  · {rule}: {count}")


@guard.command()
def reset() -> None:
    """Reset violation history.

    Clears all accumulated violations. Use with caution.
    """
    import shutil

    violation_path = Path(".sunwell/guard-violations")

    if not violation_path.exists():
        console.print("[holy.gold]◇ No violation history to reset.[/holy.gold]")
        return

    if not click.confirm("Reset all violation history? This cannot be undone."):
        console.print("[neutral.dim]Aborted[/neutral.dim]")
        return

    shutil.rmtree(violation_path)
    console.print("[holy.success]✓ Violation history reset[/holy.success]")
