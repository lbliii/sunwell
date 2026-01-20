"""Chat command - Interactive headspace chat session."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from sunwell.binding import BindingManager
from sunwell.cli.helpers import create_model
from sunwell.core.errors import SunwellError
from sunwell.core.types import LensReference
from sunwell.embedding import create_embedder
from sunwell.fount.client import FountClient
from sunwell.fount.resolver import LensResolver
from sunwell.schema.loader import LensLoader
from sunwell.spectrum.simulacrum.context.assembler import ContextAssembler
from sunwell.spectrum.simulacrum.core.store import SimulacrumStore

console = Console()


@click.command()
@click.argument("binding_or_lens", required=False)
@click.option("--session", "-s", help="Session name (creates new or resumes existing)")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--provider", "-p", default=None, help="Provider")
@click.option(
    "--memory-path", type=click.Path(), default=".sunwell/memory", help="Memory store path"
)
@click.option("--tools/--no-tools", default=None, help="Override tool calling (Agent mode)")
@click.option(
    "--trust",
    type=click.Choice(["discovery", "read_only", "workspace", "shell"]),
    default=None,
    help="Override tool trust level",
)
@click.option("--smart", is_flag=True, help="Enable Adaptive Model Selection")
@click.option(
    "--mirror", is_flag=True, help="Enable Mirror Neurons (self-introspection)"
)
@click.option(
    "--model-routing", is_flag=True, help="Enable Model-Aware Task Routing"
)
@click.option("--router-model", default=None, help="Tiny LLM for cognitive routing")
@click.option(
    "--naaru/--no-naaru",
    default=True,
    help=": Enable Naaru Shards for parallel processing",
)
def chat(
    binding_or_lens: str | None,
    session: str | None,
    model: str | None,
    provider: str | None,
    memory_path: str,
    tools: bool | None,
    trust: str | None,
    smart: bool,
    mirror: bool,
    model_routing: bool,
    router_model: str | None,
    naaru: bool,
) -> None:
    """Start an interactive headspace chat session.

    Uses your default binding if no argument given. Can also specify
    a binding name or lens path directly.

    Your headspace (learnings, dead ends, context) persists across:
    - Model switches: /switch anthropic:claude-sonnet-4-20250514
    - Session restarts: sunwell chat --session my-project

    Key commands:
    - /switch <provider:model>: Switch models mid-conversation
    - /branch <name>: Create a branch to try something
    - /dead-end: Mark current path as dead end
    - /learn <fact>: Add a persistent learning
    - /quit: Exit (auto-saves)

    Examples:

    sunwell chat # Uses default binding

    sunwell chat writer # Uses 'writer' binding

    sunwell chat lenses/tech-writer.lens # Direct lens path

    sunwell chat --session auth-debug # Named session

    # Mid-conversation: /switch anthropic:claude-sonnet-4-20250514
    """
    # Resolve binding/lens and settings
    lens_path, provider, model, session, tools_enabled, trust_level = _resolve_binding(
        binding_or_lens, provider, model, session, tools, trust
    )

    if lens_path is None:
        sys.exit(1)

    # Load lens
    lens = _load_lens(lens_path)
    if lens is None:
        sys.exit(1)

    # Initialize memory store
    store = SimulacrumStore(Path(memory_path))

    # Create or resume session
    dag = _init_session(store, session)

    # Create model and assembler
    llm = create_model(provider, model)
    embedder = create_embedder()

    assembler = ContextAssembler(
        dag=dag,
        embedder=embedder,
        summarizer=llm,
    )

    # Build system prompt from lens
    system_prompt = lens.to_context()

    # Display session info
    _display_session_info(lens, provider, model, session, tools_enabled, trust_level)

    # Import and run chat loop
    from sunwell.cli.chat.loop import chat_loop

    asyncio.run(
        chat_loop(
            dag=dag,
            store=store,
            assembler=assembler,
            initial_model=llm,
            initial_model_name=f"{provider}:{model}",
            system_prompt=system_prompt,
            tools_enabled=tools_enabled or False,
            trust_level=trust_level or "workspace",
            smart=smart,
            lens=lens,
            mirror_enabled=mirror,
            model_routing_enabled=model_routing,
            memory_path=Path(memory_path),
            naaru_enabled=naaru,
            identity_enabled=naaru,
        )
    )


def _resolve_binding(
    binding_or_lens: str | None,
    provider: str | None,
    model: str | None,
    session: str | None,
    tools: bool | None,
    trust: str | None,
) -> tuple[str | None, str, str, str | None, bool | None, str | None]:
    """Resolve binding/lens to settings."""
    manager = BindingManager()
    lens_path: str | None = None

    # Track if CLI overrode the provider
    cli_provider_override = provider is not None
    cli_model_override = model is not None

    # Tool settings (may be overridden by CLI flags)
    tools_enabled = tools
    trust_level = trust

    if binding_or_lens:
        # Check if it's a binding name first
        binding = manager.get(binding_or_lens)
        if binding:
            lens_path = binding.lens_path
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            if tools_enabled is None:
                tools_enabled = binding.tools_enabled
            if trust_level is None:
                trust_level = binding.trust_level
        elif Path(binding_or_lens).exists():
            lens_path = binding_or_lens
        else:
            console.print(
                f"[red]Not found:[/red] '{binding_or_lens}' is neither a binding nor a lens file"
            )
            console.print("[dim]List bindings: sunwell bind list[/dim]")
            return None, "", "", None, None, None
    else:
        # Try default binding
        binding = manager.get_default()
        if binding:
            lens_path = binding.lens_path
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            if tools_enabled is None:
                tools_enabled = binding.tools_enabled
            if trust_level is None:
                trust_level = binding.trust_level
        else:
            console.print("[yellow]No binding specified and no default set.[/yellow]")
            console.print()
            console.print("Options:")
            console.print("  1. Run [cyan]sunwell setup[/cyan] to create default bindings")
            console.print("  2. Specify a lens: [cyan]sunwell chat path/to/lens.lens[/cyan]")
            console.print(
                "  3. Create a binding: [cyan]sunwell bind create my-chat --lens my.lens[/cyan]"
            )
            return None, "", "", None, None, None

    # Set defaults
    provider = provider or "openai"
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
            "mock": "mock",
        }.get(provider, "gpt-4o")

    return lens_path, provider, model, session, tools_enabled, trust_level


def _load_lens(lens_path: str) -> object | None:
    """Load lens from path."""
    fount = FountClient()
    loader = LensLoader(fount_client=fount)
    resolver = LensResolver(loader=loader)

    try:
        source = str(lens_path)
        if not (source.startswith("/") or source.startswith("./") or source.startswith("../")):
            source = f"./{source}"

        ref = LensReference(source=source)
        return asyncio.run(resolver.resolve(ref))
    except SunwellError as e:
        console.print(f"[red]Error loading/resolving lens:[/red] {e.message}")
        return None


def _init_session(store: SimulacrumStore, session: str | None) -> object:
    """Initialize or resume session."""
    if session:
        try:
            dag = store.load_session(session)
            console.print(f"[green]✓ Resumed session:[/green] {session}")
            console.print(f"[dim]  {len(dag.turns)} turns, {len(dag.learnings)} learnings[/dim]")
        except FileNotFoundError:
            store.new_session(session)
            dag = store.get_dag()
            console.print(f"[green]✓ Created new session:[/green] {session}")
    else:
        session = store.new_session()
        dag = store.get_dag()
        console.print(f"[green]✓ New session:[/green] {session}")

    return dag


def _display_session_info(
    lens: object,
    provider: str,
    model: str,
    session: str | None,
    tools_enabled: bool | None,
    trust_level: str | None,
) -> None:
    """Display session information panel."""
    mode_label = "Agent" if tools_enabled else "Chat"
    mode_color = "green" if tools_enabled else "blue"
    trust_display = f" ({trust_level or 'workspace'})" if tools_enabled else ""

    console.print(
        Panel(
            f"[bold]{lens.metadata.name}[/bold] ({provider}:{model}): "
            f"[{mode_color}]{mode_label}{trust_display}[/{mode_color}]\n"
            f"Commands: /switch, /branch, /learn, /stats, /quit"
            + (" | /tools on/off" if not tools_enabled else ""),
            title=f"Session: {session}",
            border_style=mode_color,
        )
    )
