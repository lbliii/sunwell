"""Holy Light CLI Theme (RFC-131).

Brings Sunwell's visual identity to the terminal with:
- Branded Unicode spinners (mote, spiral, radiant)
- Holy/Void color spectrum
- Sparkle animations
- Rising motes for thinking states
- Consistent visual indicators

The aesthetic:
    Golden accents radiating from the void — sacred light emerging from darkness.
    Holy spectrum for positive states, Void spectrum for warnings/errors.
"""

import asyncio
import os
import random
import sys
from dataclasses import dataclass
from enum import Enum
from collections.abc import Iterator
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme

# =============================================================================
# COLOR PALETTES (RFC-131)
# =============================================================================

# Holy Spectrum — Light, positive, active states
HOLY_LIGHT = {
    "radiant": "#ffd700",      # Active, thinking, primary
    "gold": "#c9a227",         # Progress, standard accent
    "gold_light": "#ffe566",   # Sparkle, highlight
    "gold_dim": "#8a7235",     # Muted, disabled
    "warm": "#fff4d4",         # Warm background
    "success": "#22c55e",      # Complete, pass
}

# Void Spectrum — Shadow, danger, unknown states
VOID_SHADOW = {
    "void": "#1e1b4b",         # Deep unknown
    "purple": "#7c3aed",       # Error, violation
    "indigo": "#4f46e5",       # Warning, caution
    "deep": "#2e1065",         # Critical, fatal
    "shadow": "#3730a3",       # Muted danger
}

# Neutral — The canvas
NEUTRAL = {
    "obsidian": "#0d0d0d",     # Background
    "surface": "#1a1a1a",      # Cards
    "elevated": "#262626",     # Hover
    "text": "#e5e5e5",         # Primary text
    "muted": "#a8a8a8",        # Secondary text
    "dim": "#525252",          # Tertiary
}


# =============================================================================
# RICH THEME (RFC-131)
# =============================================================================

SUNWELL_THEME = Theme({
    # ═══════════════════════════════════════════════════════════════
    # HOLY SPECTRUM — Light, positive, active states
    # ═══════════════════════════════════════════════════════════════
    "holy.radiant": "bold bright_yellow",         # ✦ Active, magical moments
    "holy.gold": "yellow",                        # Standard UI accent
    "holy.gold.dim": "dim yellow",                # Muted, disabled
    "holy.success": "bold green",                 # ✓ Completion (green-gold)

    # ═══════════════════════════════════════════════════════════════
    # VOID SPECTRUM — Shadow, danger, unknown states
    # ═══════════════════════════════════════════════════════════════
    "void.purple": "bold magenta",                # ✗ Error, violation
    "void.indigo": "bright_magenta",              # △ Warning, caution
    "void.deep": "bold red",                      # ⊗ Critical, fatal
    "void.shadow": "dim magenta",                 # Muted danger
    "void": "dim blue",                           # Unknown, waiting

    # ═══════════════════════════════════════════════════════════════
    # NEUTRAL — The canvas
    # ═══════════════════════════════════════════════════════════════
    "neutral.text": "white",                      # Primary text
    "neutral.muted": "dim white",                 # Secondary text
    "neutral.dim": "dim",                         # Tertiary, hints

    # ═══════════════════════════════════════════════════════════════
    # SEMANTIC ALIASES (map to spectrum)
    # ═══════════════════════════════════════════════════════════════
    "sunwell.success": "bold green",              # Light triumphs
    "sunwell.warning": "bright_magenta",          # Shadow creeping in
    "sunwell.error": "bold magenta",              # Void corruption
    "sunwell.critical": "bold red",               # Full void

    # Phase indicators
    "sunwell.phase": "bold yellow",               # Phase headers
    "sunwell.phase.active": "bold bright_yellow", # Current phase
    "sunwell.phase.complete": "dim green",        # Done phases

    # Progress
    "sunwell.progress.bar": "yellow",
    "sunwell.progress.complete": "bright_yellow",
    "sunwell.progress.remaining": "dim white",

    # Text hierarchy
    "sunwell.heading": "bold white",
    "sunwell.body": "white",
    "sunwell.muted": "dim white",
    "sunwell.highlight": "bold bright_yellow",

    # Aliases for common usage
    "sunwell.radiant": "bold bright_yellow",
    "sunwell.gold": "yellow",
    "sunwell.gold.dim": "dim yellow",
})


