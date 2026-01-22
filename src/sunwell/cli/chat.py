"""Chat command - Interactive headspace chat session."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
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
from sunwell.runtime.model_router import ModelRouter
from sunwell.schema.loader import LensLoader
from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.store import SimulacrumStore
from sunwell.simulacrum.core.turn import Learning

console = Console()


@dataclass
class ChatState:
    """Mutable state for chat loop - enables model switching."""
    model: object
    model_name: str
    lens_name: str = "Assistant"
    tools_enabled: bool = False
    trust_level: str = "workspace"
    models_used: list[str] = field(default_factory=list)
    last_response: str = ""
    tool_executor: object = None

    def switch_model(self, new_model: object, new_name: str) -> None:
        """Switch to a new model, tracking history."""
        self.models_used.append(self.model_name)
        self.model = new_model
        self.model_name = new_name

    @property
    def mode(self) -> str:
        """Return 'Agent' if tools enabled, else 'Chat'."""
        return "Agent" if self.tools_enabled else "Chat"

    @property
    def mode_display(self) -> str:
        """Return mode with trust level for display."""
        if self.tools_enabled:
            return f"Agent ({self.trust_level})"
        return "Chat"


@click.command()
@click.argument("binding_or_lens", required=False)
@click.option("--session", "-s", help="Session name (creates new or resumes existing)")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--provider", "-p", default=None, help="Provider")
@click.option("--memory-path", type=click.Path(), default=".sunwell/memory", help="Memory store path")
@click.option("--tools/--no-tools", default=None, help="Override tool calling (Agent mode)")
@click.option("--trust", type=click.Choice(["discovery", "read_only", "workspace", "shell"]),
              default=None, help="Override tool trust level")
@click.option("--smart", is_flag=True, help="Enable RFC-015 Adaptive Model Selection")
@click.option("--mirror", is_flag=True, help="Enable RFC-015 Mirror Neurons (self-introspection)")
@click.option("--model-routing", is_flag=True, help="Enable RFC-015 Model-Aware Task Routing")
@click.option("--router-model", default=None, help="Tiny LLM for cognitive routing (RFC-020)")
@click.option("--naaru/--no-naaru", default=True, help="RFC-019: Enable Naaru Shards for parallel processing")
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

        sunwell chat                              # Uses default binding

        sunwell chat writer                       # Uses 'writer' binding

        sunwell chat lenses/tech-writer.lens     # Direct lens path

        sunwell chat --session auth-debug        # Named session

        # Mid-conversation: /switch anthropic:claude-sonnet-4-20250514
    """
    manager = BindingManager()
    lens_path: str | None = None

    # Track if CLI overrode the provider (important for model defaults)
    cli_provider_override = provider is not None
    cli_model_override = model is not None

    # Tool settings (may be overridden by CLI flags)
    tools_enabled = tools  # CLI override or None
    trust_level = trust  # CLI override or None

    # Resolve binding or lens path
    if binding_or_lens:
        # Check if it's a binding name first
        binding = manager.get(binding_or_lens)
        if binding:
            lens_path = binding.lens_path
            # Only use binding's model if provider wasn't overridden
            # (otherwise the model might be wrong for the new provider)
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            # Use binding's tool settings if not overridden
            if tools_enabled is None:
                tools_enabled = binding.tools_enabled
            if trust_level is None:
                trust_level = binding.trust_level
        elif Path(binding_or_lens).exists():
            # It's a lens path
            lens_path = binding_or_lens
        else:
            console.print(f"[red]Not found:[/red] '{binding_or_lens}' is neither a binding nor a lens file")
            console.print("[dim]List bindings: sunwell bind list[/dim]")
            sys.exit(1)
    else:
        # Try default binding
        binding = manager.get_default()
        if binding:
            lens_path = binding.lens_path
            # Only use binding's model if provider wasn't overridden
            provider = provider or binding.provider
            if not cli_provider_override or cli_model_override:
                model = model or binding.model
            session = session or binding.simulacrum
            # Use binding's tool settings if not overridden
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
            console.print("  3. Create a binding: [cyan]sunwell bind create my-chat --lens my.lens[/cyan]")
            sys.exit(1)

    # Set defaults
    provider = provider or "openai"
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "gemma3:4b",
            "mock": "mock",
        }.get(provider, "gpt-4o")

    # Load lens
    fount = FountClient()
    loader = LensLoader(fount_client=fount)
    resolver = LensResolver(loader=loader)

    try:
        source = str(lens_path)
        if not (source.startswith("/") or source.startswith("./") or source.startswith("../")):
            source = f"./{source}"

        ref = LensReference(source=source)
        lens = asyncio.run(resolver.resolve(ref))
    except SunwellError as e:
        console.print(f"[red]Error loading/resolving lens:[/red] {e.message}")
        sys.exit(1)

    # Initialize memory store
    store = SimulacrumStore(Path(memory_path))

    # Create or resume session
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

    # Create model
    llm = create_model(provider, model)
    embedder = create_embedder()

    # Set embedder on store for semantic retrieval (RFC-013)
    store.set_embedder(embedder)

    # Build system prompt from lens
    system_prompt = lens.to_context()

    # Determine mode label
    mode_label = "Agent" if tools_enabled else "Chat"
    mode_color = "green" if tools_enabled else "blue"
    trust_display = f" ({trust_level or 'workspace'})" if tools_enabled else ""

    console.print(Panel(
        f"[bold]{lens.metadata.name}[/bold] ({provider}:{model}): [{mode_color}]{mode_label}{trust_display}[/{mode_color}]\n"
        f"Commands: /switch, /branch, /learn, /stats, /quit" + (" | /tools on/off" if not tools_enabled else ""),
        title=f"Session: {session}",
        border_style=mode_color,
    ))

    # Main chat loop with model state
    asyncio.run(_chat_loop(
        dag=dag,
        store=store,
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
        naaru_enabled=naaru,  # RFC-019: Naaru-powered chat
        identity_enabled=naaru,  # RFC-023: Adaptive identity (follows naaru flag)
    ))


