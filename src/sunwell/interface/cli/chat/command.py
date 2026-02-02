"""Chat command - Interactive headspace chat session.

Holy Light aesthetic (RFC-131): Golden accents radiating from the void.
"""


import asyncio
import sys
from pathlib import Path

import click
from rich.panel import Panel

from sunwell.core.types.types import LensReference
from sunwell.features.fount.client import FountClient
from sunwell.features.fount.resolver import LensResolver
from sunwell.foundation.binding import BindingManager
from sunwell.foundation.errors import SunwellError
from sunwell.foundation.schema.loader import LensLoader
from sunwell.interface.cli.core.theme import (
    CHARS_CHECKS,
    CHARS_STARS,
    create_sunwell_console,
    print_banner,
    render_error,
)
from sunwell.interface.cli.helpers import create_model
from sunwell.knowledge.embedding import create_embedder
from sunwell.memory.simulacrum.context.assembler import ContextAssembler
from sunwell.memory.simulacrum.core.store import SimulacrumStore

# Holy Light themed console
console = create_sunwell_console()


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
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging (shows model calls, intent classification, etc.)",
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
    debug: bool,
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
    # Configure debug logging if requested
    if debug:
        from sunwell.foundation.logging import configure_logging

        configure_logging(debug=True)

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

    # Use CLI flag if provided, otherwise respect binding's setting
    # Binding defaults to tools_enabled=True (manager.py:98)
    final_tools_enabled = tools if tools is not None else tools_enabled

    # Display session info
    _display_session_info(lens, provider, model, session, final_tools_enabled, trust_level)

    # Import and run chat loop
    from sunwell.interface.cli.chat.loop import chat_loop
    
    asyncio.run(
        chat_loop(
            dag=dag,
            store=store,
            assembler=assembler,
            initial_model=llm,
            initial_model_name=f"{provider}:{model}",
            system_prompt=system_prompt,
            tools_enabled=final_tools_enabled,
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
            lens_path = binding.get_lens_reference()
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
                f"[void.purple]{CHARS_CHECKS['fail']} Not found:[/void.purple] '{binding_or_lens}' is neither a binding nor a lens file"
            )
            console.print("[neutral.dim]List bindings: sunwell bind list[/neutral.dim]")
            return None, "", "", None, None, None
    else:
        # Try default binding
        binding = manager.get_default()
        if binding:
            lens_path = binding.get_lens_reference()
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            if tools_enabled is None:
                tools_enabled = binding.tools_enabled
            if trust_level is None:
                trust_level = binding.trust_level
        else:
            console.print(f"[void.indigo]{CHARS_STARS['progress']} No binding specified and no default set.[/void.indigo]")
            console.print()
            console.print("[neutral.text]Options:[/neutral.text]")
            console.print(f"  1. Run [holy.radiant]sunwell setup[/holy.radiant] to create default bindings")
            console.print(f"  2. Specify a lens: [holy.radiant]sunwell chat path/to/lens.lens[/holy.radiant]")
            console.print(
                f"  3. Create a binding: [holy.radiant]sunwell bind create my-chat --lens my.lens[/holy.radiant]"
            )
            return None, "", "", None, None, None

    # Set defaults
    provider = provider or "ollama"
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "llama3.1:8b",
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
        render_error(
            console,
            "Error loading/resolving lens",
            details=e.message,
            suggestion="Check the lens path and try again",
        )
        return None


def _init_session(store: SimulacrumStore, session: str | None) -> object:
    """Initialize or resume session with Holy Light feedback."""
    if session:
        try:
            dag = store.load_session(session)
            console.print(f"[holy.success]{CHARS_STARS['complete']} Resumed session:[/holy.success] {session}")
            console.print(f"[neutral.dim]  {len(dag.turns)} turns, {len(dag.learnings)} learnings[/neutral.dim]")
        except FileNotFoundError:
            store.new_session(session)
            dag = store.get_dag()
            console.print(f"[holy.success]{CHARS_STARS['complete']} Created new session:[/holy.success] {session}")
    else:
        session = store.new_session()
        dag = store.get_dag()
        console.print(f"[holy.success]{CHARS_STARS['complete']} New session:[/holy.success] {session}")

    return dag


def _display_session_info(
    lens: object,
    provider: str,
    model: str,
    session: str | None,
    tools_enabled: bool | None,
    trust_level: str | None,
) -> None:
    """Display session information panel with Holy Light styling."""
    # Show branded banner (small version for chat)
    print_banner(console, small=True)

    mode_label = "Agent" if tools_enabled else "Chat"
    mode_style = "holy.success" if tools_enabled else "holy.gold"
    trust_display = f" ({trust_level or 'workspace'})" if tools_enabled else ""

    # Holy Light panel: golden border, radiant highlights
    console.print(
        Panel(
            f"[sunwell.heading]{lens.metadata.name}[/sunwell.heading] [neutral.dim]({provider}:{model})[/neutral.dim]: "
            f"[{mode_style}]{mode_label}{trust_display}[/{mode_style}]\n"
            f"[neutral.muted]Commands:[/neutral.muted] /switch, /branch, /learn, /stats, /quit"
            + (" | /tools on/off" if not tools_enabled else ""),
            title=f"[holy.radiant]{CHARS_STARS['radiant']} Session: {session}[/holy.radiant]",
            border_style="holy.gold",
        )
    )
