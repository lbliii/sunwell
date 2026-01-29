"""Benchmark CLI commands (RFC-018).

Provides CLI interface for the benchmark framework:
- sunwell benchmark run - Run benchmark suite
- sunwell benchmark compare - Compare two versions
- sunwell benchmark report - Generate report from results
"""


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
    default=None,
    help="Model to benchmark (default: from config)",
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
@click.option(
    "--strategy",
    type=click.Choice(["raw", "guided", "cot", "constraints", "few_shot"]),
    default="constraints",
    help="Prompt strategy for presenting heuristics (default: constraints for small models)",
)
@click.option(
    "--naaru",
    type=click.Choice(["none", "harmonic", "resonance", "full"]),
    default="none",
    help="Naaru coordination mode (harmonic=3x tokens, resonance=1.5x, full=4x)",
)
def run(
    model: str | None,
    category: str | None,
    task_id: str | None,
    tasks_dir: Path,
    output: Path,
    max_tasks: int | None,
    skip_eval: bool,
    judge_model: str | None,
    verbose: bool,
    router_model: str | None,
    strategy: str,
    naaru: str,
) -> None:
    """Run benchmark suite against specified model.

    \b
    Examples:
        # Run full benchmark suite
        sunwell benchmark run --model gpt-4o

        # Run only documentation tasks
        sunwell benchmark run --category docs

        # Quick run with limited tasks
        sunwell benchmark run --max-tasks 5

        # Test different prompt strategies
        sunwell benchmark run --model qwen2.5:1.5b --strategy constraints
        sunwell benchmark run --model qwen2.5:1.5b --strategy cot
        sunwell benchmark run --model qwen2.5:1.5b --strategy few_shot

        # Enable Naaru coordination (more tokens, better quality)
        sunwell benchmark run --model qwen2.5:1.5b --naaru harmonic
        sunwell benchmark run --model qwen2.5:1.5b --naaru full

    \b
    Prompt Strategies (best by model size):
        - constraints: MUST/MUST NOT (best for 1-2B models)
        - raw: Just dump heuristics as-is
        - guided: "Apply these principles" meta-instructions
        - cot: Chain-of-thought (THINK→PLAN→CODE→VERIFY, best for 4B+)
        - few_shot: Include example of applying heuristics

    \b
    Naaru Modes (quality vs cost tradeoff):
        - none: Single generation (1x tokens)
        - harmonic: Multi-persona voting (3x tokens, Self-Consistency)
        - resonance: Feedback loop (1.5x tokens)
        - full: Both (4x tokens, best quality)
    """
    from sunwell.foundation.config import get_config

    cfg = get_config()

    # Resolve model from config if not specified
    if model is None:
        model = cfg.model.default_model if cfg else "llama3.1:8b"

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
        strategy=strategy,
        naaru=naaru,
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
    strategy: str = "constraints",
    naaru: str = "none",
) -> None:
    """Async benchmark execution."""
    from sunwell.benchmark.core.runner import BenchmarkRunner
    from sunwell.benchmark.evaluation.evaluator import BenchmarkEvaluator
    from sunwell.benchmark.reporting.reporter import BenchmarkReporter
    from sunwell.benchmark.types import NaaruMode, PromptStrategy
    from sunwell.foundation.schema.loader import LensLoader
    from sunwell.models import OllamaModel

    # Convert string options to enums
    prompt_strategy = PromptStrategy(strategy)
    naaru_mode = NaaruMode(naaru)

    # Banner
    console.print()
    console.print("╔" + "═" * 60 + "╗")
    console.print("║" + " 🔬 QUALITY BENCHMARK (RFC-018)".ljust(60) + "║")
    console.print("║" + f"    Model: {model}".ljust(60) + "║")
    console.print("║" + f"    Strategy: {strategy}".ljust(60) + "║")
    if naaru != "none":
        console.print("║" + f"    Naaru: {naaru}".ljust(60) + "║")
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

    # Create runner with strategy configuration
    runner = BenchmarkRunner(
        model=llm,
        lens_loader=loader,
        tasks_dir=tasks_dir,
        output_dir=output_dir,
        lens_dir=Path("lenses"),
        router_model=router_llm,
        prompt_strategy=prompt_strategy,
        naaru_mode=naaru_mode,
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
        "| Metric | Value |",
        "|--------|-------|",
        f"| Tasks | {stats.get('n_tasks', 0)} |",
        f"| Win Rate | {stats.get('win_rate', 0):.1%} |",
        f"| Effect Size | {stats.get('effect_size_cohens_d', 0):.3f} |",
        f"| p-value | {stats.get('p_value', 1):.4f} |",
        f"| Claim Level | {stats.get('claim_level', 'unknown')} |",
    ]
    return "\n".join(lines)


