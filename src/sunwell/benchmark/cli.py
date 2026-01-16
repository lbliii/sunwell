"""Benchmark CLI commands (RFC-018).

Provides CLI interface for the benchmark framework:
- sunwell benchmark run - Run benchmark suite
- sunwell benchmark compare - Compare two versions
- sunwell benchmark report - Generate report from results
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def benchmark() -> None:
    """Quality benchmark framework for validating output quality.
    
    Run benchmarks to compare selective retrieval against baselines.
    """
    pass


@benchmark.command()
@click.option(
    "--model",
    default="hhao/qwen2.5-coder-tools:14b",
    help="Model to benchmark",
)
@click.option(
    "--category",
    type=click.Choice(["documentation", "code_review", "code_generation", "analysis"]),
    help="Run only tasks in this category",
)
@click.option(
    "--task",
    "task_id",
    help="Run a single task by ID",
)
@click.option(
    "--tasks-dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path("benchmark/tasks"),
    help="Directory containing task YAML files",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("benchmark/results"),
    help="Output directory for results",
)
@click.option(
    "--max-tasks",
    type=int,
    help="Maximum number of tasks to run",
)
@click.option(
    "--skip-eval",
    is_flag=True,
    help="Skip LLM evaluation (run tasks only)",
)
@click.option(
    "--judge-model",
    default=None,
    help="Model to use as judge (defaults to same as --model)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--router-model",
    default=None,
    help="Tiny LLM for cognitive routing (enables ROUTED condition, RFC-020)",
)
def run(
    model: str,
    category: str | None,
    task_id: str | None,
    tasks_dir: Path,
    output: Path,
    max_tasks: int | None,
    skip_eval: bool,
    judge_model: str | None,
    verbose: bool,
    router_model: str | None,
) -> None:
    """Run benchmark suite against specified model.
    
    \b
    Examples:
        # Run full benchmark suite
        sunwell benchmark run --model gpt-4o
        
        # Run only documentation tasks
        sunwell benchmark run --category docs
        
        # Run single task for debugging
        sunwell benchmark run --task docs-api-ref-001 --verbose
        
        # Quick run with limited tasks
        sunwell benchmark run --max-tasks 5
    """
    asyncio.run(_run_benchmark(
        model=model,
        category=category,
        task_id=task_id,
        tasks_dir=tasks_dir,
        output_dir=output,
        max_tasks=max_tasks,
        skip_eval=skip_eval,
        judge_model=judge_model or model,
        verbose=verbose,
        router_model=router_model,
    ))


async def _run_benchmark(
    model: str,
    category: str | None,
    task_id: str | None,
    tasks_dir: Path,
    output_dir: Path,
    max_tasks: int | None,
    skip_eval: bool,
    judge_model: str,
    verbose: bool,
    router_model: str | None = None,
) -> None:
    """Async benchmark execution."""
    from sunwell.benchmark.runner import BenchmarkRunner
    from sunwell.benchmark.evaluator import BenchmarkEvaluator
    from sunwell.benchmark.report import BenchmarkReporter
    from sunwell.models.ollama import OllamaModel
    from sunwell.schema.loader import LensLoader
    
    # Banner
    console.print()
    console.print("╔" + "═" * 60 + "╗")
    console.print("║" + " 🔬 QUALITY BENCHMARK (RFC-018)".ljust(60) + "║")
    console.print("║" + f"    Model: {model}".ljust(60) + "║")
    if category:
        console.print("║" + f"    Category: {category}".ljust(60) + "║")
    if task_id:
        console.print("║" + f"    Task: {task_id}".ljust(60) + "║")
    if router_model:
        console.print("║" + f"    Router: {router_model} (RFC-020)".ljust(60) + "║")
    console.print("╚" + "═" * 60 + "╝")
    console.print()
    
    # Create model and loader
    llm = OllamaModel(model=model)
    loader = LensLoader()
    
    # Create router model if specified
    router_llm = OllamaModel(model=router_model) if router_model else None
    
    # Create runner
    runner = BenchmarkRunner(
        model=llm,
        lens_loader=loader,
        tasks_dir=tasks_dir,
        output_dir=output_dir,
        lens_dir=Path("lenses"),
        router_model=router_llm,
    )
    
    # Run benchmarks
    console.print("📊 Running benchmark tasks...")
    console.print()
    
    task_ids = [task_id] if task_id else None
    results = await runner.run_suite(
        category=category,
        task_ids=task_ids,
        max_tasks=max_tasks,
    )
    
    console.print()
    console.print(f"✅ Completed {len(results.task_results)} tasks")
    console.print()
    
    if skip_eval:
        console.print("⏭️  Skipping evaluation (--skip-eval)")
        return
    
    # Run evaluation
    console.print("🧑‍⚖️ Running LLM evaluation...")
    console.print()
    
    judge_llm = OllamaModel(model=judge_model)
    evaluator = BenchmarkEvaluator(judge_model=judge_llm)
    
    # Load tasks for evaluation
    tasks = runner._load_tasks(category=category, task_ids=task_ids)
    evaluations = await evaluator.evaluate_suite(tasks, list(results.task_results))
    
    console.print()
    console.print(f"✅ Evaluated {len(evaluations)} tasks")
    console.print()
    
    # Compute statistics
    console.print("📈 Computing statistics...")
    reporter = BenchmarkReporter()
    summary = reporter.compute_statistics(list(results.task_results), evaluations)
    
    # Display results
    _display_summary(summary)
    
    # Save results
    console.print()
    reporter.save_results(results, evaluations, summary, output_dir)


def _display_summary(summary) -> None:
    """Display summary statistics in a table."""
    from sunwell.benchmark.types import StatisticalSummary
    
    table = Table(title="Benchmark Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Tasks", str(summary.n_tasks))
    table.add_row(
        "Win/Loss/Tie",
        f"{summary.wins}W / {summary.losses}L / {summary.ties}T"
    )
    table.add_row("Win Rate", f"{summary.win_rate:.1%}")
    table.add_row(
        "Effect Size",
        f"{summary.effect_size_cohens_d:.3f} ({summary.effect_size_interpretation})"
    )
    table.add_row(
        "p-value",
        f"{summary.p_value:.4f} {'✓' if summary.significant else '✗'}"
    )
    table.add_row(
        "95% CI",
        f"[{summary.ci_lower:.3f}, {summary.ci_upper:.3f}]"
    )
    table.add_row(
        "Claim Level",
        summary.claim_level(),
        style="bold"
    )
    
    console.print(table)


@benchmark.command()
@click.argument("version1")
@click.argument("version2")
@click.option(
    "--results-dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path("benchmark/results"),
    help="Directory containing benchmark results",
)
def compare(
    version1: str,
    version2: str,
    results_dir: Path,
) -> None:
    """Compare benchmark results between two versions.
    
    \b
    Examples:
        sunwell benchmark compare v0.1.0 v0.2.0
        sunwell benchmark compare 2024-01-15 2024-01-16
    """
    console.print()
    console.print(f"📊 Comparing {version1} vs {version2}")
    console.print()
    
    # Load results
    v1_path = results_dir / version1
    v2_path = results_dir / version2
    
    if not v1_path.exists():
        console.print(f"[red]Error: Results not found for {version1}[/red]")
        return
    
    if not v2_path.exists():
        console.print(f"[red]Error: Results not found for {version2}[/red]")
        return
    
    # Load statistics
    v1_stats = _load_statistics(v1_path / "statistics.json")
    v2_stats = _load_statistics(v2_path / "statistics.json")
    
    if v1_stats is None or v2_stats is None:
        console.print("[red]Error: Could not load statistics files[/red]")
        return
    
    # Display comparison
    table = Table(title=f"Version Comparison: {version1} vs {version2}")
    table.add_column("Metric", style="cyan")
    table.add_column(version1, style="yellow")
    table.add_column(version2, style="green")
    table.add_column("Δ", style="bold")
    
    # Win rate
    wr1 = v1_stats.get("win_rate", 0)
    wr2 = v2_stats.get("win_rate", 0)
    delta = wr2 - wr1
    table.add_row(
        "Win Rate",
        f"{wr1:.1%}",
        f"{wr2:.1%}",
        f"{delta:+.1%}"
    )
    
    # Effect size
    es1 = v1_stats.get("effect_size_cohens_d", 0)
    es2 = v2_stats.get("effect_size_cohens_d", 0)
    delta = es2 - es1
    table.add_row(
        "Effect Size",
        f"{es1:.3f}",
        f"{es2:.3f}",
        f"{delta:+.3f}"
    )
    
    # p-value
    p1 = v1_stats.get("p_value", 1)
    p2 = v2_stats.get("p_value", 1)
    table.add_row(
        "p-value",
        f"{p1:.4f}",
        f"{p2:.4f}",
        f"{p2 - p1:+.4f}"
    )
    
    # Claim level
    cl1 = v1_stats.get("claim_level", "insufficient")
    cl2 = v2_stats.get("claim_level", "insufficient")
    table.add_row("Claim Level", cl1, cl2, "→" if cl1 != cl2 else "=")
    
    console.print(table)
    
    # Regression check
    console.print()
    if wr2 < wr1 - 0.05:
        console.print(
            f"[red]⚠️  REGRESSION: Win rate dropped {wr1 - wr2:.1%}[/red]"
        )
    elif wr2 > wr1 + 0.05:
        console.print(
            f"[green]✅ IMPROVEMENT: Win rate increased {wr2 - wr1:.1%}[/green]"
        )
    else:
        console.print("[yellow]→ No significant change in win rate[/yellow]")


def _load_statistics(path: Path) -> dict | None:
    """Load statistics from JSON file."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


