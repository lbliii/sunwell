"""Apply command - Apply a lens to a prompt."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from sunwell.cli.helpers import create_model, display_execution_stats, format_args
from sunwell.cli.state import get_simulacrum_manager
from sunwell.core.errors import SunwellError
from sunwell.core.types import LensReference, Tier
from sunwell.embedding import create_embedder
from sunwell.fount.client import FountClient
from sunwell.fount.resolver import LensResolver
from sunwell.runtime.engine import RuntimeEngine
from sunwell.runtime.episode import EpisodeSnapshot
from sunwell.runtime.model_router import ModelRouter
from sunwell.schema.loader import LensLoader
from sunwell.simulacrum.core import Simulacrum
from sunwell.workspace.detector import WorkspaceDetector
from sunwell.workspace.indexer import CodebaseIndexer

console = Console()

try:
    from sunwell.skills.executor import SkillExecutor
except ImportError:
    SkillExecutor = None  # Skills not implemented yet


@click.command()
@click.argument("lens_path", type=click.Path(exists=True))
@click.argument("prompt")
@click.option("--model", "-m", default=None, help="Model to use (default: auto based on provider)")
@click.option("--provider", "-p", default="openai", help="Provider (openai, anthropic, mock)")
@click.option("--stream/--no-stream", default=True, help="Stream output")
@click.option(
    "--tier",
    type=click.Choice(["0", "1", "2"]),
    help="Force execution tier (0=fast, 1=standard, 2=deep)",
)
@click.option("--context", "-c", multiple=True, help="File patterns to include as context (e.g. 'src/**/*.py')")
@click.option("--no-workspace", is_flag=True, help="Disable auto workspace indexing")
@click.option("--output", "-o", type=click.Path(), help="Write output to file")
@click.option("--save-session", type=click.Path(), help="Save expertise session snapshot")
@click.option("--headspace", "-H", help="Simulacrum name (persists learnings across calls)")
@click.option("--no-auto-headspace", is_flag=True, help="Disable automatic headspace routing")
@click.option("--learn", "-l", multiple=True, help="Add a learning to headspace")
@click.option("--dead-end", help="Mark something as a dead end")
@click.option("--skill", "-s", help="Execute a specific skill from the lens")
@click.option("--dry-run", is_flag=True, help="Skill execution: don't write files, output to stdout")
@click.option("--tools/--no-tools", default=False, help="Enable tool calling (RFC-012)")
@click.option("--tools-only", multiple=True, help="Restrict to specific tools (comma-separated)")
@click.option("--trust", type=click.Choice(["discovery", "read_only", "workspace", "shell"]), 
              default="workspace", help="Tool trust level")
@click.option("--smart", is_flag=True, help="Enable RFC-015 Adaptive Model Selection")
@click.option("--router-model", default=None, help="Tiny LLM for cognitive routing (RFC-020)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def apply(
    lens_path: str,
    prompt: str,
    model: str | None,
    provider: str,
    stream: bool,
    tier: str | None,
    context: tuple[str, ...],
    no_workspace: bool,
    output: str | None,
    save_session: str | None,
    headspace: str | None,
    no_auto_headspace: bool,
    learn: tuple[str, ...],
    dead_end: str | None,
    skill: str | None,
    dry_run: bool,
    tools: bool,
    tools_only: tuple[str, ...],
    trust: str,
    smart: bool,
    router_model: str | None,
    verbose: bool,
) -> None:
    """Apply a lens to a prompt.

    By default, Sunwell auto-routes queries to relevant headspaces, spawning
    new ones when a novel domain is detected. Use --no-auto-headspace to disable.
    
    With --headspace, explicitly specify which headspace to use:
    
        sunwell apply lens.lens "Question 1" --headspace my-project
        sunwell apply lens.lens "Question 2" --headspace my-project  # Has Q1 context!
        sunwell apply lens.lens "Question 3" --headspace my-project --learn "API timeout is 5s"
    
    Without --headspace (default), headspaces evolve automatically:
    
        sunwell apply lens.lens "How do I set up JWT auth?"  # → Tracked
        sunwell apply lens.lens "Best token expiry times?"   # → Tracked (related)
        sunwell apply lens.lens "How to refresh tokens?"     # → Auto-spawns "jwt-auth-tokens"
    
    With --tools, enable LLM tool calling (RFC-012):
    
        sunwell apply lens.lens "Read config.yaml and summarize" --tools
        sunwell apply lens.lens "Create docs for src/" --tools --trust workspace
        sunwell apply lens.lens "Run tests" --tools --trust shell

    Examples:

        sunwell apply tech-writer.lens "Write API docs for the CLI" -o docs/cli.md

        sunwell apply ./my.lens -c "src/*.py" "Review auth" --save-session review.json

        sunwell apply lens.yaml --tier 2 --no-workspace "General writing task"

        sunwell apply tech-writer.lens "Create API docs for auth.py" --skill create-api-docs
        
        sunwell apply lens.lens "Read and summarize README.md" --tools
    """
    # Auto-select model based on provider if not specified
    if model is None:
        model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "mock": "mock-model",
        }.get(provider, "gpt-4o")
    
    # Parse tools_only into a set if provided
    allowed_tools: set[str] | None = None
    if tools_only:
        allowed_tools = set()
        for t in tools_only:
            allowed_tools.update(t.split(","))
    
    asyncio.run(_apply_async(
        lens_path, prompt, model, provider, stream, tier, 
        list(context), not no_workspace, output, save_session,
        headspace, not no_auto_headspace, list(learn), dead_end,
        skill, dry_run, tools, allowed_tools, trust, smart, router_model, verbose
    ))


async def _apply_async(
    lens_path: str,
    prompt: str,
    model_name: str,
    provider: str,
    stream: bool,
    tier_str: str | None,
    context_patterns: list[str],
    use_workspace: bool,
    output_path: str | None,
    session_path: str | None,
    headspace_name: str | None,
    auto_headspace: bool,
    learnings_to_add: list[str],
    dead_end_to_mark: str | None,
    skill_name: str | None,
    dry_run: bool,
    use_tools: bool,
    allowed_tools: set[str] | None,
    trust_level: str,
    use_smart_routing: bool,
    router_model_name: str | None,
    verbose: bool,
) -> None:
    """Async implementation of apply command."""
    # Load lens
    fount = FountClient()
    loader = LensLoader(fount_client=fount)
    resolver = LensResolver(loader=loader)
    
    try:
        # Convert local path to a source string that LensReference recognizes as local
        source = str(lens_path)
        if not (source.startswith("/") or source.startswith("./") or source.startswith("../")):
            source = f"./{source}"
            
        ref = LensReference(source=source)
        lens = await resolver.resolve(ref)
    except SunwellError as e:
        console.print(f"[red]Error loading/resolving lens:[/red] {e.message}")
        sys.exit(1)

    if verbose:
        console.print(Panel(lens.summary(), title="Lens Loaded", border_style="green"))

    # Create model
    model = create_model(provider, model_name)
    
    # Simulacrum handling: explicit name, auto-routing, or none
    hs = None
    headspace_path = None
    simulacrum_store = None  # SimulacrumStore from manager (for persistence)
    was_spawned = False
    
    if headspace_name:
        # Explicit headspace specified - use legacy Simulacrum object
        headspace_path = Path(".sunwell/headspaces") / f"{headspace_name}.json"
        
        if headspace_path.exists():
            hs = Simulacrum.load(headspace_path, lens=lens)
            if verbose:
                stats = hs.stats
                console.print(f"\n[cyan]Simulacrum:[/cyan] {headspace_name}")
                console.print(f"  Learnings: {stats['learnings']} | Dead ends: {stats['dead_ends']}")
                console.print(f"  Focus: {', '.join(hs.focus.active_topics[:5]) or 'none'}")
        else:
            hs = Simulacrum.create(headspace_name, lens=lens)
            if verbose:
                console.print(f"\n[cyan]Simulacrum:[/cyan] {headspace_name} (new)")
        
        # Add any learnings from command line
        for learning_text in learnings_to_add:
            await hs.add_learning(learning_text, category="fact")
            if verbose:
                console.print(f"  [green]+ Learning:[/green] {learning_text}")
        
        # Mark dead end if specified
        if dead_end_to_mark:
            hs.mark_dead_end(dead_end_to_mark)
            if verbose:
                console.print(f"  [yellow]❌ Dead end:[/yellow] {dead_end_to_mark}")
    
    elif auto_headspace:
        # Auto-routing: find best headspace or spawn new one
        try:
            manager = get_simulacrum_manager()
            simulacrum_store, was_spawned, explanation = manager.route_query(prompt)
            
            if simulacrum_store:
                headspace_name = manager._active_name
                if verbose:
                    if was_spawned:
                        console.print(f"\n[cyan]Simulacrum:[/cyan] {headspace_name} [green](auto-spawned)[/green]")
                    else:
                        console.print(f"\n[cyan]Simulacrum:[/cyan] {headspace_name} [dim](auto-routed)[/dim]")
                    stats = simulacrum_store.stats()
                    console.print(f"  Nodes: {stats.get('total_nodes', 0)} | Sessions: {stats.get('sessions', 0)}")
            else:
                if verbose:
                    console.print(f"\n[dim]Simulacrum: {explanation}[/dim]")
        except Exception as e:
            if verbose:
                console.print(f"\n[dim]Auto-headspace skipped: {e}[/dim]")

    # Handle skill execution path (RFC-011)
    if skill_name:
        if SkillExecutor is None:
            console.print("[red]Skills not available.[/red]")
            sys.exit(1)
            
        skill = lens.get_skill(skill_name)
        if not skill:
            available = [s.name for s in lens.skills] if lens.skills else []
            console.print(f"[red]Skill not found:[/red] {skill_name}")
            if available:
                console.print(f"[dim]Available skills: {', '.join(available)}[/dim]")
            else:
                console.print("[dim]This lens has no skills defined.[/dim]")
            sys.exit(1)

        if verbose:
            console.print(f"\n[cyan]Executing skill:[/cyan] {skill.name}")
            console.print(f"  Trust: {skill.trust.value}")
            if skill.scripts:
                console.print(f"  Scripts: {', '.join(s.name for s in skill.scripts)}")

        # Detect workspace for skill execution
        workspace_root = None
        if use_workspace:
            detector = WorkspaceDetector()
            workspace = detector.detect()
            workspace_root = workspace.root

        # Create executor and run skill
        executor = SkillExecutor(
            skill=skill,
            lens=lens,
            model=model,
            workspace_root=workspace_root,
        )

        skill_result = await executor.execute(
            context={"task": prompt},
            validate=not dry_run,
            dry_run=dry_run,
        )

        # Display result
        if verbose:
            console.print(f"\n[cyan]Skill Result:[/cyan]")
            console.print(f"  Validation: {'✅ Passed' if skill_result.validation_passed else '⚠️ Issues found'}")
            console.print(f"  Confidence: {skill_result.confidence:.0%}")
            if skill_result.scripts_run:
                console.print(f"  Scripts run: {', '.join(skill_result.scripts_run)}")
            if skill_result.refinement_count:
                console.print(f"  Refinements: {skill_result.refinement_count}")

        console.print(f"\n{skill_result.content}")

        # Write output if requested
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(skill_result.content)
            console.print(f"\n[green]✓ Output written to:[/green] {output_path}")

        return  # Skill execution complete

    # Create embedder (auto-detects Ollama if available)
    embedder = create_embedder()

    # Detect workspace and index codebase
    codebase_indexer = None
    workspace = None
    if use_workspace:
        detector = WorkspaceDetector()
        workspace = detector.detect()
        
        if verbose:
            console.print(f"\n[cyan]Workspace:[/cyan] {workspace.root}")
            console.print(f"  Git repo: {'Yes' if workspace.is_git else 'No'}")
        
        # Create codebase indexer
        codebase_indexer = CodebaseIndexer(
            embedder=embedder,
            include_patterns=context_patterns if context_patterns else None,
        )
        
        # Index the workspace
        if verbose:
            console.print("  [dim]Indexing codebase...[/dim]")
        
        index = await codebase_indexer.index_workspace(workspace)
        
        if verbose:
            console.print(f"  Files: {index.file_count} | Chunks: {len(index.chunks)} | Lines: {index.total_lines}")

    # Set up tool executor if tools enabled (RFC-012)
    tool_executor = None
    if use_tools:
        from sunwell.tools.executor import ToolExecutor
        from sunwell.tools.types import ToolPolicy, ToolTrust
        
        workspace_root = workspace.root if workspace else Path.cwd()
        
        # Create sandbox for run_command
        sandbox = None
        if trust_level in ("shell", "full"):
            from sunwell.skills.sandbox import ScriptSandbox
            from sunwell.skills.types import TrustLevel
            sandbox = ScriptSandbox(trust=TrustLevel.SANDBOXED)
        
        # Create tool policy
        policy = ToolPolicy(
            trust_level=ToolTrust.from_string(trust_level),
            allowed_tools=frozenset(allowed_tools) if allowed_tools else None,
        )
        
        tool_executor = ToolExecutor(
            workspace=workspace_root,
            sandbox=sandbox,
            policy=policy,
            audit_path=Path(".sunwell/audit") if verbose else None,
        )
        
        if verbose:
            console.print(f"\n[cyan]Tool Calling:[/cyan] Enabled")
            console.print(f"  Trust level: {trust_level}")
            console.print(f"  Available tools: {', '.join(tool_executor.get_available_tools())}")

    # Set up model router if requested (RFC-015)
    model_router = None
    if use_smart_routing:
        # Use a "stupid" model for classification if available
        stupid_model = None
        if provider == "ollama":
            stupid_model = create_model("ollama", "gemma3:1b")
        elif provider == "openai":
            stupid_model = create_model("openai", "gpt-4o-mini")
        
        model_router = ModelRouter(
            primary_model=model,
            stupid_model=stupid_model,
            lens=lens,
        )
        
        if verbose:
            console.print(f"\n[cyan]Adaptive Model Selection:[/cyan] Enabled")
    
    # RFC-020: Cognitive routing
    cognitive_router = None
    if router_model_name:
        from sunwell.routing import CognitiveRouter
        
        router_model = create_model("ollama", router_model_name)
        
        # Discover available lenses
        lens_dir = Path("lenses")
        available_lenses = []
        if lens_dir.exists():
            available_lenses = [p.stem for p in lens_dir.glob("*.lens")]
        
        cognitive_router = CognitiveRouter(
            router_model=router_model,
            available_lenses=available_lenses,
        )
        
        if verbose:
            console.print(f"\n[cyan]Cognitive Routing (RFC-020):[/cyan] {router_model_name}")

    # Create runtime
    engine = RuntimeEngine(
        model=model,
        lens=lens,
        embedder=embedder,
        codebase_indexer=codebase_indexer,
        tool_executor=tool_executor,
        model_router=model_router,
        cognitive_router=cognitive_router,
    )

    # Parse tier
    force_tier = None
    if tier_str:
        force_tier = Tier(int(tier_str))

    # Show what's being retrieved/injected in verbose mode
    if verbose:
        from sunwell.runtime.classifier import IntentClassifier
        from sunwell.runtime.retriever import ExpertiseRetriever
        
        # Classify intent
        classifier = IntentClassifier(lens=lens)
        classification = classifier.classify(prompt)
        
        console.print(f"\n[cyan]Intent Classification:[/cyan]")
        console.print(f"  Tier: [bold]{classification.tier.name}[/bold]")
        if classification.signals:
            console.print(f"  Signals: {', '.join(classification.signals)}")
        
        # Show lens retrieval
        if classification.tier.value > 0:  # Not FAST_PATH
            retriever = ExpertiseRetriever(lens=lens, embedder=embedder, relevance_threshold=0.0)
            await retriever.initialize()
            retrieval = await retriever.retrieve(prompt, top_k=5)
            
            console.print(f"\n[cyan]Retrieved Lens Components:[/cyan]")
            if retrieval.heuristics:
                console.print("  [green]Heuristics:[/green]")
                for h in retrieval.heuristics:
                    score = retrieval.relevance_scores.get(f"heuristic:{h.name}", 0)
                    console.print(f"    • {h.name} [dim](score: {score:.2f})[/dim]")
            if retrieval.personas:
                console.print("  [magenta]Personas:[/magenta]")
                for p in retrieval.personas:
                    console.print(f"    • {p.name}")
            if retrieval.validators:
                console.print("  [red]Validators:[/red]")
                for v in retrieval.validators:
                    console.print(f"    • {v.name}")
        
        # Show codebase retrieval
        if codebase_indexer:
            code_retrieval = await codebase_indexer.retrieve(prompt, top_k=5)
            if code_retrieval.chunks:
                console.print(f"\n[cyan]Retrieved Code Context:[/cyan]")
                for chunk in code_retrieval.chunks:
                    score = code_retrieval.relevance_scores.get(chunk.id, 0)
                    console.print(f"  [blue]• {chunk.reference}[/blue] [dim](score: {score:.2f})[/dim]")
        
        console.print()

    # Build prompt with headspace context if available
    full_prompt = prompt
    if hs:
        # Get headspace context (learnings, dead ends, focus)
        hs_context, hs_result = await hs.assemble_context(prompt, parallel=True)
        
        if hs_context:
            full_prompt = f"{hs_context}\n\n---\n\n## Current Task\n\n{prompt}"
            
            if verbose and hs_result.learnings:
                console.print(f"\n[cyan]Simulacrum Context:[/cyan]")
                console.print(f"  Learnings injected: {len(hs_result.learnings)}")
                if hs_result.focus_topics:
                    console.print(f"  Focus: {', '.join(hs_result.focus_topics[:5])}")
        
        # Record user message in headspace
        await hs.add_user_message(prompt)

    if use_tools and tool_executor:
        # Tool-aware execution (RFC-012)
        if stream:
            # Streaming with tools
            console.print("[dim]Generating with tools...[/dim]\n")
            content_parts = []
            
            from sunwell.runtime.engine import TextEvent, ToolCallEvent, ToolResultEvent, DoneEvent
            
            async for event in engine.execute_stream_with_tools(
                full_prompt,
                allowed_tools=allowed_tools,
            ):
                if isinstance(event, TextEvent):
                    console.print(event.text, end="")
                    content_parts.append(event.text)
                elif isinstance(event, ToolCallEvent):
                    console.print(f"\n[cyan][Tool Call][/cyan] {event.tool_call.name}({format_args(event.tool_call.arguments)})")
                    console.print("[dim]Executing...[/dim]")
                elif isinstance(event, ToolResultEvent):
                    status = "[green]✓[/green]" if event.result.success else "[red]✗[/red]"
                    output_preview = event.result.output[:100] + "..." if len(event.result.output) > 100 else event.result.output
                    console.print(f"{status} {output_preview}\n")
                elif isinstance(event, DoneEvent):
                    if event.truncated:
                        console.print(f"\n[yellow]⚠ Max tool calls reached ({event.total_tool_calls})[/yellow]")
            
            console.print()
            final_content = "".join(content_parts)
            result = None
        else:
            # Non-streaming with tools
            with console.status("[bold green]Processing with tools..."):
                tool_result = await engine.execute_with_tools(
                    full_prompt,
                    allowed_tools=allowed_tools,
                )
            
            # Display tool history if verbose
            if verbose and tool_result.tool_history:
                console.print(f"\n[cyan]Tool Execution History:[/cyan]")
                for tool_call, tool_res in tool_result.tool_history:
                    status = "[green]✓[/green]" if tool_res.success else "[red]✗[/red]"
                    console.print(f"  {status} {tool_call.name}: {tool_res.execution_time_ms}ms")
            
            # Display result
            console.print(Markdown(tool_result.content))
            final_content = tool_result.content
            
            if verbose:
                console.print(f"\n[dim]Total tool calls: {tool_result.total_tool_calls}[/dim]")
                if tool_result.truncated:
                    console.print("[yellow]⚠ Max tool calls reached[/yellow]")
            
            result = None  # Different result type
    elif stream:
        # Stream output - collect for potential file writing
        console.print("[dim]Generating...[/dim]\n")
        content_parts = []
        async for chunk in engine.execute_stream(full_prompt):
            console.print(chunk, end="")
            content_parts.append(chunk)
        console.print()
        final_content = "".join(content_parts)
        result = None  # No full result in stream mode
    else:
        # Full execution with validation
        with console.status("[bold green]Processing..."):
            result = await engine.execute(full_prompt, force_tier=force_tier)

        # Display result
        console.print(Markdown(result.content))
        final_content = result.content

        if verbose:
            console.print()
            display_execution_stats(result)
    
    # Update headspace with response and auto-extract learnings
    if hs and headspace_path:
        # Legacy Simulacrum path
        await hs.add_assistant_message(final_content, model=f"{provider}:{model_name}")
        
        # Auto-extract learnings from response
        from sunwell.simulacrum.extractor import auto_extract_learnings
        extracted = auto_extract_learnings(final_content, min_confidence=0.6)
        
        for learning_text, category, confidence in extracted[:3]:  # Top 3
            await hs.add_learning(learning_text, category=category, confidence=confidence)
            if verbose:
                console.print(f"  [green]+ Auto-learned ({category}):[/green] {learning_text[:60]}...")
        
        hs.save(headspace_path)
        
        if verbose:
            stats = hs.stats
            console.print(f"\n[dim]Simulacrum saved: {headspace_name} ({stats['learnings']} learnings)[/dim]")
    
    elif simulacrum_store:
        # SimulacrumStore from manager (auto-routed)
        # Store the turn in the DAG
        simulacrum_store.add_turn(
            role="user",
            content=prompt,
        )
        simulacrum_store.add_turn(
            role="assistant",
            content=final_content,
            model=f"{provider}:{model_name}",
        )
        
        # Auto-extract and store learnings
        try:
            from sunwell.simulacrum.extractor import auto_extract_learnings
            extracted = auto_extract_learnings(final_content, min_confidence=0.6)
            
            for learning_text, category, confidence in extracted[:3]:
                simulacrum_store.add_learning(learning_text, category=category, confidence=confidence)
                if verbose:
                    console.print(f"  [green]+ Auto-learned ({category}):[/green] {learning_text[:60]}...")
        except ImportError:
            pass
        
        # SimulacrumStore auto-saves, but ensure it's flushed
        simulacrum_store.flush()
        
        if verbose:
            stats = simulacrum_store.stats()
            console.print(f"\n[dim]Simulacrum updated: {headspace_name} ({stats.get('total_nodes', 0)} nodes)[/dim]")
    
    # Write output to file if requested
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(final_content)
        console.print(f"\n[green]✓ Output written to:[/green] {output_path}")
    
    # Save session snapshot if requested
    if session_path and result:
        snapshot = EpisodeSnapshot.from_result(
            lens=lens,
            prompt=prompt,
            result=result,
            retrieved_code=list(result.retrieved_code) if result.retrieved_code else [],
        )
        snapshot.save(Path(session_path))
        console.print(f"[green]✓ Session saved to:[/green] {session_path}")
