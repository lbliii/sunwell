"""Evaluation CLI command — Real Metrics, Real Transparency (RFC-098).

Rigorous evaluation comparing single-shot prompting vs Sunwell's cognitive
architecture on complex multi-file tasks.

Usage:
    sunwell eval                           # Default evaluation (forum_app)
    sunwell eval --task cli_tool           # Specific task
    sunwell eval --task forum_app --runs 3 # Statistical validity
    sunwell eval --history                 # View past evaluations
    sunwell eval --ci --min-score 7.0      # CI mode
"""

import asyncio
import hashlib
import json
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.command()
@click.option(
    "--task",
    "-t",
    default="forum_app",
    help="Task: forum_app, cli_tool, rest_api, fixture_minimal, or custom prompt",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (default: from config)",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["openai", "anthropic", "ollama"]),
    default=None,
    help="Model provider (default: from config)",
)
@click.option(
    "--lens",
    "-l",
    default=None,
    help="Lens to use (default: auto-detect)",
)
@click.option(
    "--compare-lens",
    default=None,
    help="Compare against a different lens configuration",
)
@click.option(
    "--runs",
    "-n",
    default=1,
    type=int,
    help="Number of runs for statistical validity (default: 1, recommended: 3)",
)
@click.option(
    "--history",
    is_flag=True,
    help="Show evaluation history",
)
@click.option(
    "--stats",
    is_flag=True,
    help="Show aggregate statistics",
)
@click.option(
    "--ci",
    is_flag=True,
    help="CI mode: exit code reflects pass/fail, minimal output",
)
@click.option(
    "--min-score",
    default=7.0,
    type=float,
    help="Minimum Sunwell score for CI pass (default: 7.0)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--export",
    type=click.Path(),
    help="Export results to file (json, csv, or xml for JUnit)",
)
@click.option(
    "--stream",
    is_flag=True,
    help="Stream NDJSON for real-time UI updates",
)
@click.option(
    "--show-cost",
    is_flag=True,
    help="Show token usage and estimated cost",
)
@click.option(
    "--regression",
    is_flag=True,
    help="Check for regression against baseline",
)
@click.option(
    "--baseline",
    default=None,
    help="Baseline version for regression check",
)
@click.option(
    "--list-tasks",
    is_flag=True,
    help="List available evaluation tasks",
)
def eval_cmd(
    task: str,
    model: str | None,
    provider: str | None,
    lens: str | None,
    compare_lens: str | None,
    runs: int,
    history: bool,
    stats: bool,
    ci: bool,
    min_score: float,
    json_output: bool,
    export: str | None,
    stream: bool,
    show_cost: bool,
    regression: bool,
    baseline: str | None,
    list_tasks: bool,
) -> None:
    """Evaluate Sunwell vs single-shot on complex tasks.

    \b
    Run rigorous evaluation comparing single-shot prompting against
    Sunwell's cognitive architecture (Lens + Judge + Resonance).

    \b
    Examples:
        sunwell eval                           # Default forum_app task
        sunwell eval --task cli_tool           # CLI tool task
        sunwell eval --runs 3                  # 3 runs for consistency
        sunwell eval --history                 # View past runs
        sunwell eval --ci --min-score 7.0      # CI mode
        sunwell eval --export results.json     # Export results
    """
    if list_tasks:
        _list_available_tasks()
        return

    if history:
        _show_history(json_output)
        return

    if stats:
        _show_stats(json_output)
        return

    if stream:
        asyncio.run(
            _run_evaluation_streaming(
                task=task,
                provider_override=provider,
                model_override=model,
                lens=lens,
            )
        )
        return

    asyncio.run(
        _run_evaluation(
            task=task,
            provider_override=provider,
            model_override=model,
            lens=lens,
            runs=runs,
            ci=ci,
            min_score=min_score,
            json_output=json_output,
            export=export,
            show_cost=show_cost,
        )
    )


def _list_available_tasks() -> None:
    """List available evaluation tasks."""
    from sunwell.benchmark.eval.tasks import FULL_STACK_TASKS

    console.print("\n[bold]Available Evaluation Tasks:[/bold]\n")

    for name, task in FULL_STACK_TASKS.items():
        console.print(f"  [cyan]{name}[/cyan] ({task.estimated_minutes} min)")
        console.print(f"    {task.description}")
        console.print(f"    [dim]Features: {', '.join(task.expected_features)}[/dim]")
        console.print()

    console.print(
        "[dim]Or provide a custom prompt: sunwell eval --task \"your prompt here\"[/dim]"
    )
    console.print()


