"""CLI renderer for Adaptive Agent streaming (RFC-042, RFC-131).

Uses Rich library for beautiful, real-time terminal output with
Holy Light aesthetic (RFC-131):
- Branded Unicode spinners (mote, spiral, radiant)
- Holy/Void color spectrum
- Sparkle animations for key moments
- Consistent visual indicators

Modes:
- Interactive: Full Rich rendering with Holy Light theme (default)
- Quiet: Minimal output for CI/scripts
- JSON: Newline-delimited JSON events
"""

import json
import sys
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Protocol, TextIO

from sunwell.agent.events import AgentEvent, EventType
from sunwell.agent.events.types import event_to_dict


# =============================================================================
# Event Formatting (Shared Between Renderers)
# =============================================================================


@dataclass(frozen=True, slots=True)
class EventFormat:
    """Defines how to format an event for display.

    Used by both Rich and simple renderers to avoid duplicating format logic.
    """

    icon: str
    """Unicode icon/symbol for the event."""

    template: str
    """Format template using {data_key} placeholders from event.data."""

    rich_style: str = "holy.gold"
    """Rich markup style for the icon (Rich renderer only)."""

    line_end: str = "\n"
    """Line ending: '\\n' for newline, '\\r' for overwrite."""

    condition: str | None = None
    """Optional data key that must be truthy for event to render."""


def _format_event_simple(event: AgentEvent, fmt: EventFormat) -> str | None:
    """Format an event for simple (non-Rich) output.

    Args:
        event: The event to format
        fmt: Format specification

    Returns:
        Formatted string or None if condition not met
    """
    # Check condition if specified
    if fmt.condition and not event.data.get(fmt.condition):
        return None

    try:
        text = fmt.template.format(**event.data)
        return f"{fmt.icon} {text}"
    except KeyError:
        # Missing data key - skip this event
        return None


# Simple event formats - used by _render_simple() for straightforward events
_SIMPLE_EVENT_FORMATS: dict[EventType, EventFormat] = {
    EventType.TASK_START: EventFormat(
        icon="✧",
        template="Task: {task_id}",
    ),
    EventType.TASK_COMPLETE: EventFormat(
        icon="✓",
        template="Done ({duration_ms}ms)",
    ),
    EventType.GATE_PASS: EventFormat(
        icon="✧",
        template="Gate passed: {gate_id}",
    ),
    EventType.GATE_FAIL: EventFormat(
        icon="✗",
        template="Gate failed: {gate_id}",
    ),
    EventType.FIX_START: EventFormat(
        icon="⚙",
        template="Auto-fixing...",
    ),
    EventType.FIX_COMPLETE: EventFormat(
        icon="✓",
        template="Fix applied",
    ),
    EventType.ERROR: EventFormat(
        icon="✗",
        template="Error: {message}",
    ),
    EventType.ESCALATE: EventFormat(
        icon="△",
        template="Escalating: {reason}",
    ),
}


