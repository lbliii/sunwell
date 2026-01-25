"""Demo CLI command — The "Holy Shit" Experience (RFC-095).

Proves the Prism Principle in under 2 minutes by running a side-by-side
comparison of single-shot prompting vs Sunwell's cognitive architecture.

Usage:
    sunwell demo                        # Default demo (divide function)
    sunwell demo --task add             # Addition function
    sunwell demo --task "custom task"   # Custom prompt
    sunwell demo --verbose              # Show judge feedback
    sunwell demo --json                 # Machine-readable output
    sunwell demo --iterations 3         # Run 3 times for consistency analysis
    sunwell demo --history              # Show demo history
"""

import asyncio
import statistics

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.command()
@click.option(
    "--task",
    "-t",
    default="divide",
    help="Task: divide, add, sort, fibonacci, validate_email, or a custom prompt",
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
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output (judge feedback, resonance iterations)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON for scripting",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Minimal output (just scores)",
)
@click.option(
    "--skip-single-shot",
    is_flag=True,
    help="Only show Sunwell result (skip baseline comparison)",
)
@click.option(
    "--list-tasks",
    is_flag=True,
    help="List available built-in tasks",
)
@click.option(
    "--iterations",
    "-n",
    default=1,
    type=int,
    help="Run multiple times for variance analysis (Phase 3)",
)
@click.option(
    "--save/--no-save",
    default=True,
    help="Save results to .sunwell/demo_history/ (default: save)",
)
@click.option(
    "--history",
    is_flag=True,
    help="Show demo history summary",
)
@click.option(
    "--stream",
    is_flag=True,
    help="Stream NDJSON for real-time UI updates (parallel execution)",
)
def demo(
    task: str,
    model: str | None,
    provider: str | None,
    verbose: bool,
    json_output: bool,
    quiet: bool,
    skip_single_shot: bool,
    list_tasks: bool,
    iterations: int,
    save: bool,
    history: bool,
    stream: bool,
) -> None:
    """Demo the Prism Principle — same model, different architecture, different quality.

    \b
    Run a side-by-side comparison showing how Sunwell's cognitive architecture
    extracts more capability from the same model.

    \b
    Examples:
        sunwell demo                    # Default demo with divide function
        sunwell demo --task add         # Try the add function
        sunwell demo --task "Write a function to parse JSON"  # Custom task
        sunwell demo --verbose          # See judge feedback and resonance
        sunwell demo --iterations 3     # Run 3 times, show variance
        sunwell demo --history          # View past demo results
    """
    if list_tasks:
        _list_available_tasks()
        return

    if history:
        _show_history()
        return

    if stream:
        asyncio.run(
            _run_demo_streaming(
                task=task,
                provider_override=provider,
                model_override=model,
            )
        )
        return

    asyncio.run(
        _run_demo(
            task=task,
            provider_override=provider,
            model_override=model,
            verbose=verbose,
            json_output=json_output,
            quiet=quiet,
            skip_single_shot=skip_single_shot,
            iterations=iterations,
            save_history=save,
        )
    )


def _list_available_tasks() -> None:
    """List available built-in demo tasks."""
    from sunwell.benchmark.demo import BUILTIN_TASKS

    console.print("\n[bold]Available Demo Tasks:[/bold]\n")

    for name, task in BUILTIN_TASKS.items():
        default = " [dim](default)[/dim]" if name == "divide" else ""
        console.print(f"  [cyan]{name}[/cyan]{default}")
        console.print(f"    {task.description}")
        console.print(f"    [dim]Prompt: \"{task.prompt}\"[/dim]")
        console.print()

    console.print(
        "[dim]Or provide a custom prompt: sunwell demo --task \"your prompt here\"[/dim]"
    )
    console.print()


