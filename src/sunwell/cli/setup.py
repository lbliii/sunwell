"""Setup command - Initialize Sunwell with default bindings."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from sunwell.binding import BindingManager

console = Console()


@click.command()
@click.option("--provider", "-p", default="openai", help="Default LLM provider")
@click.option("--model", "-m", help="Default model (auto-selected if not specified)")
@click.option("--lenses-dir", type=click.Path(exists=True), help="Directory containing lens files")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing bindings")
def setup(provider: str, model: str | None, lenses_dir: str | None, force: bool) -> None:
    """Set up Sunwell with default bindings.

    Creates sensible default bindings for common use cases:
    - writer: Technical writing (default)
    - reviewer: Code review
    - helper: General assistance

    Examples:

        sunwell setup                           # Use defaults (openai)

        sunwell setup --provider anthropic      # Use Claude

        sunwell setup --provider openai --model gpt-4o-mini  # Specific model
    """

    manager = BindingManager()

    # Find lenses directory
    if lenses_dir:
        lens_path = Path(lenses_dir)
    else:
        # Check common locations
        candidates = [
            Path.cwd() / "lenses",
            Path(__file__).parent.parent.parent.parent / "lenses",  # In sunwell repo
            Path.home() / ".sunwell" / "lenses",
        ]
        lens_path = None
        for c in candidates:
            if c.exists() and list(c.glob("*.lens")):
                lens_path = c
                break

        if not lens_path:
            console.print("[red]No lenses directory found.[/red]")
            console.print("[dim]Specify with --lenses-dir or create ./lenses/[/dim]")
            sys.exit(1)

    # Default bindings to create
    default_bindings = [
        {
            "name": "writer",
            "lens": "tech-writer.lens",
            "description": "Technical documentation",
            "tier": 1,
            "is_default": True,
        },
        {
            "name": "reviewer",
            "lens": "code-reviewer.lens",
            "description": "Code review",
            "tier": 2,  # Deep by default for reviews
        },
        {
            "name": "helper",
            "lens": "helper.lens",
            "description": "General assistance",
            "tier": 0,  # Fast for quick questions
        },
    ]

    # Auto-select model based on provider
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
        }.get(provider, "gpt-4o")

    console.print("\n[bold]Setting up Sunwell[/bold]")
    console.print(f"Provider: {provider}")
    console.print(f"Model: {model}")
    console.print(f"Lenses: {lens_path}\n")

    created = []
    skipped = []

    for binding_def in default_bindings:
        name = binding_def["name"]
        lens_file = lens_path / binding_def["lens"]

        # Check if lens exists
        if not lens_file.exists():
            console.print(f"[yellow]⚠ Skipping {name}:[/yellow] {binding_def['lens']} not found")
            skipped.append(name)
            continue

        # Check if binding exists
        existing = manager.get(name)
        if existing and not force:
            console.print(f"[dim]• {name}: already exists (use --force to overwrite)[/dim]")
            skipped.append(name)
            continue

        # Create binding
        manager.create(
            name=name,
            lens_path=str(lens_file),
            provider=provider,
            model=model,
            tier=binding_def.get("tier", 1),
        )

        # Set default if specified
        if binding_def.get("is_default"):
            manager.set_default(name)

        console.print(f"[green]✓ {name}:[/green] {binding_def['description']}")
        created.append(name)

    # Summary
    console.print()
    if created:
        default = manager.get_default()
        console.print(f"[bold green]Created {len(created)} binding(s)[/bold green]")
        if default:
            console.print(f"[cyan]Default:[/cyan] {default.name}")

        console.print("\n[bold]Quick start:[/bold]")
        console.print("  sunwell ask \"Write docs for my API\"")
        console.print("  sunwell ask reviewer \"Review this code\"")
        console.print("  sunwell ask helper \"Quick question\"")
    else:
        console.print("[yellow]No bindings created.[/yellow]")
        if skipped:
            console.print(f"[dim]Use --force to overwrite existing: {', '.join(skipped)}[/dim]")
