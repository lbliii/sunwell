"""Generative Interface CLI Commands (RFC-075).

Commands for the LLM-driven interaction routing system.
"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def interface() -> None:
    """Generative interface commands (RFC-075)."""
    pass


@interface.command("process")
@click.option("--goal", "-g", required=True, help="User goal to process")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--data-dir", "-d", default=None, help="Data directory path")
@click.option("--model", "-m", default=None, help="Model to use for intent analysis")
@click.option("--history", default=None, help="JSON array of prior conversation messages")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def process(
    goal: str,
    json_output: bool,
    data_dir: str | None,
    model: str | None,
    history: str | None,
    verbose: bool,
) -> None:
    """Process a goal through the generative interface."""
    # Parse history if provided
    parsed_history = None
    if history:
        try:
            parsed_history = json.loads(history)
        except json.JSONDecodeError:
            if not json_output:
                console.print("[yellow]Warning: Could not parse history JSON, ignoring[/yellow]")

    asyncio.run(_process(goal, json_output, data_dir, model, parsed_history, verbose))


async def _process(
    goal: str,
    json_output: bool,
    data_dir_str: str | None,
    model_name: str | None,
    history: list[dict[str, str]] | None,
    verbose: bool,
) -> None:
    """Process a goal through the generative interface."""
    from sunwell.interface.analyzer import IntentAnalyzer
    from sunwell.interface.executor import ActionExecutor
    from sunwell.interface.router import InteractionRouter
    from sunwell.interface.views import ViewRenderer
    from sunwell.providers.registry import ProviderRegistry

    # Setup data directory
    data_dir = Path(data_dir_str) if data_dir_str else Path.cwd() / ".sunwell"

    if verbose and not json_output:
        console.print(f"[dim]Data directory: {data_dir}[/dim]")

    # Initialize providers
    providers = ProviderRegistry.create_default(data_dir)

    # Initialize LLM
    try:
        from sunwell.models.ollama import OllamaModel

        model = OllamaModel(model=model_name or "gemma3:4b")
        if verbose and not json_output:
            console.print(f"[dim]Using model: {model.model}[/dim]")
    except Exception as e:
        if json_output:
            click.echo(json.dumps({"error": f"Failed to load model: {e}"}))
        else:
            console.print(f"[red]Failed to load model: {e}[/red]")
        return

    # Build analyzer
    analyzer = IntentAnalyzer(
        model=model,
        calendar=providers.calendar,
        lists=providers.lists,
        notes=providers.notes,
    )

    # Analyze intent (with conversation history for context)
    if verbose and not json_output:
        console.print(f"[dim]Analyzing: {goal}[/dim]")
        if history:
            console.print(f"[dim]With {len(history)} prior messages[/dim]")

    analysis = await analyzer.analyze(goal, conversation_history=history)

    if verbose and not json_output:
        confidence = f"{analysis.confidence:.0%}"
        console.print(f"[dim]Intent: {analysis.interaction_type} (confidence: {confidence})[/dim]")
        if analysis.reasoning:
            console.print(f"[dim]Reasoning: {analysis.reasoning}[/dim]")

    # Build router
    router = InteractionRouter(
        action_executor=ActionExecutor(
            calendar=providers.calendar,
            lists=providers.lists,
        ),
        view_renderer=ViewRenderer(providers),
    )

    # Route to appropriate handler
    output = await router.route(analysis)

    # Output result
    if json_output:
        click.echo(json.dumps(output.to_dict()))
    else:
        _print_output(output, analysis, verbose)


def _print_output(output, analysis, verbose: bool) -> None:
    """Print output in a human-readable format."""
    from sunwell.interface.router import (
        ActionOutput,
        ConversationOutput,
        HybridOutput,
        ViewOutput,
        WorkspaceOutput,
    )

    if isinstance(output, ActionOutput):
        if output.success:
            console.print(Panel(
                f"✓ {output.response}",
                title="Action Complete",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"✗ {output.response}",
                title="Action Failed",
                border_style="red",
            ))

    elif isinstance(output, ViewOutput):
        console.print(Panel(
            output.response or "Here's what I found:",
            title=f"View: {output.view_type.title()}",
            border_style="blue",
        ))
        _print_view_data(output.view_type, output.data)

    elif isinstance(output, WorkspaceOutput):
        console.print(Panel(
            output.response or "Workspace ready.",
            title="Workspace",
            border_style="magenta",
        ))
        if output.workspace_spec and verbose:
            console.print(f"[dim]Primary: {output.workspace_spec.get('primary')}[/dim]")
            if output.workspace_spec.get("secondary"):
                secondary = ", ".join(output.workspace_spec.get("secondary", []))
                console.print(f"[dim]Secondary: {secondary}[/dim]")

    elif isinstance(output, ConversationOutput):
        if output.mode == "informational":
            emoji = "💬"
        elif output.mode == "empathetic":
            emoji = "💜"
        else:
            emoji = "🤝"
        console.print(Panel(
            output.response,
            title=f"{emoji} Response",
            border_style="cyan",
        ))

    elif isinstance(output, HybridOutput):
        console.print(Panel(
            f"✓ {output.action.response}",
            title="Action",
            border_style="green",
        ))
        console.print()
        _print_view_data(output.view.view_type, output.view.data)


def _print_view_data(view_type: str, data: dict) -> None:
    """Print view data in a formatted way."""
    if view_type == "calendar":
        events = data.get("events", [])
        if not events:
            console.print("[dim]No events found.[/dim]")
            return

        table = Table(title=f"Calendar ({data.get('event_count', 0)} events)")
        table.add_column("Date", style="cyan")
        table.add_column("Time", style="green")
        table.add_column("Title")
        table.add_column("Location", style="dim")

        for event in events[:10]:
            from datetime import datetime
            start = datetime.fromisoformat(event["start"])
            table.add_row(
                start.strftime("%a %b %d"),
                start.strftime("%I:%M %p"),
                event["title"],
                event.get("location") or "",
            )

        console.print(table)

    elif view_type == "list":
        items = data.get("items", [])
        if not items:
            console.print("[dim]No items found.[/dim]")
            return

        list_name = data.get("list_name", "default")
        console.print(f"[bold]{list_name.title()} List[/bold] ({len(items)} items)")

        for item in items[:20]:
            status = "✓" if item.get("completed") else "○"
            style = "dim strikethrough" if item.get("completed") else ""
            console.print(f"  {status} [{style}]{item['text']}[/]")

    elif view_type == "notes":
        notes = data.get("notes", [])
        if not notes:
            console.print("[dim]No notes found.[/dim]")
            return

        for note in notes[:10]:
            console.print(f"[bold]{note['title']}[/bold]")
            preview = note.get("content", "")[:100]
            if len(note.get("content", "")) > 100:
                preview += "..."
            console.print(f"  [dim]{preview}[/dim]")

    elif view_type == "search":
        results = data.get("results", [])
        if not results:
            console.print(f"[dim]No results for '{data.get('query')}'[/dim]")
            return

        console.print(f"[bold]Search Results[/bold] ({len(results)} found)")
        for result in results[:10]:
            result_type = result.get("type", "unknown")
            if result_type == "note":
                console.print(f"  📝 {result.get('title')}")
            elif result_type == "list_item":
                console.print(f"  📋 {result.get('text')} [{result.get('list')}]")
            elif result_type == "event":
                console.print(f"  📅 {result.get('title')}")


@interface.command("demo")
@click.option("--data-dir", "-d", default=None, help="Data directory path")
def demo(data_dir: str | None) -> None:
    """Run a demo of the generative interface with sample data."""
    asyncio.run(_demo(data_dir))


async def _demo(data_dir_str: str | None) -> None:
    """Set up demo data and show capabilities."""
    from datetime import datetime, timedelta

    from sunwell.providers.registry import ProviderRegistry

    # Setup data directory
    data_dir = Path(data_dir_str) if data_dir_str else Path.cwd() / ".sunwell"

    console.print("[bold]🌟 Generative Interface Demo[/bold]")
    console.print(f"[dim]Data directory: {data_dir}[/dim]\n")

    # Initialize providers
    providers = ProviderRegistry.create_default(data_dir)

    # Create sample data
    console.print("[bold]Creating sample data...[/bold]")

    # Sample lists
    await providers.lists.add_item("grocery", "Milk")
    await providers.lists.add_item("grocery", "Bread")
    await providers.lists.add_item("grocery", "Eggs")
    await providers.lists.add_item("todo", "Review RFC-075")
    await providers.lists.add_item("todo", "Write tests")
    console.print("  ✓ Created grocery and todo lists")

    # Sample events
    from sunwell.providers.base import CalendarEvent

    now = datetime.now()
    await providers.calendar.create_event(CalendarEvent(
        id="",
        title="Team Meeting",
        start=now + timedelta(days=1, hours=10),
        end=now + timedelta(days=1, hours=11),
        location="Conference Room A",
    ))
    await providers.calendar.create_event(CalendarEvent(
        id="",
        title="Dinner with Sarah",
        start=now + timedelta(days=2, hours=19),
        end=now + timedelta(days=2, hours=21),
        location="Italian Restaurant",
    ))
    console.print("  ✓ Created calendar events")

    # Sample notes
    ideas_content = (
        "# Project Ideas\n\n"
        "- Build a habit tracker\n"
        "- Create a recipe app\n"
        "- Design a meditation timer"
    )
    await providers.notes.create("Project Ideas", ideas_content, ["ideas", "projects"])
    await providers.notes.create(
        "Meeting Notes",
        "# Team Sync - Jan 20\n\nDiscussed Q1 goals and resource allocation.",
        ["meeting", "work"],
    )
    console.print("  ✓ Created sample notes")

    console.print("\n[bold]Sample commands to try:[/bold]")
    console.print('  sunwell interface process -g "add broccoli to grocery list"')
    console.print('  sunwell interface process -g "what am i doing tomorrow"')
    console.print('  sunwell interface process -g "show my todo list"')
    console.print('  sunwell interface process -g "write a story about dragons"')
    console.print('  sunwell interface process -g "i feel stressed today"')


@interface.command("list-providers")
@click.option("--data-dir", "-d", default=None, help="Data directory path")
def list_providers(data_dir: str | None) -> None:
    """List configured data providers."""
    from sunwell.providers.registry import ProviderRegistry

    data_dir_path = Path(data_dir) if data_dir else Path.cwd() / ".sunwell"
    providers = ProviderRegistry.create_default(data_dir_path)

    table = Table(title="Configured Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Status", style="yellow")

    table.add_row(
        "Calendar",
        "SunwellCalendar",
        "✓ Active" if providers.has_calendar() else "✗ Not configured",
    )
    table.add_row(
        "Lists",
        "SunwellLists",
        "✓ Active" if providers.has_lists() else "✗ Not configured",
    )
    table.add_row(
        "Notes",
        "SunwellNotes",
        "✓ Active" if providers.has_notes() else "✗ Not configured",
    )

    console.print(table)
    console.print(f"\n[dim]Data directory: {data_dir_path}[/dim]")


@interface.command("compose")
@click.option("--input", "-i", "user_input", required=True, help="User input to analyze")
@click.option("--page", "-p", default="home", help="Current page type")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def compose(user_input: str, page: str, json_output: bool) -> None:
    """Predict UI composition (RFC-082 Tier 0/1).

    Fast speculative composition prediction for skeleton rendering.
    Uses regex pattern matching (Tier 0) and optionally fast model (Tier 1).

    Examples:
        sunwell interface compose -i "plan my week" --json
        sunwell interface compose -i "help me write a story" -p conversation
    """
    asyncio.run(_compose(user_input, page, json_output))


async def _compose(user_input: str, current_page: str, json_output: bool) -> None:
    """Predict UI composition."""
    from sunwell.interface.compositor import CompositionContext, Compositor

    compositor = Compositor()

    context = CompositionContext(
        current_page=current_page,
        recent_panels=[],
    )

    spec = await compositor.predict(user_input, context)

    if json_output:
        click.echo(json.dumps(spec.to_dict()))
    else:
        confidence_pct = f"{spec.confidence:.0%}"
        console.print(f"[bold]Composition Prediction[/bold] ({spec.source})")
        console.print(f"  Page: [cyan]{spec.page_type}[/cyan]")
        console.print(f"  Input Mode: [green]{spec.input_mode}[/green]")
        console.print(f"  Confidence: [yellow]{confidence_pct}[/yellow]")

        if spec.panels:
            panels = ", ".join(p.panel_type for p in spec.panels)
            console.print(f"  Panels: [magenta]{panels}[/magenta]")

        if spec.suggested_tools:
            tools = ", ".join(spec.suggested_tools)
            console.print(f"  Tools: [blue]{tools}[/blue]")


@interface.command("action")
@click.option("--action-id", "-a", required=True, help="Action ID to execute")
@click.option("--item-id", "-i", default=None, help="Item ID for the action")
@click.option("--data-dir", "-d", default=None, help="Data directory path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def action(action_id: str, item_id: str | None, data_dir: str | None, json_output: bool) -> None:
    """Execute a block action (RFC-080).

    Actions are quick operations like completing a habit, checking a list item,
    or opening a file. They are embedded in Home blocks.

    Examples:
        sunwell interface action -a complete -i habit_123
        sunwell interface action -a check -i item_456
        sunwell interface action -a add_event
    """
    asyncio.run(_execute_action(action_id, item_id, data_dir, json_output))


async def _execute_action(
    action_id: str,
    item_id: str | None,
    data_dir_str: str | None,
    json_output: bool,
) -> None:
    """Execute a block action."""
    from sunwell.interface.block_actions import BlockActionExecutor
    from sunwell.providers.registry import ProviderRegistry

    # Setup data directory
    data_dir = Path(data_dir_str) if data_dir_str else Path.cwd() / ".sunwell"

    # Initialize providers
    providers = ProviderRegistry.create_default(data_dir)

    # Build executor with all available providers
    executor = BlockActionExecutor(
        calendar=providers.calendar if providers.has_calendar() else None,
        lists=providers.lists if providers.has_lists() else None,
        notes=providers.notes if providers.has_notes() else None,
        habits=providers.habits if providers.has_habits() else None,
    )

    # Execute action
    result = await executor.execute(action_id, item_id)

    # Output result
    if json_output:
        click.echo(json.dumps({
            "success": result.success,
            "message": result.message,
            "data": result.data,
        }))
    else:
        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
        else:
            console.print(f"[red]✗ {result.message}[/red]")