@benchmark.command()
@click.argument(
    "results_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["markdown", "json", "table"]),
    default="table",
    help="Output format",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output file (defaults to stdout)",
)
def report(
    results_path: Path,
    output_format: str,
    output: Path | None,
) -> None:
    """Generate report from benchmark results.
    
    \b
    Examples:
        # Display table summary
        sunwell benchmark report benchmark/results/2024-01-16/
        
        # Generate markdown report
        sunwell benchmark report benchmark/results/2024-01-16/ -f markdown -o report.md
    """
    # Load statistics
    stats_path = results_path / "statistics.json"
    if not stats_path.exists():
        console.print(f"[red]Error: {stats_path} not found[/red]")
        return
    
    stats = _load_statistics(stats_path)
    if stats is None:
        console.print("[red]Error: Could not parse statistics[/red]")
        return
    
    if output_format == "table":
        _display_report_table(stats)
    elif output_format == "json":
        content = json.dumps(stats, indent=2)
        if output:
            output.write_text(content)
            console.print(f"Saved to {output}")
        else:
            console.print(content)
    elif output_format == "markdown":
        # Load full report if available
        report_path = results_path / "report.md"
        if report_path.exists():
            content = report_path.read_text()
        else:
            content = _generate_simple_markdown(stats)
        
        if output:
            output.write_text(content)
            console.print(f"Saved to {output}")
        else:
            console.print(content)


