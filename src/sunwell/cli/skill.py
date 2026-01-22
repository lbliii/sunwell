"""Skill commands - Execute and validate skills from lenses (RFC-011, RFC-087)."""


import asyncio
import json as json_module
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.cli.helpers import create_model
from sunwell.core.errors import SunwellError
from sunwell.core.types import LensReference
from sunwell.fount.client import FountClient
from sunwell.fount.resolver import LensResolver
from sunwell.schema.loader import LensLoader
from sunwell.skills.executor import SkillExecutor
from sunwell.workspace.detector import WorkspaceDetector

if TYPE_CHECKING:
    from sunwell.skills.cache import SkillCache

console = Console()

# Global skill cache instance (shared across commands in same process)
_skill_cache: SkillCache | None = None


def _get_cache() -> SkillCache:
    """Get or create the global skill cache."""
    global _skill_cache
    if _skill_cache is None:
        from sunwell.skills.cache import SkillCache
        _skill_cache = SkillCache(max_size=1000)
    return _skill_cache


# =============================================================================
# CLI Group
# =============================================================================


@click.group()
def skill() -> None:
    """Skill commands - execute, validate, and manage skills (RFC-011, RFC-087)."""
    pass


# =============================================================================
# Skill Commands
# =============================================================================


@skill.command("validate")
@click.argument("lens_path", type=click.Path(exists=True))
def validate_cmd(lens_path: str) -> None:
    """Validate a lens file.

    Checks:
    - YAML syntax
    - Schema compliance
    - Component references

    Examples:

        sunwell skill validate my-lens.lens

        sunwell skill validate ./lenses/tech-writer.lens
    """
    loader = LensLoader()

    try:
        lens = loader.load(Path(lens_path))
        console.print(f"[green]✅ Valid lens:[/green] {lens.metadata.name}")
        console.print()

        # Display lens summary
        table = Table(title=f"Lens: {lens.metadata.name}")
        table.add_column("Component", style="cyan")
        table.add_column("Count", style="green")

        table.add_row("Heuristics", str(len(lens.heuristics)))
        table.add_row("Anti-Heuristics", str(len(lens.anti_heuristics)))
        table.add_row("Personas", str(len(lens.personas)))
        table.add_row("Validators (Deterministic)", str(len(lens.deterministic_validators)))
        table.add_row("Validators (Heuristic)", str(len(lens.heuristic_validators)))
        table.add_row("Workflows", str(len(lens.workflows)))
        table.add_row("Skills", str(len(lens.skills)))

        if lens.framework:
            table.add_row("Framework", lens.framework.name)
        if lens.extends:
            table.add_row("Extends", lens.extends.source)

        console.print(table)

        # Show skills if present
        if lens.skills:
            console.print("\n[bold]Skills:[/bold]")
            for s in lens.skills:
                trust = {"full": "🔓", "sandboxed": "🔒", "none": "📝"}[s.trust.value]
                console.print(f"  {trust} {s.name}")

    except SunwellError as e:
        console.print(f"[red]❌ Invalid lens:[/red] {e.message}")
        sys.exit(1)