async def _generate_with_tools(
    model,
    messages: list[dict],
    tool_executor,
    console,
    max_iterations: int = 10,
) -> str:
    """Generate response with tool calling support.

    Handles the multi-turn tool calling loop:
    1. Send prompt + tools to model
    2. If model returns tool calls, execute them
    3. Send tool results back to model
    4. Repeat until model returns text or max iterations
    """
    from sunwell.models.protocol import Message
    from sunwell.tools.builtins import CORE_TOOLS

    # Get available tools from executor
    available_tool_names = tool_executor.get_available_tools()

    # Build tools list from CORE_TOOLS
    tool_list = [CORE_TOOLS[name] for name in available_tool_names if name in CORE_TOOLS]

    # Add mirror tools if mirror handler is configured (RFC-015)
    if tool_executor.mirror_handler:
        from sunwell.mirror.tools import MIRROR_TOOL_TRUST, MIRROR_TOOLS
        from sunwell.tools.types import ToolTrust

        # Get current trust level
        current_trust = tool_executor.policy.trust_level if tool_executor.policy else ToolTrust.WORKSPACE
        trust_order = ["discovery", "read_only", "workspace", "shell", "full"]
        current_idx = trust_order.index(current_trust.value.lower()) if hasattr(current_trust, 'value') else 2

        # Add mirror tools available at current trust level
        for tool_name, tool_def in MIRROR_TOOLS.items():
            required_level = MIRROR_TOOL_TRUST.get(tool_name, "workspace")
            required_idx = trust_order.index(required_level)
            if current_idx >= required_idx:
                tool_list.append(tool_def)

    tools = tuple(tool_list)

    # Build conversation as Message objects
    conversation: list[Message] = []
    for msg in messages:
        conversation.append(Message(role=msg["role"], content=msg["content"]))

    response_text = ""

    for _iteration in range(max_iterations):
        # Generate with tools
        result = await model.generate(
            tuple(conversation),
            tools=tools,
            tool_choice="auto",
        )

        # If no tool calls, we're done
        if not result.has_tool_calls:
            response_text = result.text
            console.print(response_text, end="")
            break

        # Add assistant message with tool calls to conversation
        conversation.append(Message(
            role="assistant",
            content=result.content,
            tool_calls=result.tool_calls,
        ))

        # Execute each tool call
        for tool_call in result.tool_calls:
            console.print(f"\n[cyan]⚡ {tool_call.name}[/cyan]", end="")
            args_preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(tool_call.arguments.items())[:2])
            console.print(f"[dim]({args_preview})[/dim]")

            # Execute the tool
            tool_result = await tool_executor.execute(tool_call)

            # Show result status
            if tool_result.success:
                output_preview = tool_result.output[:100] + "..." if len(tool_result.output) > 100 else tool_result.output
                console.print(f"[green]✓[/green] [dim]{output_preview}[/dim]")
            else:
                console.print(f"[red]✗[/red] {tool_result.error}")

            # Add tool result to conversation
            conversation.append(Message(
                role="tool",
                content=tool_result.output if tool_result.success else f"Error: {tool_result.error}",
                tool_call_id=tool_call.id,
            ))

        console.print()  # Newline after tool results
    else:
        # Max iterations reached
        console.print(f"\n[yellow]⚠ Max tool iterations ({max_iterations}) reached[/yellow]")
        response_text = result.text if result else ""

    return response_text


