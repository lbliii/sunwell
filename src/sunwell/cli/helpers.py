"""Shared helper functions for CLI commands."""


import os
from pathlib import Path

from rich.console import Console
from rich.table import Table

from sunwell.core.freethreading import is_free_threaded

console = Console()
# RFC-053: Separate stderr console for warnings (keeps stdout clean for NDJSON)
stderr_console = Console(stderr=True)


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


def format_args(args: dict) -> str:
    """Format tool call arguments for display."""
    parts = []
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 50:
            v = v[:47] + "..."
        parts.append(f"{k}={repr(v)}")
    return ", ".join(parts)


def load_dotenv() -> None:
    """Load .env file if it exists."""
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    # Remove quotes if present
                    value = value.strip().strip("'\"")
                    os.environ.setdefault(key.strip(), value)


def create_model(provider: str, model_name: str):
    """Create model instance based on provider."""
    if provider == "mock":
        from sunwell.models.mock import MockModel
        return MockModel()

    elif provider == "anthropic":
        from sunwell.models.anthropic import AnthropicModel
        return AnthropicModel(model=model_name)

    elif provider == "openai":
        from sunwell.models.openai import OpenAIModel
        return OpenAIModel(model=model_name)

    elif provider == "ollama":
        from sunwell.config import get_config
        from sunwell.models.ollama import OllamaModel

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
