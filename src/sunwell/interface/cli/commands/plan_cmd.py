"""Plan command for DAG visualization and export (RFC-043 prep, RFC-120 versioning).

Provides a dedicated command for planning without execution:
- Read goals from files (RFCs, specs, etc.)
- Output in multiple formats (human, json, mermaid)
- Save plans for later evaluation
- View plan history and diffs (RFC-120)

Example:
    sunwell plan "Build a forum app"
    sunwell plan --file docs/RFC-043.md
    sunwell plan "Build app" --output plan.json --format json
    sunwell plan --file RFC.md --output plan.json
    sunwell plan history abc123
    sunwell plan diff abc123 1 2
"""


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


# Pre-compiled regex patterns (avoid per-call compilation)
_RE_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_RE_SUMMARY = re.compile(r"##\s*Summary\s*\n+(.*?)(?=\n##|\Z)", re.IGNORECASE | re.DOTALL)

console = Console()


# =============================================================================
# Plan Group
# =============================================================================


@click.group(invoke_without_command=True)
@click.pass_context
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
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output including dependencies",
)
@click.option(
    "--extract-goal",
    is_flag=True,
    help="Extract goal from file's Summary section (for RFCs)",
)
@click.option(
    "--digest",
    is_flag=True,
    help="Use Simulacrum to fully digest the file (no truncation)",
)
@click.option(
    "--compound",
    is_flag=True,
    help="Use Compound Eye to extract requirements from multiple perspectives",
)
@click.option(
    "--squash",
    is_flag=True,
    help="Use squash extraction (3x per question, keep only agreement)",
)
def plan(
    ctx: click.Context,
    goal: str | None,
    input_file: str | None,
    output: str | None,
    output_format: str,
    provider: str | None,
    model: str | None,
    verbose: bool,
    extract_goal: bool,
    digest: bool,
    compound: bool,
    squash: bool,
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
    Subcommands:
        history - View plan version history
        diff    - Compare two plan versions
        show    - Show specific version details

    \b
    Output formats:
        human   - Rich terminal output with tables and waves (default)
        json    - Machine-readable JSON (implies --output if not set)
        mermaid - Mermaid diagram syntax
        tree    - ASCII dependency tree
    """
    # If a subcommand is invoked, don't run the default plan generation
    if ctx.invoked_subcommand is not None:
        return
    # Resolve goal from arguments or file
    if squash and input_file:
        # Use squash extraction (best for avoiding hallucination)
        final_goal = asyncio.run(_squash_extract(input_file, provider, model, verbose))
    elif digest and input_file:
        # Use Simulacrum to fully digest the document
        final_goal = asyncio.run(_digest_document(input_file, provider, model, verbose))
    elif compound and input_file:
        # Use Compound Eye to extract requirements
        final_goal = asyncio.run(_compound_extract(input_file, provider, model, verbose))
    else:
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
        provider_override=provider,
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

    # For full file, extract key sections intelligently
    # Don't truncate - use structured extraction
    key_sections = _extract_key_sections(content)

    return f"Implement the following specification:\n\n{key_sections}"


def _extract_key_sections(content: str) -> str:
    """Extract key sections from a document for planning context.
    
    Instead of truncating, intelligently extract:
    - Summary/Overview
    - Goals/Non-Goals  
    - Technical Architecture
    - Implementation Plan
    - Requirements (from headers)
    """
    sections = []

    # Priority sections to extract (in order)
    priority_headers = [
        r"##?\s*summary",
        r"##?\s*overview",
        r"##?\s*goals",
        r"##?\s*non-goals",
        r"##?\s*requirements",
        r"##?\s*technical\s*architecture",
        r"##?\s*stack",
        r"##?\s*implementation\s*plan",
        r"##?\s*phase\s*1",
    ]

    for pattern in priority_headers:
        match = re.search(
            rf"({pattern})\s*\n+(.*?)(?=\n##|\n---|\Z)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            header = match.group(1).strip()
            body = match.group(2).strip()
            # Limit each section to ~500 chars to stay reasonable
            if len(body) > 500:
                body = body[:500] + "..."
            sections.append(f"{header}\n{body}")

    if sections:
        return "\n\n".join(sections)

    # Fallback: title + first 1000 chars
    title_match = _RE_TITLE.search(content)
    title = title_match.group(1) if title_match else "Specification"

    preview = content[:1000]
    if len(content) > 1000:
        preview += f"\n\n[...{len(content) - 1000} more characters...]"

    return f"# {title}\n\n{preview}"


def _extract_goal_from_rfc(content: str) -> str | None:
    """Extract goal from RFC Summary section."""
    # Look for ## Summary section (pre-compiled pattern)
    summary_match = _RE_SUMMARY.search(content)
    if summary_match:
        summary = summary_match.group(1).strip()
        # Take first paragraph
        first_para = summary.split("\n\n")[0].strip()
        if first_para:
            return f"Implement: {first_para}"

    # Fallback: use title (pre-compiled pattern)
    title_match = _RE_TITLE.search(content)
    if title_match:
        return f"Implement {title_match.group(1)}"

    return None


async def _squash_extract(
    input_file: str,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> str:
    """Use squash extraction to get grounded facts from document.
    
    This extracts each question 3x and only keeps what all extractors agree on.
    Much more reliable than single-shot extraction.
    """
    from sunwell.interface.cli.helpers import resolve_model

    path = Path(input_file)
    content = path.read_text()

    if verbose:
        console.print(f"[dim]Squash extracting from {len(content):,} chars (3x per question)...[/dim]")

    # Load model using resolve_model()
    model = None
    try:
        model = resolve_model(provider_override, model_override)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load model for squash: {e}[/yellow]")
        return f"Implement the following specification:\n\n{_extract_key_sections(content)}"

    # Run section-aware squash extraction (finds relevant sections first)
    from sunwell.knowledge.extraction.squash import section_aware_extract

    result = await section_aware_extract(
        document=content,
        model=model,
        n_extractions=2,  # 2x per section is enough with targeted extraction
    )

    if verbose:
        console.print("\n[cyan]Squash Extraction Results:[/cyan]")
        console.print(f"  Agreement rate: {result.agreement_rate:.0%}")
        console.print(f"  Confident facts: {len(result.confident_facts)}")
        console.print(f"  Uncertain facts: {len(result.uncertain_facts)}")

        if result.confident_facts:
            console.print("\n[green]✓ Confident (agreement >= 60%):[/green]")
            for fact in result.confident_facts:
                console.print(f"  • {fact.source_question}")
                console.print(f"    → {fact.content[:100]}...")

        if result.uncertain_facts:
            console.print("\n[yellow]? Uncertain (low agreement):[/yellow]")
            for fact in result.uncertain_facts:
                console.print(f"  • {fact.source_question}: {fact.confidence:.0%} agreement")

    if verbose:
        console.print(f"\n[cyan]Synthesized goal ({len(result.synthesized_goal)} chars)[/cyan]")

    return f"Implement the following specification:\n\n{result.synthesized_goal}"


async def _digest_document(
    input_file: str,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> str:
    """Use Simulacrum to fully digest a document.
    
    This ingests the document into memory, then queries for:
    - Summary/overview
    - Technical requirements
    - Key constraints
    - Implementation guidance
    
    No truncation - the full document is available via semantic retrieval.
    """
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    path = Path(input_file)
    content = path.read_text()

    if verbose:
        console.print(f"[dim]Digesting {len(content):,} characters via Simulacrum...[/dim]")

    # Create a temporary simulacrum for this document
    store = SimulacrumStore(base_path=Path(".sunwell/plan_digest"))

    # Ingest the full document
    await store.ingest_document(
        file_path=str(path),
        content=content,
        extract_facets=True,
        extract_topology=True,
    )

    # Query for planning-relevant information
    queries = [
        "What is the main goal and purpose?",
        "What are the technical requirements and stack?",
        "What are the key constraints and non-goals?",
        "What is the implementation plan or phases?",
    ]

    extracted_parts = []
    for query in queries:
        results = await store.semantic_search(query, limit=3)
        if results:
            extracted_parts.append(f"### {query}\n" + "\n".join(r.content for r in results))

    if extracted_parts:
        return "Implement the following specification:\n\n" + "\n\n".join(extracted_parts)

    # Fallback if semantic search not available
    return f"Implement the following specification:\n\n{_extract_key_sections(content)}"


async def _compound_extract(
    input_file: str,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> str:
    """Use Compound Eye to extract requirements from multiple perspectives.
    
    Runs the document through multiple "lenses":
    - Product lens: What are we building?
    - Tech lens: What stack/architecture?
    - UX lens: What's the user experience?
    - Constraints lens: What are the boundaries?
    
    Synthesizes into a comprehensive goal.
    """
    from sunwell.interface.cli.helpers import resolve_model

    path = Path(input_file)
    content = path.read_text()

    if verbose:
        console.print(f"[dim]Analyzing {len(content):,} chars via Compound Eye...[/dim]")

    # Load model using resolve_model()
    model = None
    try:
        model = resolve_model(provider_override, model_override)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load model for Compound Eye: {e}[/yellow]")
        return f"Implement the following specification:\n\n{_extract_key_sections(content)}"

    # Define perspectives for extraction
    perspectives = [
        ("product", "What product/feature is being built? Summarize in 2-3 sentences."),
        ("tech_stack", "What technology stack is specified? List frameworks, languages, tools."),
        ("ux_requirements", "What are the UX/UI requirements? List key screens and interactions."),
        ("constraints", "What are the constraints, non-goals, or things explicitly excluded?"),
        ("phases", "What implementation phases or milestones are defined?"),
    ]

    # Run document through each perspective
    from sunwell.models.protocol import GenerateOptions

    extracted = {}
    for name, question in perspectives:
        prompt = f"""Given this specification document, {question}

Document:
{content[:8000]}  # Use more context per perspective

Answer concisely:"""

        try:
            result = await model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=500),
            )
            extracted[name] = result.text.strip()
            if verbose:
                console.print(f"[dim]  ✓ {name}[/dim]")
        except Exception as e:
            if verbose:
                console.print(f"[dim]  ✗ {name}: {e}[/dim]")

    # Synthesize into goal
    goal_parts = []

    if extracted.get("product"):
        goal_parts.append(f"**Goal**: {extracted['product']}")

    if extracted.get("tech_stack"):
        goal_parts.append(f"**Tech Stack**: {extracted['tech_stack']}")

    if extracted.get("ux_requirements"):
        goal_parts.append(f"**UX Requirements**:\n{extracted['ux_requirements']}")

    if extracted.get("phases"):
        goal_parts.append(f"**Implementation Phases**:\n{extracted['phases']}")

    if extracted.get("constraints"):
        goal_parts.append(f"**Constraints**: {extracted['constraints']}")

    synthesized = "\n\n".join(goal_parts)

    # Keep synthesis manageable for the planner (max ~4000 chars)
    # This is still 2x what we had before, but digestible
    if len(synthesized) > 4000:
        # Prioritize: Goal > Tech Stack > Phases > UX > Constraints
        priority_parts = []
        remaining = 4000

        for key in ["product", "tech_stack", "phases", "ux_requirements", "constraints"]:
            if extracted.get(key) and remaining > 0:
                part = extracted[key][:remaining]
                label = key.replace("_", " ").title()
                if key == "product":
                    priority_parts.append(f"**Goal**: {part}")
                else:
                    priority_parts.append(f"**{label}**: {part}")
                remaining -= len(part) + 50  # Account for formatting

        synthesized = "\n\n".join(priority_parts)

    if verbose:
        console.print(f"\n[cyan]Synthesized goal ({len(synthesized)} chars)[/cyan]")

    return f"Implement the following specification:\n\n{synthesized}"


async def _plan_async(
    goal: str,
    input_file: str | None,
    output_path: str | None,
    output_format: str,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> None:
    """Generate and display/save the plan."""
    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.foundation.config import get_config
    from sunwell.planning.naaru import get_model_distribution
    from sunwell.planning.naaru.planners import ExpertiseAwareArtifactPlanner
    from sunwell.planning.routing import UnifiedRouter

    # Load model using resolve_model()
    config = get_config()
    model = None

    try:
        model = resolve_model(provider_override, model_override)
        if output_format == "human":
            provider = provider_override or (config.model.default_provider if config else "ollama")
            model_name = model_override or (config.model.default_model if config else "gemma3:4b")
            console.print(f"[dim]Using model: {provider}:{model_name}[/dim]")
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

    # Warn if plan looks trivial (single artifact echoing the goal)
    artifacts = plan_data.get("artifacts", [])
    if len(artifacts) == 1 and artifacts[0].get("id") == "main":
        console.print(
            "\n[yellow]⚠️  Minimal plan generated.[/yellow] "
            "[dim]Try providing more specific details or a longer description.[/dim]"
        )

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


# =============================================================================
# Plan Versioning Subcommands (RFC-120)
# =============================================================================


@plan.command("history")
@click.argument("plan_id", required=False)
@click.option(
    "--limit", "-l",
    default=20,
    help="Maximum number of versions to show",
)
def plan_history(plan_id: str | None, limit: int) -> None:
    """View plan version history.

    Shows all saved versions of a plan with timestamps, reasons, and scores.

    \b
    Examples:
        sunwell plan history            # List recent plans
        sunwell plan history abc123     # Show versions for specific plan
        sunwell plan history --limit 50 # Show more versions
    """
    from sunwell.planning.naaru.persistence import PlanStore

    store = PlanStore()

    if plan_id:
        # Show versions for specific plan
        versions = store.get_versions(plan_id)

        if not versions:
            console.print(f"[yellow]No versions found for plan {plan_id}[/yellow]")
            return

        table = Table(title=f"Plan History: {plan_id[:16]}")
        table.add_column("Version", style="cyan", width=8)
        table.add_column("Created", style="dim")
        table.add_column("Reason", style="green")
        table.add_column("Artifacts", style="yellow", width=10)
        table.add_column("Score", style="magenta", width=8)
        table.add_column("Changes", style="blue")

        for v in versions[-limit:]:
            changes = []
            if v.added_artifacts:
                changes.append(f"+{len(v.added_artifacts)}")
            if v.removed_artifacts:
                changes.append(f"-{len(v.removed_artifacts)}")
            change_str = " ".join(changes) if changes else "-"

            table.add_row(
                f"v{v.version}",
                v.created_at.strftime("%Y-%m-%d %H:%M"),
                v.reason[:40] + ("..." if len(v.reason) > 40 else ""),
                str(len(v.artifacts)),
                f"{v.score:.1f}" if v.score else "-",
                change_str,
            )

        console.print(table)

    else:
        # List all plans with version info
        plans = store.list_recent(limit=limit)

        if not plans:
            console.print("[yellow]No saved plans found[/yellow]")
            return

        table = Table(title="Recent Plans with Versions")
        table.add_column("Plan ID", style="cyan")
        table.add_column("Goal", style="green")
        table.add_column("Versions", style="yellow", width=10)
        table.add_column("Last Updated", style="dim")

        for p in plans:
            versions = store.get_versions(p.goal_hash)
            version_count = len(versions)
            goal_preview = p.goal[:50] + ("..." if len(p.goal) > 50 else "")

            table.add_row(
                p.goal_hash[:16],
                goal_preview,
                str(version_count) if version_count else "-",
                p.updated_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
        console.print("\n[dim]Use 'sunwell plan history <plan_id>' to see version details[/dim]")


@plan.command("diff")
@click.argument("plan_id")
@click.argument("v1", type=int)
@click.argument("v2", type=int)
def plan_diff(plan_id: str, v1: int, v2: int) -> None:
    """Compare two plan versions.

    Shows what changed between two versions of the same plan.

    \b
    Examples:
        sunwell plan diff abc123 1 2
        sunwell plan diff abc123 1 3
    """
    from sunwell.planning.naaru.persistence import PlanStore

    store = PlanStore()

    diff = store.diff(plan_id, v1, v2)

    if not diff:
        console.print(f"[red]Could not compute diff. Check plan ID and versions exist.[/red]")
        return

    console.print(Panel(
        f"Comparing v{v1} → v{v2}",
        title=f"Plan Diff: {plan_id[:16]}",
        border_style="blue",
    ))

    # Show changes
    if diff.added:
        console.print("\n[green]+ Added artifacts:[/green]")
        for artifact in diff.added:
            console.print(f"  + {artifact}")

    if diff.removed:
        console.print("\n[red]- Removed artifacts:[/red]")
        for artifact in diff.removed:
            console.print(f"  - {artifact}")

    if diff.modified:
        console.print("\n[yellow]~ Modified artifacts:[/yellow]")
        for artifact in diff.modified:
            console.print(f"  ~ {artifact}")

    if not diff.added and not diff.removed and not diff.modified:
        console.print("\n[dim]No changes detected between versions[/dim]")

    # Summary
    console.print(f"\n[dim]Summary: +{len(diff.added)} -{len(diff.removed)} ~{len(diff.modified)}[/dim]")


@plan.command("show")
@click.argument("plan_id")
@click.argument("version", type=int)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["human", "json"]),
    default="human",
    help="Output format",
)
def plan_show_version(plan_id: str, version: int, output_format: str) -> None:
    """Show details of a specific plan version.

    \b
    Examples:
        sunwell plan show abc123 2
        sunwell plan show abc123 1 --format json
    """
    from sunwell.planning.naaru.persistence import PlanStore

    store = PlanStore()
    v = store.get_version(plan_id, version)

    if not v:
        console.print(f"[red]Version {version} not found for plan {plan_id}[/red]")
        return

    if output_format == "json":
        print(json.dumps(v.to_dict(), indent=2))
        return

    # Human format
    console.print(Panel(
        f"Version {v.version} • {v.created_at.strftime('%Y-%m-%d %H:%M')}",
        title=f"Plan: {plan_id[:16]}",
        border_style="blue",
    ))

    console.print(f"\n[bold]Goal:[/bold] {v.goal[:100]}{'...' if len(v.goal) > 100 else ''}")
    console.print(f"[bold]Reason:[/bold] {v.reason}")

    if v.score:
        console.print(f"[bold]Score:[/bold] {v.score:.2f}")

    # Artifacts
    if v.artifacts:
        console.print(f"\n[bold]Artifacts ({len(v.artifacts)}):[/bold]")
        for artifact in v.artifacts[:20]:
            console.print(f"  • {artifact}")
        if len(v.artifacts) > 20:
            console.print(f"  [dim]... and {len(v.artifacts) - 20} more[/dim]")

    # Changes from previous
    if v.added_artifacts or v.removed_artifacts:
        console.print("\n[bold]Changes from previous version:[/bold]")
        if v.added_artifacts:
            console.print(f"  [green]+{len(v.added_artifacts)} added[/green]")
        if v.removed_artifacts:
            console.print(f"  [red]-{len(v.removed_artifacts)} removed[/red]")
