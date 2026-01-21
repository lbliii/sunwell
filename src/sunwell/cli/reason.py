"""CLI interface for Reasoned Decisions (RFC-073).

Provides cross-domain access to the Python reasoner for:
- Rust (Tauri backend) via subprocess
- Manual testing and debugging
- Batch reasoning operations

Example:
    $ sunwell reason severity_assessment --context '{"signal_type": "todo"}'
    $ sunwell reason recovery_strategy --context '{"error_type": "TimeoutError"}'
"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def reason() -> None:
    """Reasoned decisions - LLM-driven judgment over rule-based logic.

    \b
    Make context-aware decisions using LLM reasoning:

        sunwell reason decide severity_assessment --context '{"signal_type": "todo"}'
        sunwell reason calibration --show

    \b
    Decision types:
        severity_assessment  - Assess severity of code signals
        auto_fixable        - Determine if signal can be auto-fixed
        recovery_strategy   - Choose error recovery strategy
        semantic_approval   - Decide if change can be auto-approved
        risk_assessment     - Assess change risk level
    """
    pass


@reason.command(name="decide")
@click.argument("decision_type")
@click.option("--context", "-c", required=True, help="JSON context for the decision")
@click.option("--model", "-m", default=None, help="Override model selection")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--force", is_flag=True, help="Force LLM reasoning (skip cache)")
@click.option("--fast", is_flag=True, help="Fast mode: skip tool calling, use JSON parsing")
def decide(
    decision_type: str,
    context: str,
    model: str | None,
    output_json: bool,
    force: bool,
    fast: bool,
) -> None:
    """Make a reasoned decision.

    \b
    Decision types:
        severity_assessment  - Assess severity: critical, high, medium, low
        auto_fixable        - Can be auto-fixed: true/false
        recovery_strategy   - Recovery: retry, retry_different, escalate, abort
        semantic_approval   - Approval: approve, flag, deny
        risk_assessment     - Risk level: low, medium, high, critical

    \b
    Example:
        sunwell reason decide severity_assessment \\
            -c '{"signal_type": "fixme_comment", "content": "race condition"}'
    """
    try:
        context_dict = json.loads(context)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON context: {e}[/red]")
        raise SystemExit(1) from None

    asyncio.run(_decide(decision_type, context_dict, model, output_json, force, fast))


async def _decide(
    decision_type: str,
    context: dict,
    model_name: str | None,
    output_json: bool,
    force: bool,
    fast: bool = False,
) -> None:
    """Execute the decision."""
    from sunwell.config import get_config
    from sunwell.reasoning import DecisionType, Reasoner

    # Validate decision type
    try:
        dtype = DecisionType(decision_type)
    except ValueError:
        valid_types = [t.value for t in DecisionType]
        console.print(f"[red]Invalid decision type: {decision_type}[/red]")
        console.print(f"[dim]Valid types: {', '.join(valid_types)}[/dim]")
        raise SystemExit(1) from None

    # Load model
    try:
        from sunwell.models.ollama import OllamaModel

        config = get_config()
        model = model_name

        # Fast mode defaults to smaller, faster model
        if fast and not model:
            model = "llama3.2:3b"
        elif not model and config and hasattr(config, "naaru"):
            model = getattr(config.naaru, "wisdom", "qwen3:8b")
        elif not model:
            model = "qwen3:8b"

        llm = OllamaModel(model=model)
        mode_str = "[fast]" if fast else ""
        if not output_json:
            console.print(f"[dim]Using model: {model} {mode_str}[/dim]")

    except Exception as e:
        console.print(f"[red]Failed to load model: {e}[/red]")
        raise SystemExit(1) from None

    # Create reasoner and decide
    reasoner = Reasoner(model=llm, use_tool_calling=not fast)

    try:
        decision = await reasoner.decide(dtype, context, force_reasoning=force)
    except Exception as e:
        console.print(f"[red]Reasoning failed: {e}[/red]")
        raise SystemExit(1) from None

    # Output
    if output_json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        _display_decision(decision)


def _display_decision(decision) -> None:
    """Display decision in a nice format."""
    # Confidence indicator
    conf_emoji = decision.confidence_emoji
    conf_level = decision.confidence_level
    conf_pct = f"{decision.confidence:.0%}"

    # Create panel
    content = f"""[bold]Outcome:[/bold] {decision.outcome}
[bold]Confidence:[/bold] {conf_pct} {conf_emoji} ({conf_level})