# =============================================================================
# UNICODE CHARACTER SETS (RFC-131 Appendix)
# =============================================================================

# Stars & Sparkles
CHARS_STARS = {
    "radiant": "✦",      # U+2726 Active/Important
    "progress": "✧",     # U+2727 Secondary
    "complete": "★",     # U+2605 Success
    "cache": "⋆",        # U+22C6 Fast
    "dim": "·",          # U+00B7 Pending/Debug
}

# Spirals (Uzumaki — for thinking)
CHARS_SPIRAL = ["◜", "◝", "◞", "◟"]  # Quarter arcs

# Diamonds
CHARS_DIAMONDS = {
    "solid": "◆",        # U+25C6 Ready
    "hollow": "◇",       # U+25C7 Waiting
    "inset": "◈",        # U+25C8 Paused
}

# Circles
CHARS_CIRCLES = {
    "filled": "●",       # U+25CF High
    "target": "◉",       # U+25C9 Moderate
    "empty": "○",        # U+25CB Low
    "dotted": "◌",       # U+25CC Uncertain
    "double": "◎",       # U+25CE Model
    "half": "◐",         # U+25D0 Lens
    "quarter": "◔",      # U+25D4 Timeout
}

# Checks & Crosses
CHARS_CHECKS = {
    "pass": "✓",         # U+2713
    "fail": "✗",         # U+2717
}

# Misc
CHARS_MISC = {
    "gear": "⚙",         # U+2699 Fixing
    "warning": "△",      # U+25B3 Warning/Stub
    "approval": "⊗",     # U+2297 Approval needed
    "violation": "⊘",    # U+2298 Violation
    "refresh": "↻",      # U+21BB Refresh
    "learning": "≡",     # U+2261 Learning
    "insight": "※",      # U+203B Insight
    "decision": "▣",     # U+25A3 Decision
    "save": "▤",         # U+25A4 Save/Checkpoint
    "workspace": "▢",    # U+25A2 Workspace
    "budget": "¤",       # U+00A4 Budget
    "prompt": "?",       # Question
    "input": "›",        # U+203A Input marker
}


# =============================================================================
# ICON MIGRATION MAP (RFC-131 Appendix)
# Emoji → Unicode character mapping for consistent CLI rendering
# =============================================================================

ICON_MAP = {
    # Status
    "✅": "★",           # Success/complete
    "❌": "✗",           # Error/fail
    "⚠️": "△",           # Warning
    "⚠": "△",            # Warning (alt)

    # Actions
    "🔥": "✦",           # Hot/active
    "⚡": "✧",           # Fast/action
    "✨": "★",           # Complete/sparkle
    "💡": "✧",           # Idea/tip
    "🚀": "✦",           # Launch/start
    "🔧": "⚙",           # Fix/tool
    "🔍": "◇",           # Search/find
    "🔬": "◎",           # Analyze

    # Information
    "📁": "▢",           # File/directory
    "📊": "≡",           # Data/stats
    "📈": "≡",           # Metrics
    "🎯": "◇",           # Goal/target
    "💾": "▤",           # Save/checkpoint
    "📍": "◆",           # Location/position
    "📋": "≡",           # List/summary

    # Thinking
    "💭": "◜",           # Thinking
    "🧠": "◎",           # Model/brain
    "💬": "›",           # Chat/message

    # Security
    "🛡": "⊗",           # Guard/protection
    "🔒": "⊘",           # Lock/secure
    "🔓": "◇",           # Unlock

    # Process
    "🔀": "↻",           # Split/branch
    "↻": "↻",            # Refresh (already unicode)
    "⏸️": "◈",           # Pause
    "⏸": "◈",            # Pause (alt)
    "▶": "◆",            # Play/run

    # Misc
    "🧬": "≡",           # Evolution/DNA
    "⏰": "◔",           # Timeout
    "🟢": "●",           # Active/on
    "🔴": "●",           # Error (use color for distinction)
    "🟡": "◉",           # Warning
}