async def _chat_loop(
    dag: ConversationDAG,
    store: SimulacrumStore,
    initial_model,
    initial_model_name: str,
    system_prompt: str,
    tools_enabled: bool = False,
    trust_level: str = "workspace",
    smart: bool = False,
    lens = None,
    mirror_enabled: bool = False,
    model_routing_enabled: bool = False,
    memory_path: Path | None = None,
    naaru_enabled: bool = True,  # RFC-019: Naaru-powered chat
    identity_enabled: bool = True,  # RFC-023: Adaptive identity
) -> None:
    """Main interactive chat loop with model-switching support.

    When naaru_enabled=True, uses Naaru's Shards for parallel processing:
    - Consolidator: Extract learnings in background
    - Memory Fetcher: Pre-fetch relevant history
    - Lookahead: Pre-embed queries for next turn

    When identity_enabled=True (RFC-023), uses adaptive identity:
    - Extracts behavioral observations from user messages
    - Periodically digests into identity prompt
    - Injects identity into system prompt
    """

    # RFC-023: Initialize identity store
    identity_store = None
    if identity_enabled and memory_path:
        try:
            from sunwell.identity.store import IdentityStore
            from sunwell.naaru.persona import MURU
            identity_store = IdentityStore(memory_path / "sessions" / dag._session_id if hasattr(dag, '_session_id') else memory_path / "sessions" / "default")
            if identity_store.identity.is_usable():
                console.print(f"[cyan]{MURU.name}:[/cyan] Identity loaded (confidence: {identity_store.identity.confidence:.0%})")
            elif identity_store.identity.observations:
                console.print(f"[cyan]{MURU.name}:[/cyan] Building identity ({len(identity_store.identity.observations)} observations)")
        except Exception as e:
            console.print(f"[dim yellow]Identity disabled: {e}[/dim yellow]")
            identity_store = None

    # Set up tool executor if tools enabled
    tool_executor = None
    mirror_handler = None

    if tools_enabled:
        from sunwell.tools.executor import ToolExecutor
        from sunwell.tools.types import ToolPolicy, ToolTrust

        workspace_root = Path.cwd()

        # Create sandbox for shell commands if trust allows
        sandbox = None
        if trust_level in ("shell", "full"):
            from sunwell.skills.sandbox import ScriptSandbox
            from sunwell.skills.types import TrustLevel
            sandbox = ScriptSandbox(trust=TrustLevel.SANDBOXED)

        policy = ToolPolicy(
            trust_level=ToolTrust.from_string(trust_level),
        )

        # RFC-015: Set up mirror handler if enabled
        if mirror_enabled or model_routing_enabled:
            # RFC-085: MirrorHandler now uses Self.get() for source introspection
            # so we just pass the user's workspace (cwd), not Sunwell source root
            from sunwell.mirror import MirrorHandler

            # Get lens config for model routing
            lens_config = None
            if lens and hasattr(lens, "raw_config"):
                lens_config = lens.raw_config

            mirror_storage = memory_path / "mirror" if memory_path else Path(".sunwell/mirror")

            mirror_handler = MirrorHandler(
                workspace=Path.cwd(),  # User's workspace
                storage_path=mirror_storage,
                lens=lens,
                lens_config=lens_config,
                session_model=initial_model_name,
            )

            if mirror_enabled:
                console.print("[cyan]Mirror Neurons:[/cyan] Enabled (self-introspection)")
            if model_routing_enabled:
                console.print("[cyan]Model Routing:[/cyan] Enabled (task-aware model selection)")

        # RFC-027: Set up expertise tools if lens is available
        expertise_handler = None
        if lens:
            from sunwell.embedding import create_embedder
            from sunwell.runtime.retriever import ExpertiseRetriever
            from sunwell.tools.expertise import ExpertiseToolHandler

            embedder = create_embedder()
            retriever = ExpertiseRetriever(lens=lens, embedder=embedder, top_k=5)
            expertise_handler = ExpertiseToolHandler(retriever=retriever, lens=lens)
            console.print("[cyan]Self-Directed Expertise:[/cyan] Enabled (RFC-027)")

        tool_executor = ToolExecutor(
            workspace=workspace_root,
            sandbox=sandbox,
            policy=policy,
            mirror_handler=mirror_handler,
            expertise_handler=expertise_handler,
        )

    # Mutable chat state
    state = ChatState(
        model=initial_model,
        model_name=initial_model_name,
        lens_name=lens.metadata.name if lens else "Assistant",
        tools_enabled=tools_enabled,
        trust_level=trust_level,
        tool_executor=tool_executor,
    )

    # Set up model router if requested (RFC-015)
    model_router = None
    if smart:
        # Determine provider from model name (crude)
        provider = initial_model_name.split(":")[0]
        stupid_model = None
        if provider == "ollama":
            stupid_model = create_model("ollama", "gemma3:1b")
        elif provider == "openai":
            stupid_model = create_model("openai", "gpt-4o-mini")

        model_router = ModelRouter(
            primary_model=initial_model,
            stupid_model=stupid_model,
            lens=lens,
        )

        if lens:
            console.print("[cyan]Adaptive Model Selection:[/cyan] Enabled")

    # RFC-019: Initialize Naaru Shards for parallel processing
    shard_pool = None
    convergence = None
    tiny_model = None  # For fact extraction
    if naaru_enabled:
        try:
            from sunwell.naaru.convergence import Convergence
            from sunwell.naaru.shards import ShardPool, ShardType

            convergence = Convergence(capacity=7)  # Miller's Law: 7±2 items
            shard_pool = ShardPool(convergence=convergence)

            # Create tiny LLM for fact extraction (RFC-020 style micro-distillation)
            try:
                from sunwell.config import get_config, resolve_naaru_model
                from sunwell.models.ollama import OllamaModel
                from sunwell.naaru.persona import MURU

                cfg = get_config()
                voice_model = resolve_naaru_model(
                    cfg.naaru.voice,
                    cfg.naaru.voice_models,
                    check_availability=True,
                )
                if voice_model:
                    tiny_model = OllamaModel(
                        model=voice_model,
                        use_native_api=cfg.naaru.use_native_ollama_api,
                    )
                    console.print(f"[cyan]{MURU.name}:[/cyan] Enabled (parallel + LLM learning via {voice_model})")
                else:
                    tiny_model = None
                    console.print(f"[cyan]{MURU.name}:[/cyan] Enabled (parallel + regex learning)")
            except Exception:
                # Fall back to regex extraction
                from sunwell.naaru.persona import MURU
                tiny_model = None
                console.print(f"[cyan]{MURU.name}:[/cyan] Enabled (parallel + regex learning)")
        except ImportError:
            naaru_enabled = False  # Fall back if Naaru not available

    # RFC-013: No explicit initialization needed - SimulacrumStore handles it

    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd_result = await _handle_chat_command(
                    user_input, dag, store, state,
                    identity_store=identity_store,
                    tiny_model=tiny_model,
                    system_prompt=system_prompt,
                )
                if cmd_result == "quit":
                    break
                continue

            # RFC-023: Inject identity into system prompt
            # Always inject M'uru's identity; user identity only if usable
            from sunwell.identity.injection import build_system_prompt_with_identity
            user_identity = None
            if identity_store and identity_store.identity.is_usable():
                user_identity = identity_store.identity
            effective_system_prompt = build_system_prompt_with_identity(
                system_prompt, user_identity, include_muru_identity=True
            )

            # RFC-013: Assemble context using hierarchical chunking (hot/warm/cold tiers)
            # This enables infinite rolling history across model switches
            messages, context_stats = store.assemble_messages(
                query=user_input,
                system_prompt=effective_system_prompt,
                max_tokens=4000,
            )

            # Show retrieval info
            if context_stats["retrieved_chunks"] > 0:
                console.print(f"[dim]Retrieved {context_stats['hot_turns']} turns from {context_stats['retrieved_chunks']} chunks[/dim]")
            if context_stats["compression_applied"]:
                console.print(f"[dim]Compressed old context ({context_stats['warm_summaries']} warm, {context_stats['cold_summaries']} cold summaries)[/dim]")

            # Add current user input
            messages.append({"role": "user", "content": user_input})

            # Now add user turn to DAG for future history
            dag.add_user_message(user_input)

            # Extract facts from user message (name, preferences, context)
            # RFC-019: Use Naaru Consolidator Shard if available
            # RFC-023: Also extract behaviors for identity
            if shard_pool and naaru_enabled:
                # Fire-and-forget: Shard extracts in background with tiny LLM
                asyncio.create_task(_naaru_extract_user_facts_and_behaviors(
                    shard_pool, dag, user_input, console, tiny_model, identity_store
                ))
            else:
                # Inline extraction (fallback)
                try:
                    from sunwell.simulacrum.extractors.extractor import extract_user_facts
                    user_facts = extract_user_facts(user_input)
                    for fact_text, category, confidence in user_facts:
                        learning = Learning(
                            fact=fact_text,
                            source_turns=(dag.active_head,) if dag.active_head else (),
                            confidence=confidence,
                            category=category,
                        )
                        dag.add_learning(learning)
                        console.print(f"[dim]+ Noted: {fact_text}[/dim]")
                except ImportError:
                    pass

                # RFC-023: Extract behaviors (fallback regex)
                if identity_store:
                    try:
                        from sunwell.identity.extractor import extract_behaviors_regex
                        behaviors = extract_behaviors_regex(user_input)
                        from sunwell.naaru.persona import MURU
                        for behavior_text, confidence in behaviors:
                            identity_store.add_observation(behavior_text, confidence)
                            console.print(MURU.msg_observed(behavior_text))
                    except ImportError:
                        pass

            # RFC-015: Adaptive Model Selection
            if model_router:
                # Pass requires_tools hint to the router (from state.tools_enabled)
                recommended_model_id = await model_router.route(
                    user_input,
                    requires_tools=state.tools_enabled
                )

                # If the recommended model is different and from the same provider, switch
                provider = state.model_name.split(":")[0]
                if recommended_model_id != state.model_name.split(":")[1]:
                    try:
                        new_llm = create_model(provider, recommended_model_id)
                        state.switch_model(new_llm, f"{provider}:{recommended_model_id}")
                        console.print(f"[dim]Auto-switched to {recommended_model_id} for this task[/dim]")
                    except Exception:
                        pass # Ignore failures in auto-switching

            mode_indicator = f"[green]{state.mode}[/green]" if state.tools_enabled else ""
            console.print(f"\n[bold green]{state.lens_name}[/bold green] [dim]({state.model_name})[/dim]{' ' + mode_indicator if mode_indicator else ''}: ", end="")

            if state.tools_enabled and state.tool_executor:
                # Tool-aware generation
                response = await _generate_with_tools(
                    model=state.model,
                    messages=messages,
                    tool_executor=state.tool_executor,
                    console=console,
                )
            else:
                # Standard streaming generation with proper message structure
                from sunwell.models.protocol import Message

                # Convert dict messages to Message objects with proper roles
                structured_messages = tuple(
                    Message(role=m["role"], content=m["content"])
                    for m in messages
                )

                response_parts = []
                async for chunk in state.model.generate_stream(structured_messages):
                    console.print(chunk, end="")
                    response_parts.append(chunk)
                response = "".join(response_parts)

            console.print()

            # Track last response for /write command
            state.last_response = response

            # Add assistant turn to DAG (tracks which model generated it)
            dag.add_assistant_message(response, model=state.model_name)

            # Auto-extract learnings from response
            # RFC-019: Use Naaru Consolidator Shard if available
            if shard_pool and naaru_enabled:
                # Fire-and-forget: Shard consolidates learnings in background
                asyncio.create_task(_naaru_consolidate_learnings(
                    shard_pool, dag, response, user_input, console
                ))
            else:
                # Inline extraction (fallback)
                try:
                    from sunwell.simulacrum.extractors.extractor import auto_extract_learnings
                    extracted = auto_extract_learnings(response, min_confidence=0.6)
                    for learning_text, category, confidence in extracted[:3]:
                        learning = Learning(
                            fact=learning_text,
                            source_turns=(dag.active_head,) if dag.active_head else (),
                            confidence=confidence,
                            category=category,
                        )
                        dag.add_learning(learning)
                except ImportError:
                    pass  # Learning extractor not available

            # RFC-023: Check if identity digest needed
            if identity_store and identity_store.needs_digest(len(dag.turns)):
                asyncio.create_task(_digest_identity_background(
                    identity_store, tiny_model, len(dag.turns), console
                ))

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Saving session...[/yellow]")
            break
        except EOFError:
            break
        except SunwellError as e:
            # Structured error with recovery hints
            console.print(f"\n[red]Error {e.error_id}:[/red] {e.message}")
            if e.recovery_hints:
                console.print("[yellow]Recovery options:[/yellow]")
                for i, hint in enumerate(e.recovery_hints, 1):
                    console.print(f"  {i}. {hint}")
            if e.is_recoverable:
                console.print("[dim]Session preserved. You can retry or use a different approach.[/dim]")
            continue
        except Exception as e:
            # Unexpected error - log and continue
            console.print(f"\n[red]Unexpected error:[/red] {e}")
            console.print("[dim]Type /quit to exit or continue with your next message.[/dim]")
            continue

    # Save on exit with model history
    store.save_session()

    # RFC-023: Persist identity to global on exit
    if identity_store:
        try:
            from sunwell.naaru.persona import MURU
            asyncio.get_event_loop().run_until_complete(identity_store.persist_to_global())
            console.print(f"[dim]{MURU.name} saved ({len(identity_store.identity.observations)} observations)[/dim]")
        except Exception:
            pass  # Non-critical

    if state.models_used:
        console.print(f"[dim]Models used: {' → '.join(state.models_used + [state.model_name])}[/dim]")
    console.print("[green]✓ Session saved[/green]")


