"""Lens commands - List and inspect lenses."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sunwell.core.errors import SunwellError
from sunwell.schema.loader import LensLoader

console = Console()


@click.command("list")
@click.option("--path", "-p", type=click.Path(exists=True), help="Path to search for lenses")
def lens(path: str | None) -> None:
    """List available lenses.

    By default, searches current directory and ~/.sunwell/lenses/

    Examples:

        sunwell lens list

        sunwell lens list --path ./my-lenses/
    """
    search_paths = []

    if path:
        search_paths.append(Path(path))
    else:
        search_paths.append(Path.cwd())
        home_lenses = Path.home() / ".sunwell" / "lenses"
        if home_lenses.exists():
            search_paths.append(home_lenses)

    lenses_found = []
    loader = LensLoader()

    for search_path in search_paths:
        for lens_file in search_path.glob("**/*.lens"):
            try:
                lens = loader.load(lens_file)
                lenses_found.append((lens_file, lens))
            except SunwellError:
                pass  # Skip invalid lenses

        # Also check .yaml files
        for lens_file in search_path.glob("**/*.lens.yaml"):
            try:
                lens = loader.load(lens_file)
                lenses_found.append((lens_file, lens))
            except SunwellError:
                pass

    if not lenses_found:
        console.print("[yellow]No lenses found.[/yellow]")
        console.print(f"Searched: {', '.join(str(p) for p in search_paths)}")
        return

    table = Table(title="Available Lenses")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Domain", style="yellow")
    table.add_column("Path", style="dim")

    for lens_file, lens_obj in sorted(lenses_found, key=lambda x: x[1].metadata.name):
        table.add_row(
            lens_obj.metadata.name,
            str(lens_obj.metadata.version) if lens_obj.metadata.version else "-",
            lens_obj.metadata.domain or "-",
            str(lens_file.relative_to(Path.cwd())) if lens_file.is_relative_to(Path.cwd()) else str(lens_file),
        )

    console.print(table)