# =============================================================================
# STYLE MIGRATION MAP (RFC-131)
# Old Rich markup → Holy Light theme styles
# =============================================================================

STYLE_MAP = {
    # Basic colors → Semantic styles
    "[red]": "[void.purple]",
    "[/red]": "[/void.purple]",
    "[bold red]": "[void.deep]",
    "[/bold red]": "[/void.deep]",

    "[green]": "[holy.success]",
    "[/green]": "[/holy.success]",
    "[bold green]": "[holy.success]",
    "[/bold green]": "[/holy.success]",

    "[yellow]": "[holy.gold]",
    "[/yellow]": "[/holy.gold]",
    "[bold yellow]": "[holy.radiant]",
    "[/bold yellow]": "[/holy.radiant]",

    "[cyan]": "[holy.radiant]",
    "[/cyan]": "[/holy.radiant]",
    "[bold cyan]": "[holy.radiant]",
    "[/bold cyan]": "[/holy.radiant]",

    "[blue]": "[holy.gold.dim]",
    "[/blue]": "[/holy.gold.dim]",

    "[magenta]": "[void.purple]",
    "[/magenta]": "[/void.purple]",
    "[bold magenta]": "[void.purple]",
    "[/bold magenta]": "[/void.purple]",

    "[dim]": "[neutral.dim]",
    "[/dim]": "[/neutral.dim]",

    "[bold]": "[sunwell.heading]",
    "[/bold]": "[/sunwell.heading]",
}


def migrate_icons(text: str) -> str:
    """Replace emojis with Holy Light Unicode characters."""
    for emoji, char in ICON_MAP.items():
        text = text.replace(emoji, char)
    return text


def migrate_styles(text: str) -> str:
    """Replace hardcoded colors with Holy Light theme styles."""
    for old, new in STYLE_MAP.items():
        text = text.replace(old, new)
    return text


def holy_print(console: Console, text: str, **kwargs: Any) -> None:
    """Print with automatic Holy Light style and icon migration."""
    console.print(migrate_styles(migrate_icons(text)), **kwargs)


# =============================================================================
# SPINNERS (RFC-131)
# =============================================================================

SPINNERS = {
    # Mote cycle - for progress/activity
    "mote": ["·", "✧", "✦", "✧", "·", " "],

    # Spiral (Uzumaki) - for deep thinking/reasoning
    "spiral": ["◜", "◝", "◞", "◟"],

    # Radiant pulse - for important operations
    "radiant": ["✦", "★", "✦", "✧"],

    # Rising effect - particles ascending
    "rising": ["⋆", "✧", "✦", "✧", "⋆", "·"],

    # Diamond pulse - for validation
    "diamond": ["◇", "◈", "◆", "◈"],

    # Deep spiral - thinking with depth indicator
    "spiral_deep": ["◜ ·", "◝ ○", "◞ ◎", "◟ ◉"],
}


class SpinnerStyle(Enum):
    """Spinner animation styles."""

    MOTE = "mote"
    SPIRAL = "spiral"
    RADIANT = "radiant"
    RISING = "rising"
    DIAMOND = "diamond"
    SPIRAL_DEEP = "spiral_deep"


class MoteSpinner(Spinner):
    """Sunwell-branded spinner using star characters."""

    def __init__(self, style: SpinnerStyle = SpinnerStyle.MOTE, speed: float = 0.15):
        frames = SPINNERS.get(style.value, SPINNERS["mote"])
        super().__init__(
            name="custom",
            frames=frames,
            speed=speed,
            style="bold yellow",
        )