# =============================================================================
# Naaru Benchmark Commands (RFC-027)
# =============================================================================


@benchmark.command()
@click.option(
    "--model",
    default=None,
    help="Synthesis model (default: from config)",
)
@click.option(
    "--judge-model",
    default=None,
    help="Judge model for evaluation (default: from config or naaru.wisdom)",
)
@click.option(
    "--conditions",
    default=None,
    help="Comma-separated conditions (e.g., BASELINE,HARMONIC,NAARU_FULL)",
)
@click.option(
    "--category",
    type=click.Choice(["documentation", "code_review", "code_generation", "analysis"]),
    help="Run only tasks in this category",
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
    default=Path("benchmark/results/naaru"),
    help="Output directory for results",
)
@click.option(
    "--max-tasks",
    type=int,
    help="Maximum number of tasks to run",
)
@click.option(
    "--quick",
    is_flag=True,
    help="Quick smoke test (5 tasks, all conditions)",
)
@click.option(
    "--ablation",
    is_flag=True,
    help="Run ablation study (incremental technique enablement)",
)
@click.option(
    "--full",
    is_flag=True,
    help="Full statistical run (all tasks, all conditions)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
def naaru(
    model: str | None,
    judge_model: str | None,
    conditions: str | None,
    category: str | None,
    tasks_dir: Path,
    output: Path,
    max_tasks: int | None,
    quick: bool,
    ablation: bool,
    full: bool,
    verbose: bool,
) -> None:
    """Run Naaru benchmark suite (RFC-027).

    Validates Naaru's quality claims with statistical rigor by testing
    7 conditions (A-G) that systematically enable features.

    \b
    Conditions:
        A: BASELINE      - Raw model capability
        B: BASELINE_LENS - Lens context alone
        C: HARMONIC      - Multi-persona voting
        D: HARMONIC_LENS - Harmonic + lens personas
        E: RESONANCE     - Feedback loop refinement
        F: NAARU_FULL    - All techniques combined
        G: NAARU_FULL_LENS - Full Naaru + lens

    \b
    Examples:
        # Quick smoke test (5 tasks)
        sunwell benchmark naaru --quick

        # Run ablation study
        sunwell benchmark naaru --ablation --max-tasks 30

        # Run specific conditions only
        sunwell benchmark naaru --conditions BASELINE,HARMONIC,NAARU_FULL

        # Full statistical run (all tasks, all conditions)
        sunwell benchmark naaru --full
    """
    from sunwell.foundation.config import get_config

    cfg = get_config()

    # Resolve model from config if not specified
    if model is None:
        model = cfg.naaru.voice if cfg else "gemma3:1b"

    # Resolve judge model from config if not specified
    if judge_model is None:
        judge_model = cfg.naaru.wisdom if cfg else "llama3.1:8b"

    asyncio.run(_run_naaru_benchmark(
        model=model,
        judge_model=judge_model,
        conditions_str=conditions,
        category=category,
        tasks_dir=tasks_dir,
        output_dir=output,
        max_tasks=max_tasks,
        quick=quick,
        ablation=ablation,
        full=full,
        verbose=verbose,
    ))


async def _run_naaru_benchmark(
    model: str,
    judge_model: str,
    conditions_str: str | None,
    category: str | None,
    tasks_dir: Path,
    output_dir: Path,
    max_tasks: int | None,
    quick: bool,
    ablation: bool,
    full: bool,
    verbose: bool,
) -> None:
    """Async Naaru benchmark execution."""
    from sunwell.benchmark.naaru import NaaruBenchmarkRunner, NaaruCondition
    from sunwell.foundation.schema.loader import LensLoader
    from sunwell.models import OllamaModel

    # Parse conditions
    conditions: list[NaaruCondition] | None = None
    if conditions_str:
        conditions = [
            NaaruCondition(c.strip().lower())
            for c in conditions_str.split(",")
        ]

    # Banner
    console.print()
    console.print("╔" + "═" * 60 + "╗")
    console.print("║" + " 🌟 NAARU BENCHMARK SUITE (RFC-027)".ljust(60) + "║")
    console.print("║" + f"    Synthesis: {model}".ljust(60) + "║")
    console.print("║" + f"    Judge: {judge_model}".ljust(60) + "║")
    if quick:
        console.print("║" + "    Mode: Quick (5 tasks)".ljust(60) + "║")
    elif ablation:
        console.print("║" + "    Mode: Ablation Study".ljust(60) + "║")
    elif full:
        console.print("║" + "    Mode: Full Statistical Run".ljust(60) + "║")
    if conditions:
        console.print("║" + f"    Conditions: {len(conditions)} selected".ljust(60) + "║")
    if category:
        console.print("║" + f"    Category: {category}".ljust(60) + "║")
    console.print("╚" + "═" * 60 + "╝")
    console.print()

    # Create models and runner
    synthesis_model = OllamaModel(model=model)
    judge = OllamaModel(model=judge_model)
    loader = LensLoader()

    runner = NaaruBenchmarkRunner(
        model=synthesis_model,
        judge_model=judge,
        lens_loader=loader,
        tasks_dir=tasks_dir,
        output_dir=output_dir,
        lens_dir=Path("lenses"),
    )

    # Run appropriate mode
    console.print("📊 Running Naaru benchmark...")
    console.print()

    if quick:
        results = await runner.run_quick(n_tasks=5)
    elif ablation:
        results = await runner.run_ablation(max_tasks=max_tasks or 10)
    else:
        results = await runner.run_suite(
            category=category,
            conditions=conditions,
            max_tasks=max_tasks,
        )

    console.print()
    console.print(f"✅ Completed {results.n_tasks} tasks across {len(results.conditions)} conditions")
    console.print()

    # Display summary
    _display_naaru_summary(results)

    # Save results
    results_dir = runner.save_results(results, output_dir)
    console.print()
    console.print(f"📁 Results saved to: {results_dir}")


def _display_naaru_summary(results) -> None:
    """Display Naaru benchmark summary."""

    table = Table(title="Naaru Benchmark Summary")
    table.add_column("Condition", style="cyan")
    table.add_column("Tasks", style="white")
    table.add_column("Avg Tokens", style="yellow")
    table.add_column("Avg Time (s)", style="green")
    table.add_column("Consensus", style="magenta")

    # Compute per-condition stats
    condition_data: dict = {}
    for condition in results.conditions:
        tokens_list: list[int] = []
        times_list: list[float] = []
        consensus_list: list[float] = []

        for task_result in results.results:
            output = task_result.outputs.get(condition)
            if output is None:
                continue

            tokens_list.append(output.tokens_used)
            times_list.append(output.time_seconds)

            if output.harmonic_metrics:
                consensus_list.append(output.harmonic_metrics.consensus_strength)

        if tokens_list:
            condition_data[condition] = {
                "n_tasks": len(tokens_list),
                "avg_tokens": sum(tokens_list) / len(tokens_list),
                "avg_time": sum(times_list) / len(times_list),
                "consensus": sum(consensus_list) / len(consensus_list) if consensus_list else None,
            }

    for condition, data in condition_data.items():
        consensus_str = f"{data['consensus']:.2f}" if data['consensus'] else "—"
        table.add_row(
            condition.value,
            str(data["n_tasks"]),
            f"{data['avg_tokens']:.0f}",
            f"{data['avg_time']:.2f}",
            consensus_str,
        )

    console.print(table)


@benchmark.command("naaru-report")
@click.argument(
    "results_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output file for markdown report",
)
def naaru_report(
    results_path: Path,
    output: Path | None,
) -> None:
    """Generate report from Naaru benchmark results.

    \b
    Example:
        sunwell benchmark naaru-report benchmark/results/naaru/2026-01-18/
    """

    # Load results
    config_path = results_path / "config.json"
    if not config_path.exists():
        console.print(f"[red]Error: {config_path} not found[/red]")
        return

    config = _load_statistics(config_path)
    if config is None:
        console.print("[red]Error: Could not parse config[/red]")
        return

    # Generate simple summary for now
    console.print()
    console.print("📊 Naaru Benchmark Results")
    console.print()
    console.print(f"  Model: {config.get('model', 'unknown')}")
    console.print(f"  Judge: {config.get('judge_model', 'unknown')}")
    console.print(f"  Tasks: {config.get('n_tasks', 0)}")
    console.print(f"  Conditions: {', '.join(config.get('conditions', []))}")

    # Load condition scores if available
    scores_path = results_path / "condition_scores.json"
    if scores_path.exists():
        scores = _load_statistics(scores_path)
        if scores:
            console.print()
            table = Table(title="Condition Statistics")
            table.add_column("Condition", style="cyan")
            table.add_column("Tasks", style="white")
            table.add_column("Avg Tokens", style="yellow")
            table.add_column("Refinement Rate", style="green")

            for cond, data in scores.items():
                ref_rate = data.get("refinement_rate")
                ref_str = f"{ref_rate:.1%}" if ref_rate is not None else "—"
                table.add_row(
                    cond,
                    str(data.get("n_tasks", 0)),
                    f"{data.get('mean_tokens', 0):.0f}",
                    ref_str,
                )

            console.print(table)

    if output:
        # Generate markdown report
        report_content = f"""# Naaru Benchmark Report

**Model**: {config.get('model', 'unknown')} (synthesis) / {config.get('judge_model', 'unknown')} (judge)
**Tasks**: {config.get('n_tasks', 0)}
**Conditions**: {', '.join(config.get('conditions', []))}

## Results

See `condition_scores.json` for detailed statistics.
"""
        output.write_text(report_content)
        console.print(f"\n📄 Report saved to: {output}")


# =============================================================================
# Planning Evaluation (RFC-043 prep)
# =============================================================================


@benchmark.command("plan-eval")
@click.argument(
    "task_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.argument(
    "plan_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Save evaluation results to JSON",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["human", "json"]),
    default="human",
    help="Output format",
)
def plan_eval(
    task_path: Path,
    plan_path: Path,
    output: Path | None,
    output_format: str,
) -> None:
    """Evaluate a plan against a benchmark task.

    Measures planning quality:
    - Coverage: Did the plan include required artifacts?
    - Coherence: Are dependencies correctly ordered?
    - Tech Alignment: Did it use the right tech stack?
    - Granularity: Right level of decomposition?
    - Speed: How fast was planning?

    \b
    Examples:
        sunwell benchmark plan-eval tasks/rfc043.yaml results/plan.json
        sunwell benchmark plan-eval tasks/rfc043.yaml plan.json -o eval.json
        sunwell benchmark plan-eval tasks/rfc043.yaml plan.json --format json
    """
    from sunwell.benchmark.planning.evaluator import PlanningEvaluator

    try:
        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        if output_format == "json":
            json_output = json.dumps(result.to_dict(), indent=2)
            if output:
                output.write_text(json_output)
                console.print(f"[green]Evaluation saved to: {output}[/green]")
            else:
                print(json_output)
        else:
            console.print(result.report())

            if output:
                output.write_text(json.dumps(result.to_dict(), indent=2))
                console.print(f"\n[dim]JSON saved to: {output}[/dim]")

    except Exception as e:
        console.print(f"[red]Evaluation failed: {e}[/red]")
        raise SystemExit(1) from e


