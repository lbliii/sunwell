"""CLI renderer for Adaptive Agent streaming (RFC-042).

Uses Rich library for beautiful, real-time terminal output.
Shows:
- Signal extraction and routing decisions
- Plan candidates and selection
- Task progress with progress bars
- Gate validation cascade
- Fix attempts and outcomes

Modes:
- Interactive: Full Rich rendering (default)
- Quiet: Minimal output for CI/scripts
- JSON: Newline-delimited JSON events
"""

import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TextIO

from sunwell.adaptive.events import AgentEvent, EventType


@dataclass
class RendererConfig:
    """Configuration for the renderer."""

    mode: str = "interactive"
    """Rendering mode: interactive, quiet, json."""

    refresh_rate: int = 10
    """Refresh rate for Rich live display."""

    show_learnings: bool = True
    """Whether to show learnings as they're extracted."""

    verbose: bool = False
    """Show detailed routing decisions."""


# =============================================================================
# Rich Renderer (Interactive Mode)
# =============================================================================


class RichRenderer:
    """Rich-based renderer for interactive terminal output.

    Renders events in real-time with progress bars, spinners,
    and colored status indicators.
    """

    def __init__(self, config: RendererConfig | None = None):
        self.config = config or RendererConfig()

        # Try to import Rich
        try:
            from rich.console import Console

            self.console = Console()
            self.rich_available = True
        except ImportError:
            self.rich_available = False
            self.console = None

        # State
        self._current_phase = ""
        self._tasks_total = 0
        self._tasks_completed = 0
        self._current_task = ""
        self._current_gate = ""
        self._errors: list[str] = []
        self._learnings: list[str] = []

    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render events as they stream in.

        Args:
            events: Async iterator of agent events
        """
        if not self.rich_available:
            # Fallback to simple rendering
            async for event in events:
                self._render_simple(event)
            return

        from rich.live import Live
        from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        with Live(progress, console=self.console, refresh_per_second=self.config.refresh_rate):
            task_id = None

            async for event in events:
                self._update_state(event)

                match event.type:
                    case EventType.SIGNAL:
                        if event.data.get("status") == "extracting":
                            task_id = progress.add_task("🎯 Understanding goal...", total=None)
                        elif event.data.get("signals"):
                            if task_id is not None:
                                progress.update(task_id, completed=100, total=100)
                            self._render_signals(event.data["signals"])

                    case EventType.PLAN_START:
                        technique = event.data.get("technique", "unknown")
                        task_id = progress.add_task(f"📋 Planning ({technique})...", total=None)

                    case EventType.PLAN_WINNER:
                        if task_id is not None:
                            progress.update(task_id, completed=100, total=100)
                        self._render_plan(event.data)

                    case EventType.TASK_START:
                        self._tasks_total = max(self._tasks_total, 1)
                        tid = event.data.get('task_id', 'task')
                        desc = f"[{self._tasks_completed + 1}/{self._tasks_total}] {tid}"
                        task_id = progress.add_task(desc, total=100)

                    case EventType.TASK_COMPLETE:
                        if task_id is not None:
                            progress.update(task_id, completed=100)
                        self._tasks_completed += 1

                    case EventType.GATE_START:
                        gate_id = event.data.get("gate_id", "gate")
                        self._render_gate_header(gate_id)

                    case EventType.GATE_STEP:
                        self._render_gate_step(event.data)

                    case EventType.GATE_PASS:
                        self._render_gate_pass(event.data)

                    case EventType.GATE_FAIL:
                        self._render_gate_fail(event.data)

                    case EventType.FIX_START:
                        self.console.print("\n🔧 [yellow]Auto-fixing...[/yellow]")

                    case EventType.FIX_PROGRESS:
                        self._render_fix_progress(event.data)

                    case EventType.FIX_COMPLETE:
                        self.console.print("   └─ [green]Fix applied[/green]")

                    case EventType.MEMORY_LEARNING:
                        if self.config.show_learnings:
                            fact = event.data.get("fact", "")
                            self.console.print(f"   📚 [dim]Learned: {fact[:50]}...[/dim]")

                    case EventType.ESCALATE:
                        self._render_escalate(event.data)

                    case EventType.COMPLETE:
                        self._render_complete(event.data)

                    case EventType.ERROR:
                        self._render_error(event.data)

    def _update_state(self, event: AgentEvent) -> None:
        """Update internal state from event."""
        if event.type == EventType.PLAN_WINNER:
            self._tasks_total = event.data.get("tasks", 0)
        elif event.type == EventType.MEMORY_LEARNING:
            self._learnings.append(event.data.get("fact", ""))
        elif event.type == EventType.VALIDATE_ERROR:
            self._errors.append(event.data.get("message", ""))

    def _render_signals(self, signals: dict) -> None:
        """Render signal extraction results."""
        self.console.print("\n🎯 [bold]Understanding goal...[/bold]")
        self.console.print(f"   ├─ complexity: {signals.get('complexity', '?')}")
        self.console.print(f"   ├─ needs_tools: {signals.get('needs_tools', '?')}")
        self.console.print(f"   ├─ confidence: {signals.get('effective_confidence', 0):.0%}")
        self.console.print(f"   └─ route: {signals.get('planning_route', '?')}")

    def _render_plan(self, data: dict) -> None:
        """Render plan selection."""
        tasks = data.get("tasks", 0)
        gates = data.get("gates", 0)
        technique = data.get("technique", "unknown")
        self.console.print(f"\n📋 [bold]Plan ready[/bold] ({technique})")
        self.console.print(f"   ├─ {tasks} tasks")
        self.console.print(f"   └─ {gates} validation gates")

    def _render_gate_header(self, gate_id: str) -> None:
        """Render gate header."""
        self.console.print(f"\n{'═' * 50}")
        self.console.print(f"[bold]GATE: {gate_id}[/bold]")
        self.console.print("═" * 50)

    def _render_gate_step(self, data: dict) -> None:
        """Render a gate validation step."""
        step = data.get("step", "?")
        passed = data.get("passed", False)
        message = data.get("message", "")
        auto_fixed = data.get("auto_fixed", 0)

        icon = "✅" if passed else "❌"
        color = "green" if passed else "red"

        line = f"   ├─ {step.ljust(10)} [{color}]{icon}[/{color}]"
        if auto_fixed:
            line += f" [dim](auto-fixed {auto_fixed})[/dim]"
        if message and not passed:
            line += f" [dim]{message[:40]}[/dim]"

        self.console.print(line)

    def _render_gate_pass(self, data: dict) -> None:
        """Render gate pass."""
        duration = data.get("duration_ms", 0)
        self.console.print(f"   └─ [green]PASSED[/green] ({duration}ms)")

    def _render_gate_fail(self, data: dict) -> None:
        """Render gate failure."""
        failed_step = data.get("failed_step", "unknown")
        self.console.print(f"   └─ [red]FAILED[/red] at {failed_step}")

    def _render_fix_progress(self, data: dict) -> None:
        """Render fix progress."""
        stage = data.get("stage", "?")
        detail = data.get("detail", "")
        self.console.print(f"   ├─ {stage}: {detail}")

    def _render_escalate(self, data: dict) -> None:
        """Render escalation to user."""
        reason = data.get("reason", "unknown")
        message = data.get("message", "")
        self.console.print("\n⚠️  [bold yellow]Escalating to user[/bold yellow]")
        self.console.print(f"   Reason: {reason}")
        if message:
            self.console.print(f"   {message}")

    def _render_complete(self, data: dict) -> None:
        """Render completion summary."""
        tasks = data.get("tasks_completed", 0)
        gates = data.get("gates_passed", 0)
        duration = data.get("duration_s", 0)
        learnings = data.get("learnings", 0)

        self.console.print("\n" + "═" * 50)
        self.console.print("[bold green]✨ Complete[/bold green]")
        self.console.print(f"   ├─ {tasks} tasks executed")
        self.console.print(f"   ├─ {gates} gates passed")
        self.console.print(f"   ├─ {learnings} learnings extracted")
        self.console.print(f"   └─ {duration:.1f}s total time")
        self.console.print("═" * 50)

    def _render_error(self, data: dict) -> None:
        """Render error."""
        message = data.get("message", "Unknown error")
        self.console.print(f"\n[bold red]❌ Error: {message}[/bold red]")

    def _render_simple(self, event: AgentEvent) -> None:
        """Simple fallback rendering without Rich."""
        match event.type:
            case EventType.SIGNAL:
                if event.data.get("signals"):
                    print(f"Signals: {event.data['signals']}")
            case EventType.PLAN_WINNER:
                tasks = event.data.get('tasks', 0)
                gates = event.data.get('gates', 0)
                print(f"Plan: {tasks} tasks, {gates} gates")
            case EventType.TASK_START:
                print(f"Task: {event.data.get('task_id', 'task')}")
            case EventType.TASK_COMPLETE:
                print(f"  Done ({event.data.get('duration_ms', 0)}ms)")
            case EventType.GATE_PASS:
                print(f"Gate passed: {event.data.get('gate_id', 'gate')}")
            case EventType.GATE_FAIL:
                print(f"Gate failed: {event.data.get('gate_id', 'gate')}")
            case EventType.COMPLETE:
                tasks = event.data.get('tasks_completed', 0)
                dur = event.data.get('duration_s', 0)
                print(f"Complete: {tasks} tasks in {dur:.1f}s")
            case EventType.ERROR:
                print(f"Error: {event.data.get('message', 'Unknown')}")


# =============================================================================
# Quiet Renderer
# =============================================================================


class QuietRenderer:
    """Minimal renderer for CI/scripts.

    Only outputs:
    - Final status (success/failure)
    - Error messages
    - File list on success
    """

    def __init__(self, output: TextIO | None = None):
        self.output = output or sys.stdout

    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render minimal output."""
        errors: list[str] = []
        tasks_completed = 0
        success = True

        async for event in events:
            if event.type == EventType.TASK_COMPLETE:
                tasks_completed += 1
            elif event.type == EventType.ERROR:
                errors.append(event.data.get("message", "Unknown error"))
                success = False
            elif event.type == EventType.ESCALATE:
                errors.append(f"Escalated: {event.data.get('reason', 'unknown')}")
                success = False
            elif event.type == EventType.COMPLETE:
                duration = event.data.get("duration_s", 0)
                print(f"✓ Complete: {tasks_completed} tasks in {duration:.1f}s", file=self.output)

        if not success:
            print("✗ Failed", file=self.output)
            for error in errors:
                print(f"  - {error}", file=self.output)


# =============================================================================
# JSON Renderer
# =============================================================================


class JSONRenderer:
    """JSON renderer for programmatic consumption.

    Outputs newline-delimited JSON (NDJSON) events.
    """

    def __init__(self, output: TextIO | None = None):
        self.output = output or sys.stdout

    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render events as NDJSON."""
        async for event in events:
            line = json.dumps(event.to_dict())
            print(line, file=self.output)


# =============================================================================
# Renderer Factory
# =============================================================================


def create_renderer(
    mode: str = "interactive",
    verbose: bool = False,
) -> RichRenderer | QuietRenderer | JSONRenderer:
    """Create appropriate renderer based on mode.

    Args:
        mode: "interactive", "quiet", or "json"
        verbose: Show detailed output

    Returns:
        Renderer instance
    """
    if mode == "quiet":
        return QuietRenderer()
    elif mode == "json":
        return JSONRenderer()
    else:
        config = RendererConfig(verbose=verbose)
        return RichRenderer(config)