class SpiralSpinner:
    """Uzumaki-style spiral spinner for deep thinking.

    Quarter-arc rotation creates a hypnotic vortex effect.
    """

    FRAMES = ["◜", "◝", "◞", "◟"]
    DEEP_FRAMES = ["◜ ·", "◝ ○", "◞ ◎", "◟ ◉"]

    def __init__(self, deep: bool = False, interval: float = 0.15):
        self.frames = self.DEEP_FRAMES if deep else self.FRAMES
        self.interval = interval
        self._index = 0

    def __next__(self) -> str:
        frame = self.frames[self._index]
        self._index = (self._index + 1) % len(self.frames)
        return frame

    def __iter__(self) -> Iterator[str]:
        return self


# =============================================================================
# SPARKLE ANIMATIONS (RFC-131)
# =============================================================================

class Sparkle:
    """Animated sparkle for terminal feedback."""

    FRAMES = ["✦", "✧", "·", " ", "·", "✧", "✦"]

    @classmethod
    async def burst(cls, text: str = "", duration: float = 0.5) -> None:
        """Show a sparkle burst animation."""
        frame_time = duration / len(cls.FRAMES)

        for frame in cls.FRAMES:
            sys.stdout.write(f"\r  {frame} {text}")
            sys.stdout.flush()
            await asyncio.sleep(frame_time)

        sys.stdout.write(f"\r  ✦ {text}\n")
        sys.stdout.flush()

    @classmethod
    def static(cls, text: str) -> str:
        """Return text with sparkle prefix."""
        return f"✦ {text}"


# =============================================================================
# RISING MOTES ANIMATION (RFC-131)
# =============================================================================

@dataclass(slots=True)
class Mote:
    """A single rising particle."""

    x: int
    y: int
    char: str
    age: int = 0


class RisingMotes:
    """Terminal animation of rising star particles.

    Creates a visual effect of particles rising from the bottom,
    fading as they ascend — like the Holy Light emerging from the void.
    """

    CHARS = ["✦", "✧", "⋆", "·"]
    WIDTH = 20
    HEIGHT = 4

    def __init__(self):
        self.motes: list[Mote] = []

    def _spawn_mote(self) -> None:
        """Spawn a new mote at the bottom."""
        self.motes.append(Mote(
            x=random.randint(0, self.WIDTH - 1),
            y=self.HEIGHT - 1,
            char=random.choice(self.CHARS),
        ))

    def _update(self) -> None:
        """Update mote positions."""
        # Rise and age
        for mote in self.motes:
            mote.y -= 1
            mote.age += 1
            # Fade character as it rises
            if mote.age > 2:
                mote.char = "·"

        # Remove motes that floated away
        self.motes = [m for m in self.motes if m.y >= 0]

    def _render(self) -> str:
        """Render current frame."""
        # Build grid
        grid = [[" "] * self.WIDTH for _ in range(self.HEIGHT)]
        for mote in self.motes:
            if 0 <= mote.y < self.HEIGHT and 0 <= mote.x < self.WIDTH:
                grid[mote.y][mote.x] = mote.char

        # Return as string
        return "\n".join("".join(row) for row in grid)

    async def animate(self, message: str, duration: float = 3.0) -> None:
        """Show rising motes animation."""
        start = asyncio.get_event_loop().time()
        frame = 0

        # Print initial space
        for _ in range(self.HEIGHT):
            print()

        while asyncio.get_event_loop().time() - start < duration:
            # Spawn occasionally
            if frame % 3 == 0:
                self._spawn_mote()

            # Update and render
            self._update()
            rendered = self._render()

            # Clear and redraw
            sys.stdout.write(f"\033[{self.HEIGHT + 1}A")  # Move up
            sys.stdout.write(rendered + "\n")
            sys.stdout.write(f"  ✦ {message}")
            sys.stdout.flush()

            await asyncio.sleep(0.15)
            frame += 1


# =============================================================================
# PHASE HEADERS (RFC-131)
# =============================================================================