@benchmark.command("plan-compare")
@click.argument(
    "task_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.argument(
    "plans",
    type=click.Path(exists=True, path_type=Path),
    nargs=-1,
    required=True,
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Save comparison to JSON",
)
def plan_compare(
    task_path: Path,
    plans: tuple[Path, ...],
    output: Path | None,
) -> None:
    """Compare multiple plans against the same task.

    Useful for comparing:
    - Sunwell planner vs baseline model
    - Different model sizes
    - Different planning strategies

    \b
    Examples:
        sunwell benchmark plan-compare tasks/rfc043.yaml sunwell.json baseline.json
        sunwell benchmark plan-compare tasks/rfc043.yaml *.json -o comparison.json
    """
    from sunwell.benchmark.planning.evaluator import PlanningEvaluator

    evaluator = PlanningEvaluator.from_task(task_path)

    results = []
    for plan_path in plans:
        try:
            result = evaluator.evaluate(plan_path)
            results.append({
                "plan": str(plan_path),
                "scores": result.to_dict()["scores"],
            })
        except Exception as e:
            results.append({
                "plan": str(plan_path),
                "error": str(e),
            })

    # Display comparison table
    table = Table(title=f"Plan Comparison: {task_path.name}")
    table.add_column("Plan", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Coherence", justify="right")
    table.add_column("Tech", justify="right")
    table.add_column("Granularity", justify="right")
    table.add_column("Speed", justify="right")
    table.add_column("TOTAL", justify="right", style="bold")

    for r in results:
        if "error" in r:
            table.add_row(
                Path(r["plan"]).name,
                "[red]ERROR[/red]", "", "", "", "",
                f"[red]{r['error'][:20]}[/red]",
            )
        else:
            scores = r["scores"]
            table.add_row(
                Path(r["plan"]).name,
                f"{scores['coverage']:.0f}",
                f"{scores['coherence']:.0f}",
                f"{scores['tech_alignment']:.0f}",
                f"{scores['granularity']:.0f}",
                f"{scores['speed']:.0f}",
                f"{scores['total']:.1f}",
            )

    console.print(table)

    if output:
        output.write_text(json.dumps(results, indent=2))
        console.print(f"\n[dim]Comparison saved to: {output}[/dim]")


# =============================================================================
# Journey E2E Testing (Behavioral Testing Framework)
# =============================================================================


@benchmark.command("journeys")
@click.option(
    "--journey",
    "journey_id",
    help="Run a single journey by ID",
)
@click.option(
    "--category",
    type=click.Choice(["single-turn", "multi-turn"]),
    help="Run only journeys in this category",
)
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Filter by tag (can specify multiple)",
)
@click.option(
    "--journeys-dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path("benchmark/journeys"),
    help="Directory containing journey YAML files",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file for JSON results",
)
@click.option(
    "--model",
    default=None,
    help="Model to use (default: from config)",
)
@click.option(
    "--provider",
    type=click.Choice(["ollama", "openai", "anthropic"]),
    default="ollama",
    help="Model provider",
)
@click.option(
    "--trust",
    type=click.Choice(["read_only", "workspace", "shell"]),
    default="shell",
    help="Tool trust level",
)
@click.option(
    "--parallel",
    is_flag=True,
    help="Run journeys in parallel",
)
@click.option(
    "--max-concurrent",
    type=int,
    default=4,
    help="Maximum concurrent journeys (with --parallel)",
)
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Don't cleanup workspace after run (for debugging)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
def journeys(
    journey_id: str | None,
    category: str | None,
    tags: tuple[str, ...],
    journeys_dir: Path,
    output: Path | None,
    model: str | None,
    provider: str,
    trust: str,
    parallel: bool,
    max_concurrent: int,
    no_cleanup: bool,
    verbose: bool,
) -> None:
    """Run E2E behavioral test journeys.

    Journeys test observable outcomes (intent, tools, state) rather than
    exact text outputs. Supports single-turn and multi-turn conversations.

    \b
    Examples:
        # Run all journeys
        sunwell benchmark journeys

        # Run specific journey
        sunwell benchmark journeys --journey create-app

        # Run category
        sunwell benchmark journeys --category single-turn

        # Run journeys with specific tag
        sunwell benchmark journeys --tag agentic

        # Output JSON report
        sunwell benchmark journeys --output report.json

        # Debug mode (no cleanup)
        sunwell benchmark journeys --journey debug-session --no-cleanup -v
    """
    asyncio.run(_run_journeys(
        journey_id=journey_id,
        category=category,
        tags=tags,
        journeys_dir=journeys_dir,
        output=output,
        model=model,
        provider=provider,
        trust=trust,
        parallel=parallel,
        max_concurrent=max_concurrent,
        cleanup=not no_cleanup,
        verbose=verbose,
    ))


