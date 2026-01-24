"""Event emitters for execution (RFC-094).

Provides stdout-based event emission for CLI usage.
"""

import json
import sys

from rich.console import Console

from sunwell.agent.events import AgentEvent, EventType


class StdoutEmitter:
    """Emit events to stdout (RFC-094).

    Supports both JSON and console output modes.
    """

    def __init__(self, json_output: bool = False):
        self.json_output = json_output
        self.console = Console()

    def emit(self, event: AgentEvent) -> None:
        """Emit an event."""
        if self.json_output:
            print(json.dumps(event.to_dict()), file=sys.stdout, flush=True)
        else:
            self._emit_console(event)

    def _emit_console(self, event: AgentEvent) -> None:
        """Emit event to console with formatting."""
        event_type = event.type
        data = event.data

        match event_type:
            case EventType.BACKLOG_GOAL_ADDED:
                self.console.print(f"[dim]📋 Goal added: {data.get('title', data.get('goal_id'))}[/dim]")

            case EventType.BACKLOG_GOAL_STARTED:
                self.console.print(f"[cyan]🚀 Starting: {data.get('title', data.get('goal_id'))}[/cyan]")

            case EventType.BACKLOG_GOAL_COMPLETED:
                artifacts = data.get("artifacts", [])
                failed = data.get("failed", [])
                partial = data.get("partial", False)
                if partial:
                    self.console.print(f"[yellow]⚠ Completed (partial): {len(artifacts)} created, {len(failed)} failed[/yellow]")
                else:
                    self.console.print(f"[green]✓ Completed: {len(artifacts)} artifacts[/green]")

            case EventType.BACKLOG_GOAL_FAILED:
                self.console.print(f"[red]✗ Failed: {data.get('error', 'Unknown error')}[/red]")

            case EventType.PLAN_START:
                self.console.print(f"[dim]Planning: {data.get('goal', '')}[/dim]")

            case EventType.PLAN_WINNER:
                self.console.print(f"[dim]Plan ready: {data.get('tasks', 0)} tasks[/dim]")

            case EventType.TASK_START:
                self.console.print(f"  [cyan]→[/cyan] {data.get('description', data.get('task_id'))}")

            case EventType.TASK_COMPLETE:
                pass  # Handled silently

            case EventType.TASK_FAILED:
                self.console.print(f"  [red]✗[/red] {data.get('task_id')}: {data.get('error', '')}")

            case EventType.COMPLETE:
                completed = data.get("tasks_completed", 0)
                failed = data.get("tasks_failed", 0)
                duration = data.get("duration_s", 0)
                self.console.print(f"\n[bold]Completed: {completed} tasks, {failed} failed ({duration:.1f}s)[/bold]")

            case EventType.ERROR:
                self.console.print(f"[red]Error: {data.get('message', '')}[/red]")

            case _:
                # Other events: show in verbose mode only
                pass