class Renderer(Protocol):
    """Protocol for agent event renderers.

    All renderers must implement an async render method that consumes
    an async iterator of AgentEvent and displays them appropriately.
    """

    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render events to output.

        Args:
            events: Async iterator of agent events to render
        """
        ...


@dataclass(frozen=True, slots=True)
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

    # RFC-131: Holy Light options
    enable_sparkles: bool = True
    """Enable sparkle animations for key events."""

    reduced_motion: bool = False
    """Disable animations for accessibility."""


# =============================================================================
# Rich Renderer (Interactive Mode) — Holy Light Theme (RFC-131)
# =============================================================================


class RichRenderer:
    """Rich-based renderer with Holy Light aesthetic (RFC-131).

    Renders events in real-time with:
    - Branded mote spinners (✦ ✧ · ✧ ✦)
    - Holy/Void color spectrum
    - Phase headers (Understanding → Illuminating → Crafting → Verifying)
    - Sparkle animations for key moments
    """

    def __init__(self, config: RendererConfig | None = None):
        self.config = config or RendererConfig()

        # Try to import Rich with Holy Light theme
        try:
            from dataclasses import replace

            from rich.console import Console

            from sunwell.interface.cli.core.theme import SUNWELL_THEME, should_reduce_motion

            self.console = Console(theme=SUNWELL_THEME)
            self.rich_available = True

            # Auto-detect reduced motion (create new frozen config if needed)
            if should_reduce_motion() and not self.config.reduced_motion:
                self.config = replace(
                    self.config,
                    reduced_motion=True,
                    enable_sparkles=False,
                )
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
        self._files_created: list[str] = []
        self._files_modified: list[str] = []
        # Telemetry state (from TOOL_LOOP_COMPLETE events)
        self._model_calls = 0
        self._tool_calls = 0
        self._tokens_input = 0
        self._tokens_output = 0

    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render events as they stream in with Holy Light aesthetic.

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

        # RFC-131: Holy Light branded progress with mote spinner
        progress = Progress(
            SpinnerColumn(spinner_name="dots", style="holy.gold"),
            TextColumn("[sunwell.phase]{task.description}"),
            BarColumn(
                complete_style="sunwell.progress.complete",
                finished_style="holy.radiant",
                pulse_style="holy.gold",
            ),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        with Live(progress, console=self.console, refresh_per_second=self.config.refresh_rate):
            task_id = None

            async for event in events:
                self._update_state(event)

                match event.type:
                    # RFC-131: Holy Light phase headers
                    case EventType.INTENT_CLASSIFIED:
                        self._render_intent_classified(event.data)

                    case EventType.NODE_TRANSITION:
                        self._render_node_transition(event.data)

                    case EventType.SIGNAL:
                        if event.data.get("status") == "extracting":
                            task_id = progress.add_task(
                                "[holy.radiant]✦[/] Understanding goal...",
                                total=None
                            )
                        elif event.data.get("signals"):
                            if task_id is not None:
                                progress.update(task_id, completed=100, total=100)
                            self._render_signals(event.data["signals"])

                    case EventType.PLAN_START:
                        technique = event.data.get("technique", "unknown")
                        task_id = progress.add_task(
                            f"[holy.radiant]✦[/] Illuminating ({technique})...",
                            total=None
                        )

                    # RFC-058: Harmonic planning candidate visibility
                    case EventType.PLAN_CANDIDATE_START:
                        total_candidates = event.data.get("total_candidates", 5)
                        variance = event.data.get("variance_strategy", "prompting")
                        # Create a sub-progress for candidate generation
                        self._candidate_task_id = progress.add_task(
                            f"   [holy.gold]◇[/] Generating {total_candidates} candidates ({variance})...",
                            total=total_candidates
                        )

                    case EventType.PLAN_CANDIDATE_GENERATED:
                        artifact_count = event.data.get("artifact_count", 0)
                        prog = event.data.get("progress", 1)
                        total = event.data.get("total_candidates", 5)
                        style = event.data.get("variance_config", {}).get("prompt_style", "?")

                        if hasattr(self, "_candidate_task_id") and self._candidate_task_id is not None:
                            progress.update(
                                self._candidate_task_id,
                                completed=prog,
                                description=f"   [holy.gold]◇[/] [{prog}/{total}] {style}: {artifact_count} artifacts"
                            )

                    case EventType.PLAN_CANDIDATES_COMPLETE:
                        if hasattr(self, "_candidate_task_id") and self._candidate_task_id is not None:
                            total = event.data.get("total_candidates", 5)
                            successful = event.data.get("successful_candidates", total)
                            progress.update(
                                self._candidate_task_id,
                                completed=total,
                                description=f"   [holy.success]◆[/] {successful} candidates generated"
                            )

                    case EventType.PLAN_CANDIDATE_SCORED:
                        score = event.data.get("score", 0)
                        prog = event.data.get("progress", 1)
                        total = event.data.get("total_candidates", 5)

                        if hasattr(self, "_candidate_task_id") and self._candidate_task_id is not None:
                            progress.update(
                                self._candidate_task_id,
                                description=f"   [holy.gold]·[/] Scoring [{prog}/{total}]: {score:.1f}"
                            )

                    case EventType.PLAN_WINNER:
                        # Clean up candidate progress bar
                        if hasattr(self, "_candidate_task_id") and self._candidate_task_id is not None:
                            selected = event.data.get("selected_candidate_id", "?")
                            score = event.data.get("score", 0)
                            progress.update(
                                self._candidate_task_id,
                                completed=event.data.get("total_candidates", 5),
                                description=f"   [holy.success]★[/] Selected: {selected} (score: {score:.1f})"
                            )
                            # Keep it visible briefly, it will be cleaned up naturally
                            self._candidate_task_id = None
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

                    case EventType.TASK_OUTPUT:
                        # Display output for conversational tasks (no target file)
                        content = event.data.get("content", "")
                        if content:
                            self.console.print()
                            self.console.print(content)

                    case EventType.TOOL_COMPLETE:
                        # Show tool completion, especially self-corrections
                        self._render_tool_complete(event.data)

                    case EventType.GATE_START:
                        gate_id = event.data.get("gate_id", "gate")
                        self._render_gate_header(gate_id)

                    case EventType.GATE_STEP:
                        self._render_gate_step(event.data)

                    case EventType.GATE_PASS:
                        self._render_gate_pass(event.data)

                    case EventType.GATE_FAIL:
                        self._render_gate_fail(event.data)

                    # RFC-131: Holy Light fix styling
                    case EventType.FIX_START:
                        self.console.print("\n  [void.indigo]⚙[/] Auto-fixing...")

                    case EventType.FIX_PROGRESS:
                        self._render_fix_progress(event.data)

                    case EventType.FIX_COMPLETE:
                        self.console.print("   └─ [holy.success]✓[/] Fix applied")

                    # RFC-131: Learning with Holy Light styling
                    case EventType.MEMORY_LEARNING:
                        if self.config.show_learnings:
                            fact = event.data.get("fact", "")
                            self._learnings.append(fact)
                            self.console.print(f"   [holy.gold.dim]≡[/] Learned: {fact[:50]}...")

                    # RFC-081, RFC-131: Inference visibility with Holy Light styling
                    case EventType.MODEL_START:
                        model = event.data.get("model", "model")
                        # Store model task ID separately - don't overwrite task_id
                        # which is used for TASK_START/TASK_COMPLETE tracking
                        self._model_task_id = progress.add_task(
                            f"[holy.gold]◎ {model}[/]",
                            total=None,  # Indeterminate
                        )
                        self._model_start_time = event.timestamp

                    case EventType.MODEL_TOKENS:
                        if hasattr(self, "_model_task_id") and self._model_task_id is not None:
                            token_count = event.data.get("token_count", 0)
                            tps = event.data.get("tokens_per_second")
                            tps_str = f" ({tps:.1f} tok/s)" if tps else ""
                            progress.update(
                                self._model_task_id,
                                description=f"[holy.gold]◎ {token_count} tokens{tps_str}[/]",
                            )

                    case EventType.MODEL_THINKING:
                        # RFC-131: Show thinking with spiral indicator (Uzumaki)
                        content = event.data.get("content", "")
                        phase = event.data.get("phase", "thinking")
                        is_complete = event.data.get("is_complete", False)
                        if content and is_complete:
                            # Truncate for display
                            display = content[:200] + "..." if len(content) > 200 else content
                            self.console.print(
                                f"   [neutral.dim]◜ {phase}: {display}[/]"
                            )

                    case EventType.MODEL_COMPLETE:
                        if hasattr(self, "_model_task_id") and self._model_task_id is not None:
                            progress.remove_task(self._model_task_id)
                            self._model_task_id = None

                        total = event.data.get("total_tokens", 0)
                        duration = event.data.get("duration_s", 0)
                        tps = event.data.get("tokens_per_second", 0)
                        ttft = event.data.get("time_to_first_token_ms")

                        ttft_str = f", TTFT: {ttft}ms" if ttft else ""
                        self.console.print(
                            f"   [holy.success]✓[/] Generated {total} tokens "
                            f"in {duration:.1f}s ({tps:.1f} tok/s{ttft_str})"
                        )

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
        elif event.type == EventType.TOOL_LOOP_COMPLETE:
            # Capture telemetry from tool loop completion
            self._model_calls += event.data.get("model_calls", 0)
            self._tool_calls += event.data.get("tool_calls_total", 0)
            self._tokens_input += event.data.get("tokens_input", 0)
            self._tokens_output += event.data.get("tokens_output", 0)

    def _render_intent_classified(self, data: dict) -> None:
        """Render intent classification with DAG path (Conversational DAG Architecture)."""
        path_formatted = data.get("path_formatted", "")
        confidence = data.get("confidence", 0)
        requires_approval = data.get("requires_approval", False)
        tool_scope = data.get("tool_scope")

        # Format path with colors
        path_parts = data.get("path", [])
        from sunwell.interface.cli.progress.dag_path import format_dag_path
        path_text = format_dag_path(path_parts) if path_parts else path_formatted

        self.console.print()
        self.console.print(f"  [holy.gold]→[/] Intent: ", end="")
        self.console.print(path_text)

        # Show details if verbose or requires approval
        if self.config.verbose or requires_approval:
            self.console.print(f"     [dim]confidence: {confidence:.0%}[/]")
            if tool_scope:
                self.console.print(f"     [dim]scope: {tool_scope}[/]")
            if requires_approval:
                self.console.print(f"     [void.indigo]⊗ requires approval[/]")

    def _render_node_transition(self, data: dict) -> None:
        """Render a node transition in the intent DAG."""
        from_node = data.get("from_node", "?")
        to_node = data.get("to_node", "?")
        reason = data.get("reason", "")

        self.console.print(
            f"  [dim]◇ {from_node} → [/][holy.gold]{to_node}[/]"
            + (f" [dim]({reason})[/]" if reason else "")
        )

    def _render_signals(self, signals: dict) -> None:
        """Render signal extraction results with Holy Light styling (RFC-131)."""
        self.console.print("\n[holy.radiant]✦ Understanding goal...[/]")
        self.console.print(f"   [holy.gold]├─[/] complexity: {signals.get('complexity', '?')}")
        self.console.print(f"   [holy.gold]├─[/] needs_tools: {signals.get('needs_tools', '?')}")
        conf = signals.get("effective_confidence", 0)
        self.console.print(f"   [holy.gold]├─[/] confidence: {conf:.0%}")
        self.console.print(f"   [holy.gold]└─[/] route: {signals.get('planning_route', '?')}")

    def _render_plan(self, data: dict) -> None:
        """Render plan selection with Holy Light styling (RFC-131)."""
        tasks = data.get("tasks", 0)
        gates = data.get("gates", 0)
        technique = data.get("technique", "unknown")
        self.console.print(f"\n[holy.success]★[/] [sunwell.heading]Plan ready[/] ({technique})")
        self.console.print(f"   [holy.gold]├─[/] {tasks} tasks")
        self.console.print(f"   [holy.gold]└─[/] {gates} validation gates")

    def _render_gate_header(self, gate_id: str) -> None:
        """Render gate header with Holy Light styling (RFC-131)."""
        self.console.print(f"\n  [holy.gold]{'═' * 54}[/]")
        self.console.print(f"  [sunwell.phase]GATE: {gate_id}[/]")
        self.console.print(f"  [holy.gold]{'═' * 54}[/]")

    def _render_gate_step(self, data: dict) -> None:
        """Render a gate validation step with Holy Light styling (RFC-131)."""
        step = data.get("step", "?")
        passed = data.get("passed", False)
        message = data.get("message", "")
        auto_fixed = data.get("auto_fixed", 0)

        # RFC-131: Character-map shapes only
        icon = "✧" if passed else "✗"
        color = "holy.success" if passed else "void.purple"

        line = f"    ├─ {step.ljust(12)} [{color}]{icon}[/]"
        if auto_fixed:
            line += f" [neutral.dim](auto-fixed {auto_fixed})[/]"
        if message and not passed:
            line += f" [neutral.dim]{message[:40]}[/]"

        self.console.print(line)

    def _render_gate_pass(self, data: dict) -> None:
        """Render gate pass with Holy Light styling (RFC-131)."""
        duration = data.get("duration_ms", 0)
        self.console.print(f"    └─ [holy.success]✧ PASSED[/] ({duration}ms)")

    def _render_gate_fail(self, data: dict) -> None:
        """Render gate failure with Holy Light styling (RFC-131)."""
        failed_step = data.get("failed_step", "unknown")
        self.console.print(f"    └─ [void.purple]✗ FAILED[/] at {failed_step}")

    def _render_tool_complete(self, data: dict) -> None:
        """Render tool completion, highlighting self-corrections."""
        tool_name = data.get("tool_name", "tool")
        success = data.get("success", False)
        self_corrected = data.get("self_corrected", False)

        # Only show notable events (self-corrections or failures)
        if self_corrected:
            output = data.get("output", "")
            self.console.print(
                f"   [holy.gold]⚡[/] [sunwell.accent]Self-corrected[/]: {tool_name}"
            )
            if output:
                self.console.print(f"      [neutral.dim]{output[:60]}[/]")

            # Show invocation summary if available
            summary = data.get("invocation_summary")
            if summary and self.config.verbose:
                total = summary.get("total", 0)
                corrected = summary.get("self_corrected", 0)
                self.console.print(
                    f"      [neutral.dim]({total} tools called, {corrected} self-corrected)[/]"
                )
        elif not success:
            error = data.get("error", "unknown error")
            self.console.print(
                f"   [void.purple]✗[/] {tool_name} failed: {error[:50]}"
            )

    def _render_fix_progress(self, data: dict) -> None:
        """Render fix progress with Holy Light styling (RFC-131)."""
        stage = data.get("stage", "?")
        detail = data.get("detail", "")
        self.console.print(f"   [holy.gold]├─[/] {stage}: {detail}")

    def _render_escalate(self, data: dict) -> None:
        """Render escalation to user with Holy Light styling (RFC-131)."""
        reason = data.get("reason", "unknown")
        message = data.get("message", "")
        self.console.print("\n  [void.indigo]△[/] [sunwell.warning]Escalating to user[/]")
        self.console.print(f"    Reason: {reason}")
        if message:
            self.console.print(f"    {message}")

    def _render_complete(self, data: dict) -> None:
        """Render completion summary with Holy Light styling (RFC-131)."""
        tasks = data.get("tasks_completed", 0)
        duration = data.get("duration_s", 0)
        learnings = data.get("learnings", 0)

        # RFC-131: Holy Light phase header
        self.console.print()
        self.console.print(f"┌{'─' * 53}┐")
        self.console.print(f"│  [holy.success]★ Complete[/]{'':44}│")
        self.console.print(f"└{'─' * 53}┘")

        self.console.print()
        self.console.print(f"  [holy.radiant]✦[/] {tasks} tasks completed in {duration:.1f}s")

        # Show telemetry if we have it
        if self._model_calls > 0 or self._tool_calls > 0:
            self.console.print()
            self.console.print("  [sunwell.phase]Telemetry:[/]")
            self.console.print(f"   [holy.gold]├─[/] LLM calls: {self._model_calls}")
            self.console.print(f"   [holy.gold]├─[/] Tool calls: {self._tool_calls}")
            if self._tokens_input > 0 or self._tokens_output > 0:
                total_tokens = self._tokens_input + self._tokens_output
                self.console.print(
                    f"   [holy.gold]└─[/] Tokens: {total_tokens:,} "
                    f"[neutral.dim](in: {self._tokens_input:,}, out: {self._tokens_output:,})[/]"
                )
            else:
                self.console.print(f"   [holy.gold]└─[/] Tokens: [neutral.dim]n/a[/]")

        self.console.print()

        # Show created/modified files if tracked
        if self._files_created:
            self.console.print("  Files created:")
            for f in self._files_created[:10]:
                self.console.print(f"    [green]+[/] {f}")
            if len(self._files_created) > 10:
                extra = len(self._files_created) - 10
                self.console.print(f"    [neutral.dim]... and {extra} more[/]")
            self.console.print()

        if self._files_modified:
            self.console.print("  Files modified:")
            for f in self._files_modified[:10]:
                self.console.print(f"    [yellow]~[/] {f}")
            if len(self._files_modified) > 10:
                extra = len(self._files_modified) - 10
                self.console.print(f"    [neutral.dim]... and {extra} more[/]")
            self.console.print()

        if learnings > 0 or self._learnings:
            count = learnings or len(self._learnings)
            self.console.print(f"  [holy.gold.dim]≡[/] Extracted {count} learnings")
            self.console.print()

        self.console.print("  [holy.radiant]✦✧✦[/] Goal achieved")
        self.console.print()

    def _render_error(self, data: dict) -> None:
        """Render error with Holy Light styling (RFC-131)."""
        message = data.get("message", "Unknown error")
        self.console.print(f"\n  [void.purple]✗[/] [sunwell.error]Error:[/] {message}")

    def _render_simple(self, event: AgentEvent) -> None:
        """Simple fallback rendering without Rich (RFC-131: character shapes).

        Uses _SIMPLE_EVENT_FORMATS for straightforward events, with custom
        handlers for events needing complex logic.
        """
        # Try simple format first
        fmt = _SIMPLE_EVENT_FORMATS.get(event.type)
        if fmt:
            text = _format_event_simple(event, fmt)
            if text:
                print(text)
            return

        # Custom handlers for complex events
        match event.type:
            case EventType.INTENT_CLASSIFIED:
                path = event.data.get("path_formatted", "")
                conf = event.data.get("confidence", 0)
                print(f"→ Intent: {path} ({conf:.0%})")
            case EventType.NODE_TRANSITION:
                from_n = event.data.get("from_node", "?")
                to_n = event.data.get("to_node", "?")
                print(f"  ◇ {from_n} → {to_n}")
            case EventType.SIGNAL:
                if event.data.get("signals"):
                    signals = event.data["signals"]
                    print(f"✦ Understanding: complexity={signals.get('complexity', '?')}, "
                          f"route={signals.get('planning_route', '?')}")
            case EventType.PLAN_CANDIDATE_START:
                total = event.data.get('total_candidates', 5)
                variance = event.data.get('variance_strategy', 'prompting')
                print(f"◇ Generating {total} candidates ({variance})...")
            case EventType.PLAN_CANDIDATE_GENERATED:
                prog = event.data.get('progress', 1)
                total = event.data.get('total_candidates', 5)
                style = event.data.get('variance_config', {}).get('prompt_style', '?')
                artifacts = event.data.get('artifact_count', 0)
                print(f"  ✧ [{prog}/{total}] {style}: {artifacts} artifacts")
            case EventType.PLAN_CANDIDATES_COMPLETE:
                successful = event.data.get('successful_candidates', 0)
                print(f"◆ {successful} candidates generated, scoring...")
            case EventType.PLAN_CANDIDATE_SCORED:
                prog = event.data.get('progress', 1)
                total = event.data.get('total_candidates', 5)
                score = event.data.get('score', 0)
                print(f"  · Scored [{prog}/{total}]: {score:.1f}", end='\r')
            case EventType.PLAN_WINNER:
                tasks = event.data.get('tasks', 0)
                gates = event.data.get('gates', 0)
                technique = event.data.get('technique', 'unknown')
                print(f"★ Plan ready ({technique}): {tasks} tasks, {gates} gates")
            case EventType.TOOL_COMPLETE:
                # Show self-corrections prominently
                if event.data.get('self_corrected'):
                    tool = event.data.get('tool_name', 'tool')
                    output = event.data.get('output', '')
                    print(f"  ⚡ Self-corrected: {tool} - {output[:50]}")
            # RFC-081, RFC-131: Inference visibility with character shapes
            case EventType.MODEL_START:
                model = event.data.get('model', 'model')
                print(f"◎ Generating with {model}...")
            case EventType.MODEL_TOKENS:
                tokens = event.data.get('token_count', 0)
                tps = event.data.get('tokens_per_second')
                tps_str = f" ({tps:.1f} tok/s)" if tps else ""
                print(f"  ◎ {tokens} tokens{tps_str}", end='\r')
            case EventType.MODEL_THINKING:
                content = event.data.get('content', '')
                phase = event.data.get('phase', 'thinking')
                is_complete = event.data.get('is_complete', False)
                if content and is_complete:
                    display = content[:80] + "..." if len(content) > 80 else content
                    print(f"  ◜ {phase}: {display}")
            case EventType.MODEL_COMPLETE:
                total = event.data.get('total_tokens', 0)
                duration = event.data.get('duration_s', 0)
                tps = event.data.get('tokens_per_second', 0)
                print(f"  ✓ {total} tokens in {duration:.1f}s ({tps:.1f} tok/s)")
            case EventType.MEMORY_LEARNING:
                fact = event.data.get('fact', '')
                print(f"  ≡ Learned: {fact[:50]}...")
            case EventType.TOOL_LOOP_COMPLETE:
                # Update telemetry state for simple renderer too
                self._model_calls += event.data.get('model_calls', 0)
                self._tool_calls += event.data.get('tool_calls_total', 0)
                self._tokens_input += event.data.get('tokens_input', 0)
                self._tokens_output += event.data.get('tokens_output', 0)
            case EventType.COMPLETE:
                tasks = event.data.get('tasks_completed', 0)
                dur = event.data.get('duration_s', 0)
                print(f"★ Complete: {tasks} tasks in {dur:.1f}s")
                # Show telemetry if we have it
                if self._model_calls > 0 or self._tool_calls > 0:
                    total_tokens = self._tokens_input + self._tokens_output
                    print(f"  ├─ LLM calls: {self._model_calls}")
                    print(f"  ├─ Tool calls: {self._tool_calls}")
                    if total_tokens > 0:
                        print(f"  └─ Tokens: {total_tokens:,} (in: {self._tokens_input:,}, out: {self._tokens_output:,})")
                print("✦✧✦ Goal achieved")


# =============================================================================
# Quiet Renderer
# =============================================================================


class QuietRenderer:
    """Minimal renderer for CI/scripts (RFC-131 character shapes).

    Only outputs:
    - Final status (success/failure)
    - Error messages
    - File list on success
    """

    def __init__(self, output: TextIO | None = None):
        self.output = output or sys.stdout

    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render minimal output with Holy Light character shapes."""
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
                # RFC-131: Holy Light character shapes
                print(f"★ Complete: {tasks_completed} tasks in {duration:.1f}s", file=self.output)

        if not success:
            print("✗ Failed", file=self.output)
            for error in errors:
                print(f"  ✗ {error}", file=self.output)


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
            line = json.dumps(event_to_dict(event))
            print(line, file=self.output)


# =============================================================================
# Renderer Factory (RFC-131)
# =============================================================================


def create_renderer(
    mode: str = "interactive",
    verbose: bool = False,
    enable_sparkles: bool = True,
    reduced_motion: bool = False,
) -> Renderer:
    """Create appropriate renderer based on mode.

    Args:
        mode: "interactive", "quiet", or "json"
        verbose: Show detailed output
        enable_sparkles: Enable sparkle animations (RFC-131)
        reduced_motion: Disable animations for accessibility (RFC-131)

    Returns:
        Renderer instance with Holy Light styling
    """
    if mode == "quiet":
        return QuietRenderer()
    elif mode == "json":
        return JSONRenderer()
    else:
        config = RendererConfig(
            verbose=verbose,
            enable_sparkles=enable_sparkles,
            reduced_motion=reduced_motion,
        )
        return RichRenderer(config)
