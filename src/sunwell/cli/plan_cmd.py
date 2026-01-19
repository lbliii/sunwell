"""Plan command for DAG visualization and export (RFC-043 prep).

Provides a dedicated command for planning without execution:
- Read goals from files (RFCs, specs, etc.)
- Output in multiple formats (human, json, mermaid)
- Save plans for later evaluation

Example:
    sunwell plan "Build a forum app"
    sunwell plan --file docs/RFC-043.md
    sunwell plan "Build app" --output plan.json --format json
    sunwell plan --file RFC.md --output plan.json
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


@click.command()
@click.argument("goal", required=False)
@click.option(
    "--file", "-f",
    "input_file",
    type=click.Path(exists=True),
    help="Read goal/context from file (markdown, txt)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Save plan to file (json format)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["human", "json", "mermaid", "tree"]),
    default="human",
    help="Output format (default: human)",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override model selection",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output including dependencies",
)
@click.option(
    "--extract-goal",
    is_flag=True,
    help="Extract goal from file's Summary section (for RFCs)",
)
def plan(
    goal: str | None,
    input_file: str | None,
    output: str | None,
    output_format: str,
    model: str | None,
    verbose: bool,
    extract_goal: bool,
) -> None:
    """Generate and visualize an execution plan (DAG).

    Create a plan without executing it. Useful for:
    - Reviewing what Sunwell would do before running
    - Saving plans for evaluation and comparison
    - Visualizing task dependencies

    \b
    Examples:
        sunwell plan "Build a REST API"
        sunwell plan --file docs/RFC-043.md
        sunwell plan "Build app" -o plan.json
        sunwell plan --file RFC.md --format mermaid
        sunwell plan --file RFC.md --extract-goal

    \b
    Output formats:
        human   - Rich terminal output with tables and waves (default)
        json    - Machine-readable JSON (implies --output if not set)
        mermaid - Mermaid diagram syntax
        tree    - ASCII dependency tree
    """
    # Resolve goal from arguments or file
    final_goal = _resolve_goal(goal, input_file, extract_goal)
    if not final_goal:
        console.print("[red]Error: Provide a goal or use --file[/red]")
        raise SystemExit(1)

    # If format is json and no output specified, default to stdout json
    if output_format == "json" and not output:
        output = "-"  # stdout marker

    asyncio.run(_plan_async(
        goal=final_goal,
        input_file=input_file,
        output_path=output,
        output_format=output_format,
        model_override=model,
        verbose=verbose,
    ))


def _resolve_goal(
    goal: str | None,
    input_file: str | None,
    extract_goal: bool,
) -> str | None:
    """Resolve the goal from arguments or file."""
    if goal:
        return goal

    if not input_file:
        return None

    path = Path(input_file)
    content = path.read_text()

    if extract_goal:
        # Try to extract goal from RFC Summary section
        extracted = _extract_goal_from_rfc(content)
        if extracted:
            return extracted

    # Use the file content as context, create a meta-goal
    # Truncate if too long (first ~2000 chars)
    if len(content) > 2000:
        content = content[:2000] + "\n\n[...truncated...]"

    return f"Implement the following specification:\n\n{content}"


def _extract_goal_from_rfc(content: str) -> str | None:
    """Extract goal from RFC Summary section."""
    # Look for ## Summary section
    summary_match = re.search(
        r"##\s*Summary\s*\n+(.*?)(?=\n##|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if summary_match:
        summary = summary_match.group(1).strip()
        # Take first paragraph
        first_para = summary.split("\n\n")[0].strip()
        if first_para:
            return f"Implement: {first_para}"

    # Fallback: use title
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        return f"Implement {title_match.group(1)}"

    return None


async def _plan_async(
    goal: str,
    input_file: str | None,
    output_path: str | None,
    output_format: str,
    model_override: str | None,
    verbose: bool,
) -> None:
    """Generate and display/save the plan."""
    from sunwell.config import get_config
    from sunwell.naaru import get_model_distribution
    from sunwell.naaru.planners import ExpertiseAwareArtifactPlanner
    from sunwell.routing import UnifiedRouter

    # Load model
    config = get_config()
    model = None

    try:
        from sunwell.models.ollama import OllamaModel

        model_name = model_override
        if not model_name and config and hasattr(config, "naaru"):
            model_name = getattr(config.naaru, "wisdom", "gemma3:4b")
        if not model_name:
            model_name = "gemma3:4b"

        model = OllamaModel(model=model_name)
        if output_format == "human":
            console.print(f"[dim]Using model: {model_name}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to load model: {e}[/red]")
        raise SystemExit(1)

    # Create planner
    router = None
    try:
        router = UnifiedRouter(model=model)
    except Exception:
        pass

    planner = ExpertiseAwareArtifactPlanner(
        model=model,
        router=router,
        enable_expertise=True,
    )

    # Generate plan
    if output_format == "human":
        console.print("[yellow]Planning...[/yellow]\n")

    try:
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Planning failed: {e}[/red]")
        raise SystemExit(1)

    waves = graph.execution_waves()
    dist = get_model_distribution(graph)

    # Build plan data structure
    plan_data = _build_plan_data(
        goal=goal,
        input_file=input_file,
        graph=graph,
        waves=waves,
        dist=dist,
        planner=planner,
    )

    # Output based on format
    if output_format == "human":
        _output_human(plan_data, graph, waves, dist, verbose)
    elif output_format == "json":
        _output_json(plan_data, output_path)
    elif output_format == "mermaid":
        _output_mermaid(graph, output_path)
    elif output_format == "tree":
        _output_tree(plan_data, graph, waves)

    # Save to file if specified (and not json which handles its own output)
    if output_path and output_path != "-" and output_format != "json":
        # Also save json for programmatic access
        json_path = Path(output_path).with_suffix(".json")
        _output_json(plan_data, str(json_path))
        console.print(f"\n[dim]Plan saved to: {json_path}[/dim]")


def _build_plan_data(
    goal: str,
    input_file: str | None,
    graph,
    waves: list,
    dist: dict,
    planner,
) -> dict:
    """Build structured plan data."""
    artifacts = []
    for wave_num, wave in enumerate(waves, 1):
        for artifact_id in wave:
            artifact = graph[artifact_id]
            artifacts.append({
                "id": artifact_id,
                "description": artifact.description,
                "domain_type": artifact.domain_type,
                "produces_file": artifact.produces_file,
                "requires": list(artifact.requires) if artifact.requires else [],
                "wave": wave_num,
            })

    expertise = {}
    if hasattr(planner, "get_expertise_summary"):
        expertise = planner.get_expertise_summary()

    return {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "goal": goal,
        "source_file": input_file,
        "expertise": expertise,
        "statistics": {
            "total_artifacts": len(artifacts),
            "total_waves": len(waves),
            "parallelization": len(artifacts) / len(waves) if waves else 0,
            "model_distribution": dist,
        },
        "waves": [
            {
                "wave": i + 1,
                "artifacts": [aid for aid in wave],
            }
            for i, wave in enumerate(waves)
        ],
        "artifacts": artifacts,
    }


def _output_human(
    plan_data: dict,
    graph,
    waves: list,
    dist: dict,
    verbose: bool,
) -> None:
    """Output human-readable format."""
    goal = plan_data["goal"]
    if len(goal) > 100:
        goal = goal[:100] + "..."

    console.print(Panel(goal, title="[bold]Plan", border_style="blue"))

    # Expertise info
    expertise = plan_data.get("expertise", {})
    if expertise.get("loaded"):
        console.print(f"\n[cyan]Expertise:[/cyan] {expertise.get('domain', 'unknown')} domain")

    # Artifact table
    table = Table(title="\nArtifacts", show_header=True, header_style="bold")
    table.add_column("Wave", style="cyan", width=5)
    table.add_column("ID", style="green")
    table.add_column("Description")
    table.add_column("File", style="magenta")

    for artifact in plan_data["artifacts"]:
        desc = artifact["description"]
        if len(desc) > 50:
            desc = desc[:47] + "..."
        table.add_row(
            str(artifact["wave"]),
            artifact["id"],
            desc,
            artifact["produces_file"] or "-",
        )

    console.print(table)

    # Execution waves
    console.print("\n[bold]Execution Order:[/bold]")
    for wave_data in plan_data["waves"]:
        wave_num = wave_data["wave"]
        aids = wave_data["artifacts"]
        prefix = "⚡" if wave_num == 1 else "→"
        console.print(f"  {prefix} Wave {wave_num}: {', '.join(aids)}")

    # Statistics
    stats = plan_data["statistics"]
    console.print("\n[bold]Statistics:[/bold]")
    console.print(f"  Artifacts: {stats['total_artifacts']}")
    console.print(f"  Waves: {stats['total_waves']}")
    console.print(f"  Parallelization: {stats['parallelization']:.1f}x")
    console.print(f"  Model mix: {stats['model_distribution']}")

    # Mermaid diagram (verbose only)
    if verbose:
        console.print("\n[bold]Dependency Graph:[/bold]")
        console.print("```mermaid")
        console.print(graph.to_mermaid())
        console.print("```")


def _output_json(plan_data: dict, output_path: str | None) -> None:
    """Output JSON format."""
    json_str = json.dumps(plan_data, indent=2)

    if output_path == "-" or output_path is None:
        print(json_str)
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str)
        console.print(f"[green]Plan saved to: {path}[/green]")


def _output_mermaid(graph, output_path: str | None) -> None:
    """Output Mermaid diagram."""
    mermaid = graph.to_mermaid()

    if output_path == "-" or output_path is None:
        print(mermaid)
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mermaid)
        console.print(f"[green]Mermaid diagram saved to: {path}[/green]")


def _output_tree(plan_data: dict, graph, waves: list) -> None:
    """Output ASCII tree format."""
    tree = Tree(f"[bold blue]Plan: {plan_data['goal'][:60]}...[/bold blue]")

    for wave_data in plan_data["waves"]:
        wave_num = wave_data["wave"]
        wave_branch = tree.add(f"[yellow]Wave {wave_num}[/yellow]")

        for artifact_id in wave_data["artifacts"]:
            artifact = graph[artifact_id]
            desc = artifact.description[:40]
            file_info = f" → {artifact.produces_file}" if artifact.produces_file else ""
            wave_branch.add(f"[green]{artifact_id}[/green]: {desc}{file_info}")

    console.print(tree)