async def _handle_chat_command(
    command: str,
    dag: ConversationDAG,
    store: SimulacrumStore,
    state: ChatState,
    identity_store=None,  # RFC-023: Identity store
    tiny_model=None,  # RFC-023: For identity refresh
    system_prompt: str = "",  # Base system prompt from lens
) -> str | None:
    """Handle chat commands. Returns 'quit' to exit."""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/quit" or cmd == "/exit":
        return "quit"

    elif cmd == "/switch":
        # Switch to a different model mid-conversation
        if not arg:
            console.print("[red]Usage: /switch <provider>:<model>[/red]")
            console.print("  Examples: /switch anthropic:claude-sonnet-4-20250514")
            console.print("            /switch openai:gpt-4o")
            console.print("            /switch openai:o1-preview")
            console.print(f"  Current: {state.model_name}")
        else:
            try:
                if ":" in arg:
                    new_provider, new_model = arg.split(":", 1)
                else:
                    new_provider = arg
                    new_model = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514"}.get(arg, "gpt-4o")

                new_llm = create_model(new_provider, new_model)
                old_name = state.model_name
                state.switch_model(new_llm, f"{new_provider}:{new_model}")

                console.print(f"[green]✓ Switched model:[/green] {old_name} → {state.model_name}")
                console.print("[dim]Your headspace (learnings, history, dead ends) is preserved.[/dim]")
            except Exception as e:
                console.print(f"[red]Failed to switch: {e}[/red]")

    elif cmd == "/models":
        # Show model history
        if state.models_used:
            console.print(f"[bold]Model history:[/bold] {' → '.join(state.models_used + [state.model_name])}")
        else:
            console.print(f"[bold]Current model:[/bold] {state.model_name}")

    elif cmd == "/tools":
        # Toggle or configure tools
        if not arg:
            console.print(f"[bold]Tools:[/bold] {'Enabled' if state.tools_enabled else 'Disabled'} ({state.mode_display})")
            console.print("  Usage: /tools on|off")
            if state.tools_enabled:
                console.print(f"  Trust level: {state.trust_level}")
        elif arg.lower() in ("on", "enable", "yes"):
            if not state.tool_executor:
                # Initialize tool executor
                from pathlib import Path as PathLib

                from sunwell.tools.executor import ToolExecutor
                from sunwell.tools.types import ToolPolicy, ToolTrust

                policy = ToolPolicy(trust_level=ToolTrust.from_string(state.trust_level))
                state.tool_executor = ToolExecutor(
                    workspace=PathLib.cwd(),
                    sandbox=None,
                    policy=policy,
                )
            state.tools_enabled = True
            console.print(f"[green]✓ Tools enabled[/green] ({state.trust_level})")
        elif arg.lower() in ("off", "disable", "no"):
            state.tools_enabled = False
            console.print("[yellow]✓ Tools disabled[/yellow]")
        else:
            console.print(f"[red]Unknown: /tools {arg}[/red]")
            console.print("  Usage: /tools on|off")

    elif cmd == "/save":
        store.save_session()
        console.print("[green]✓ Session saved[/green]")

    elif cmd == "/write":
        # Write last response to a file
        if not arg:
            console.print("[red]Usage: /write <path>[/red]")
            console.print("  Saves the last assistant response to a file")
        elif not state.last_response:
            console.print("[yellow]No response to save yet[/yellow]")
        else:
            from pathlib import Path
            try:
                path = Path(arg).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(state.last_response)
                console.print(f"[green]✓ Saved to:[/green] {path}")
            except Exception as e:
                console.print(f"[red]Failed to write: {e}[/red]")

    elif cmd == "/read":
        # Read a file into context
        if not arg:
            console.print("[red]Usage: /read <path>[/red]")
        else:
            from pathlib import Path
            try:
                path = Path(arg).expanduser()
                if not path.exists():
                    console.print(f"[red]File not found: {path}[/red]")
                else:
                    content = path.read_text()
                    # Show preview and add to context
                    lines = content.split('\n')
                    preview = '\n'.join(lines[:10])
                    if len(lines) > 10:
                        preview += f"\n... ({len(lines) - 10} more lines)"
                    console.print(f"[dim]Read {path} ({len(lines)} lines):[/dim]")
                    console.print(f"```\n{preview}\n```")
                    # Add as a system message
                    dag.add_user_message(f"[File: {path}]\n```\n{content}\n```")
            except Exception as e:
                console.print(f"[red]Failed to read: {e}[/red]")

    elif cmd == "/debug":
        # Debug commands for troubleshooting
        if arg == "prompt" or arg == "system":
            # Show the effective system prompt
            from sunwell.identity.injection import build_system_prompt_with_identity
            user_identity = None
            if identity_store and identity_store.identity.is_usable():
                user_identity = identity_store.identity
            effective_prompt = build_system_prompt_with_identity(
                system_prompt, user_identity, include_muru_identity=True
            )
            console.print("[bold]Effective System Prompt:[/bold]")
            console.print("─" * 60)
            console.print(effective_prompt)
            console.print("─" * 60)
            console.print(f"[dim]Length: {len(effective_prompt)} chars[/dim]")
        elif arg == "identity":
            if identity_store:
                console.print("[bold]Identity Debug:[/bold]")
                console.print(f"  Paused: {identity_store.identity.paused}")
                console.print(f"  Confidence: {identity_store.identity.confidence:.0%}")
                console.print(f"  Observations: {len(identity_store.identity.observations)}")
                console.print(f"  Usable: {identity_store.identity.is_usable()}")
                if identity_store.identity.prompt:
                    console.print(f"  Prompt length: {len(identity_store.identity.prompt)} chars")
            else:
                console.print("[yellow]Identity store not initialized[/yellow]")
        else:
            console.print("[bold]Debug commands:[/bold]")
            console.print("  /debug prompt   - Show effective system prompt")
            console.print("  /debug identity - Show identity state")

    elif cmd == "/stats":
        stats = dag.stats
        console.print(f"Turns: {stats['total_turns']} | Branches: {stats['branches']} | "
                     f"Dead ends: {stats['dead_ends']} | Learnings: {stats['learnings']}")

    elif cmd == "/branch":
        if not arg:
            console.print("[red]Usage: /branch <name>[/red]")
        else:
            dag.branch(arg)
            console.print(f"[green]✓ Created branch:[/green] {arg}")

    elif cmd == "/checkout":
        if not arg:
            console.print("[red]Usage: /checkout <branch>[/red]")
            console.print(f"Available: {', '.join(dag.branches.keys()) or 'none'}")
        else:
            try:
                dag.checkout(arg)
                console.print(f"[green]✓ Switched to:[/green] {arg}")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")

    elif cmd == "/dead-end":
        dag.mark_dead_end()
        console.print("[yellow]✓ Marked current path as dead end[/yellow]")

    elif cmd == "/learn":
        if not arg:
            console.print("[red]Usage: /learn <fact>[/red]")
        else:
            learning = Learning(
                fact=arg,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=1.0,
                category="fact",
            )
            dag.add_learning(learning)
            console.print("[green]✓ Learning added[/green]")

    elif cmd == "/learnings":
        learnings = dag.get_active_learnings()
        if not learnings:
            console.print("[dim]No learnings yet[/dim]")
        else:
            console.print("[bold]Learnings:[/bold]")
            for l in learnings:
                console.print(f"  [{l.category}] {l.fact}")

    elif cmd == "/memory":
        # RFC-026: Unified memory view
        import json as json_module

        from sunwell.simulacrum.unified_view import UnifiedMemoryView

        view = UnifiedMemoryView.from_session(
            dag=dag,
            identity_store=identity_store,
            session_name=store.session_name if hasattr(store, 'session_name') else "",
        )

        if arg.lower() == "json":
            console.print(json_module.dumps(view.to_json(), indent=2))
        elif arg.lower() == "facts":
            if view.facts:
                console.print("[bold]Facts:[/bold]")
                for f in view.facts:
                    status = "✅" if f.quality_score and f.quality_score >= 0.7 else "⚠️"
                    console.print(f"  {status} [{f.category}] {f.content} ({int(f.confidence*100)}%)")
            else:
                console.print("[dim]No facts learned yet[/dim]")
        elif arg.lower() == "identity":
            if view.identity_prompt:
                console.print(f"[bold]Identity (confidence: {int(view.identity_confidence*100)}%):[/bold]")
                console.print(f"  {view.identity_prompt}")
            else:
                console.print("[dim]No identity model yet[/dim]")
        else:
            console.print(view.render_panel())

    elif cmd == "/identity":
        # RFC-023: Identity management commands
        if not identity_store:
            console.print("[yellow]Identity system not enabled[/yellow]")
            console.print("[dim]Start chat with --identity flag or check memory_path configuration[/dim]")
        else:
            from sunwell.identity.commands import handle_identity_command
            await handle_identity_command(
                arg, identity_store, console, tiny_model, len(dag.turns)
            )

    elif cmd == "/help":
        console.print("""
[bold]File Operations:[/bold]
  /write <path>     Save last response to a file
  /read <path>      Read a file into context

[bold]Model & Tools:[/bold]
  /switch <p:m>     Switch model (e.g. /switch anthropic:claude-sonnet-4-20250514)
  /models           Show model history for this session
  /tools on|off     Toggle Agent mode (tool calling)

[bold]Memory Commands (RFC-026):[/bold]
  /memory           View unified memory (facts, identity, behaviors)
  /memory facts     Show just facts
  /memory identity  Show identity model
  /memory json      Export as JSON
  /learnings        Show all learnings
  /learn <fact>     Add a learning/insight

[bold]Simulacrum Commands:[/bold]
  /branch <name>    Create a named branch
  /checkout <name>  Switch to a branch
  /dead-end         Mark current path as dead end
  /stats            Show session statistics
  /save             Save session
  /quit             Exit (auto-saves)

[bold]Identity (RFC-023):[/bold]
  /identity         View your identity model
  /identity rate    Rate how accurate the model is (1-5)
  /identity refresh Force re-synthesis
  /identity pause   Stop learning (keep existing)
  /identity resume  Continue learning
  /identity clear   Start fresh
  /identity export  Export to JSON

[bold]Evolution Analysis:[/bold]
  /trace            Show turn-by-turn evolution report
  /trace clear      Clear trace history
  /trace json       Export traces as JSON

[bold]Tip:[/bold] Your headspace persists when you /switch models!
[bold]Tip:[/bold] Use /tools on to enable Agent mode with file read/write!
""")

    elif cmd == "/trace":
        # Turn-by-turn evolution analysis
        from sunwell.simulacrum.tracer import TRACER

        if arg.lower() == "clear":
            TRACER.clear()
            console.print("[green]✓ Trace history cleared[/green]")
        elif arg.lower() == "json":
            import json
            traces = TRACER.get_json_export()
            if traces:
                console.print(json.dumps(traces, indent=2))
            else:
                console.print("[yellow]No traces recorded yet[/yellow]")
        else:
            report = TRACER.get_evolution_report()
            console.print(report)

    else:
        console.print(f"[red]Unknown command: {cmd}[/red]")
        console.print("[dim]Type /help for available commands[/dim]")

    return None