@skill.command("exec")
@click.argument("lens_path", type=click.Path(exists=True))
@click.argument("skill_name")
@click.argument("task")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--provider", "-p", default="openai", help="Provider")
@click.option("--output", "-o", type=click.Path(), help="Write output to file")
@click.option("--no-validate", is_flag=True, help="Skip lens validation")
@click.option("--dry-run", is_flag=True, help="Don't write files, output to stdout")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def exec(
    lens_path: str,
    skill_name: str,
    task: str,
    model: str | None,
    provider: str,
    output: str | None,
    no_validate: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Execute a skill from a lens.

    Skills are action capabilities defined in lenses (RFC-011).
    They combine lens judgment (heuristics, validators) with
    execution (instructions, scripts, templates).

    Examples:

        sunwell exec tech-writer.lens create-api-docs "Document auth.py"

        sunwell exec my.lens generate-tests "Add tests for utils" -o tests/test_utils.py

        sunwell exec lens.lens my-skill "task" --dry-run
    """
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
            "mock": "mock",
        }.get(provider, "gpt-4o")

    asyncio.run(_exec_skill_async(
        lens_path, skill_name, task, model, provider, output,
        not no_validate, dry_run, verbose
    ))


async def _exec_skill_async(
    lens_path: str,
    skill_name: str,
    task: str,
    model_name: str,
    provider: str,
    output_path: str | None,
    validate: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Async implementation of exec command."""
    # Load lens
    fount = FountClient()
    loader = LensLoader(fount_client=fount)
    resolver = LensResolver(loader=loader)

    try:
        source = str(lens_path)
        if not (source.startswith("/") or source.startswith("./") or source.startswith("../")):
            source = f"./{source}"

        ref = LensReference(source=source)
        lens = await resolver.resolve(ref)
    except SunwellError as e:
        console.print(f"[red]Error loading/resolving lens:[/red] {e.message}")
        sys.exit(1)

    # Find skill
    skill = lens.get_skill(skill_name)
    if not skill:
        available = [s.name for s in lens.skills] if lens.skills else []
        console.print(f"[red]Skill not found:[/red] {skill_name}")
        if available:
            console.print(f"[dim]Available: {', '.join(available)}[/dim]")
        else:
            console.print("[dim]This lens has no skills.[/dim]")
        sys.exit(1)

    if verbose:
        console.print(Panel(
            f"[bold]{skill.name}[/bold]\n"
            f"{skill.description or 'No description'}\n\n"
            f"Type: {skill.skill_type.value} | Trust: {skill.trust.value}",
            title="Skill",
            border_style="green",
        ))

    # Create model
    model = create_model(provider, model_name)

    # Detect workspace
    workspace_root = None
    try:
        detector = WorkspaceDetector()
        workspace = detector.detect()
        workspace_root = workspace.root
        if verbose:
            console.print(f"[dim]Workspace: {workspace_root}[/dim]")
    except Exception:
        pass

    # Execute skill
    executor = SkillExecutor(
        skill=skill,
        lens=lens,
        model=model,
        workspace_root=workspace_root,
    )

    with console.status("[bold green]Executing skill..."):
        result = await executor.execute(
            context={"task": task},
            validate=validate,
            dry_run=dry_run,
        )

    # Display results
    if verbose:
        console.print("\n[cyan]Execution completed:[/cyan]")
        console.print(f"  Time: {result.execution_time_ms}ms")
        if result.scripts_run:
            console.print(f"  Scripts: {', '.join(result.scripts_run)}")
        console.print(f"  Validation: {'✅' if result.validation_passed else '⚠️'} ({result.confidence:.0%})")
        if result.refinement_count:
            console.print(f"  Refinements: {result.refinement_count}")

    console.print(f"\n{result.content}")

    # Write output
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(result.content)
        console.print(f"\n[green]✓ Written to:[/green] {output_path}")


# =============================================================================
# RFC-087: Skill Cache Commands
# =============================================================================


@skill.command("cache-stats")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def cache_stats(json_output: bool) -> None:
    """Show skill cache statistics (RFC-087).

    Displays cache size, hit rate, and other metrics.

    Examples:

        sunwell skill cache-stats

        sunwell skill cache-stats --json
    """
    cache = _get_cache()
    stats = cache.stats()

    if json_output:
        print(json_module.dumps(stats, indent=2))
        return

    console.print("[bold]Skill Cache Statistics[/bold]")
    console.print(f"Size: {stats['size']} / {stats['max_size']}")
    console.print(f"Hits: {stats['hits']}")
    console.print(f"Misses: {stats['misses']}")
    console.print(f"Hit Rate: {stats['hit_rate']:.1%}")


@skill.command("cache-clear")
@click.option("--skill-name", "-s", "skill_name", help="Clear cache for specific skill only")
def cache_clear(skill_name: str | None) -> None:
    """Clear the skill cache (RFC-087).

    Clears all cached skill execution results, or just for a specific skill.

    Examples:

        sunwell skill cache-clear

        sunwell skill cache-clear --skill-name analyze-code
    """
    cache = _get_cache()

    if skill_name:
        count = cache.invalidate_skill(skill_name)
        console.print(f"[green]✓[/green] Cleared {count} cache entries for skill: {skill_name}")
    else:
        cache.clear()
        console.print("[green]✓[/green] Skill cache cleared")


# =============================================================================
# Legacy Commands (for backward compatibility with `sunwell exec` etc.)
# =============================================================================


@click.command("exec")
@click.argument("lens_path", type=click.Path(exists=True))
@click.argument("skill_name")
@click.argument("task")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--provider", "-p", default="openai", help="Provider")
@click.option("--output", "-o", type=click.Path(), help="Write output to file")
@click.option("--no-validate", is_flag=True, help="Skip lens validation")
@click.option("--dry-run", is_flag=True, help="Don't write files, output to stdout")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def exec_legacy(
    lens_path: str,
    skill_name: str,
    task: str,
    model: str | None,
    provider: str,
    output: str | None,
    no_validate: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Execute a skill from a lens (legacy command, use `sunwell skill exec`).

    Skills are action capabilities defined in lenses (RFC-011).
    """
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
            "mock": "mock",
        }.get(provider, "gpt-4o")

    asyncio.run(_exec_skill_async(
        lens_path, skill_name, task, model, provider, output,
        not no_validate, dry_run, verbose
    ))


@click.command("validate")
@click.argument("lens_path", type=click.Path(exists=True))
def validate_legacy(lens_path: str) -> None:
    """Validate a lens file (legacy command, use `sunwell skill validate`)."""
    loader = LensLoader()

    try:
        lens_obj = loader.load(Path(lens_path))
        console.print(f"[green]✅ Valid lens:[/green] {lens_obj.metadata.name}")
    except SunwellError as e:
        console.print(f"[red]❌ Invalid lens:[/red] {e.message}")
        sys.exit(1)