def _display_report_table(stats: dict) -> None:
    """Display statistics as a rich table."""
    table = Table(title="Benchmark Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Tasks", str(stats.get("n_tasks", 0)))
    table.add_row(
        "Results",
        f"{stats.get('wins', 0)}W / {stats.get('losses', 0)}L / {stats.get('ties', 0)}T"
    )
    table.add_row("Win Rate", f"{stats.get('win_rate', 0):.1%}")
    table.add_row(
        "Effect Size",
        f"{stats.get('effect_size_cohens_d', 0):.3f} "
        f"({stats.get('effect_size_interpretation', 'unknown')})"
    )
    
    sig = "✓ significant" if stats.get("significant") else "✗ not significant"
    table.add_row("p-value", f"{stats.get('p_value', 1):.4f} ({sig})")
    table.add_row(
        "95% CI",
        f"[{stats.get('ci_lower', 0):.3f}, {stats.get('ci_upper', 0):.3f}]"
    )
    table.add_row("Claim Level", stats.get("claim_level", "unknown"))
    
    console.print(table)
    
    # Category breakdown
    categories = stats.get("category_breakdown", {})
    if categories:
        console.print()
        cat_table = Table(title="Category Breakdown")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Win Rate", style="green")
        cat_table.add_column("W/L/T")
        
        for cat, data in categories.items():
            cat_table.add_row(
                cat,
                f"{data.get('win_rate', 0):.0%}",
                f"{data.get('wins', 0)}/{data.get('losses', 0)}/{data.get('ties', 0)}"
            )
        
        console.print(cat_table)


def _generate_simple_markdown(stats: dict) -> str:
    """Generate simple markdown report from statistics."""
    lines = [
        "# Benchmark Report",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Tasks | {stats.get('n_tasks', 0)} |",
        f"| Win Rate | {stats.get('win_rate', 0):.1%} |",
        f"| Effect Size | {stats.get('effect_size_cohens_d', 0):.3f} |",
        f"| p-value | {stats.get('p_value', 1):.4f} |",
        f"| Claim Level | {stats.get('claim_level', 'unknown')} |",
    ]
    return "\n".join(lines)


# Export for CLI integration
def register_benchmark_commands(cli: click.Group) -> None:
    """Register benchmark commands with main CLI."""
    cli.add_command(benchmark)