# RFC-019: Naaru Shard helper functions for background processing

async def _naaru_extract_user_facts(
    shard_pool: ShardPool,
    dag: ConversationDAG,
    user_input: str,
    console,
    tiny_model=None,  # Optional tiny LLM for fact extraction
) -> None:
    """Use Naaru Consolidator Shard to extract facts from user input.

    Uses tiny LLM (gemma3:1b) for flexible fact extraction:
    - "i have a cat named milo" → Noted: User has a cat named Milo
    - "her nickname is kiki" → Noted: User's cat's nickname is Kiki

    Falls back to regex patterns if no tiny model available.

    Runs in background while model generates response.
    """
    try:
        # Prefer LLM-based extraction (more flexible)
        if tiny_model:
            from sunwell.simulacrum.extractors.extractor import extract_user_facts_with_llm
            user_facts = await extract_user_facts_with_llm(user_input, tiny_model)
        else:
            # Fall back to regex
            from sunwell.simulacrum.extractors.extractor import extract_user_facts
            user_facts = extract_user_facts(user_input)

        for fact_text, category, confidence in user_facts:
            learning = Learning(
                fact=fact_text,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=confidence,
                category=category,
            )
            dag.add_learning(learning)
            from sunwell.naaru.persona import MURU
            console.print(MURU.msg_noted(fact_text, category))
    except Exception as e:
        # Log but don't crash - this is background task
        from sunwell.naaru.persona import MURU
        console.print(MURU.msg_error("fact extraction", str(e)))