def _show_history(json_output: bool) -> None:
    """Show evaluation history."""
    from sunwell.benchmark.eval.store import EvaluationStore

    store = EvaluationStore()
    summaries = store.load_summaries(limit=20)

    if not summaries:
        console.print("\n[yellow]No evaluation history found.[/yellow]")
        console.print("[dim]Run 'sunwell eval' to create your first evaluation.[/dim]\n")
        return

    if json_output:
        data = [
            {
                "id": s.id,
                "timestamp": s.timestamp.isoformat(),
                "task": s.task,
                "model": s.model,
                "lens": s.lens,
                "single_shot_score": s.single_shot_score,
                "sunwell_score": s.sunwell_score,
                "improvement_percent": s.improvement_percent,
                "winner": s.winner,
            }
            for s in summaries
        ]
        console.print(json.dumps(data, indent=2))
        return

    console.print("\n[bold]📊 Evaluation History[/bold]\n")

    table = Table()
    table.add_column("Time", style="dim")
    table.add_column("Task", style="cyan")
    table.add_column("Model")
    table.add_column("Lens")
    table.add_column("Single", justify="center")
    table.add_column("Sunwell", justify="center")
    table.add_column("Δ", justify="center")
    table.add_column("Winner", justify="center")

    for s in summaries:
        ts = s.timestamp.strftime("%m-%d %H:%M")
        improvement = f"+{s.improvement_percent:.0f}%"

        winner_display = {
            "sunwell": "[green]🔮[/green]",
            "single_shot": "[red]⚫[/red]",
            "tie": "[yellow]≈[/yellow]",
        }.get(s.winner, "?")

        table.add_row(
            ts,
            s.task,
            s.model[:15] if s.model else "",
            s.lens[:12] if s.lens else "-",
            f"{s.single_shot_score:.1f}",
            f"{s.sunwell_score:.1f}",
            f"[green]{improvement}[/green]" if s.improvement_percent > 0 else improvement,
            winner_display,
        )

    console.print(table)
    console.print()


def _show_stats(json_output: bool) -> None:
    """Show aggregate statistics."""
    from sunwell.benchmark.eval.store import EvaluationStore

    store = EvaluationStore()
    stats = store.aggregate_stats()

    if stats.total_runs == 0:
        console.print("\n[yellow]No evaluation data found.[/yellow]\n")
        return

    if json_output:
        data = {
            "total_runs": stats.total_runs,
            "sunwell_wins": stats.sunwell_wins,
            "single_shot_wins": stats.single_shot_wins,
            "ties": stats.ties,
            "win_rate": stats.win_rate,
            "avg_improvement": stats.avg_improvement,
            "avg_sunwell_score": stats.avg_sunwell_score,
            "avg_single_shot_score": stats.avg_single_shot_score,
            "by_task": stats.by_task,
            "by_model": stats.by_model,
            "by_lens": stats.by_lens,
        }
        console.print(json.dumps(data, indent=2))
        return

    console.print("\n[bold]📊 Evaluation Statistics[/bold]\n")

    # Summary table
    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Runs", str(stats.total_runs))
    table.add_row("Sunwell Wins", str(stats.sunwell_wins))
    table.add_row("Single-shot Wins", str(stats.single_shot_wins))
    table.add_row("Ties", str(stats.ties))
    table.add_row("Win Rate", f"{stats.win_rate:.0f}%")
    table.add_row("Avg Improvement", f"+{stats.avg_improvement:.0f}%")
    table.add_row("Avg Sunwell Score", f"{stats.avg_sunwell_score:.1f}")
    table.add_row("Avg Single-shot Score", f"{stats.avg_single_shot_score:.1f}")

    console.print(table)

    # By task breakdown
    if stats.by_task:
        console.print("\n[bold]By Task:[/bold]")
        for task_name, task_stats in stats.by_task.items():
            console.print(
                f"  {task_name}: {task_stats['count']} runs, "
                f"+{task_stats['avg_improvement']:.0f}% avg, "
                f"{task_stats['win_rate']:.0f}% win rate"
            )

    # By lens breakdown
    if stats.by_lens:
        console.print("\n[bold]By Lens:[/bold]")
        for lens_name, lens_stats in stats.by_lens.items():
            console.print(
                f"  {lens_name}: {lens_stats['count']} runs, "
                f"+{lens_stats['avg_improvement']:.0f}% avg, "
                f"{lens_stats['avg_score']:.1f} avg score"
            )

    console.print()