class PhaseStyle(Enum):
    """Agent execution phases."""

    UNDERSTANDING = "understanding"
    ILLUMINATING = "illuminating"
    CRAFTING = "crafting"
    VERIFYING = "verifying"
    COMPLETE = "complete"


PHASE_HEADERS = {
    "signal": "✦ Understanding",
    "understanding": "✦ Understanding",
    "plan": "✦ Illuminating",
    "illuminating": "✦ Illuminating",
    "execute": "✦ Crafting",
    "crafting": "✦ Crafting",
    "validate": "✦ Verifying",
    "verifying": "✦ Verifying",
    "complete": "★ Complete",
}


# =============================================================================
# SEMANTIC LEVELS (RFC-131)
# =============================================================================

class Level(Enum):
    """Semantic severity levels for messaging."""

    DEBUG = ("·", "dim white", False)
    INFO = ("✧", "holy.gold", False)
    SUCCESS = ("✓", "green", False)
    WARNING = ("△", "void.indigo", False)
    ERROR = ("✗", "void.purple", False)
    CRITICAL = ("⊗", "void.deep", True)  # May trigger bell

    @property
    def icon(self) -> str:
        return self.value[0]

    @property
    def style(self) -> str:
        return self.value[1]

    @property
    def urgent(self) -> bool:
        return self.value[2]


# =============================================================================
# STATE INDICATORS (RFC-131)
# =============================================================================

STATE_INDICATORS = {
    "thinking": ("✦", "holy.radiant", "mote"),
    "executing": ("✧", "holy.gold", "progress"),
    "waiting": ("◇", "holy.gold.dim", "pulse"),
    "paused": ("◈", "neutral.muted", None),
    "complete": ("★", "holy.success", "sparkle"),
    "failed": ("✗", "void.purple", None),
}


# =============================================================================
# FILE OPERATION INDICATORS (RFC-131)
# =============================================================================

FILE_OPS = {
    "create": ("+", "green"),
    "modify": ("~", "yellow"),
    "delete": ("-", "red"),
    "move": ("→", "cyan"),
    "read": ("◦", "dim"),
    "copy": ("⎘", "dim yellow"),
}


# =============================================================================
# CONFIDENCE INDICATORS (RFC-131)
# =============================================================================

CONFIDENCE_LEVELS = {
    "high": ("●", "green", "High"),      # 90-100%
    "moderate": ("◉", "yellow", "Moderate"),  # 70-89%
    "low": ("○", "bright_magenta", "Low"),        # 50-69%
    "uncertain": ("◌", "red", "Uncertain"),   # 0-49%
}


def get_confidence_level(score: float) -> tuple[str, str, str]:
    """Get confidence level info based on score (0.0-1.0)."""
    if score >= 0.9:
        return CONFIDENCE_LEVELS["high"]
    elif score >= 0.7:
        return CONFIDENCE_LEVELS["moderate"]
    elif score >= 0.5:
        return CONFIDENCE_LEVELS["low"]
    else:
        return CONFIDENCE_LEVELS["uncertain"]


# =============================================================================
# ACCESSIBILITY (RFC-131)
# =============================================================================

def should_reduce_motion() -> bool:
    """Check if animations should be disabled."""
    # Respect user preference or NO_COLOR standard
    return bool(
        os.environ.get("SUNWELL_REDUCED_MOTION") or os.environ.get("NO_COLOR")
    )


def is_plain_mode() -> bool:
    """Check if plain output mode is enabled."""
    return bool(os.environ.get("SUNWELL_PLAIN") or os.environ.get("NO_COLOR"))


# =============================================================================
# SUNWELL RENDERER CONFIG (RFC-131)
# =============================================================================

@dataclass(frozen=True, slots=True)
class SunwellRendererConfig:
    """Configuration for Sunwell CLI rendering."""

    # Animation settings
    enable_motes: bool = True
    enable_sparkles: bool = True
    spinner_style: SpinnerStyle = SpinnerStyle.MOTE

    # Color settings
    use_true_color: bool = True  # Fall back to 256 if not supported

    # Verbosity
    show_learnings: bool = True
    show_token_stats: bool = True
    show_reasoning: bool = True

    # Accessibility
    reduced_motion: bool = False  # Disable animations

    # Mode
    mode: str = "interactive"  # interactive, quiet, json

    refresh_rate: int = 10
    verbose: bool = False

    def __post_init__(self):
        # Auto-detect reduced motion
        if should_reduce_motion():
            self.reduced_motion = True
            self.enable_motes = False
            self.enable_sparkles = False