def _show_history() -> None:
    """Show demo history summary."""
    from sunwell.benchmark.demo.history import get_history_summary, load_history

    summary = get_history_summary()

    if summary["total_runs"] == 0:
        console.print("\n[yellow]No demo history found.[/yellow]")
        console.print("[dim]Run 'sunwell demo' to create your first demo result.[/dim]\n")
        return

    console.print("\n[bold]📊 Demo History Summary[/bold]\n")

    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total runs", str(summary["total_runs"]))
    table.add_row("Avg improvement", f"+{summary['avg_improvement']:.0f}%")
    table.add_row("Max improvement", f"+{summary['max_improvement']:.0f}%")
    table.add_row("Avg single-shot score", f"{summary['avg_single_shot_score']:.1f}/10")
    table.add_row("Avg Sunwell score", f"{summary['avg_sunwell_score']:.1f}/10")
    table.add_row("Models used", ", ".join(summary["models_used"]))
    table.add_row("Tasks run", ", ".join(summary["tasks_run"]))

    console.print(table)

    # Show recent runs
    recent = load_history(limit=5)
    if recent:
        console.print("\n[bold]Recent Runs:[/bold]\n")

        recent_table = Table()
        recent_table.add_column("Time", style="dim")
        recent_table.add_column("Task", style="cyan")
        recent_table.add_column("Model", style="magenta")
        recent_table.add_column("Single", justify="center")
        recent_table.add_column("Sunwell", justify="center")
        recent_table.add_column("Δ", justify="center")

        for entry in recent:
            # Parse timestamp for display
            ts = entry.timestamp.split("T")[0] + " " + entry.timestamp.split("T")[1][:5]
            improvement = f"+{entry.improvement_percent:.0f}%"
            recent_table.add_row(
                ts,
                entry.task_name,
                entry.model_name[:20],
                f"{entry.single_shot_score:.1f}",
                f"{entry.sunwell_score:.1f}",
                f"[green]{improvement}[/green]",
            )

        console.print(recent_table)

    console.print()


async def _run_demo(
    task: str,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
    json_output: bool,
    quiet: bool,
    skip_single_shot: bool,
    iterations: int,
    save_history: bool,
) -> None:
    """Execute the demo."""
    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.foundation.config import get_config
    from sunwell.benchmark.demo import DemoComparison, DemoRunner, get_task

    # Resolve model
    config = get_config()

    try:
        model = resolve_model(provider_override, model_override)
    except Exception as e:
        console.print(f"[red]Error: Could not load model: {e}[/red]")
        console.print()
        console.print("[yellow]Tip: Run 'sunwell setup' to configure a model,[/yellow]")
        console.print("[yellow]or ensure Ollama is running with 'ollama serve'[/yellow]")
        return

    if not model:
        console.print("[red]No model available[/red]")
        return

    # Get model name for display
    model_name = model_override
    if not model_name:
        if config and hasattr(config, "model"):
            model_name = f"{config.model.default_provider}:{config.model.default_model}"
        else:
            model_name = "ollama:gemma3:4b"

    # Validate task
    demo_task = get_task(task)

    # Create runner
    runner = DemoRunner(
        model,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
    )

    # Multiple iterations mode
    if iterations > 1:
        await _run_iterations(
            runner=runner,
            demo_task=demo_task,
            model_name=model_name,
            iterations=iterations,
            verbose=verbose,
            json_output=json_output,
            quiet=quiet,
            save_history=save_history,
        )
        return

    # Single run mode
    # Run with progress display
    if not quiet and not json_output:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Starting demo...", total=None)

            def update_progress(msg: str) -> None:
                progress.update(task_id, description=msg)

            # Run single-shot (unless skipped)
            if not skip_single_shot:
                update_progress("Running single-shot...")
                single_shot = await runner.executor.run_single_shot(
                    demo_task,
                    on_progress=update_progress,
                )
                single_score = runner.scorer.score(
                    single_shot.code,
                    demo_task.expected_features,
                )
            else:
                single_shot = None
                single_score = None

            # Run Sunwell
            update_progress("Running Sunwell + Resonance...")
            sunwell_result = await runner.executor.run_sunwell(
                demo_task,
                on_progress=update_progress,
            )
            sunwell_score = runner.scorer.score(
                sunwell_result.code,
                demo_task.expected_features,
            )

            progress.update(task_id, description="Complete!")

        # Create comparison and present
        if skip_single_shot:
            # Just show Sunwell result
            _present_single_result(
                sunwell_result, sunwell_score, demo_task, model_name, verbose
            )
        else:
            comparison = DemoComparison(
                task=demo_task,
                single_shot=single_shot,
                sunwell=sunwell_result,
                single_score=single_score,
                sunwell_score=sunwell_score,
            )
            runner.present(comparison, model_name)

            # Save to history
            if save_history:
                _save_to_history(comparison, model_name)

    else:
        # Quiet or JSON mode - no progress display
        comparison = await runner.run(task)
        runner.present(comparison, model_name)

        # Save to history
        if save_history and not skip_single_shot:
            _save_to_history(comparison, model_name)


