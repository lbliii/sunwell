"""Benchmark command for agent CLI."""


import asyncio
from pathlib import Path

import click
from rich.console import Console

from sunwell.foundation.utils import safe_json_dumps

console = Console()


@click.command(name="benchmark")
@click.option(
    "--tasks-dir", "-d",
    default="benchmark/tasks/agent",
    help="Directory containing agent benchmark tasks",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Evaluate planning only (no execution)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Directory to save results",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def agent_benchmark(tasks_dir: str, dry_run: bool, output: str | None, verbose: bool) -> None:
    """Run agent mode benchmarks (RFC-032).

    Tests planning quality, task decomposition, and execution accuracy.

    Examples:

    \b
        sunwell agent benchmark
        sunwell agent benchmark --dry-run
        sunwell agent benchmark -o benchmark/results/agent/
    """
    asyncio.run(_benchmark_async(tasks_dir, dry_run, output, verbose))


async def _benchmark_async(
    tasks_dir: str,
    dry_run: bool,
    output: str | None,
    verbose: bool,
) -> None:
    """Async implementation of benchmark command."""

    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        console.print(f"[red]Error: Tasks directory not found: {tasks_dir}[/red]")
        return

    task_files = list(tasks_path.glob("*.yaml"))
    if not task_files:
        console.print(f"[yellow]No benchmark tasks found in {tasks_dir}[/yellow]")
        return

    console.print("[bold]Agent Benchmark Suite[/bold]")
    console.print(f"  Mode: {'Planning Only' if dry_run else 'Full Execution'}")
    console.print(f"  Tasks: {len(task_files)} found\n")

    # Load model
    try:
        from sunwell.foundation.config import get_config
        from sunwell.models.ollama import OllamaModel

        config = get_config()

        if config and hasattr(config, "naaru"):
            model_name = getattr(config.naaru, "wisdom", "gemma3:4b")
        else:
            model_name = "gemma3:4b"

        model = OllamaModel(model=model_name)
        console.print(f"[dim]Using model: {model_name}[/dim]\n")
    except Exception as e:
        console.print(f"[red]Error loading model: {e}[/red]")
        return

    # Run benchmarks
    try:
        from sunwell.benchmark.agent_runner import AgentBenchmarkRunner

        runner = AgentBenchmarkRunner(
            model=model,
            dry_run=dry_run,
        )

        results = await runner.run_all(
            tasks_dir=tasks_dir,
            on_progress=console.print if verbose else None,
        )

        # Summary
        summary = runner.summarize(results)

        console.print("\n[bold]═══ Summary ═══[/bold]")
        console.print(f"  Total: {summary['total_tasks']} tasks")
        console.print(f"  Passed: {summary['successful_tasks']}")
        console.print(f"  Failed: {summary['failed_tasks']}")
        console.print(f"  Average Score: [bold]{summary['average_score']:.2f}[/bold]")

        if summary.get("by_category"):
            console.print("\n[bold]By Category:[/bold]")
            for cat, score in summary["by_category"].items():
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                console.print(f"  {cat:15} {bar} {score:.2f}")

        # Save results
        if output:
            output_path = Path(output)
            output_path.mkdir(parents=True, exist_ok=True)

            import json
            from datetime import datetime

            results_file = output_path / f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            with open(results_file, "w") as f:
                json.dump({
                    "summary": summary,
                    "results": [r.to_dict() for r in results],
                }, f, indent=2)

            console.print(f"\n[dim]Results saved to: {results_file}[/dim]")

    except Exception as e:
        console.print(f"\n[red]Benchmark error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


# =============================================================================
# Helper: Extract Learnings from Execution Result (RFC-054)
# =============================================================================


async def _extract_learnings_from_result(
    result,
    graph,
    emit: callable | None = None,
) -> int:
    """Extract learnings from execution result and persist to .sunwell/intelligence/.

    Args:
        result: ExecutionResult from incremental executor
        graph: ArtifactGraph for context
        emit: Optional event emitter for JSON mode

    Returns:
        Number of learnings extracted
    """
    import json
    import uuid
    from datetime import datetime

    try:
        from sunwell.memory.simulacrum.extractors.extractor import auto_extract_learnings
    except ImportError:
        # Learning extractor not available
        return 0

    learnings = []

    # Extract learnings from completed artifacts
    for artifact_id in result.completed:
        artifact = graph.get(artifact_id)
        if not artifact:
            continue

        # Get content from artifact result
        # ExecutionResult.completed maps artifact_id -> ArtifactResult which has .content
        content = ""
        artifact_result = result.completed.get(artifact_id)
        if artifact_result and artifact_result.content:
            content = artifact_result.content
        elif artifact.description:
            content = artifact.description

        if not content:
            continue

        try:
            extracted = auto_extract_learnings(content, min_confidence=0.6)
            for fact, category, confidence in extracted[:3]:  # Max 3 per artifact
                learning = {
                    "id": f"learn-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
                    "fact": fact,
                    "category": category,
                    "confidence": confidence,
                    "source_file": artifact_id,
                    "created_at": datetime.now().isoformat(),
                }
                learnings.append(learning)

                # Emit memory_learning event for real-time updates
                if emit:
                    emit("memory_learning", {
                        "fact": fact,
                        "category": category,
                        "confidence": confidence,
                        "source": artifact_id,
                    })
        except Exception:
            # Learning extraction failed for this artifact
            continue

    # Persist learnings to .sunwell/intelligence/learnings.jsonl
    if learnings:
        intel_path = Path.cwd() / ".sunwell" / "intelligence"
        intel_path.mkdir(parents=True, exist_ok=True)

        learnings_file = intel_path / "learnings.jsonl"
        with open(learnings_file, "a") as f:
            for learning in learnings:
                f.write(safe_json_dumps(learning) + "\n")

    return len(learnings)
