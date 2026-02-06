"""Setup command - Unified project initialization (RFC-126).

One command to rule them all:
    sunwell setup

This replaces the fragmented setup flow:
- OLD: sunwell project init + sunwell setup (bindings) + sunwell config
- NEW: sunwell setup (does everything)

Idempotent and fast - safe to run multiple times.

Extended with MCP host configuration:
    sunwell setup cursor   # Configure Sunwell as MCP server for Cursor
    sunwell setup claude   # Configure Sunwell as MCP server for Claude Desktop
"""


import json
import sys
from pathlib import Path

import click

from sunwell.foundation.utils import normalize_path, safe_yaml_dump, safe_yaml_load
from sunwell.interface.cli.core.theme import create_sunwell_console

console = create_sunwell_console()


# Use a group with invoke_without_command=True to allow both:
# - sunwell setup (runs default project setup)
# - sunwell setup cursor (runs MCP host setup)
@click.group(invoke_without_command=True)
@click.argument("path", type=click.Path(), default=".", required=False)
@click.option("--provider", "-p", default=None, help="LLM provider (default: config/ollama)")
@click.option("--model", "-m", default=None, help="Model name (auto-selected based on provider)")
@click.option("--trust", type=click.Choice(["read_only", "workspace", "shell"]),
              default="workspace", help="Default tool trust level")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing configuration")
@click.option("--minimal", is_flag=True, help="Skip lens bindings (project only)")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
@click.pass_context
def setup(
    ctx: click.Context,
    path: str,
    provider: str | None,
    model: str | None,
    trust: str,
    force: bool,
    minimal: bool,
    quiet: bool,
) -> None:
    """Initialize Sunwell for this project or configure MCP hosts.

    One command that handles everything:
    - Creates .sunwell/ directory with project manifest
    - Builds workspace context cache for fast startup
    - Registers project globally for easy access
    - Optionally sets up lens bindings

    Safe to run multiple times - only updates what's needed.

    \b
    Examples:
        sunwell setup                    # Setup current directory
        sunwell setup ~/projects/myapp   # Setup specific path
        sunwell setup --provider openai  # Use OpenAI
        sunwell setup --minimal          # Just project, no bindings
        sunwell setup cursor             # Configure MCP for Cursor IDE
        sunwell setup claude             # Configure MCP for Claude Desktop
    """
    # If a subcommand was invoked, don't run default setup
    if ctx.invoked_subcommand is not None:
        return
    from sunwell.foundation.config import get_config
    from sunwell.interface.cli.helpers import build_workspace_context

    project_path = normalize_path(path)

    # Ensure directory exists
    if not project_path.exists():
        if not quiet:
            console.print(f"[void.purple]✗ Not found:[/void.purple] {project_path}")
            console.print("[neutral.dim]Create the directory first.[/neutral.dim]")
        sys.exit(1)

    if not quiet:
        console.print(f"\n[sunwell.heading]✦ Setting up Sunwell[/] in {project_path.name}/")
        console.print()

    # Track what we did
    actions: list[str] = []

    # =========================================================================
    # Step 1: Project initialization (.sunwell/project.toml)
    # =========================================================================
    sunwell_dir = project_path / ".sunwell"
    manifest_path = sunwell_dir / "project.toml"

    if manifest_path.exists() and not force:
        if not quiet:
            console.print("[neutral.dim]✓ Project manifest exists[/neutral.dim]")
    else:
        from sunwell.knowledge.project import ProjectValidationError, init_project

        try:
            proj = init_project(
                root=project_path,
                project_id=project_path.name,
                name=project_path.name,
                trust=trust,
                register=True,
            )
            if not quiet:
                console.print(f"[holy.success]✓[/] Initialized: {proj.id}")
            actions.append("project_init")
        except ProjectValidationError as e:
            if "already initialized" in str(e).lower():
                if not quiet:
                    console.print("[neutral.dim]✓ Project already initialized[/neutral.dim]")
            else:
                console.print(f"[void.purple]✗ Error:[/void.purple] {e}")
                sys.exit(1)

    # =========================================================================
    # Step 2: Build workspace context cache (for fast goal processing)
    # =========================================================================
    context_cache = sunwell_dir / "context.json"

    # Always rebuild if forced, otherwise only if missing or stale
    rebuild_context = force or not context_cache.exists()

    if rebuild_context:
        try:
            ctx = build_workspace_context(project_path, use_cache=False)
            if not quiet:
                ptype = ctx.get("type", "unknown")
                framework = ctx.get("framework")
                type_str = ptype.title()
                if framework:
                    type_str += f" ({framework})"
                console.print(f"[holy.success]✓[/holy.success] Detected: {type_str}")
                if ctx.get("key_files"):
                    files = [kf[0] for kf in ctx["key_files"][:3]]
                    console.print(f"[neutral.dim]  Key files: {', '.join(files)}[/neutral.dim]")
            actions.append("context_cache")
        except Exception as e:
            if not quiet:
                console.print(f"[holy.gold]△[/holy.gold] Could not build context: {e}")
    else:
        if not quiet:
            console.print("[neutral.dim]✓ Workspace context cached[/neutral.dim]")

    # =========================================================================
    # Step 3: Resolve model configuration
    # =========================================================================
    cfg = get_config()

    # Resolve provider
    resolved_provider = provider
    if not resolved_provider and cfg and hasattr(cfg, "model"):
        resolved_provider = cfg.model.default_provider
    if not resolved_provider:
        resolved_provider = "ollama"

    # Resolve model
    resolved_model = model
    if not resolved_model and cfg and hasattr(cfg, "model"):
        resolved_model = cfg.model.default_model
    if not resolved_model:
        resolved_model = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "llama3.1:8b",
        }.get(resolved_provider, "llama3.1:8b")

    if not quiet:
        # Model info is important - show prominently
        console.print(f"[bold cyan]◆ Model:[/bold cyan] {resolved_provider}:{resolved_model}")

    # =========================================================================
    # Step 4: Lens bindings (optional, skip with --minimal)
    # =========================================================================
    if not minimal:
        from sunwell.foundation.binding import BindingManager

        manager = BindingManager()
        default_binding = manager.get_default()

        if default_binding and not force:
            if not quiet:
                console.print(f"[neutral.dim]✓ Default: {default_binding.name}[/neutral.dim]")
        else:
            # Find lenses directory
            lens_candidates = [
                project_path / "lenses",
                Path(__file__).parent.parent.parent.parent / "lenses",
                Path.home() / ".sunwell" / "lenses",
            ]
            lens_path = None
            for c in lens_candidates:
                if c.exists() and list(c.glob("*.lens")):
                    lens_path = c
                    break

            if lens_path:
                bindings_created = _setup_default_bindings(
                    manager, lens_path, resolved_provider, resolved_model,
                    force, quiet, project_path,
                )
                if bindings_created:
                    actions.append("bindings")
            elif not quiet:
                console.print("[neutral.dim]  No lenses found, skipping bindings[/neutral.dim]")

    # =========================================================================
    # Step 5: Create .gitignore entries
    # =========================================================================
    gitignore_path = sunwell_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = """# Sunwell local state (not for version control)
context.json
memory/
cache/
*.log

# Keep these in version control:
# project.toml - project configuration
# team/ - shared team knowledge
"""
        try:
            gitignore_path.write_text(gitignore_content)
            actions.append("gitignore")
        except OSError:
            pass

    # =========================================================================
    # Summary (RFC-131: Holy Light styling)
    # =========================================================================
    if not quiet:
        console.print()
        if actions:
            console.print("[holy.success]★ Setup complete[/holy.success]")
        else:
            console.print("[sunwell.heading]✓ Already configured[/sunwell.heading]")

        console.print()
        console.print("[sunwell.heading]Get started:[/sunwell.heading]")
        console.print('  sunwell "what is this project?"')
        console.print('  sunwell "add tests for the main module"')


