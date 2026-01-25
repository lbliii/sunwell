"""Surface composition CLI commands (RFC-072).

Provides CLI interface for surface composition, called by Tauri.
Uses SurfaceComposer for intelligent goal-to-layout conversion.
"""

import json
from pathlib import Path

import click

from sunwell.surface import (
    PrimitiveRegistry,
    SurfaceComposer,
    SurfaceRenderer,
    render_with_fallback,
)
from sunwell.interface.generative.surface.memory_integration import (
    load_memory_patterns,
    record_layout_interaction,
)
from sunwell.interface.generative.surface.types import SurfaceLayout, SurfacePrimitive


@click.group()
def surface() -> None:
    """Surface composition commands (RFC-072)."""


@surface.command("compose")
@click.option("--goal", required=True, help="Goal to compose surface for")
@click.option("--project", default=None, help="Project path")
@click.option("--lens", default=None, help="Lens name for affordances")
@click.option("--arrangement", default=None, help="Override layout arrangement")
@click.option("--json", "json_output", is_flag=True, default=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Include reasoning in output")
def compose(
    goal: str,
    project: str | None,
    lens: str | None,
    arrangement: str | None,
    json_output: bool,
    verbose: bool,
) -> None:
    """Compose a surface layout for a goal.

    Uses SurfaceComposer for intelligent composition with:
    - Intent extraction from goal
    - Lens affordances (if provided)
    - Historical success patterns
    - Domain inference from project

    Called by Tauri's compose_surface command.
    """
    project_path = Path(project) if project else Path.cwd()

    # Load memory patterns for historical success rates
    memory_patterns = load_memory_patterns(project_path)

    # Load lens if specified
    loaded_lens = None
    if lens:
        loaded_lens = _load_lens(lens, project_path)

    # Compose using SurfaceComposer
    composer = SurfaceComposer()
    result = composer.compose(
        goal=goal,
        project_path=project_path,
        lens=loaded_lens,
        memory_patterns=memory_patterns,
    )

    # Override arrangement if specified
    if arrangement:
        result.spec = result.spec.__class__(
            primary=result.spec.primary,
            secondary=result.spec.secondary,
            contextual=result.spec.contextual,
            arrangement=arrangement,  # type: ignore[arg-type]
            seed_content=result.spec.seed_content,
            primary_props=result.spec.primary_props,
        )

    # Render to layout
    registry = PrimitiveRegistry.default()
    renderer = SurfaceRenderer(registry)
    layout = render_with_fallback(
        renderer=renderer,
        spec=result.spec,
        project_path=project_path,
    )

    # Output
    if json_output:
        output = layout.to_dict()
        if verbose:
            output["_meta"] = {
                "confidence": result.confidence,
                "intent": {
                    "primary_domain": result.intent.primary_domain,
                    "triggered_primitives": result.intent.triggered_primitives,
                },
                "reasoning": result.reasoning,
            }
        click.echo(json.dumps(output))
    else:
        click.echo(f"Confidence: {result.confidence:.0%}")
        click.echo(f"Primary: {layout.primary.id} ({layout.primary.size})")
        for p in layout.secondary:
            click.echo(f"Secondary: {p.id} ({p.size})")
        for p in layout.contextual:
            click.echo(f"Contextual: {p.id} ({p.size})")
        if verbose:
            click.echo(f"\nIntent: {result.intent.primary_domain}")
            click.echo(f"Triggers: {', '.join(result.intent.triggered_primitives)}")


@surface.command("record")
@click.option("--goal", required=True, help="Goal that was active")
@click.option("--layout", required=True, help="Layout JSON")
@click.option("--duration", type=int, required=True, help="Duration in seconds")
@click.option("--completed", type=bool, required=True, help="Whether goal was completed")
@click.option("--project", default=None, help="Project path")
def record(
    goal: str,
    layout: str,
    duration: int,
    completed: bool,
    project: str | None,
) -> None:
    """Record a successful layout for future reference.

    Stores layout success patterns in the project's .sunwell directory
    for use in future compositions.

    Called by Tauri's record_layout_success command.
    """
    project_path = Path(project) if project else Path.cwd()

    # Parse layout JSON
    layout_data = json.loads(layout)
    surface_layout = _parse_layout(layout_data)

    # Record interaction
    result = record_layout_interaction(
        project_path=project_path,
        layout=surface_layout,
        goal=goal,
        duration_seconds=duration,
        completed=completed,
    )

    click.echo(json.dumps(result))


@surface.command("registry")
@click.option("--json", "json_output", is_flag=True, default=True, help="Output as JSON")
@click.option("--category", default=None, help="Filter by category")
def registry(json_output: bool, category: str | None) -> None:
    """List all available primitives.

    Called by Tauri's get_primitive_registry command.
    """
    reg = PrimitiveRegistry.default()
    primitives = reg.list_by_category(category) if category else reg.list_all()

    if json_output:
        output = [
            {
                "id": p.id,
                "category": p.category,
                "component": p.component,
                "can_be_primary": p.can_be_primary,
                "can_be_secondary": p.can_be_secondary,
                "can_be_contextual": p.can_be_contextual,
                "default_size": p.default_size,
                "size_options": list(p.size_options),
            }
            for p in primitives
        ]
        click.echo(json.dumps(output))
    else:
        for p in primitives:
            flags = []
            if p.can_be_primary:
                flags.append("P")
            if p.can_be_secondary:
                flags.append("S")
            if p.can_be_contextual:
                flags.append("C")
            click.echo(f"{p.id} [{p.category}] ({','.join(flags)}) default: {p.default_size}")


@surface.command("analyze")
@click.argument("goal")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def analyze(goal: str, json_output: bool) -> None:
    """Analyze a goal to show intent signals.

    Useful for debugging and understanding composition decisions.
    """
    from sunwell.interface.generative.surface.intent import extract_intent

    intent = extract_intent(goal)

    if json_output:
        output = {
            "primary_domain": intent.primary_domain,
            "domain_scores": intent.domain_scores,
            "triggered_primitives": intent.triggered_primitives,
            "keywords": intent.keywords,
            "suggested_arrangement": intent.suggested_arrangement,
            "confidence": intent.confidence,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"Primary Domain: {intent.primary_domain}")
        click.echo(f"Confidence: {intent.confidence:.0%}")
        click.echo(f"Arrangement: {intent.suggested_arrangement}")
        click.echo("\nDomain Scores:")
        for domain, score in sorted(
            intent.domain_scores.items(), key=lambda x: x[1], reverse=True
        ):
            bar = "█" * int(score * 20)
            click.echo(f"  {domain:12} {bar} {score:.2f}")
        if intent.triggered_primitives:
            click.echo(f"\nTriggered: {', '.join(intent.triggered_primitives)}")


@surface.command("patterns")
@click.option("--project", default=None, help="Project path")
def patterns(project: str | None) -> None:
    """Show learned layout patterns for a project.

    Displays historical primitive success rates.
    """
    project_path = Path(project) if project else Path.cwd()

    memory_patterns = load_memory_patterns(project_path)

    if not memory_patterns:
        click.echo("No learned patterns yet.")
        return

    click.echo("Primitive Success Rates:\n")
    for prim_id, rate in sorted(
        memory_patterns.items(), key=lambda x: x[1], reverse=True
    ):
        bar = "█" * int(rate * 20)
        click.echo(f"  {prim_id:16} {bar} {rate:.0%}")


# =============================================================================
# HELPERS
# =============================================================================


def _load_lens(lens_name: str, project_path: Path):
    """Load a lens by name."""
    try:
        from sunwell.planning.lens.manager import LensManager

        manager = LensManager()
        return manager.load(lens_name)
    except Exception:
        return None


def _parse_layout(data: dict) -> SurfaceLayout:
    """Parse a layout from JSON data."""
    primary_data = data["primary"]
    primary = SurfacePrimitive(
        id=primary_data["id"],
        category=primary_data["category"],
        size=primary_data["size"],
        props=primary_data.get("props", {}),
    )

    secondary = tuple(
        SurfacePrimitive(
            id=p["id"],
            category=p["category"],
            size=p["size"],
            props=p.get("props", {}),
        )
        for p in data.get("secondary", [])
    )

    contextual = tuple(
        SurfacePrimitive(
            id=p["id"],
            category=p["category"],
            size=p["size"],
            props=p.get("props", {}),
        )
        for p in data.get("contextual", [])
    )

    return SurfaceLayout(
        primary=primary,
        secondary=secondary,
        contextual=contextual,
        arrangement=data.get("arrangement", "standard"),
    )