async def _naaru_consolidate_learnings(
    shard_pool: ShardPool,
    dag: ConversationDAG,
    response: str,
    user_input: str,
    console=None,  # For visibility into what Naaru did
) -> None:
    """Use Naaru Consolidator Shard to extract learnings from response.

    Runs in background after response is shown to user.
    Shows what was learned so user knows what Naaru did.
    """

    try:
        # Use Shard's consolidate method
        await shard_pool.consolidate_learnings(
            task={"user_input": user_input, "response": response},
            result={"content": response},
        )

        # Also run inline extraction for now (Shard stores in Convergence)
        from sunwell.simulacrum.extractors.extractor import auto_extract_learnings
        extracted = auto_extract_learnings(response, min_confidence=0.6)

        added_count = 0
        for learning_text, category, confidence in extracted[:3]:
            learning = Learning(
                fact=learning_text,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=confidence,
                category=category,
            )
            dag.add_learning(learning)
            added_count += 1
            # Show what M'uru learned
            if console:
                from sunwell.naaru.persona import MURU
                console.print(MURU.msg_learned(learning_text))

        # Summary if learnings were added
        if added_count > 0 and console:
            console.print(f"[dim]📚 Total learnings in session: {len(dag.learnings)}[/dim]")
    except Exception as e:
        if console:
            from sunwell.naaru.persona import MURU
            console.print(MURU.msg_error("consolidation", str(e)))