def _setup_default_bindings(
    manager,
    lens_path: Path,
    provider: str,
    model: str,
    force: bool,
    quiet: bool,
    project_path: Path,
) -> bool:
    """Set up default lens bindings. Returns True if any created."""

    # Default bindings - minimal set
    default_bindings = [
        {
            "name": "coder",
            "lens": "coder-v2.lens",
            "description": "Code generation & modification",
            "tier": 1,
            "is_default": True,
        },
        {
            "name": "writer",
            "lens": "tech-writer-v2.lens",
            "description": "Technical documentation",
            "tier": 1,
        },
    ]

    created = []
    default_binding_name: str | None = None

    for binding_def in default_bindings:
        name = binding_def["name"]
        lens_file = lens_path / binding_def["lens"]

        if not lens_file.exists():
            continue

        existing = manager.get(name)
        if existing and not force:
            # If this is the default and it exists, note it
            if binding_def.get("is_default"):
                default_binding_name = name
            continue

        try:
            manager.create(
                name=name,
                lens_uri=str(lens_file),
                provider=provider,
                model=model,
                tier=binding_def.get("tier", 1),
            )

            if binding_def.get("is_default"):
                default_binding_name = name

            created.append(name)
        except Exception:
            pass

    # Write default to user-global config.yaml (not project-local)
    # This ensures it works across all projects
    if default_binding_name:
        _update_global_config_default(default_binding_name)

    if created and not quiet:
        console.print(f"[holy.success]✓[/holy.success] Created bindings: {', '.join(created)}")

    return bool(created)