async def _run_evaluation(
    task: str,
    provider_override: str | None,
    model_override: str | None,
    lens: str | None,
    runs: int,
    ci: bool,
    min_score: float,
    json_output: bool,
    export: str | None,
    show_cost: bool,
) -> None:
    """Run evaluation."""
    import sys

    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.foundation.config import get_config
    from sunwell.benchmark.eval import (
        EvaluationError,
        EvaluationStore,
        FullStackEvaluator,
        SingleShotExecutor,
        SunwellFullStackExecutor,
        get_eval_task,
    )
    from sunwell.benchmark.eval.evaluator import compute_improvement, determine_winner
    from sunwell.benchmark.eval.store import EvaluationRun
    from sunwell.benchmark.eval.types import EvaluationDetails

    # Resolve model
    config = get_config()

    try:
        model = resolve_model(provider_override, model_override)
    except Exception as e:
        if ci:
            console.print(json.dumps({"error": str(e)}))
            sys.exit(1)
        console.print(f"[red]Error: Could not load model: {e}[/red]")
        console.print()
        console.print("[yellow]Tip: Run 'sunwell setup' to configure a model,[/yellow]")
        console.print("[yellow]or use --model to specify a tool-capable model.[/yellow]")
        return

    if not model:
        if ci:
            console.print(json.dumps({"error": "No model available"}))
            sys.exit(1)
        console.print("[red]No model available[/red]")
        return

    # Get model name for display
    model_name = model_override
    if not model_name:
        if config and hasattr(config, "model"):
            model_name = f"{config.model.default_provider}:{config.model.default_model}"
        else:
            model_name = "ollama:gemma3:4b"

    # Get task
    try:
        eval_task = get_eval_task(task)
    except ValueError as e:
        if ci:
            console.print(json.dumps({"error": str(e)}))
            sys.exit(1)
        console.print(f"[red]{e}[/red]")
        return

    # Create executors
    single_shot_exec = SingleShotExecutor(model)
    sunwell_exec = SunwellFullStackExecutor(model, lens_name=lens)
    evaluator = FullStackEvaluator()
    store = EvaluationStore()

    results = []

    for run_num in range(runs):
        # Create temp directories for outputs
        with tempfile.TemporaryDirectory() as single_shot_dir, \
             tempfile.TemporaryDirectory() as sunwell_dir:

            single_shot_path = Path(single_shot_dir)
            sunwell_path = Path(sunwell_dir)

            if not ci and not json_output:
                console.print(
                    Panel(
                        f"[bold cyan]📊 Evaluation[/bold cyan] — {eval_task.name}",
                        border_style="cyan",
                    )
                )
                console.print(f"Model: [cyan]{model_name}[/cyan]")
                console.print(f"Task: [cyan]{eval_task.description}[/cyan]")
                console.print(f"Estimated time: ~{eval_task.estimated_minutes} minutes")
                if runs > 1:
                    console.print(f"Run: {run_num + 1}/{runs}")
                console.print()

            # Run with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
                disable=ci or json_output,
            ) as progress:
                task_id = progress.add_task("Starting evaluation...", total=None)

                # Run single-shot
                progress.update(task_id, description="Running single-shot...")

                def on_ss_file(f: str, tid: int = task_id) -> None:
                    progress.update(tid, description=f"Single-shot: {f}")

                try:
                    single_shot_result = await single_shot_exec.run(
                        eval_task,
                        single_shot_path,
                        on_file_created=on_ss_file,
                    )
                except EvaluationError as e:
                    progress.stop()
                    if ci:
                        console.print(json.dumps({"error": str(e)}))
                        sys.exit(1)
                    console.print(f"\n[red]Evaluation failed: {e}[/red]")
                    if "tool calling" in str(e).lower():
                        console.print()
                        console.print("[yellow]This model doesn't support tool calling.[/yellow]")
                        console.print("[yellow]Try a tool-capable model:[/yellow]")
                        console.print("  sunwell eval --provider openai --model gpt-4o-mini")
                        console.print("  sunwell eval --provider anthropic --model claude-3-haiku")
                        console.print("  sunwell eval --provider ollama --model llama3.2:3b")
                    return

                # Run Sunwell
                progress.update(task_id, description="Running Sunwell...")

                def on_sw_file(f: str, tid: int = task_id) -> None:
                    progress.update(tid, description=f"Sunwell: {f}")

                def on_judge_cb(s: float, i: list, tid: int = task_id) -> None:
                    progress.update(tid, description=f"Judge: {s:.1f}/10")

                def on_resonance_cb(n: int, tid: int = task_id) -> None:
                    progress.update(tid, description=f"Resonance iteration {n}...")

                try:
                    sunwell_result = await sunwell_exec.run(
                        eval_task,
                        sunwell_path,
                        on_file_created=on_sw_file,
                        on_judge=on_judge_cb,
                        on_resonance=on_resonance_cb,
                    )
                except EvaluationError as e:
                    progress.stop()
                    if ci:
                        console.print(json.dumps({"error": str(e)}))
                        sys.exit(1)
                    console.print(f"\n[red]Evaluation failed: {e}[/red]")
                    return

                progress.update(task_id, description="Evaluating results...")

            # Score both outputs
            single_shot_score = evaluator.evaluate(single_shot_path, eval_task)
            sunwell_score = evaluator.evaluate(sunwell_path, eval_task)

            # Compute comparison
            improvement = compute_improvement(
                single_shot_score.final_score,
                sunwell_score.final_score,
            )
            winner = determine_winner(
                single_shot_score.final_score,
                sunwell_score.final_score,
            )

            # Get version info
            try:
                version = subprocess.check_output(
                    ["git", "describe", "--tags", "--always"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except Exception:
                version = "dev"

            try:
                git_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()[:8]
            except Exception:
                git_commit = None

            # Estimate cost (rough approximation)
            total_tokens = (
                single_shot_result.total_tokens + sunwell_result.total_tokens
            )
            # Rough estimate: $0.01 per 1K tokens for typical models
            estimated_cost = (total_tokens / 1000) * 0.01

            # Create run record
            run_record = EvaluationRun(
                id=str(uuid.uuid4())[:8],
                timestamp=datetime.now(),
                task=eval_task.name,
                model=model_name,
                lens=lens or sunwell_result.lens_used,
                sunwell_version=version,
                single_shot_score=single_shot_score.final_score,
                sunwell_score=sunwell_score.final_score,
                improvement_percent=improvement,
                winner=winner,
                single_shot_result=single_shot_result,
                sunwell_result=sunwell_result,
                evaluation_details=EvaluationDetails(
                    judge_rejections=tuple(
                        f"Score: {s:.1f}" for s in sunwell_result.judge_scores
                    ),
                    resonance_fixes=(
                        f"{sunwell_result.resonance_iterations} iterations",
                    ) if sunwell_result.resonance_iterations > 0 else (),
                ),
                input_tokens=single_shot_result.input_tokens + sunwell_result.input_tokens,
                output_tokens=single_shot_result.output_tokens + sunwell_result.output_tokens,
                estimated_cost_usd=estimated_cost,
                git_commit=git_commit,
                config_hash=hashlib.sha256(
                    f"{model_name}:{lens}:{eval_task.name}".encode()
                ).hexdigest()[:8],
            )

            # Save to store
            store.save(run_record)
            results.append(run_record)

    # Output results
    if json_output or ci:
        if runs == 1:
            run = results[0]
            output = {
                "task": run.task,
                "model": run.model,
                "lens": run.lens,
                "single_shot_score": run.single_shot_score,
                "sunwell_score": run.sunwell_score,
                "improvement_percent": run.improvement_percent,
                "winner": run.winner,
                "tokens": {
                    "input": run.input_tokens,
                    "output": run.output_tokens,
                    "total": run.input_tokens + run.output_tokens,
                },
                "estimated_cost_usd": run.estimated_cost_usd,
            }
        else:
            import statistics
            sunwell_scores = [r.sunwell_score for r in results]
            single_scores = [r.single_shot_score for r in results]
            improvements = [r.improvement_percent for r in results]

            output = {
                "task": results[0].task,
                "model": results[0].model,
                "runs": runs,
                "sunwell": {
                    "mean": statistics.mean(sunwell_scores),
                    "stdev": statistics.stdev(sunwell_scores) if runs > 1 else 0,
                },
                "single_shot": {
                    "mean": statistics.mean(single_scores),
                    "stdev": statistics.stdev(single_scores) if runs > 1 else 0,
                },
                "improvement": {
                    "mean": statistics.mean(improvements),
                    "stdev": statistics.stdev(improvements) if runs > 1 else 0,
                },
            }

        console.print(json.dumps(output, indent=2))

        if ci:
            # CI exit code: 0 if Sunwell score meets threshold
            final_score = results[0].sunwell_score if runs == 1 else statistics.mean(sunwell_scores)
            sys.exit(0 if final_score >= min_score else 1)

        return

    # Rich output
    run = results[0] if runs == 1 else results[-1]  # Show last result

    console.print()
    console.print("[bold]✅ Evaluation Complete[/bold]")
    console.print()

    # Comparison table
    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("⚫ Single-shot", justify="center")
    table.add_column("🔮 Sunwell", justify="center")

    # Get single shot score
    ss_score = results[0].single_shot_score
    sw_score = results[0].sunwell_score

    ss_color = "green" if ss_score >= 8.0 else "yellow" if ss_score >= 5.0 else "red"
    sw_color = "green" if sw_score >= 8.0 else "yellow" if sw_score >= 5.0 else "red"

    table.add_row(
        "Score",
        f"[{ss_color}]{ss_score:.1f}/10[/{ss_color}]",
        f"[{sw_color}]{sw_score:.1f}/10[/{sw_color}]",
    )
    table.add_row(
        "Files",
        str(len(run.single_shot_result.files)),
        str(len(run.sunwell_result.files)),
    )
    table.add_row(
        "Time",
        f"{run.single_shot_result.time_seconds:.1f}s",
        f"{run.sunwell_result.time_seconds:.1f}s",
    )
    table.add_row(
        "Turns",
        str(run.single_shot_result.turns),
        str(run.sunwell_result.turns),
    )

    console.print(table)
    console.print()

    # Winner display
    winner_display = {
        "sunwell": "[bold green]🔮 Sunwell wins![/bold green]",
        "single_shot": "[bold red]⚫ Single-shot wins[/bold red]",
        "tie": "[bold yellow]≈ Tie[/bold yellow]",
    }.get(run.winner, "?")

    console.print(f"{winner_display} (+{run.improvement_percent:.0f}% improvement)")
    console.print()

    if show_cost:
        console.print("[bold]Cost Breakdown:[/bold]")
        console.print(f"  Input tokens: {run.input_tokens:,}")
        console.print(f"  Output tokens: {run.output_tokens:,}")
        console.print(f"  Total tokens: {run.input_tokens + run.output_tokens:,}")
        console.print(f"  Estimated cost: ${run.estimated_cost_usd:.4f}")
        console.print()

    # Sunwell advantages
    if run.sunwell_result.lens_used:
        console.print(f"[dim]Lens used: {run.sunwell_result.lens_used}[/dim]")
    if run.sunwell_result.resonance_iterations > 0:
        console.print(f"[dim]Resonance iterations: {run.sunwell_result.resonance_iterations}[/dim]")
    console.print()

    # Export if requested
    if export:
        _export_results(results, export)
        console.print(f"[dim]Results exported to {export}[/dim]")


async def _run_evaluation_streaming(
    task: str,
    provider_override: str | None,
    model_override: str | None,
    lens: str | None,
) -> None:
    """Run evaluation with streaming NDJSON output."""
    import sys

    def emit(data: dict) -> None:
        """Emit NDJSON line."""
        print(json.dumps(data), flush=True)

    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.foundation.config import get_config
    from sunwell.benchmark.eval import (
        FullStackEvaluator,
        SingleShotExecutor,
        SunwellFullStackExecutor,
        get_eval_task,
    )
    from sunwell.benchmark.eval.evaluator import compute_improvement, determine_winner

    # Resolve model
    config = get_config()

    try:
        model = resolve_model(provider_override, model_override)
    except Exception as e:
        emit({"type": "error", "message": str(e)})
        sys.exit(1)

    if not model:
        emit({"type": "error", "message": "No model available"})
        sys.exit(1)

    model_name = model_override or (
        f"{config.model.default_provider}:{config.model.default_model}"
        if config and hasattr(config, "model")
        else "ollama:gemma3:4b"
    )

    try:
        eval_task = get_eval_task(task)
    except ValueError as e:
        emit({"type": "error", "message": str(e)})
        sys.exit(1)

    emit({
        "type": "start",
        "task": eval_task.name,
        "model": model_name,
        "estimated_minutes": eval_task.estimated_minutes,
    })

    single_shot_exec = SingleShotExecutor(model)
    sunwell_exec = SunwellFullStackExecutor(model, lens_name=lens)
    evaluator = FullStackEvaluator()

    with tempfile.TemporaryDirectory() as single_shot_dir, \
         tempfile.TemporaryDirectory() as sunwell_dir:

        single_shot_path = Path(single_shot_dir)
        sunwell_path = Path(sunwell_dir)

        # Run single-shot
        emit({"type": "phase", "phase": "single_shot"})

        single_shot_result = await single_shot_exec.run(
            eval_task,
            single_shot_path,
            on_file_created=lambda f: emit({
                "type": "file_created",
                "side": "single_shot",
                "path": f,
            }),
        )

        emit({
            "type": "single_shot_complete",
            "files": list(single_shot_result.files),
            "time_seconds": single_shot_result.time_seconds,
        })

        # Run Sunwell
        emit({"type": "phase", "phase": "sunwell"})

        sunwell_result = await sunwell_exec.run(
            eval_task,
            sunwell_path,
            on_file_created=lambda f: emit({
                "type": "file_created",
                "side": "sunwell",
                "path": f,
            }),
            on_judge=lambda s, i: emit({
                "type": "judge",
                "score": s,
                "issues": i,
            }),
            on_resonance=lambda n: emit({
                "type": "resonance",
                "iteration": n,
            }),
        )

        emit({
            "type": "sunwell_complete",
            "files": list(sunwell_result.files),
            "time_seconds": sunwell_result.time_seconds,
            "lens": sunwell_result.lens_used,
        })

        # Evaluate
        emit({"type": "phase", "phase": "evaluating"})

        single_shot_score = evaluator.evaluate(single_shot_path, eval_task)
        sunwell_score = evaluator.evaluate(sunwell_path, eval_task)

        improvement = compute_improvement(
            single_shot_score.final_score,
            sunwell_score.final_score,
        )
        winner = determine_winner(
            single_shot_score.final_score,
            sunwell_score.final_score,
        )

        emit({
            "type": "complete",
            "single_shot": {
                "score": single_shot_score.final_score,
                "subscores": single_shot_score.subscores,
                "runnable": single_shot_score.runnable,
                "files": single_shot_score.files_count,
                "lines": single_shot_score.lines_count,
            },
            "sunwell": {
                "score": sunwell_score.final_score,
                "subscores": sunwell_score.subscores,
                "runnable": sunwell_score.runnable,
                "files": sunwell_score.files_count,
                "lines": sunwell_score.lines_count,
            },
            "improvement_percent": improvement,
            "winner": winner,
        })


def _export_results(results: list, export_path: str) -> None:
    """Export results to file."""
    path = Path(export_path)

    if path.suffix == ".json":
        data = [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "task": r.task,
                "model": r.model,
                "lens": r.lens,
                "single_shot_score": r.single_shot_score,
                "sunwell_score": r.sunwell_score,
                "improvement_percent": r.improvement_percent,
                "winner": r.winner,
            }
            for r in results
        ]
        path.write_text(json.dumps(data, indent=2))

    elif path.suffix == ".csv":
        import csv

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "timestamp", "task", "model", "lens",
                "single_shot_score", "sunwell_score", "improvement_percent", "winner"
            ])
            for r in results:
                writer.writerow([
                    r.id, r.timestamp.isoformat(), r.task, r.model, r.lens,
                    r.single_shot_score, r.sunwell_score, r.improvement_percent, r.winner
                ])

    elif path.suffix == ".xml":
        # JUnit XML format for CI tools
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<testsuite name="sunwell-eval" tests="{}" failures="{}">'.format(
            len(results),
            sum(1 for r in results if r.winner == "single_shot"),
        ))

        for r in results:
            time_str = f"{r.sunwell_result.time_seconds:.1f}"
            xml.append(f'  <testcase name="{r.task}" time="{time_str}">')
            if r.winner == "single_shot":
                msg = f"Single-shot won: {r.single_shot_score:.1f} vs {r.sunwell_score:.1f}"
                xml.append(f'    <failure message="{msg}"/>')
            xml.append('  </testcase>')

        xml.append('</testsuite>')
        path.write_text("\n".join(xml))
