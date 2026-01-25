"""Bind command group - Manage bindings (attuned lens configurations)."""


import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.foundation.binding import BindingManager

console = Console()


@click.group()
def bind() -> None:
    """Manage bindings (your attuned lens configurations).

    A binding is like a soul stone - attune once, use forever.
    It saves all your preferences: lens, model, headspace, settings.

    Examples:

        sunwell bind create my-project --lens tech-writer.lens

        sunwell ask my-project "Write docs"  # No flags needed!

        sunwell bind default my-project
        sunwell ask "Write docs"  # Uses default binding
    """
    pass


@bind.command("create")
@click.argument("name")
@click.option("--lens", "-l", required=True, type=click.Path(exists=True), help="Path to lens file")
@click.option("--provider", "-p", default=None, help="LLM provider (default: from config)")
@click.option("--model", "-m", help="Model name (auto-selected based on provider if not specified)")
@click.option("--tier", type=click.Choice(["0", "1", "2"]), default="1", help="Default execution tier")
@click.option("--no-stream", is_flag=True, help="Disable streaming by default")
@click.option("--verbose", is_flag=True, help="Enable verbose by default")
@click.option("--no-workspace", is_flag=True, help="Disable workspace indexing by default")
@click.option("--tools/--no-tools", default=False, help="Enable tool calling (Agent mode)")
@click.option("--trust", type=click.Choice(["discovery", "read_only", "workspace", "shell"]),
              default="workspace", help="Tool trust level")
@click.option("--set-default", is_flag=True, help="Set as default binding")
def bind_create(
    name: str,
    lens: str,
    provider: str | None,
    model: str | None,
    tier: str,
    no_stream: bool,
    verbose: bool,
    no_workspace: bool,
    tools: bool,
    trust: str,
    set_default: bool,
) -> None:
    """Create a new binding (attune to a lens).

    Once created, use `sunwell ask <binding-name> "prompt"` without flags!

    Examples:

        sunwell bind create my-docs --lens tech-writer.lens

        sunwell bind create prod-review --lens code-reviewer.lens -p anthropic

        sunwell bind create fast-helper --lens helper.lens --tier 0 --set-default
    """
    from sunwell.foundation.config import get_config

    cfg = get_config()

    # Resolve provider from config if not specified
    if provider is None:
        provider = cfg.model.default_provider if cfg else "ollama"

    # Resolve model from config if not specified
    if model is None:
        model = cfg.model.default_model if cfg else "gemma3:4b"

    manager = BindingManager()

    # Check if exists
    if manager.get(name):
        console.print(f"[red]Binding '{name}' already exists.[/red]")
        console.print(f"[dim]Use `sunwell bind update {name}` to modify it.[/dim]")
        sys.exit(1)

    binding = manager.create(
        name=name,
        lens_uri=lens if lens and ("/" in lens or "\\" in lens or lens.startswith("sunwell:")) else None,
        lens_path=lens if lens and not ("/" in lens or "\\" in lens or lens.startswith("sunwell:")) else None,
        provider=provider,
        model=model,
        tier=int(tier),
        stream=not no_stream,
        verbose=verbose,
        index_workspace=not no_workspace,
        tools_enabled=tools,
        trust_level=trust,
    )

    if set_default:
        manager.set_default(name)
        console.print(f"[green]✓ Created binding:[/green] {name} [dim](set as default)[/dim]")
    else:
        console.print(f"[green]✓ Created binding:[/green] {name}")

    # Show summary
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_row("Lens", binding.get_lens_reference())
    table.add_row("Model", f"{binding.provider}:{binding.model}")
    table.add_row("Simulacrum", binding.simulacrum or name)
    table.add_row("Tier", str(binding.tier))
    mode = "Agent" if binding.tools_enabled else "Chat"
    table.add_row("Mode", f"{mode}" + (f" ({binding.trust_level})" if binding.tools_enabled else ""))
    console.print(table)

    console.print(f"\n[dim]Now use: sunwell ask {name} \"your prompt\"[/dim]")
    if binding.tools_enabled:
        console.print(f"[dim]  Or chat: sunwell chat {name}[/dim]")