# RFC-023: Identity extraction and digest helper functions

async def _naaru_extract_user_facts_and_behaviors(
    shard_pool: ShardPool,
    dag: ConversationDAG,
    user_input: str,
    console,
    tiny_model=None,
    identity_store=None,
) -> None:
    """Extract facts AND behaviors from user input.

    RFC-023 extension of _naaru_extract_user_facts to also capture
    behavioral observations for the identity system.

    Includes turn-by-turn tracing for evolution analysis.
    """
    # Import tracer for turn evolution tracking
    from sunwell.simulacrum.tracer import TRACER

    # Begin tracing this turn
    turn_id = dag.active_head or "unknown"
    TRACER.begin_turn(turn_id, user_input)

    # Snapshot identity before extraction
    if identity_store:
        TRACER.log_identity_snapshot(
            "before",
            observation_count=len(identity_store.identity.observations),
            confidence=identity_store.identity.confidence,
            prompt=identity_store.identity.prompt,
            tone=identity_store.identity.tone,
            values=identity_store.identity.values,
        )

    try:
        if tiny_model:
            # Use two-tier extraction (RFC-023)
            from sunwell.identity.extractor import extract_with_categories
            facts, behaviors = await extract_with_categories(user_input, tiny_model)

            from sunwell.naaru.persona import MURU

            # Store facts in DAG (existing behavior)
            for fact_text, category, confidence in facts:
                learning = Learning(
                    fact=fact_text,
                    source_turns=(dag.active_head,) if dag.active_head else (),
                    confidence=confidence,
                    category=category,
                )
                dag.add_learning(learning)
                console.print(MURU.msg_noted(fact_text, category))

                # Trace the extraction
                TRACER.log_extraction("fact", fact_text, confidence, category)

            # Store behaviors in identity store (RFC-023)
            if identity_store:
                for behavior_text, confidence in behaviors:
                    identity_store.add_observation(
                        behavior_text,
                        confidence,
                        turn_id=dag.active_head
                    )
                    console.print(MURU.msg_observed(behavior_text))

                    # Trace the extraction
                    TRACER.log_extraction("behavior", behavior_text, confidence)
        else:
            # Fall back to regex for both
            from sunwell.simulacrum.extractors.extractor import extract_user_facts
            user_facts = extract_user_facts(user_input)

            from sunwell.naaru.persona import MURU

            for fact_text, category, confidence in user_facts:
                learning = Learning(
                    fact=fact_text,
                    source_turns=(dag.active_head,) if dag.active_head else (),
                    confidence=confidence,
                    category=category,
                )
                dag.add_learning(learning)
                console.print(MURU.msg_noted(fact_text, category))

                # Trace the extraction
                TRACER.log_extraction("fact", fact_text, confidence, category)

            # RFC-023: Extract behaviors with regex fallback
            if identity_store:
                from sunwell.identity.extractor import extract_behaviors_regex
                behaviors = extract_behaviors_regex(user_input)
                for behavior_text, confidence in behaviors:
                    identity_store.add_observation(behavior_text, confidence)
                    console.print(MURU.msg_observed(behavior_text))

                    # Trace the extraction
                    TRACER.log_extraction("behavior", behavior_text, confidence)

        # Snapshot identity after extraction
        if identity_store:
            TRACER.log_identity_snapshot(
                "after",
                observation_count=len(identity_store.identity.observations),
                confidence=identity_store.identity.confidence,
                prompt=identity_store.identity.prompt,
                tone=identity_store.identity.tone,
                values=identity_store.identity.values,
            )

    except Exception as e:
        from sunwell.naaru.persona import MURU
        console.print(MURU.msg_error("extraction", str(e)))
    finally:
        # End the turn trace (without assistant response - that's added later)
        TRACER.end_turn()