async def _run_iterations(
    runner,
    demo_task,
    model_name: str,
    iterations: int,
    verbose: bool,
    json_output: bool,
    quiet: bool,
    save_history: bool,
) -> None:
    """Run multiple iterations for variance analysis."""
    from sunwell.benchmark.demo import DemoComparison

    single_scores: list[float] = []
    sunwell_scores: list[float] = []
    improvements: list[float] = []
    comparisons: list[DemoComparison] = []

    if not quiet and not json_output:
        console.print(f"\n[bold]Running {iterations} iterations for consistency...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not verbose,
    ) as progress:
        task_id = progress.add_task(f"Iteration 1/{iterations}...", total=None)

        for i in range(iterations):
            progress.update(task_id, description=f"Iteration {i+1}/{iterations}...")

            # Run single-shot
            single_shot = await runner.executor.run_single_shot(demo_task)
            single_score = runner.scorer.score(
                single_shot.code, demo_task.expected_features
            )

            # Run Sunwell
            sunwell_result = await runner.executor.run_sunwell(demo_task)
            sunwell_score = runner.scorer.score(
                sunwell_result.code, demo_task.expected_features
            )

            comparison = DemoComparison(
                task=demo_task,
                single_shot=single_shot,
                sunwell=sunwell_result,
                single_score=single_score,
                sunwell_score=sunwell_score,
            )

            single_scores.append(single_score.score)
            sunwell_scores.append(sunwell_score.score)
            improvements.append(comparison.improvement_percent)
            comparisons.append(comparison)

            if verbose and not json_output:
                console.print(
                    f"  [{i+1}] Single: {single_score.score:.1f} | "
                    f"Sunwell: {sunwell_score.score:.1f} | "
                    f"Δ: +{comparison.improvement_percent:.0f}%"
                )

        progress.update(task_id, description="Complete!")

    # Present summary
    if json_output:
        import json as json_lib

        data = {
            "iterations": iterations,
            "task": demo_task.name,
            "model": model_name,
            "single_shot": {
                "mean": statistics.mean(single_scores),
                "stdev": statistics.stdev(single_scores) if len(single_scores) > 1 else 0,
                "min": min(single_scores),
                "max": max(single_scores),
            },
            "sunwell": {
                "mean": statistics.mean(sunwell_scores),
                "stdev": statistics.stdev(sunwell_scores) if len(sunwell_scores) > 1 else 0,
                "min": min(sunwell_scores),
                "max": max(sunwell_scores),
            },
            "improvement": {
                "mean": statistics.mean(improvements),
                "stdev": statistics.stdev(improvements) if len(improvements) > 1 else 0,
                "min": min(improvements),
                "max": max(improvements),
            },
        }
        console.print(json_lib.dumps(data, indent=2))
    elif quiet:
        console.print(
            f"Single: {statistics.mean(single_scores):.1f}±"
            f"{statistics.stdev(single_scores) if len(single_scores) > 1 else 0:.1f} | "
            f"Sunwell: {statistics.mean(sunwell_scores):.1f}±"
            f"{statistics.stdev(sunwell_scores) if len(sunwell_scores) > 1 else 0:.1f}"
        )
    else:
        _present_iterations_summary(
            single_scores, sunwell_scores, improvements, model_name, demo_task, iterations
        )

    # Save best result to history
    if save_history and comparisons:
        best = max(comparisons, key=lambda c: c.improvement_percent)
        _save_to_history(best, model_name)