@bind.command("list")
def bind_list() -> None:
    """List all bindings.

    Shows all your attuned configurations with their settings.

    Examples:

        sunwell bind list
    """
    manager = BindingManager()
    bindings = manager.list_all()
    default = manager.get_default()

    if not bindings:
        console.print("[dim]No bindings yet.[/dim]")
        console.print("[dim]Create one: sunwell bind create my-project --lens my.lens[/dim]")
        return

    table = Table(title="Bindings")
    table.add_column("Name", style="cyan")
    table.add_column("Lens")
    table.add_column("Model")
    table.add_column("Mode", justify="center")
    table.add_column("Uses", justify="right")
    table.add_column("Default", justify="center")

    for b in bindings:
        is_default = "⭐" if default and b.name == default.name else ""
        lens_ref = b.get_lens_reference()
        lens_short = Path(lens_ref).name if "/" in lens_ref or "\\" in lens_ref else lens_ref
        mode = "🤖 Agent" if b.tools_enabled else "💬 Chat"
        table.add_row(
            b.name,
            lens_short,
            f"{b.provider}:{b.model}",
            mode,
            str(b.use_count),
            is_default,
        )

    console.print(table)


@bind.command("show")
@click.argument("name")
def bind_show(name: str) -> None:
    """Show details of a binding.

    Examples:

        sunwell bind show my-project
    """
    manager = BindingManager()
    binding = manager.get(name)

    if not binding:
        console.print(f"[red]Binding '{name}' not found.[/red]")
        sys.exit(1)

    default = manager.get_default()
    is_default = default and binding.name == default.name

    title = f"Binding: {name}"
    if is_default:
        title += " ⭐ (default)"

    console.print(Panel(title, border_style="cyan"))

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Lens", binding.get_lens_reference())
    table.add_row("Provider", binding.provider)
    table.add_row("Model", binding.model)
    table.add_row("Simulacrum", binding.simulacrum or name)
    table.add_row("Tier", ["Fast", "Standard", "Deep"][binding.tier])
    table.add_row("Stream", "✓" if binding.stream else "✗")
    table.add_row("Verbose", "✓" if binding.verbose else "✗")
    table.add_row("Auto-learn", "✓" if binding.auto_learn else "✗")
    table.add_row("Index workspace", "✓" if binding.index_workspace else "✗")
    table.add_row("", "")
    mode = "Agent" if binding.tools_enabled else "Chat"
    table.add_row("Mode", f"{mode}" + (f" ({binding.trust_level})" if binding.tools_enabled else ""))
    table.add_row("", "")
    table.add_row("Created", binding.created_at[:19])
    table.add_row("Last used", binding.last_used[:19])
    table.add_row("Use count", str(binding.use_count))

    console.print(table)


@bind.command("default")
@click.argument("name", required=False)
def bind_default(name: str | None) -> None:
    """Set or show the default binding.

    With no argument, shows the current default.
    With a name, sets that binding as default.

    Examples:

        sunwell bind default                # Show current default

        sunwell bind default my-project     # Set default
    """
    manager = BindingManager()

    if name is None:
        # Show current default
        default = manager.get_default()
        if default:
            console.print(f"[cyan]Default binding:[/cyan] {default.name}")
            console.print(f"[dim]  Lens: {default.get_lens_reference()}[/dim]")
            console.print(f"[dim]  Model: {default.provider}:{default.model}[/dim]")
        else:
            console.print("[dim]No default binding set.[/dim]")
            console.print("[dim]Set one: sunwell bind default <name>[/dim]")
    else:
        # Set default
        if manager.set_default(name):
            console.print(f"[green]✓ Default set to:[/green] {name}")
        else:
            console.print(f"[red]Binding '{name}' not found.[/red]")
            sys.exit(1)


@bind.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Delete without confirmation")
def bind_delete(name: str, force: bool) -> None:
    """Delete a binding.

    Examples:

        sunwell bind delete old-project

        sunwell bind delete temp --force
    """
    manager = BindingManager()
    binding = manager.get(name)

    if not binding:
        console.print(f"[red]Binding '{name}' not found.[/red]")
        sys.exit(1)

    if not force:
        console.print(f"[yellow]Delete binding '{name}'?[/yellow]")
        console.print(f"[dim]  Lens: {binding.get_lens_reference()}[/dim]")
        console.print(f"[dim]  Uses: {binding.use_count}[/dim]")
        if not click.confirm("Continue?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    manager.delete(name)
    console.print(f"[green]✓ Deleted binding:[/green] {name}")