async def _run_journeys(
    journey_id: str | None,
    category: str | None,
    tags: tuple[str, ...],
    journeys_dir: Path,
    output: Path | None,
    model: str | None,
    provider: str,
    trust: str,
    parallel: bool,
    max_concurrent: int,
    cleanup: bool,
    verbose: bool,
) -> None:
    """Async journey execution."""
    from rich.live import Live
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    from sunwell.benchmark.journeys import (
        JourneyRunner,
        load_journey,
        load_journeys_from_directory,
    )
    from sunwell.benchmark.journeys.runner import JourneyResult
    from sunwell.benchmark.journeys.types import Journey
    from sunwell.foundation.config import get_config

    # Resolve actual model being used
    cfg = get_config()
    resolved_model = model or (cfg.model.default_model if cfg else "llama3.1:8b")

    # Banner - always show resolved model
    console.print()
    console.print("╔" + "═" * 60 + "╗")
    console.print("║" + " 🧪 E2E BEHAVIORAL TESTING".ljust(60) + "║")
    if journey_id:
        console.print("║" + f"    Journey: {journey_id}".ljust(60) + "║")
    if category:
        console.print("║" + f"    Category: {category}".ljust(60) + "║")
    if tags:
        console.print("║" + f"    Tags: {', '.join(tags)}".ljust(60) + "║")
    console.print("║" + f"    Provider: {provider}".ljust(60) + "║")
    console.print("║" + f"    Model: {resolved_model}".ljust(60) + "║")
    console.print("╚" + "═" * 60 + "╝")
    console.print()

    # Load journeys
    journeys_to_run: list[Journey] = []

    if journey_id:
        # Load specific journey
        patterns = [
            journeys_dir / f"**/{journey_id}.yaml",
            journeys_dir / f"**/{journey_id}.yml",
        ]
        found = False
        for pattern in patterns:
            for path in journeys_dir.glob(f"**/{journey_id}.yaml"):
                journeys_to_run.append(load_journey(path))
                found = True
                break
            if found:
                break

        if not found:
            console.print(f"[red]Journey not found: {journey_id}[/red]")
            return
    else:
        # Load from directory
        search_dir = journeys_dir
        if category:
            search_dir = journeys_dir / category

        journeys_to_run = load_journeys_from_directory(search_dir)

    # Filter by tags
    if tags:
        journeys_to_run = [
            j for j in journeys_to_run
            if any(t in j.tags for t in tags)
        ]

    if not journeys_to_run:
        console.print("[yellow]No journeys found matching criteria[/yellow]")
        return

    console.print(f"📋 Running {len(journeys_to_run)} journey(s)")
    console.print()

    # Suppress noisy logging during benchmark runs (unless verbose)
    import logging
    if not verbose:
        # Quiet the agent/tools logs (budget warnings, blocked tools, etc.)
        # Use parent logger to catch all child loggers
        logging.getLogger("sunwell.agent").setLevel(logging.ERROR)
        logging.getLogger("sunwell.tools").setLevel(logging.ERROR)
        logging.getLogger("sunwell.models").setLevel(logging.ERROR)

    # Create runner
    runner = JourneyRunner(
        provider=provider,
        model_name=resolved_model,
        trust_level=trust,
        cleanup_workspace=cleanup,
        debug=verbose,
    )

    # Track results and real-time status
    results: list[JourneyResult] = []
    passed_count = 0
    failed_count = 0

    # Progress display with real-time updates
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("[green]{task.fields[passed]}✓[/green]"),
        TextColumn("[red]{task.fields[failed]}✗[/red]"),
        TimeElapsedColumn(),
        console=console,
        transient=not verbose,  # Keep visible in verbose mode
    )

    with progress:
        task_id = progress.add_task(
            "Running journeys",
            total=len(journeys_to_run),
            passed=0,
            failed=0,
        )

        if parallel:
            # Parallel execution with semaphore
            import asyncio
            semaphore = asyncio.Semaphore(max_concurrent)

            async def run_with_tracking(journey: Journey) -> JourneyResult:
                nonlocal passed_count, failed_count
                async with semaphore:
                    result = await runner.run(journey)
                    if result.passed:
                        passed_count += 1
                    else:
                        failed_count += 1
                    progress.update(
                        task_id,
                        advance=1,
                        passed=passed_count,
                        failed=failed_count,
                    )
                    # Print immediate result in verbose mode
                    if verbose:
                        status = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
                        progress.console.print(
                            f"  {status} {journey.id} ({result.duration_ms}ms)"
                        )
                    return result

            results = await asyncio.gather(*[run_with_tracking(j) for j in journeys_to_run])
        else:
            # Sequential execution
            for journey in journeys_to_run:
                # Update description to show current journey
                progress.update(
                    task_id,
                    description=f"[cyan]{journey.id}[/cyan]",
                )

                result = await runner.run(journey)
                results.append(result)

                if result.passed:
                    passed_count += 1
                else:
                    failed_count += 1

                progress.update(
                    task_id,
                    advance=1,
                    passed=passed_count,
                    failed=failed_count,
                )

                # Print immediate result
                if verbose:
                    status = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
                    progress.console.print(
                        f"  {status} {journey.id} ({result.duration_ms}ms)"
                    )
                elif not result.passed:
                    # Always show failures even in non-verbose mode
                    progress.console.print(
                        f"  [red]✗ {journey.id}[/red]: {result.error or 'assertions failed'}"
                    )

    console.print()

    # Display results
    _display_journey_results(results, verbose)

    # Save JSON output
    if output:
        import json
        report = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "results": [
                {
                    "journey_id": r.journey_id,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                    "intent_match": r.intent_match,
                    "signals_match": r.signals_match,
                    "tools_match": r.tools_match,
                    "state_match": r.state_match,
                    "output_match": r.output_match,
                    "assertions": r.assertion_report.summary(),
                }
                for r in results
            ],
        }
        output.write_text(json.dumps(report, indent=2))
        console.print(f"\n📄 Results saved to: {output}")