# =============================================================================
# CONSOLE FACTORY (RFC-131)
# =============================================================================

def create_sunwell_console() -> Console:
    """Create a Rich console with Sunwell theme."""
    return Console(theme=SUNWELL_THEME)


def create_sunwell_progress(console: Console | None = None) -> Progress:
    """Create Sunwell-branded progress display."""
    console = console or create_sunwell_console()
    return Progress(
        SpinnerColumn(spinner_name="dots", style="holy.gold"),
        TextColumn("[sunwell.phase]{task.description}"),
        BarColumn(
            complete_style="sunwell.progress.complete",
            finished_style="holy.radiant",
            pulse_style="holy.gold",
        ),
        TaskProgressColumn(),
        console=console,
    )


# =============================================================================
# RENDERING HELPERS (RFC-131)
# =============================================================================

def emit(console: Console, level: Level, message: str) -> None:
    """Emit a message at the given severity level."""
    icon, style, urgent = level.value
    prefix = f"[{style}]{icon}[/]"
    console.print(f"  {prefix} {message}")


def render_phase_header(console: Console, phase: str) -> None:
    """Render a branded phase header."""
    header = PHASE_HEADERS.get(phase, f"✦ {phase.title()}")

    console.print()
    console.print(f"┌{'─' * 53}┐")
    console.print(f"│  [sunwell.phase]{header:<51}[/]│")
    console.print(f"└{'─' * 53}┘")


def render_confidence(console: Console, score: float, label: str = "") -> None:
    """Render confidence score with visual indicator."""
    icon, color, level_name = get_confidence_level(score)

    bar_width = 10
    filled = int(score * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)

    label_str = f"{label}: " if label else "Confidence: "
    console.print(f"  {label_str}[{color}]{bar}[/] {score:.0%} {icon} {level_name}")


def render_file_operation(console: Console, op: str, path: str, details: str = "") -> None:
    """Render a file operation indicator."""
    icon, color = FILE_OPS.get(op, ("?", "white"))
    detail_str = f" [dim]({details})[/]" if details else ""
    console.print(f"  [{color}]{icon}[/] {path}{detail_str}")


def render_validation(console: Console, name: str, passed: bool, details: str = "") -> None:
    """Render a validation result."""
    if passed:
        icon, color = "✧", "green"
    else:
        icon, color = "✗", "red"

    detail_str = f" [dim]{details}[/]" if details else ""
    console.print(f"    ├─ {name.ljust(12)} [{color}]{icon}[/{color}]{detail_str}")


def render_gate_header(console: Console, gate_id: str) -> None:
    """Render a validation gate header."""
    console.print(f"\n  {'═' * 54}")
    console.print(f"  [sunwell.phase]GATE: {gate_id}[/]")
    console.print(f"  {'═' * 54}")


def render_learning(console: Console, fact: str, source: str = "") -> None:
    """Show a fact the agent learned."""
    source_str = f" [dim]({source})[/]" if source else ""
    console.print(f"  ≡ [holy.gold.dim]Learned:[/] {fact}{source_str}")


def render_decision(console: Console, decision: str, rationale: str = "") -> None:
    """Show a decision made."""
    console.print(f"  ▣ [holy.gold]Decision:[/] {decision}")
    if rationale:
        console.print(f"       [dim]↳ {rationale}[/]")


def render_thinking(console: Console, thought: str, depth: int = 0) -> None:
    """Show agent reasoning."""
    indent = "  " * depth
    console.print(f"  ◜ [dim]{indent}{thought}[/]")


