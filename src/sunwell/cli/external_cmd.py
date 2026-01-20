"""CLI Commands for External Integration (RFC-049).

Commands for managing external event sources, webhooks, and scheduled jobs.
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def external():
    """External integration commands.

    Manage CI/CD, Git, Issue Tracker, and Production Monitoring integrations.

    \b
    Quick start:
        sunwell external start      # Start webhook server + polling
        sunwell external status     # Show integration status
        sunwell external events     # List recent events
    """
    pass


@external.command()
@click.option("--no-server", is_flag=True, help="Polling only (no webhook server)")
@click.option("--host", default="0.0.0.0", help="Webhook server host")
@click.option("--port", default=8080, type=int, help="Webhook server port")
def start(no_server: bool, host: str, port: int):
    """Start external integration.

    Starts the webhook server (unless --no-server) and begins polling
    configured event sources.
    """
    asyncio.run(_start_external(no_server, host, port))


async def _start_external(no_server: bool, host: str, port: int):
    """Start external integration."""
    from sunwell.backlog.manager import BacklogManager
    from sunwell.external.policy import ExternalGoalPolicy
    from sunwell.external.processor import EventProcessor
    from sunwell.external.scheduler import ExternalScheduler

    root = Path.cwd()

    # Initialize backlog manager
    backlog_manager = BacklogManager(root)

    # Initialize processor
    policy = ExternalGoalPolicy()
    processor = EventProcessor(root, backlog_manager, policy)

    # Try to setup adapters based on environment
    await _setup_adapters(processor)

    # Setup scheduler
    scheduler = ExternalScheduler(processor)
    scheduler.add_default_schedules()

    # Check for crash recovery
    unprocessed = await processor.recover_from_crash()
    if unprocessed:
        console.print(f"[yellow]⚠️ Found {len(unprocessed)} unprocessed events from previous session[/yellow]")

    # Display status
    console.print("\n[bold green]🌐 External Integration Started[/bold green]")

    if not no_server:
        console.print(f"   Webhook server: http://{host}:{port}")

    console.print("\n   [bold]Sources:[/bold]")
    for source, adapter in processor._adapters.items():
        console.print(f"   ✅ {source.value}: ready")

    if not processor._adapters:
        console.print("   [yellow]No adapters configured[/yellow]")
        console.print("   Set GITHUB_TOKEN environment variable to enable GitHub integration")

    # Display schedules
    scheduler.start()
    jobs = scheduler.get_jobs()
    if jobs:
        console.print("\n   [bold]📅 Scheduled Jobs:[/bold]")
        for job in jobs:
            next_run = job.get("next_run", "unknown")
            console.print(f"   • {job['name']}: {job['cron']} (next: {next_run})")

    if not no_server:
        # Start webhook server
        from sunwell.external.server import WebhookServer

        server = WebhookServer(processor, host, port)
        urls = server.get_webhook_urls()

        console.print("\n   [bold]Endpoints:[/bold]")
        for name, url in urls.items():
            console.print(f"   POST {url}")

        console.print("\n[dim]Listening for events... (Ctrl+C to stop)[/dim]\n")

        try:
            await server.start()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
    else:
        console.print("\n[dim]Running in polling mode... (Ctrl+C to stop)[/dim]\n")

        try:
            # Just keep running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")

    scheduler.stop()


async def _setup_adapters(processor):
    """Setup adapters based on environment variables."""
    import os

    from sunwell.external.adapters.github import GitHubAdapter

    # GitHub
    github_token = os.environ.get("GITHUB_TOKEN")
    github_webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    github_repo = os.environ.get("GITHUB_REPO")

    if github_token:
        adapter = GitHubAdapter(
            token=github_token,
            webhook_secret=github_webhook_secret,
            repo=github_repo,
        )
        processor.register_adapter(adapter)


@external.command()
def status():
    """Show external integration status."""
    asyncio.run(_show_status())


async def _show_status():
    """Show status of external integration."""
    import os

    from sunwell.external.store import ExternalEventStore

    root = Path.cwd()
    store = ExternalEventStore(root)

    console.print("\n[bold]External Integration Status[/bold]\n")

    # Check environment
    table = Table(title="Configuration")
    table.add_column("Source", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    # GitHub
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    if github_token:
        table.add_row("GitHub", "✅ Configured", github_repo or "No repo set")
    else:
        table.add_row("GitHub", "❌ Not configured", "Set GITHUB_TOKEN")

    # Linear
    linear_key = os.environ.get("LINEAR_API_KEY")
    if linear_key:
        table.add_row("Linear", "✅ Configured", "")
    else:
        table.add_row("Linear", "⏸️ Disabled", "Set LINEAR_API_KEY")

    # Sentry
    sentry_secret = os.environ.get("SENTRY_WEBHOOK_SECRET")
    if sentry_secret:
        table.add_row("Sentry", "✅ Configured", "")
    else:
        table.add_row("Sentry", "⏸️ Disabled", "Set SENTRY_WEBHOOK_SECRET")

    console.print(table)

    # Recent events
    events = await store.get_recent(limit=5)
    if events:
        console.print("\n[bold]Recent Events[/bold]")
        event_table = Table()
        event_table.add_column("Time", style="dim")
        event_table.add_column("Source", style="cyan")
        event_table.add_column("Type")
        event_table.add_column("ID")

        for event in events:
            event_table.add_row(
                event.timestamp.strftime("%Y-%m-%d %H:%M"),
                event.source.value,
                event.event_type.value,
                event.id[:20] + "..." if len(event.id) > 20 else event.id,
            )

        console.print(event_table)
    else:
        console.print("\n[dim]No recent events[/dim]")


@external.command()
@click.option("--source", help="Filter by source (github, linear, sentry)")
@click.option("--limit", default=20, help="Number of events to show")
def events(source: str | None, limit: int):
    """List recent external events."""
    asyncio.run(_list_events(source, limit))


async def _list_events(source: str | None, limit: int):
    """List recent events."""
    from sunwell.external.store import ExternalEventStore
    from sunwell.external.types import EventSource

    root = Path.cwd()
    store = ExternalEventStore(root)

    events = await store.get_recent(limit=limit)

    if source:
        try:
            source_enum = EventSource(source)
            events = [e for e in events if e.source == source_enum]
        except ValueError:
            console.print(f"[red]Unknown source: {source}[/red]")
            return

    if not events:
        console.print("[dim]No events found[/dim]")
        return

    table = Table(title=f"External Events (showing {len(events)})")
    table.add_column("Time", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Type")
    table.add_column("ID")
    table.add_column("URL", style="dim")

    for event in events:
        url = event.external_url or ""
        if len(url) > 40:
            url = url[:37] + "..."

        table.add_row(
            event.timestamp.strftime("%Y-%m-%d %H:%M"),
            event.source.value,
            event.event_type.value,
            event.id[:25] + "..." if len(event.id) > 25 else event.id,
            url,
        )

    console.print(table)


@external.command()
@click.argument("source")
def poll(source: str):
    """Force poll a specific source now.

    SOURCE: github, gitlab, etc.
    """
    asyncio.run(_poll_source(source))


async def _poll_source(source: str):
    """Poll a specific source."""
    import os

    from sunwell.backlog.manager import BacklogManager
    from sunwell.external.policy import ExternalGoalPolicy
    from sunwell.external.processor import EventProcessor
    from sunwell.external.types import EventSource

    try:
        source_enum = EventSource(source)
    except ValueError:
        console.print(f"[red]Unknown source: {source}[/red]")
        return

    root = Path.cwd()
    backlog_manager = BacklogManager(root)
    policy = ExternalGoalPolicy()
    processor = EventProcessor(root, backlog_manager, policy)

    await _setup_adapters(processor)

    adapter = processor._adapters.get(source_enum)
    if not adapter:
        console.print(f"[red]Adapter not configured for {source}[/red]")
        return

    console.print(f"[dim]Polling {source}...[/dim]")

    # For GitHub, we can manually trigger polling
    if source_enum == EventSource.GITHUB:
        from datetime import UTC, datetime, timedelta

        since = datetime.now(UTC) - timedelta(hours=1)
        events = []

        events.extend(await adapter._poll_workflow_runs(since))
        events.extend(await adapter._poll_issues(since))
        events.extend(await adapter._poll_pull_requests(since))

        console.print(f"\n[green]Found {len(events)} events[/green]")

        for event in events:
            goal = await processor.process_event(event)
            if goal:
                console.print(f"  ➕ Created goal: {goal.title}")
            else:
                console.print(f"  ⏭️ Skipped: {event.id}")
    else:
        console.print(f"[yellow]Polling not supported for {source}[/yellow]")


@external.command()
def schedules():
    """List scheduled jobs."""
    asyncio.run(_list_schedules())


async def _list_schedules():
    """List scheduled jobs."""
    from sunwell.backlog.manager import BacklogManager
    from sunwell.external.policy import ExternalGoalPolicy
    from sunwell.external.processor import EventProcessor
    from sunwell.external.scheduler import ExternalScheduler

    root = Path.cwd()
    backlog_manager = BacklogManager(root)
    policy = ExternalGoalPolicy()
    processor = EventProcessor(root, backlog_manager, policy)

    scheduler = ExternalScheduler(processor)
    scheduler.add_default_schedules()
    scheduler.start()

    jobs = scheduler.get_jobs()

    if not jobs:
        console.print("[dim]No scheduled jobs[/dim]")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("Name", style="cyan")
    table.add_column("Cron")
    table.add_column("Next Run")
    table.add_column("Status")

    for job in jobs:
        table.add_row(
            job["name"],
            job["cron"],
            job["next_run"] or "unknown",
            "✅ Enabled" if job["enabled"] else "⏸️ Disabled",
        )

    console.print(table)

    scheduler.stop()


@external.command()
@click.argument("name")
def run(name: str):
    """Run a scheduled job immediately.

    NAME: Job name (e.g., nightly_backlog, weekly_security)
    """
    asyncio.run(_run_job(name))


async def _run_job(name: str):
    """Run a scheduled job."""
    from sunwell.backlog.manager import BacklogManager
    from sunwell.external.policy import ExternalGoalPolicy
    from sunwell.external.processor import EventProcessor
    from sunwell.external.scheduler import ExternalScheduler

    root = Path.cwd()
    backlog_manager = BacklogManager(root)
    policy = ExternalGoalPolicy()
    processor = EventProcessor(root, backlog_manager, policy)

    scheduler = ExternalScheduler(processor)
    scheduler.add_default_schedules()

    console.print(f"[dim]Running job: {name}...[/dim]")

    success = await scheduler.run_job_now(name)
    if success:
        console.print(f"[green]✅ Job {name} completed[/green]")
    else:
        console.print(f"[red]❌ Job {name} not found or failed[/red]")


@external.command()
def webhook():
    """Show webhook URLs for configuration."""
    console.print("\n[bold]Webhook URLs[/bold]\n")
    console.print("Configure these URLs in your external services:\n")

    host = "your-server.example.com"  # Placeholder
    port = 8080

    table = Table()
    table.add_column("Service", style="cyan")
    table.add_column("URL")
    table.add_column("Required Headers", style="dim")

    table.add_row("GitHub", f"https://{host}:{port}/webhook/github", "X-Hub-Signature-256")
    table.add_row("GitLab", f"https://{host}:{port}/webhook/gitlab", "X-Gitlab-Token")
    table.add_row("Linear", f"https://{host}:{port}/webhook/linear", "Linear-Webhook-Signature")
    table.add_row("Sentry", f"https://{host}:{port}/webhook/sentry", "Sentry-Hook-Signature")

    console.print(table)

    console.print("\n[dim]For local development, use ngrok or similar to expose your local server.[/dim]")
