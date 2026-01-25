"""Shared helper functions for CLI commands."""


import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from sunwell.foundation.threading import is_free_threaded

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

console = Console()
# RFC-053: Separate stderr console for warnings (keeps stdout clean for NDJSON)
stderr_console = Console(stderr=True)


# =============================================================================
# Workspace Context Building (RFC-126)
# =============================================================================


def build_workspace_context(cwd: Path | None = None, use_cache: bool = True) -> dict[str, str | list[tuple[str, str]] | list[str]]:
    """Build workspace context dict for agent orientation.

    Returns a dict with:
    - path: Workspace path
    - name: Project name
    - type: Detected project type (python, javascript, etc.)
    - framework: Detected framework (fastapi, flask, react, etc.)
    - key_files: List of (filename, preview) tuples
    - entry_points: List of entry point files
    - tree: Directory tree string

    Args:
        cwd: Working directory (defaults to Path.cwd())
        use_cache: Whether to use cached context from .sunwell/context.json
    """
    if cwd is None:
        cwd = Path.cwd()

    cache_path = cwd / ".sunwell" / "context.json"

    # Try cache first
    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            # Validate cache has expected keys
            if cached.get("path") and cached.get("name"):
                return cached
        except (json.JSONDecodeError, OSError):
            pass  # Cache invalid, rebuild

    # Detect project type and framework
    ptype, framework = _detect_project_type(cwd)

    # Find key files
    key_files = _find_key_files(cwd)

    # Find entry points
    entry_points = _find_entry_points(cwd, ptype) if ptype != "unknown" else []

    # Build directory tree
    tree = _build_directory_tree(cwd)

    context = {
        "path": str(cwd),
        "name": cwd.name,
        "type": ptype,
        "framework": framework,
        "key_files": [(k, v) for k, v in key_files],
        "entry_points": entry_points,
        "tree": tree,
    }

    # Cache for next time
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(context, indent=2))
    except OSError:
        pass  # Non-fatal

    return context


def format_workspace_context(ctx: dict[str, str | list[tuple[str, str]] | list[str]]) -> str:
    """Format context dict into markdown for system prompt / agent context."""
    lines = [
        "## Workspace Context",
        "",
        f"**Project**: `{ctx['name']}` ({ctx['path']})",
    ]

    # Project type badge
    ptype = ctx.get("type", "unknown")
    framework = ctx.get("framework")
    if ptype != "unknown":
        type_line = f"**Type**: {ptype.title()}"
        if framework:
            type_line += f" ({framework})"
        lines.append(type_line)

    lines.append("")

    # Key files with preview
    key_files = ctx.get("key_files", [])
    if key_files:
        lines.append("### Key Files")
        for name, preview in key_files[:3]:  # Limit to 3 for prompt size
            lines.append(f"\n**{name}**:")
            lines.append("```")
            lines.append(preview)
            lines.append("```")
        lines.append("")

    # Entry points
    entry_points = ctx.get("entry_points", [])
    if entry_points:
        lines.append(f"**Entry points**: {', '.join(f'`{e}`' for e in entry_points)}")
        lines.append("")

    # Directory tree
    tree = ctx.get("tree", "")
    if tree:
        lines.append("### Structure")
        lines.append("```")
        lines.append(tree)
        lines.append("```")

    lines.append("")
    lines.append("You can reference files by their relative paths.")

    return "\n".join(lines)


