"""Ask command - Simplified command using bindings."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from sunwell.binding import BindingManager, get_binding_or_create_temp
from sunwell.cli.helpers import create_model, display_execution_stats
from sunwell.cli.state import get_simulacrum_manager
from sunwell.core.errors import SunwellError
from sunwell.core.types import LensReference, Tier
from sunwell.embedding import create_embedder
from sunwell.fount.client import FountClient
from sunwell.fount.resolver import LensResolver
from sunwell.runtime.engine import RuntimeEngine
from sunwell.runtime.model_router import ModelRouter
from sunwell.schema.loader import LensLoader
from sunwell.simulacrum.core import Simulacrum
from sunwell.workspace.detector import WorkspaceDetector
from sunwell.workspace.indexer import CodebaseIndexer

console = Console()


@click.command(deprecated=True)
@click.argument("binding_or_prompt", required=True)
@click.argument("prompt", required=False)
@click.option("--provider", "-p", help="Override provider")
@click.option("--model", "-m", help="Override model")
@click.option("--tier", type=click.Choice(["0", "1", "2"]), help="Override tier")
@click.option("--smart", is_flag=True, help="Enable RFC-015 Adaptive Model Selection")
@click.option("--output", "-o", type=click.Path(), help="Write output to file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def ask(
    binding_or_prompt: str,
    prompt: str | None,
    provider: str | None,
    model: str | None,
    tier: str | None,
    smart: bool,
    output: str | None,
    verbose: bool,
) -> None:
    """Ask a question using a binding (or default).
    
    DEPRECATED: Use the goal-first interface instead:
    
        sunwell "Build a REST API with auth"
    
    For interactive sessions:
    
        sunwell chat
    
    ---
    
    Legacy documentation (for backward compatibility):
    
    The simplest way to use Sunwell! Create a binding once,
    then just ask questions without any flags.
    
    Examples:
    
        # With named binding
        sunwell ask my-project "Write API docs"
        
        # With default binding (if set)
        sunwell ask "Review this code"
        
        # With overrides
        sunwell ask my-project "Complex task" --tier 2
    """
    # RFC-037: Show deprecation warning
    console.print(
        "[yellow]⚠ 'sunwell ask' is deprecated. Use the goal-first interface:[/yellow]"
    )
    console.print("[dim]    sunwell \"your goal here\"[/dim]")
    console.print("[dim]    sunwell chat  # for interactive sessions[/dim]")
    console.print()
    
    manager = BindingManager()
    
    # Figure out if first arg is a binding name or the prompt
    binding_name: str | None = None
    actual_prompt: str
    
    if prompt is not None:
        # Two args: first is binding name, second is prompt
        binding_name = binding_or_prompt
        actual_prompt = prompt
    else:
        # One arg: could be binding name or prompt
        # Check if it's a binding name
        if manager.get(binding_or_prompt):
            console.print(f"[red]Missing prompt. Usage: sunwell ask {binding_or_prompt} \"your prompt\"[/red]")
            sys.exit(1)
        
        # It's just a prompt, use default binding
        actual_prompt = binding_or_prompt
    
    # Get binding
    binding, is_temp = get_binding_or_create_temp(
        binding_name=binding_name,
        lens_path=None,
        provider=provider,
        model=model,
        headspace=None,
    )
    
    if not binding:
        console.print("[red]No binding specified and no default set.[/red]")
        console.print("[dim]Create a binding: sunwell bind create my-project --lens my.lens[/dim]")
        console.print("[dim]Or set a default: sunwell bind default my-project[/dim]")
        sys.exit(1)
    
    # Apply overrides
    if provider:
        binding.provider = provider
    if model:
        binding.model = model
    final_tier = int(tier) if tier else binding.tier
    final_verbose = verbose or binding.verbose
    
    # Mark as used
    if not is_temp:
        binding.touch()
        manager._save(binding)
    
    # Now run apply with the binding's settings
    asyncio.run(_ask_with_binding(
        binding=binding,
        prompt=actual_prompt,
        tier=final_tier,
        smart=smart,
        output=output,
        verbose=final_verbose,
    ))


async def _ask_with_binding(
    binding,
    prompt: str,
    tier: int,
    smart: bool,
    output: str | None,
    verbose: bool,
) -> None:
    """Execute a prompt using binding settings."""
    # Load lens
    fount = FountClient()
    loader = LensLoader(fount_client=fount)
    resolver = LensResolver(loader=loader)
    
    try:
        source = str(binding.lens_path)
        if not (source.startswith("/") or source.startswith("./") or source.startswith("../")):
            source = f"./{source}"
            
        ref = LensReference(source=source)
        lens = await resolver.resolve(ref)
    except SunwellError as e:
        console.print(f"[red]Error loading/resolving lens:[/red] {e.message}")
        sys.exit(1)
    
    # Show binding info
    if verbose:
        console.print(f"[cyan]Binding:[/cyan] {binding.name}")
        console.print(f"[cyan]Lens:[/cyan] {lens.metadata.name}")
        console.print(f"[cyan]Model:[/cyan] {binding.provider}:{binding.model}")
    
    # Create model
    model = create_model(binding.provider, binding.model)
    embedder = create_embedder()
    
    # Set up workspace indexing
    codebase_indexer = None
    if binding.index_workspace:
        try:
            detector = WorkspaceDetector()
            workspace = detector.detect()
            codebase_indexer = CodebaseIndexer(
                workspace=workspace,
                embedder=embedder,
            )
            await codebase_indexer.initialize()
            index = await codebase_indexer.index_workspace(workspace)
            if verbose:
                console.print(f"[dim]Indexed {index.file_count} files ({index.chunk_count} chunks)[/dim]")
        except Exception as e:
            if verbose:
                console.print(f"[dim]Workspace indexing skipped: {e}[/dim]")
    
    # Simulacrum handling: explicit from binding, auto-routing, or create new
    headspace = None
    simulacrum_store = None
    headspace_name = None
    was_spawned = False
    
    if binding.simulacrum:
        # Explicit headspace in binding - use legacy path
        headspace_name = binding.simulacrum
        headspace_path = Path(".sunwell/headspaces") / f"{headspace_name}.json"
        if headspace_path.exists():
            headspace = Simulacrum.load(headspace_path, lens=lens)
        else:
            headspace = Simulacrum.create(headspace_name, lens=lens)
        headspace.current_model = binding.model
        headspace.focus.update_from_query(prompt)
        
        if verbose:
            console.print(f"[cyan]Simulacrum:[/cyan] {headspace_name} ({len(headspace.long_term.learnings)} learnings)")
    else:
        # Auto-routing via SimulacrumManager
        try:
            manager = get_simulacrum_manager()
            simulacrum_store, was_spawned, explanation = manager.route_query(prompt)
            
            if simulacrum_store:
                headspace_name = manager._active_name
                if verbose:
                    if was_spawned:
                        console.print(f"[cyan]Simulacrum:[/cyan] {headspace_name} [green](auto-spawned)[/green]")
                    else:
                        console.print(f"[cyan]Simulacrum:[/cyan] {headspace_name} [dim](auto-routed)[/dim]")
                    stats = simulacrum_store.stats()
                    console.print(f"  Nodes: {stats.get('total_nodes', 0)} | Sessions: {stats.get('sessions', 0)}")
            else:
                if verbose:
                    console.print(f"[dim]Simulacrum: {explanation}[/dim]")
        except Exception as e:
            if verbose:
                console.print(f"[dim]Auto-headspace skipped: {e}[/dim]")
    
    # Set up model router if requested (RFC-015)
    model_router = None
    if smart:
        stupid_model = None
        if binding.provider == "ollama":
            stupid_model = create_model("ollama", "gemma3:1b")
        elif binding.provider == "openai":
            stupid_model = create_model("openai", "gpt-4o-mini")
            
        model_router = ModelRouter(
            primary_model=model,
            stupid_model=stupid_model,
            lens=lens,
        )
        
        if verbose:
            console.print(f"[cyan]Adaptive Model Selection:[/cyan] Enabled")

    # Create engine (headspace is managed separately for now)
    engine = RuntimeEngine(
        model=model,
        lens=lens,
        embedder=embedder,
        codebase_indexer=codebase_indexer,
        model_router=model_router,
    )
    
    # Execute
    tier_enum = Tier(tier)
    
    if binding.stream:
        console.print()
        content_parts = []
        async for chunk in engine.execute_stream(prompt):
            console.print(chunk, end="")
            content_parts.append(chunk)
        console.print()
        final_content = "".join(content_parts)
    else:
        with console.status("[bold green]Processing..."):
            result = await engine.execute(prompt, force_tier=tier_enum if tier_enum else None)
        console.print(Markdown(result.content))
        final_content = result.content
        
        if verbose:
            display_execution_stats(result)
    
    # Auto-learn from response and save
    if headspace and headspace_name:
        # Legacy Simulacrum path
        if binding.auto_learn:
            try:
                from sunwell.simulacrum.extractors.extractor import LearningExtractor
                extractor = LearningExtractor(min_confidence=0.6)
                learnings = extractor.extract_from_text(final_content)
                for l in learnings[:3]:  # Max 3 auto-learnings per response
                    await headspace.add_learning(l.text, category=l.category)
                    if verbose:
                        console.print(f"[dim]+ Auto-learned ({l.category}): {l.text[:50]}...[/dim]")
            except ImportError:
                pass  # Learning extractor not available
        
        headspace_path = Path(".sunwell/headspaces") / f"{headspace_name}.json"
        headspace.save(headspace_path)
        
    elif simulacrum_store and headspace_name:
        # SimulacrumStore from manager (auto-routed)
        simulacrum_store.add_turn(role="user", content=prompt)
        simulacrum_store.add_turn(role="assistant", content=final_content, model=f"{binding.provider}:{binding.model}")
        
        if binding.auto_learn:
            try:
                from sunwell.simulacrum.extractors.extractor import auto_extract_learnings
                extracted = auto_extract_learnings(final_content, min_confidence=0.6)
                for learning_text, category, confidence in extracted[:3]:
                    simulacrum_store.add_learning(learning_text, category=category, confidence=confidence)
                    if verbose:
                        console.print(f"[dim]+ Auto-learned ({category}): {learning_text[:50]}...[/dim]")
            except ImportError:
                pass
        
        simulacrum_store.flush()
        
        if verbose:
            stats = simulacrum_store.stats()
            console.print(f"[dim]Simulacrum updated: {headspace_name} ({stats.get('total_nodes', 0)} nodes)[/dim]")
    
    # Write output
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(final_content)
        console.print(f"\n[green]✓ Output written to:[/green] {output}")