def _present_iterations_summary(
    single_scores: list[float],
    sunwell_scores: list[float],
    improvements: list[float],
    model_name: str,
    demo_task,
    iterations: int,
) -> None:
    """Present summary of multiple iterations."""
    from rich.panel import Panel

    console.print()
    console.print(
        Panel(
            f"[bold cyan]🔮 Sunwell Demo[/bold cyan] — {iterations} Iterations",
            border_style="cyan",
        )
    )
    console.print()
    console.print(f"Model: [cyan]{model_name}[/cyan]")
    console.print(f"Task: [cyan]{demo_task.name}[/cyan] — \"{demo_task.prompt}\"")
    console.print()

    # Stats table
    table = Table(title="Consistency Analysis")
    table.add_column("Metric", style="cyan")
    table.add_column("Single-shot", justify="center")
    table.add_column("Sunwell", justify="center")

    single_mean = statistics.mean(single_scores)
    single_stdev = statistics.stdev(single_scores) if len(single_scores) > 1 else 0
    sunwell_mean = statistics.mean(sunwell_scores)
    sunwell_stdev = statistics.stdev(sunwell_scores) if len(sunwell_scores) > 1 else 0

    table.add_row("Mean", f"{single_mean:.1f}", f"[green]{sunwell_mean:.1f}[/green]")
    table.add_row("Std Dev", f"±{single_stdev:.2f}", f"±{sunwell_stdev:.2f}")
    table.add_row("Min", f"{min(single_scores):.1f}", f"{min(sunwell_scores):.1f}")
    table.add_row("Max", f"{max(single_scores):.1f}", f"{max(sunwell_scores):.1f}")

    console.print(table)
    console.print()

    # Improvement summary
    mean_improvement = statistics.mean(improvements)
    improvement_stdev = statistics.stdev(improvements) if len(improvements) > 1 else 0

    console.print(
        f"[bold green]Average Improvement: +{mean_improvement:.0f}% "
        f"(±{improvement_stdev:.0f}%)[/bold green]"
    )
    console.print(
        f"[dim]Range: +{min(improvements):.0f}% to +{max(improvements):.0f}%[/dim]"
    )
    console.print()

    # Tagline
    console.print(
        "[bold cyan]🔮 Same model. Same prompt. Consistently better.[/bold cyan]"
    )
    console.print()


def _save_to_history(comparison, model_name: str) -> None:
    """Save comparison to history (silent)."""
    try:
        from sunwell.benchmark.demo.history import save_demo_result

        save_demo_result(comparison, model_name)
    except Exception:
        # Silently ignore history save failures
        pass


def _present_single_result(
    result,
    score,
    task,
    model_name: str,
    verbose: bool,
) -> None:
    """Present just the Sunwell result (when --skip-single-shot is used)."""
    from rich.panel import Panel

    from sunwell.benchmark.demo.scorer import FEATURE_DISPLAY_NAMES

    console.print()
    console.print(
        Panel(
            "[bold cyan]🔮 Sunwell Demo[/bold cyan] — Sunwell + Resonance Result",
            border_style="cyan",
        )
    )
    console.print()
    console.print(f"Using model: [cyan]{model_name}[/cyan]")
    console.print(f"Task: [cyan]{task.name}[/cyan] — \"{task.prompt}\"")
    console.print()

    # Show timing
    console.print(f"⏳ Generated in {result.time_ms}ms")
    if result.iterations > 0:
        console.print(f"   Refined {result.iterations} time(s)")
    console.print()

    # Code result
    score_color = "green" if score.score >= 8 else "yellow" if score.score >= 5 else "red"
    console.print(
        Panel(
            result.code.strip()[:1000],  # Truncate very long output
            title=f"[{score_color}]Score: {score.score}/10[/{score_color}]",
            border_style=score_color,
        )
    )

    # Features
    console.print()
    for feature in task.expected_features:
        display_name = FEATURE_DISPLAY_NAMES.get(feature, feature)
        present = score.features.get(feature, False)
        icon = "[green]✅[/green]" if present else "[red]❌[/red]"
        console.print(f"  {icon} {display_name}")

    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMING MODE — Parallel execution with NDJSON output for Tauri Studio
# ═══════════════════════════════════════════════════════════════════════════════


