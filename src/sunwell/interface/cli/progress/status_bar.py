"""Persistent status bar with session metrics.

Displays live session metrics at the bottom of the terminal:
- Current DAG path
- Token usage
- Time elapsed
- Cost estimate
"""

import time
from dataclasses import dataclass, field
from typing import Sequence

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sunwell.interface.cli.core.theme import SUNWELL_THEME
from sunwell.interface.cli.progress.dag_path import format_dag_path


@dataclass
class StatusMetrics:
    """Session metrics for status bar display.
    
    Attributes:
        tokens_in: Input tokens consumed
        tokens_out: Output tokens generated
        cost: Estimated cost in USD
        start_time: Session start timestamp
        llm_calls: Number of LLM calls made
        tool_calls: Number of tool calls made
    """
    
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    start_time: float = field(default_factory=time.time)
    llm_calls: int = 0
    tool_calls: int = 0
    
    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self.tokens_in + self.tokens_out
    
    @property
    def elapsed_seconds(self) -> float:
        """Seconds since session start."""
        return time.time() - self.start_time
    
    @property
    def elapsed_formatted(self) -> str:
        """Formatted elapsed time (e.g., '2m 34s')."""
        elapsed = self.elapsed_seconds
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"
    
    def add_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Add token usage.
        
        Args:
            input_tokens: Input tokens to add
            output_tokens: Output tokens to add
        """
        self.tokens_in += input_tokens
        self.tokens_out += output_tokens
    
    def add_cost(self, amount: float) -> None:
        """Add to cost estimate.
        
        Args:
            amount: Cost in USD
        """
        self.cost += amount
    
    def record_llm_call(self) -> None:
        """Record an LLM call."""
        self.llm_calls += 1
    
    def record_tool_call(self) -> None:
        """Record a tool call."""
        self.tool_calls += 1


@dataclass
class StatusBar:
    """Persistent status bar for session metrics.
    
    Displays a horizontal bar with:
    - DAG path (if provided)
    - Token usage
    - Time elapsed
    - Cost estimate
    
    Example:
        >>> bar = StatusBar(console)
        >>> bar.update_path(["conversation", "act", "write"])
        >>> bar.metrics.add_tokens(1000, 500)
        >>> bar.render()
        ┌─────────────────────────────────────────────────────┐
        │ Path: Conv → Act → Write │ 1.5K tok │ 12s │ $0.01  │
        └─────────────────────────────────────────────────────┘
    """
    
    console: Console | None = None
    metrics: StatusMetrics = field(default_factory=StatusMetrics)
    current_path: list[str] = field(default_factory=list)
    _live: Live | None = field(default=None, init=False, repr=False)
    
    def __post_init__(self) -> None:
        if self.console is None:
            self.console = Console(theme=SUNWELL_THEME)
    
    def update_path(self, path: Sequence[str]) -> None:
        """Update the DAG path display.
        
        Args:
            path: Current DAG path
        """
        self.current_path = list(path)
    
    def start_live(self) -> None:
        """Start live updating display."""
        if self._live is not None:
            return
        
        self._live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=2,
            transient=True,
        )
        self._live.start()
    
    def stop_live(self) -> None:
        """Stop live updating display."""
        if self._live:
            self._live.stop()
            self._live = None
    
    def update(self) -> None:
        """Update the live display."""
        if self._live:
            self._live.update(self._build_display())
    
    def render(self) -> None:
        """Render the status bar once (non-live)."""
        self.console.print(self._build_display())
    
    def _build_display(self) -> Panel:
        """Build the status bar display.
        
        Returns:
            Panel with status information
        """
        # Build content as a table for alignment
        table = Table.grid(padding=(0, 2))
        table.add_column(justify="left")  # Path
        table.add_column(justify="center")  # Tokens
        table.add_column(justify="center")  # Time
        table.add_column(justify="right")  # Cost
        
        # Path
        if self.current_path:
            path_text = format_dag_path(self.current_path, bold_terminal=True)
        else:
            path_text = Text("Ready", style="dim")
        
        # Tokens
        total = self.metrics.total_tokens
        if total >= 1000:
            token_str = f"{total / 1000:.1f}K tok"
        else:
            token_str = f"{total} tok"
        token_text = Text(token_str, style="holy.gold")
        
        # Time
        time_text = Text(self.metrics.elapsed_formatted, style="dim")
        
        # Cost
        cost = self.metrics.cost
        if cost > 0:
            cost_text = Text(f"${cost:.4f}", style="holy.gold.dim")
        else:
            cost_text = Text("$0.00", style="dim")
        
        table.add_row(path_text, token_text, time_text, cost_text)
        
        return Panel(
            table,
            border_style="holy.gold.dim",
            padding=(0, 1),
        )
    
    def _build_detailed_display(self) -> Panel:
        """Build a detailed status display.
        
        Returns:
            Panel with detailed metrics
        """
        lines = []
        
        # Path
        if self.current_path:
            path_text = format_dag_path(self.current_path)
            lines.append(Text.assemble(("Path: ", "bold"), path_text))
        
        # Metrics
        m = self.metrics
        lines.append(Text.assemble(
            ("Tokens: ", "bold"),
            (f"{m.total_tokens:,}", "holy.gold"),
            (f" (in: {m.tokens_in:,}, out: {m.tokens_out:,})", "dim"),
        ))
        
        lines.append(Text.assemble(
            ("Time: ", "bold"),
            (m.elapsed_formatted, ""),
        ))
        
        if m.cost > 0:
            lines.append(Text.assemble(
                ("Cost: ", "bold"),
                (f"${m.cost:.4f}", "holy.gold"),
            ))
        
        if m.llm_calls > 0 or m.tool_calls > 0:
            lines.append(Text.assemble(
                ("Calls: ", "bold"),
                (f"{m.llm_calls} LLM, {m.tool_calls} tools", "dim"),
            ))
        
        content = Text("\n").join(lines)
        
        return Panel(
            content,
            title="[holy.gold]Session[/]",
            border_style="holy.gold.dim",
            padding=(0, 1),
        )
    
    def render_detailed(self) -> None:
        """Render detailed status (for session end)."""
        self.console.print(self._build_detailed_display())


def create_status_bar(console: Console | None = None) -> StatusBar:
    """Factory function to create a StatusBar.
    
    Args:
        console: Rich console (creates one if not provided)
        
    Returns:
        StatusBar instance
    """
    return StatusBar(console=console)