def _update_global_config_default(binding_name: str) -> None:
    """Update the default binding in user-global config.yaml."""
    config_path = Path.home() / ".sunwell" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or start fresh
    config_data: dict = {}
    if config_path.exists():
        try:
            config_data = safe_yaml_load(config_path) or {}
        except Exception:
            pass

    # Update binding.default
    if "binding" not in config_data:
        config_data["binding"] = {}
    config_data["binding"]["default"] = binding_name

    # Write back
    safe_yaml_dump(config_data, config_path)


# =============================================================================
# MCP Host Setup Commands
# =============================================================================


@setup.command("cursor")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing configuration")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
def setup_cursor(force: bool, quiet: bool) -> None:
    """Configure Sunwell as MCP server for Cursor IDE.

    Writes configuration to ~/.cursor/mcp.json so Cursor can use
    Sunwell's lens system via MCP (Model Context Protocol).

    \b
    After running this command:
    1. Restart Cursor
    2. Sunwell tools will be available: sunwell_lens, sunwell_list, sunwell_route

    \b
    Examples:
        sunwell setup cursor              # Configure MCP for Cursor
        sunwell setup cursor --force      # Overwrite existing config
    """
    _setup_mcp_host("cursor", force, quiet)


@setup.command("claude")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing configuration")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
def setup_claude(force: bool, quiet: bool) -> None:
    """Configure Sunwell as MCP server for Claude Desktop.

    Writes configuration to ~/Library/Application Support/Claude/claude_desktop_config.json
    (on macOS) so Claude Desktop can use Sunwell's lens system via MCP.

    \b
    After running this command:
    1. Restart Claude Desktop
    2. Sunwell tools will be available: sunwell_lens, sunwell_list, sunwell_route

    \b
    Examples:
        sunwell setup claude              # Configure MCP for Claude Desktop
        sunwell setup claude --force      # Overwrite existing config
    """
    _setup_mcp_host("claude", force, quiet)


def _setup_mcp_host(host: str, force: bool, quiet: bool) -> None:
    """Configure Sunwell as MCP server for a host.

    Args:
        host: Host name ("cursor" or "claude")
        force: Whether to overwrite existing config
        quiet: Suppress output
    """
    import shutil
    import sys as _sys

    # Determine config path based on host
    if host == "cursor":
        config_path = Path.home() / ".cursor" / "mcp.json"
    elif host == "claude":
        # macOS path for Claude Desktop
        if _sys.platform == "darwin":
            config_path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            )
        elif _sys.platform == "win32":
            config_path = (
                Path.home()
                / "AppData"
                / "Roaming"
                / "Claude"
                / "claude_desktop_config.json"
            )
        else:
            # Linux - best guess
            config_path = Path.home() / ".config" / "claude" / "claude_desktop_config.json"
    else:
        console.print(f"[void.purple]✗[/] Unknown host: {host}")
        _sys.exit(1)

    # Find sunwell-mcp command
    sunwell_mcp = shutil.which("sunwell-mcp")
    if not sunwell_mcp:
        # Try finding it via python -m
        sunwell_mcp = None

    # Build MCP server configuration
    if sunwell_mcp:
        server_config = {
            "command": sunwell_mcp,
            "args": [],
        }
    else:
        # Fallback to python -m sunwell.mcp
        python_path = _sys.executable
        server_config = {
            "command": python_path,
            "args": ["-m", "sunwell.mcp"],
        }

    if not quiet:
        console.print(f"\n[sunwell.heading]✦ Configuring Sunwell MCP for {host.title()}[/]")
        console.print()

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or create new
    existing_config: dict = {}
    if config_path.exists():
        try:
            existing_config = json.loads(config_path.read_text())
        except Exception:
            pass

    # Check if sunwell is already configured
    mcp_servers = existing_config.get("mcpServers", {})
    if "sunwell" in mcp_servers and not force:
        if not quiet:
            console.print("[neutral.dim]✓ Sunwell already configured[/neutral.dim]")
            console.print(f"[neutral.dim]  Config: {config_path}[/neutral.dim]")
            console.print("[neutral.dim]  Use --force to overwrite[/neutral.dim]")
        return

    # Add/update sunwell server config
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}
    existing_config["mcpServers"]["sunwell"] = server_config

    # Write config
    try:
        config_path.write_text(json.dumps(existing_config, indent=2))
        if not quiet:
            console.print(f"[holy.success]✓[/] Configured: {config_path}")
            console.print()
            console.print("[sunwell.heading]Next steps:[/sunwell.heading]")
            console.print(f"  1. Restart {host.title()}")
            console.print("  2. Sunwell tools will be available:")
            console.print("     - sunwell_lens(name) - Get lens expertise")
            console.print("     - sunwell_list() - List available lenses")
            console.print("     - sunwell_route(command) - Route shortcuts")
    except Exception as e:
        console.print(f"[void.purple]✗ Error writing config:[/void.purple] {e}")
        _sys.exit(1)