async def _digest_identity_background(
    identity_store,
    tiny_model,
    turn_count: int,
    console,
) -> None:
    """Background task to digest identity from observations.

    RFC-023: Synthesizes behavioral observations into identity prompt.
    """
    try:
        from sunwell.identity.digest import digest_identity, quick_digest

        obs_texts = [o.observation for o in identity_store.identity.observations]

        if tiny_model:
            new_identity = await digest_identity(
                observations=obs_texts,
                current_identity=identity_store.identity,
                tiny_model=tiny_model,
            )
        else:
            # Heuristic fallback
            prompt, confidence = await quick_digest(obs_texts, identity_store.identity.prompt)
            if prompt:
                from sunwell.identity.store import Identity
                new_identity = Identity(
                    observations=identity_store.identity.observations,
                    prompt=prompt,
                    confidence=confidence,
                )
            else:
                return

        if new_identity.is_usable():
            identity_store.update_digest(
                prompt=new_identity.prompt,
                confidence=new_identity.confidence,
                turn_count=turn_count,
                tone=new_identity.tone,
                values=new_identity.values,
            )
            from sunwell.naaru.persona import MURU
            console.print(MURU.msg_identity_updated(new_identity.confidence))
    except Exception as e:
        from sunwell.naaru.persona import MURU
        console.print(MURU.msg_error("identity digest", str(e)))