[bold]Rationale:[/bold]
{decision.rationale}
"""

    if decision.context_used:
        content += f"\n[bold]Context factors:[/bold] {', '.join(decision.context_used)}"

    if decision.similar_decisions:
        content += f"\n[bold]Similar decisions:[/bold] {', '.join(decision.similar_decisions)}"

    panel = Panel(
        content,
        title=f"[cyan]{decision.decision_type.value}[/cyan]",
        border_style="green" if decision.is_confident else "yellow",
    )
    console.print(panel)


@reason.command(name="calibration")
@click.option("--show", is_flag=True, help="Show calibration statistics")
@click.option("--decision-type", "-t", default=None, help="Filter by decision type")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def calibration(show: bool, decision_type: str | None, output_json: bool) -> None:
    """View and manage confidence calibration.

    \b
    Calibration tracks: predicted confidence vs actual accuracy.
    Target: ±10% (80% confidence should be right 70-90% of time).

    Example:
        sunwell reason calibration --show
        sunwell reason calibration --show -t severity_assessment
    """
    if not show:
        console.print("[yellow]Use --show to display calibration stats[/yellow]")
        return

    from sunwell.reasoning import ConfidenceCalibrator

    # Load calibrator from default path
    calibrator_path = Path.cwd() / ".sunwell" / "reasoning" / "calibration.db"

    if calibrator_path.exists():
        calibrator = ConfidenceCalibrator(db_path=calibrator_path)
    else:
        calibrator = ConfidenceCalibrator()
        console.print("[dim]No calibration data found. Start making decisions.[/dim]")
        return

    stats = calibrator.get_calibration_stats(decision_type)

    if not stats:
        console.print("[yellow]No calibration data available.[/yellow]")
        return

    if output_json:
        print(json.dumps(calibrator.to_dict(), indent=2))
        return

    # Display stats table
    table = Table(title="Confidence Calibration")
    table.add_column("Predicted", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Correct", justify="right")
    table.add_column("Actual Acc.", justify="right")
    table.add_column("Error", justify="right")
    table.add_column("Status")

    for stat in stats:
        low, high = stat.predicted_range
        pred_range = f"{low:.0%}-{high:.0%}"
        if stat.calibration_error <= 0.10:
            status = "✅"
        elif stat.calibration_error <= 0.15:
            status = "⚠️"
        else:
            status = "❌"

        table.add_row(
            pred_range,
            str(stat.count),
            str(stat.correct_count),
            f"{stat.actual_accuracy:.0%}",
            f"{stat.calibration_error:.0%}",
            status,
        )

    console.print(table)

    # Overall error
    overall = calibrator.get_overall_calibration_error(decision_type)
    is_good = calibrator.is_well_calibrated(decision_type)
    if is_good:
        cal_status = "[green]✅ Well calibrated[/green]"
    else:
        cal_status = "[yellow]⚠️ Needs calibration[/yellow]"
    console.print(f"\n[bold]Overall calibration error:[/bold] {overall:.1%} {cal_status}")


@reason.command(name="test")
@click.option("--signal-type", "-s", default="todo_comment", help="Signal type to test")
@click.option("--file", "-f", default="example.py", help="File path for context")
@click.option("--content", "-c", default="add better error handling", help="Signal content")
def test(signal_type: str, file: str, content: str) -> None:
    """Quick test of severity assessment.

    \b
    Example:
        sunwell reason test -s fixme_comment -f billing.py -c "validate payment amounts"
    """
    context = json.dumps({
        "signal_type": signal_type,
        "file_path": file,
        "content": content,
    })

    asyncio.run(_decide("severity_assessment", json.loads(context), None, False, False))


@reason.command(name="types")
def list_types() -> None:
    """List all available decision types."""
    from sunwell.reasoning import DecisionType

    table = Table(title="Decision Types")
    table.add_column("Type", style="cyan")
    table.add_column("Phase")
    table.add_column("Description")

    phases = {
        "severity_assessment": ("Phase 1", "Assess severity of code signals"),
        "auto_fixable": ("Phase 1", "Determine if signal can be auto-fixed"),
        "goal_priority": ("Phase 1", "Prioritize goals based on context"),
        "failure_diagnosis": ("Phase 2", "Diagnose root cause of failures"),
        "recovery_strategy": ("Phase 2", "Choose error recovery strategy"),
        "retry_vs_abort": ("Phase 2", "Decide to retry or abort"),
        "semantic_approval": ("Phase 3", "Auto-approve based on semantics"),
        "escalation_options": ("Phase 3", "Generate escalation options"),
        "risk_assessment": ("Phase 3", "Assess change risk level"),
        "root_cause_analysis": ("Phase 4", "Analyze failure root causes"),
        "pattern_extraction": ("Phase 4", "Extract patterns from behavior"),
        "preference_inference": ("Phase 4", "Infer user preferences"),
        "display_variant": ("Display", "UI display decision"),
    }

    for dtype in DecisionType:
        phase, desc = phases.get(dtype.value, ("Other", dtype.value))
        table.add_row(dtype.value, phase, desc)

    console.print(table)


@reason.command(name="heuristic")
@click.argument("decision_type")
@click.option("--context", "-c", required=True, help="JSON context")
def heuristic(decision_type: str, context: str) -> None:
    """Get rule-based fallback decision (no LLM).

    Useful for testing fallback behavior or when LLM is unavailable.

    Example:
        sunwell reason heuristic severity_assessment -c '{"signal_type": "fixme_comment"}'
    """
    from sunwell.reasoning import DecisionType

    try:
        dtype = DecisionType(decision_type)
    except ValueError:
        console.print(f"[red]Invalid decision type: {decision_type}[/red]")
        raise SystemExit(1) from None

    try:
        context_dict = json.loads(context)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON context: {e}[/red]")
        raise SystemExit(1) from None

    # Create reasoner without model to use fallbacks
    from sunwell.reasoning.reasoner import Reasoner

    # Create a mock model that always fails
    class NoOpModel:
        @property
        def model_id(self) -> str:
            return "noop"

        async def generate(self, *args, **kwargs):
            raise RuntimeError("NoOp model - using fallback")

        async def generate_stream(self, *args, **kwargs):
            raise RuntimeError("NoOp model - using fallback")

        async def list_models(self):
            return []

    reasoner = Reasoner(model=NoOpModel())
    decision = reasoner._apply_fallback(dtype, context_dict)

    console.print(f"[bold]Heuristic decision:[/bold] {decision.outcome}")
    console.print(f"[dim]Confidence: {decision.confidence:.0%} (fallback)[/dim]")
    console.print(f"[dim]Rationale: {decision.rationale}[/dim]")