def _display_journey_results(results: list, verbose: bool) -> None:
    """Display journey results."""
    from sunwell.benchmark.journeys.runner import JourneyResult

    # Summary table
    table = Table(title="Journey Results")
    table.add_column("Journey", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Intent", justify="center")
    table.add_column("Signals", justify="center")
    table.add_column("Tools", justify="center")
    table.add_column("State", justify="center")
    table.add_column("Output", justify="center")
    table.add_column("Time", justify="right")

    for result in results:
        status = "[green]✓ PASS[/green]" if result.passed else "[red]✗ FAIL[/red]"

        def check(val: bool) -> str:
            return "[green]✓[/green]" if val else "[red]✗[/red]"

        table.add_row(
            result.journey_id,
            status,
            check(result.intent_match),
            check(result.signals_match),
            check(result.tools_match),
            check(result.state_match),
            check(result.output_match),
            f"{result.duration_ms}ms",
        )

    console.print(table)

    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    console.print()
    if failed == 0:
        console.print(f"[green]✅ All {passed} journey(s) passed![/green]")
    else:
        console.print(f"[red]❌ {failed}/{len(results)} journey(s) failed[/red]")

    # Show failures (always show brief, verbose shows full detail)
    failed_results = [r for r in results if not r.passed]
    if failed_results:
        console.print()
        console.print("[bold]Failures:[/bold]")

        for result in failed_results:
            console.print(f"\n[red]── {result.journey_id} ──[/red]")

            if result.error:
                console.print(f"  [red]Error:[/red] {result.error}")

            # Show assertion failures
            failures = result.assertion_report.failures()
            if failures:
                for failure in failures[:5]:  # Limit to first 5
                    console.print(f"  [red]✗[/red] [{failure.category}] {failure.message}")
                if len(failures) > 5:
                    console.print(f"  ... and {len(failures) - 5} more")

            # Show tool call info if tools didn't match
            if not result.tools_match and verbose:
                tool_calls = [
                    e.data.get("tool_name", e.data.get("tool", "?"))
                    for e in result.events
                    if hasattr(e, "data") and e.data and "tool" in str(e.data)
                ]
                if tool_calls:
                    console.print(f"  [dim]Tools called: {', '.join(tool_calls[:10])}[/dim]")


# Export for CLI integration
def register_benchmark_commands(cli: click.Group) -> None:
    """Register benchmark commands with main CLI."""
    cli.add_command(benchmark)