def render_metrics(console: Console, metrics: dict[str, Any]) -> None:
    """Show execution metrics."""
    console.print("\n  [holy.gold]Metrics[/]")
    console.print(f"    ├─ Duration:    {metrics.get('duration_s', 0):.1f}s")
    console.print(f"    ├─ Tokens:      {metrics.get('total_tokens', 0):,}")
    if metrics.get('cost'):
        console.print(f"    ├─ Cost:        ${metrics['cost']:.4f}")
    else:
        console.print("    ├─ Cost:        $0.0000 (local)")
    if metrics.get('tokens_per_second'):
        console.print(f"    └─ Efficiency:  {metrics['tokens_per_second']:.1f} tok/s")


def render_code(
    console: Console,
    code: str,
    language: str = "python",
    context: str = "",
) -> None:
    """Render code with syntax highlighting and context."""
    console.print()
    if context:
        console.print(f"  [neutral.muted]# {context}[/]")
    console.print(Syntax(code, language, theme="monokai", line_numbers=True))


def render_table(
    console: Console,
    data: list[dict[str, Any]],
    columns: list[str],
    title: str = "",
) -> None:
    """Render data table with Sunwell styling."""
    table = Table(
        title=f"[sunwell.phase]{title}[/]" if title else None,
        border_style="holy.gold.dim",
        header_style="holy.gold",
    )
    for col in columns:
        table.add_column(col)

    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


# =============================================================================
# BANNER (RFC-131)
# =============================================================================

SUNWELL_BANNER = """[holy.gold]
   ✦ ✧ ✦
  ✧     ✧
 ✦   ☀   ✦   [holy.radiant]Sunwell[/]
  ✧     ✧    [neutral.muted]AI agent for software tasks[/]
   ✦ ✧ ✦
[/]"""


SUNWELL_BANNER_SMALL = "[holy.radiant]✦ Sunwell[/]"


def print_banner(console: Console, version: str = "0.3.0", small: bool = False) -> None:
    """Print the Sunwell banner."""
    if small:
        console.print(f"\n  {SUNWELL_BANNER_SMALL} v{version}\n")
    else:
        console.print(SUNWELL_BANNER)
        console.print(f"  [dim]v{version}[/]\n")


# =============================================================================
# COMPLETION DISPLAY (RFC-131)
# =============================================================================

def render_complete(
    console: Console,
    tasks_completed: int,
    gates_passed: int,
    duration_s: float,
    learnings: int = 0,
    files_created: list[str] | None = None,
    files_modified: list[str] | None = None,
) -> None:
    """Render completion summary with Holy Light styling."""
    render_phase_header(console, "complete")

    console.print()
    console.print(f"  [holy.radiant]✦ {tasks_completed} tasks completed in {duration_s:.1f}s[/]")
    console.print()

    if files_created:
        console.print("  [neutral.text]Files created:[/]")
        for f in files_created[:10]:  # Limit display
            console.print(f"    [green]+[/] {f}")
        if len(files_created) > 10:
            console.print(f"    [dim]... and {len(files_created) - 10} more[/]")
        console.print()

    if files_modified:
        console.print("  [neutral.text]Files modified:[/]")
        for f in files_modified[:10]:
            console.print(f"    [yellow]~[/] {f}")
        if len(files_modified) > 10:
            console.print(f"    [dim]... and {len(files_modified) - 10} more[/]")
        console.print()

    if learnings > 0:
        console.print(f"  ≡ [holy.gold.dim]Extracted {learnings} learnings[/]")
        console.print()

    console.print("  [holy.radiant]✦✧✦[/] Goal achieved")
    console.print()


def render_error(
    console: Console,
    message: str,
    details: str | None = None,
    suggestion: str | None = None,
) -> None:
    """Render error with Holy Light styling."""
    console.print()
    console.print(f"  [void.purple]✗ {message}[/]")
    if details:
        console.print(f"    [neutral.muted]{details}[/]")
    if suggestion:
        console.print(f"    [holy.gold.dim]※ Suggestion: {suggestion}[/]")
    console.print()
