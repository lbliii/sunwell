"""Config command — Manage Sunwell configuration (RFC-131 Holy Light styling)."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from sunwell.foundation.config import get_config, load_config, save_default_config

console = Console()


def _get_nested(obj: object, key: str) -> object:
    """Get a nested attribute using dot notation.

    Args:
        obj: The object to traverse
        key: Dot-separated path like 'model.default_provider'

    Returns:
        The value at the path, or raises KeyError if not found
    """
    parts = key.split(".")
    current = obj
    for part in parts:
        if hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(f"Key not found: {key}")
    return current


@click.group()
def config() -> None:
    """Manage Sunwell configuration.

    Configuration is loaded from (in priority order):
    1. Environment variables (SUNWELL_*)
    2. .sunwell/config.yaml (project-local)
    3. ~/.sunwell/config.yaml (user-global)
    4. Built-in defaults

    Examples:

        sunwell config show              # Show current config
        sunwell config init              # Create default config file
        sunwell config get model.default_provider
        sunwell config set model.default_model gemma3:12b

    Environment overrides:

        SUNWELL_MODEL_DEFAULT_PROVIDER=anthropic sunwell ...
        SUNWELL_EMBEDDING_OLLAMA_MODEL=nomic-embed-text sunwell ...
    """
    pass


@config.command()
@click.option("--path", type=click.Path(), help="Config file path to show")
def show(path: str | None) -> None:
    """Show current configuration.

    Displays all configuration values with their current settings,
    including which files are active.

    Examples:
        sunwell config show
        sunwell config show --path ~/.sunwell/config.yaml
    """
    cfg = load_config(path) if path else get_config()

    console.print(Panel("[bold]Sunwell Configuration[/bold]", border_style="cyan"))

    # Simulacrum config
    console.print("\n[cyan]Simulacrum[/cyan]")
    console.print(f"  Base path: {cfg.simulacrum.base_path}")

    console.print("\n  [dim]Spawn Policy:[/dim]")
    console.print(f"    Enabled: {cfg.simulacrum.spawn.enabled}")
    console.print(f"    Novelty threshold: {cfg.simulacrum.spawn.novelty_threshold}")
    console.print(f"    Min queries before spawn: {cfg.simulacrum.spawn.min_queries_before_spawn}")
    console.print(f"    Domain coherence: {cfg.simulacrum.spawn.domain_coherence_threshold}")
    console.print(f"    Max headspaces: {cfg.simulacrum.spawn.max_simulacrums}")

    console.print("\n  [dim]Lifecycle Policy:[/dim]")
    console.print(f"    Stale days: {cfg.simulacrum.lifecycle.stale_days}")
    console.print(f"    Archive days: {cfg.simulacrum.lifecycle.archive_days}")
    console.print(f"    Auto archive: {cfg.simulacrum.lifecycle.auto_archive}")

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


@config.command()
@click.option(
    "--path",
    type=click.Path(),
    default=".sunwell/config.yaml",
    help="Config file path (default: .sunwell/config.yaml)",
)
@click.option("--global", "global_config", is_flag=True, help="Create in ~/.sunwell/ instead")
def init(path: str, global_config: bool) -> None:
    """Create default config file.

    Creates a well-documented configuration file with all available
    options and their default values.

    Examples:
        sunwell config init                    # Create .sunwell/config.yaml
        sunwell config init --global           # Create ~/.sunwell/config.yaml
        sunwell config init --path custom.yaml
    """
    config_path = Path.home() / ".sunwell" / "config.yaml" if global_config else path
    saved_path = save_default_config(config_path)
    console.print(f"[green]✓[/green] Config file created: {saved_path}")
    console.print("\n[dim]Edit this file to customize Sunwell behavior.[/dim]")


@config.command()
@click.argument("key")
@click.option("--path", type=click.Path(), help="Config file path")
def get(key: str, path: str | None) -> None:
    """Get a configuration value.

    Use dot notation to access nested values.

    Examples:
        sunwell config get model.default_provider
        sunwell config get embedding.ollama_model
        sunwell config get naaru.wisdom
        sunwell config get headspace.spawn.enabled
    """
    cfg = load_config(path) if path else get_config()

    try:
        value = _get_nested(cfg, key)
        # Print value without Rich formatting for scripting
        click.echo(value)
    except KeyError:
        console.print(f"[red]✗[/red] Key not found: {key}")
        console.print("\n[dim]Available top-level keys:[/dim]")
        console.print("  model, embedding, headspace, naaru, binding, lens, ollama")
        raise SystemExit(1) from None


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--path",
    type=click.Path(),
    default=".sunwell/config.yaml",
    help="Config file to modify (default: .sunwell/config.yaml)",
)
@click.option("--global", "global_config", is_flag=True, help="Modify ~/.sunwell/config.yaml")
def set_value(key: str, value: str, path: str, global_config: bool) -> None:
    """Set a configuration value.

    Creates or updates the config file with the specified value.
    Use dot notation for nested keys.

    Type conversion:
    - "true"/"false" → boolean
    - numeric strings → int/float
    - everything else → string

    Examples:
        sunwell config set model.default_provider anthropic
        sunwell config set model.default_model claude-sonnet-4-20250514
        sunwell config set embedding.prefer_local false
        sunwell config set naaru.harmonic_candidates 7
    """
    import yaml

    config_path = Path.home() / ".sunwell" / "config.yaml" if global_config else Path(path)

    # Load existing config or create empty
    if config_path.exists():
        with config_path.open() as f:
            data = yaml.safe_load(f) or {}
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    # Parse value type
    parsed_value: str | bool | int | float
    if value.lower() == "true":
        parsed_value = True
    elif value.lower() == "false":
        parsed_value = False
    elif value.isdigit():
        parsed_value = int(value)
    elif value.replace(".", "").isdigit() and value.count(".") == 1:
        parsed_value = float(value)
    else:
        parsed_value = value

    # Set nested value
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = parsed_value

    # Save
    with config_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]✓[/green] Set {key} = {parsed_value}")
    console.print(f"[dim]Updated: {config_path}[/dim]")


@config.command()
@click.argument("key")
@click.option(
    "--path",
    type=click.Path(),
    default=".sunwell/config.yaml",
    help="Config file to modify (default: .sunwell/config.yaml)",
)
@click.option("--global", "global_config", is_flag=True, help="Modify ~/.sunwell/config.yaml")
def unset(key: str, path: str, global_config: bool) -> None:
    """Remove a configuration override.

    Removes the specified key from the config file, reverting to
    the default value.

    Examples:
        sunwell config unset model.default_provider
        sunwell config unset embedding.prefer_local --global
    """
    import yaml

    config_path = Path.home() / ".sunwell" / "config.yaml" if global_config else Path(path)

    if not config_path.exists():
        console.print(f"[yellow]![/yellow] Config file not found: {config_path}")
        return

    with config_path.open() as f:
        data = yaml.safe_load(f) or {}

    # Navigate to parent and delete key
    parts = key.split(".")
    current = data
    try:
        for part in parts[:-1]:
            current = current[part]
        if parts[-1] in current:
            del current[parts[-1]]
            # Save
            with config_path.open("w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            console.print(f"[green]✓[/green] Removed: {key}")
            console.print(f"[dim]Updated: {config_path}[/dim]")
        else:
            console.print(f"[yellow]![/yellow] Key not found in config: {key}")
    except (KeyError, TypeError):
        console.print(f"[yellow]![/yellow] Key not found in config: {key}")


@config.command()
@click.option("--binding", "-b", help="Show effective config for a specific binding")
def effective(binding: str | None) -> None:
    """Show effective configuration with sources.

    Displays where each setting comes from (code default, config file,
    binding, or CLI override). This helps debug configuration issues.

    Examples:
        sunwell config effective              # Show global effective config
        sunwell config effective -b coder     # Show config for 'coder' binding
    """
    from sunwell.foundation.binding import BindingManager
    from sunwell.foundation.types.config import ModelConfig

    cfg = get_config()
    
    # Code defaults for comparison
    code_defaults = ModelConfig()
    
    console.print(Panel("[bold]Effective Configuration[/bold]", border_style="cyan"))
    
    # Priority explanation
    console.print("\n[dim]Priority (highest to lowest):[/dim]")
    console.print("  [cyan]1.[/cyan] CLI flags (--model, --provider)")
    console.print("  [cyan]2.[/cyan] Binding file (~/.sunwell/bindings/)")
    console.print("  [cyan]3.[/cyan] Config file (~/.sunwell/config.toml or .yaml)")
    console.print("  [cyan]4.[/cyan] Code defaults")
    
    console.print("\n[cyan]Model Settings[/cyan]")
    
    # Determine sources for each setting
    def get_source(value: str, config_value: str, code_default: str) -> str:
        """Determine where a value came from."""
        if value != config_value and value != code_default:
            return "[yellow]binding[/yellow]"
        elif config_value != code_default:
            return "[green]config[/green]"
        else:
            return "[dim]default[/dim]"
    
    # If binding specified, load it
    if binding:
        manager = BindingManager()
        b = manager.get(binding)
        if b:
            console.print(f"\n  [bold]Binding:[/bold] {b.name}")
            console.print(f"  [bold]File:[/bold] ~/.sunwell/bindings/global/{b.name}.json")
            console.print()
            
            # Show binding values with sources
            source = "[yellow]binding[/yellow]"
            console.print(f"  provider: {b.provider:<20} [{source}]")
            console.print(f"  model: {b.model:<23} [{source}]")
            console.print(f"  tools_enabled: {str(b.tools_enabled):<13} [{source}]")
            console.print(f"  trust_level: {b.trust_level:<15} [{source}]")
            
            if b.lens_path:
                console.print(f"  lens_path: {b.lens_path}")
        else:
            console.print(f"\n  [red]✗[/red] Binding not found: {binding}")
            console.print("  [dim]Available bindings:[/dim]")
            for b in manager.list_all():
                console.print(f"    - {b.name}")
            return
    else:
        # Check if config file explicitly sets these values
        import yaml
        config_has_provider = False
        config_has_model = False
        
        for config_file in [
            Path(".sunwell/config.yaml"),
            Path.home() / ".sunwell" / "config.yaml",
        ]:
            if config_file.exists():
                try:
                    with config_file.open() as f:
                        raw_config = yaml.safe_load(f) or {}
                    model_section = raw_config.get("model", {})
                    if "default_provider" in model_section:
                        config_has_provider = True
                    if "default_model" in model_section:
                        config_has_model = True
                except Exception:
                    pass
        
        # Determine sources - show [config] if explicitly set, even if matches default
        if config_has_provider:
            provider_source = "[green]config[/green]"
        elif cfg.model.default_provider != code_defaults.default_provider:
            provider_source = "[green]config[/green]"
        else:
            provider_source = "[dim]default[/dim]"
            
        if config_has_model:
            model_source = "[green]config[/green]"
        elif cfg.model.default_model != code_defaults.default_model:
            model_source = "[green]config[/green]"
        else:
            model_source = "[dim]default[/dim]"
        
        console.print(f"  default_provider: {cfg.model.default_provider:<15} [{provider_source}]")
        console.print(f"  default_model: {cfg.model.default_model:<18} [{model_source}]")
    
    # Config file locations
    console.print("\n[cyan]Config Files[/cyan]")
    
    # Check for config files
    toml_global = Path.home() / ".sunwell" / "config.toml"
    yaml_global = Path.home() / ".sunwell" / "config.yaml"
    toml_local = Path(".sunwell/config.toml")
    yaml_local = Path(".sunwell/config.yaml")
    
    files_found = []
    if toml_local.exists():
        files_found.append(("local", str(toml_local)))
        console.print(f"  [green]✓[/green] {toml_local} (project)")
    if yaml_local.exists():
        files_found.append(("local", str(yaml_local)))
        console.print(f"  [green]✓[/green] {yaml_local} (project)")
    if toml_global.exists():
        files_found.append(("global", str(toml_global)))
        console.print(f"  [green]✓[/green] {toml_global} (user)")
    if yaml_global.exists():
        files_found.append(("global", str(yaml_global)))
        console.print(f"  [green]✓[/green] {yaml_global} (user)")
    
    if not files_found:
        console.print("  [dim]○[/dim] No config files found (using code defaults)")
        console.print("  [dim]  Run: sunwell config init --global[/dim]")
    
    # Bindings summary
    console.print("\n[cyan]Bindings[/cyan]")
    bindings_dir = Path.home() / ".sunwell" / "bindings" / "global"
    if bindings_dir.exists():
        binding_files = list(bindings_dir.glob("*.json"))
        console.print(f"  Found: {len(binding_files)} bindings in ~/.sunwell/bindings/global/")
        if binding_files and not binding:
            console.print("  [dim]Run: sunwell config effective -b <name> to see binding details[/dim]")
    else:
        console.print("  [dim]○[/dim] No bindings directory")


@config.command()
@click.option(
    "--path",
    type=click.Path(),
    default=".sunwell/config.yaml",
    help="Config file to display",
)
@click.option("--global", "global_config", is_flag=True, help="Show ~/.sunwell/config.yaml")
def edit(path: str, global_config: bool) -> None:
    """Display config file for editing.

    Shows the raw YAML content of the config file with syntax highlighting.
    Use your preferred editor to make changes.

    Examples:
        sunwell config edit
        sunwell config edit --global
    """
    config_path = Path.home() / ".sunwell" / "config.yaml" if global_config else Path(path)

    if not config_path.exists():
        console.print(f"[yellow]![/yellow] Config file not found: {config_path}")
        console.print("[dim]Run 'sunwell config init' to create one.[/dim]")
        return

    content = config_path.read_text()
    syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
    console.print(f"[dim]File: {config_path}[/dim]\n")
    console.print(syntax)
