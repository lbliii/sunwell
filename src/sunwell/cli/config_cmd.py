"""Config command - Manage Sunwell configuration."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from sunwell.config import get_config, load_config, save_default_config

console = Console()


@click.command()
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--init", is_flag=True, help="Create default config file")
@click.option("--path", type=click.Path(), help="Config file path (default: .sunwell/config.yaml)")
def config(show: bool, init: bool, path: str | None) -> None:
    """Manage Sunwell configuration.

    Configuration is loaded from (in priority order):
    1. Environment variables (SUNWELL_*)
    2. .sunwell/config.yaml (project-local)
    3. ~/.sunwell/config.yaml (user-global)
    4. Built-in defaults

    Examples:

        sunwell config --show              # Show current config
        sunwell config --init              # Create default config file
        sunwell config --init --path ~/.sunwell/config.yaml  # Create global config

    Environment overrides:

        SUNWELL_HEADSPACE_SPAWN_ENABLED=false sunwell apply ...
        SUNWELL_EMBEDDING_OLLAMA_MODEL=nomic-embed-text sunwell apply ...
    """
    if init:
        config_path = path or ".sunwell/config.yaml"
        saved_path = save_default_config(config_path)
        console.print(f"[green]✓ Config file created:[/green] {saved_path}")
        console.print("\n[dim]Edit this file to customize Sunwell behavior.[/dim]")
        return

    if show or not (init or path):
        # Load and display current config
        cfg = load_config(path) if path else get_config()

        console.print(Panel("[bold]Sunwell Configuration[/bold]", border_style="cyan"))

        # Simulacrum config
        console.print("\n[cyan]Simulacrum[/cyan]")
        console.print(f"  Base path: {cfg.headspace.base_path}")

        console.print("\n  [dim]Spawn Policy:[/dim]")
        console.print(f"    Enabled: {cfg.headspace.spawn.enabled}")
        console.print(f"    Novelty threshold: {cfg.headspace.spawn.novelty_threshold}")
        console.print(f"    Min queries before spawn: {cfg.headspace.spawn.min_queries_before_spawn}")
        console.print(f"    Domain coherence: {cfg.headspace.spawn.domain_coherence_threshold}")
        console.print(f"    Max headspaces: {cfg.headspace.spawn.max_headspaces}")

        console.print("\n  [dim]Lifecycle Policy:[/dim]")
        console.print(f"    Stale days: {cfg.headspace.lifecycle.stale_days}")
        console.print(f"    Archive days: {cfg.headspace.lifecycle.archive_days}")
        console.print(f"    Auto archive: {cfg.headspace.lifecycle.auto_archive}")

        # Embedding config
        console.print("\n[cyan]Embedding[/cyan]")
        console.print(f"  Prefer local: {cfg.embedding.prefer_local}")
        console.print(f"  Ollama model: {cfg.embedding.ollama_model}")
        console.print(f"  Ollama URL: {cfg.embedding.ollama_url}")
        console.print(f"  Fallback to hash: {cfg.embedding.fallback_to_hash}")

        # Model config
        console.print("\n[cyan]Model Defaults[/cyan]")
        console.print(f"  Provider: {cfg.model.default_provider}")
        console.print(f"  Model: {cfg.model.default_model}")
        console.print(f"  Smart routing: {cfg.model.smart_routing}")

        # Check for config file
        console.print("\n[dim]Config sources:[/dim]")
        if Path(".sunwell/config.yaml").exists():
            console.print("  [green]✓[/green] .sunwell/config.yaml")
        else:
            console.print("  [dim]○[/dim] .sunwell/config.yaml (not found)")

        home_config = Path.home() / ".sunwell" / "config.yaml"
        if home_config.exists():
            console.print(f"  [green]✓[/green] {home_config}")
        else:
            console.print(f"  [dim]○[/dim] {home_config} (not found)")