def _detect_project_type(cwd: Path) -> tuple[str, str | None]:
    """Detect project type and framework from directory contents."""
    ptype = "unknown"
    framework = None

    # Python indicators
    if (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
        ptype = "python"
        # Framework detection
        if (cwd / "manage.py").exists():
            framework = "django"
        elif any(cwd.rglob("**/flask*")):
            framework = "flask"
        elif (cwd / "main.py").exists():
            try:
                content = (cwd / "main.py").read_text(errors="ignore")[:2000]
                if "fastapi" in content.lower():
                    framework = "fastapi"
            except OSError:
                pass

    # JavaScript/TypeScript indicators
    elif (cwd / "package.json").exists():
        ptype = "javascript"
        try:
            pkg = json.loads((cwd / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "react" in deps:
                framework = "react"
            elif "vue" in deps:
                framework = "vue"
            elif "next" in deps:
                framework = "next.js"
            elif "svelte" in deps:
                framework = "svelte"
            elif "express" in deps:
                framework = "express"
        except (json.JSONDecodeError, OSError):
            pass

    # Go indicators
    elif (cwd / "go.mod").exists():
        ptype = "go"

    # Rust indicators
    elif (cwd / "Cargo.toml").exists():
        ptype = "rust"

    return ptype, framework


def _find_key_files(cwd: Path) -> list[tuple[str, str]]:
    """Find and preview key project files."""
    key_files: list[tuple[str, str]] = []

    # Priority files to check
    candidates = [
        "README.md",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        ".sunwell/project.toml",
    ]

    for filename in candidates:
        filepath = cwd / filename
        if filepath.exists():
            try:
                content = filepath.read_text(errors="ignore")
                # Preview first 500 chars
                preview = content[:500]
                if len(content) > 500:
                    preview += "\n... (truncated)"
                key_files.append((filename, preview))
            except OSError:
                pass

        if len(key_files) >= 3:
            break

    return key_files


def _find_entry_points(cwd: Path, ptype: str) -> list[str]:
    """Find likely entry point files based on project type."""
    entry_points: list[str] = []

    if ptype == "python":
        candidates = ["main.py", "app.py", "run.py", "__main__.py", "cli.py"]
        for c in candidates:
            if (cwd / c).exists():
                entry_points.append(c)
        # Check src/ directory
        src = cwd / "src"
        if src.exists():
            for c in candidates:
                if (src / c).exists():
                    entry_points.append(f"src/{c}")

    elif ptype == "javascript":
        candidates = ["index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts"]
        for c in candidates:
            if (cwd / c).exists():
                entry_points.append(c)
        # Check src/ directory
        src = cwd / "src"
        if src.exists():
            for c in candidates:
                if (src / c).exists():
                    entry_points.append(f"src/{c}")

    return entry_points[:5]  # Limit


def _build_directory_tree(cwd: Path, max_depth: int = 3, max_items: int = 50) -> str:
    """Build a simple directory tree string."""
    lines: list[str] = []
    count = 0

    # Directories to skip
    skip_dirs = {
        ".git", ".sunwell", "__pycache__", "node_modules", ".venv", "venv",
        "dist", "build", ".next", ".svelte-kit", "target", ".pytest_cache",
    }

    def walk(path: Path, prefix: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= max_items:
            return

        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return

        # Filter and limit
        dirs = [i for i in items if i.is_dir() and i.name not in skip_dirs]
        files = [i for i in items if i.is_file() and not i.name.startswith(".")]

        visible = dirs[:10] + files[:15]  # Limit per level

        for i, item in enumerate(visible):
            if count >= max_items:
                lines.append(f"{prefix}... (truncated)")
                return

            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if item.is_dir():
                lines.append(f"{prefix}{connector}{item.name}/")
                count += 1
                walk(item, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{item.name}")
                count += 1

    lines.append(f"{cwd.name}/")
    walk(cwd, "", 1)

    return "\n".join(lines)


def check_free_threading(quiet: bool = False) -> bool:
    """Check if running on free-threaded Python and warn if not.

    Returns True if free-threaded, False otherwise.
    Warnings are printed to stderr to keep stdout clean for --json mode.
    """
    if is_free_threaded():
        return True

    if not quiet and os.environ.get("SUNWELL_NO_GIL_WARNING") != "1":
        # RFC-053: Print to stderr so --json mode isn't corrupted
        stderr_console.print(
            "[yellow]⚠️  Running on standard Python (GIL enabled)[/yellow]"
        )
        stderr_console.print(
            "[dim]   For optimal performance, use Python 3.14t (free-threaded):[/dim]"
        )
        stderr_console.print(
            "[dim]   /usr/local/bin/python3.14t -m sunwell chat[/dim]"
        )
        stderr_console.print(
            "[dim]   Set SUNWELL_NO_GIL_WARNING=1 to suppress this message.[/dim]"
        )
        stderr_console.print()

    return False


def format_args(args: dict[str, str | int | float | bool | None]) -> str:
    """Format tool call arguments for display."""
    parts = []
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 50:
            v = v[:47] + "..."
        parts.append(f"{k}={repr(v)}")
    return ", ".join(parts)


def load_dotenv() -> None:
    """Load .env file if it exists and is readable."""
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        # Remove quotes if present
                        value = value.strip().strip("'\"")
                        os.environ.setdefault(key.strip(), value)
        except PermissionError:
            # Can't read .env (sandboxed environment, etc.) - continue without it
            pass
        except OSError:
            # Other file access issues - continue without it
            pass


def create_model(provider: str, model_name: str) -> "ModelProtocol":
    """Create model instance based on provider."""
    if provider == "mock":
        from sunwell.models import MockModel
        return MockModel()

    elif provider == "anthropic":
        from sunwell.models import AnthropicModel
        return AnthropicModel(
            model=model_name,
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    elif provider == "openai":
        from sunwell.models import OpenAIModel
        return OpenAIModel(
            model=model_name,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )

    elif provider == "ollama":
        from sunwell.foundation.config import get_config
        from sunwell.models import OllamaModel

        cfg = get_config()
        return OllamaModel(
            model=model_name,
            use_native_api=cfg.naaru.use_native_ollama_api,
        )

    else:
        console.print(f"[red]Unknown provider:[/red] {provider}")
        console.print("Available: anthropic, openai, ollama, mock")
        import sys
        sys.exit(1)


def resolve_model(
    provider_override: str | None = None,
    model_override: str | None = None,
) -> "ModelProtocol":
    """Resolve model from CLI overrides or config defaults.

    Priority:
    1. CLI overrides (--provider, --model)
    2. Config defaults (model.default_provider, model.default_model)
    3. Hardcoded fallbacks (ollama, gemma3:4b)

    Returns:
        Model instance ready for use.
    """
    from sunwell.foundation.config import get_config

    cfg = get_config()

    # Resolve provider
    provider = provider_override
    if not provider and cfg and hasattr(cfg, "model"):
        provider = cfg.model.default_provider
    if not provider:
        provider = "ollama"

    # Resolve model name
    model_name = model_override
    if not model_name and cfg and hasattr(cfg, "model"):
        model_name = cfg.model.default_model
    if not model_name:
        # Provider-specific defaults
        model_name = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
            "mock": "mock",
        }.get(provider, "gemma3:4b")

    return create_model(provider, model_name)


def display_execution_stats(result) -> None:
    """Display execution statistics."""
    table = Table(title="Execution Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Tier", result.tier.name)
    table.add_row("Confidence", f"{result.confidence.score:.0%} {result.confidence.level}")
    table.add_row("Retrieved Heuristics", str(len(result.retrieved_components)))
    table.add_row("Retrieved Code", str(len(result.retrieved_code)))
    table.add_row("Validations", str(len(result.validation_results)))
    table.add_row("Refinements", str(result.refinement_count))

    if result.token_usage:
        table.add_row("Tokens (prompt)", str(result.token_usage.prompt_tokens))
        table.add_row("Tokens (completion)", str(result.token_usage.completion_tokens))

    console.print(table)

    # Show retrieved code if any
    if result.retrieved_code:
        console.print("\n[cyan]Code Context Used:[/cyan]")
        for ref in result.retrieved_code:
            console.print(f"  [blue]• {ref}[/blue]")

    # Show validation results
    if result.validation_results:
        console.print("\n[bold]Validation Results:[/bold]")
        for v in result.validation_results:
            console.print(f"  {v.to_display()}")

    # Show persona results
    if result.persona_results:
        console.print("\n[bold]Persona Results:[/bold]")
        for p in result.persona_results:
            status = "✅" if p.approved else "⚠️"
            console.print(f"  {status} {p.persona_name}")