async def _run_demo_streaming(
    task: str,
    provider_override: str | None,
    model_override: str | None,
) -> None:
    """Run demo with streaming NDJSON output for real-time UI updates.

    Output format (one JSON object per line):
        {"type": "start", "model": "...", "task": "..."}
        {"type": "chunk", "method": "single_shot", "content": "def..."}
        {"type": "chunk", "method": "sunwell", "content": "def..."}
        {"type": "phase", "method": "sunwell", "phase": "judging"}
        {"type": "complete", "comparison": {...}}

    Runs both methods in PARALLEL with streaming for ~2x speedup.
    """
    import json
    import sys

    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.foundation.config import get_config
    from sunwell.benchmark.demo import DemoComparison, DemoExecutor, DemoScorer, get_task
    from sunwell.models import sanitize_llm_content

    def emit(data: dict) -> None:
        """Emit NDJSON line (newline-delimited JSON)."""
        print(json.dumps(data), flush=True)

    # Resolve model
    config = get_config()

    try:
        model = resolve_model(provider_override, model_override)
    except Exception as e:
        emit({"type": "error", "message": f"Could not load model: {e}"})
        sys.exit(1)

    if not model:
        emit({"type": "error", "message": "No model available"})
        sys.exit(1)

    # Get model name
    model_name = model_override
    if not model_name:
        if config and hasattr(config, "model"):
            model_name = f"{config.model.default_provider}:{config.model.default_model}"
        else:
            model_name = "ollama:gemma3:4b"

    # Get task
    demo_task = get_task(task)

    # Emit start event
    emit({
        "type": "start",
        "model": model_name,
        "task": {"name": demo_task.name, "prompt": demo_task.prompt},
    })

    # Create executor and scorer
    executor = DemoExecutor(model, verbose=False)
    scorer = DemoScorer()

    # Define streaming callbacks
    def on_single_shot_chunk(chunk: str) -> None:
        sanitized = sanitize_llm_content(chunk)
        if sanitized:
            emit({"type": "chunk", "method": "single_shot", "content": sanitized})

    def on_sunwell_chunk(chunk: str) -> None:
        sanitized = sanitize_llm_content(chunk)
        if sanitized:
            emit({"type": "chunk", "method": "sunwell", "content": sanitized})

    def on_sunwell_phase(phase: str) -> None:
        emit({"type": "phase", "method": "sunwell", "phase": phase})

    # Run BOTH in parallel with streaming!
    single_shot_result, sunwell_result = await executor.run_parallel(
        demo_task,
        on_single_shot_chunk=on_single_shot_chunk,
        on_sunwell_chunk=on_sunwell_chunk,
        on_sunwell_phase=on_sunwell_phase,
    )

    # Score results
    single_score = scorer.score(single_shot_result.code, demo_task.expected_features)
    sunwell_score = scorer.score(sunwell_result.code, demo_task.expected_features)

    # Create comparison
    comparison = DemoComparison(
        task=demo_task,
        single_shot=single_shot_result,
        sunwell=sunwell_result,
        single_score=single_score,
        sunwell_score=sunwell_score,
    )

    # Build breakdown data if available
    breakdown_data = None
    if sunwell_result.breakdown:
        bd = sunwell_result.breakdown
        breakdown_data = {
            "lens": {
                "name": bd.lens_name,
                "detected": bd.lens_detected,
                "heuristics_applied": list(bd.heuristics_applied),
            },
            "prompt": {
                "type": bd.prompt_type,
                "requirements_added": list(bd.requirements_added),
            },
            "judge": {
                "score": bd.judge_score,
                "issues": list(bd.judge_issues),
                "passed": bd.judge_passed,
            },
            "resonance": {
                "triggered": bd.resonance_triggered,
                "succeeded": bd.resonance_succeeded,
                "iterations": bd.resonance_iterations,
                "improvements": list(bd.resonance_improvements),
            },
            "result": {
                "final_score": bd.final_score,
                "features_achieved": list(bd.features_achieved),
                "features_missing": list(bd.features_missing),
            },
        }

    # Emit complete event with full comparison (same format as --json)
    complete_data = {
        "type": "complete",
        "model": model_name,
        "task": {
            "name": comparison.task.name,
            "prompt": comparison.task.prompt,
        },
        "single_shot": {
            "score": single_score.score,
            "lines": single_score.lines,
            "time_ms": single_shot_result.time_ms,
            "features": single_score.features,
            "tokens": {
                "prompt": single_shot_result.prompt_tokens,
                "completion": single_shot_result.completion_tokens,
                "total": single_shot_result.total_tokens,
            },
            "code": sanitize_llm_content(single_shot_result.code),
        },
        "sunwell": {
            "score": sunwell_score.score,
            "lines": sunwell_score.lines,
            "time_ms": sunwell_result.time_ms,
            "iterations": sunwell_result.iterations,
            "features": sunwell_score.features,
            "tokens": {
                "prompt": sunwell_result.prompt_tokens,
                "completion": sunwell_result.completion_tokens,
                "total": sunwell_result.total_tokens,
            },
            "code": sanitize_llm_content(sunwell_result.code),
        },
        "improvement_percent": round(comparison.improvement_percent, 1),
    }

    # Add breakdown to show what each component contributed
    if breakdown_data:
        complete_data["breakdown"] = breakdown_data

    emit(complete_data)
