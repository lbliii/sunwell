# RFC-131: Holy Light CLI — Bringing Sunwell's Soul to the Terminal

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-24  
**Inspiration**: Sunwell Studio design language + Claude Code personality

---

## Executive Summary

The terminal is where developers live. Sunwell's Studio has a distinctive "Holy Light" aesthetic — golden motes rising from darkness, sparkle animations, radiant glows. The CLI should inherit this soul.

This RFC proposes:
1. **Branded Unicode animations** — Custom spinners using ✦✧⋆· characters
2. **Holy Light color palette** — Gold/amber tones for the terminal  
3. **Sparkle indicators** — Visual feedback for key moments
4. **Rising motes ASCII animation** — For thinking/active states
5. **Warm personality in messaging** — Confident, magical tone
6. **Information taxonomy** — Consistent visual treatment for every type of output

**Result**: A CLI that's instantly recognizable as Sunwell — distinctive, delightful, professional. Every piece of information has a defined visual signature.

---

## The Problem

Current CLI output is generic:
```
⠋ Understanding goal...
⠙ Planning (harmonic)...
✓ Complete: 5 tasks in 12.3s
```

This could be any tool. No personality, no brand recognition.

**Claude Code's approach**: Playful naming (Ralph Wiggum), clear phase markers, but no distinctive visual language.

**Sunwell's opportunity**: We have a visual language (Holy Light). We just need to bring it to the terminal.

---

## The Holy Light Terminal Aesthetic

### Philosophy (from Studio's `variables.css`)

```
Golden accents radiating from the void — sacred light emerging from darkness.

- UI elements use SOFT, PALLID yellows (understated)
- Magical effects use BRIGHT, RADIANT golds (sparkles, glows)
- The void (dark background) is where the light emerges FROM
```

### Terminal Translation

| Studio Element | Terminal Equivalent |
|----------------|---------------------|
| Rising motes (`✦ ✧ ⋆ ·`) | ASCII animation frames |
| Radiant gold (`#ffd700`) | `bright_yellow` / ANSI 220 |
| UI gold (`#c9a227`) | `yellow` / ANSI 178 |
| Glow effect | Bold + bright color |
| Void background | Terminal default (dark) |

---

## 1. Branded Spinners

Replace generic spinners with Sunwell star characters:

### Spinner Frames

```python
# Sunwell branded spinners
SPINNERS = {
    # Spiral (Uzumaki) - for deep thinking/reasoning
    "spiral": ["◜", "◝", "◞", "◟"],
    
    # Mote cycle - for progress/activity
    "mote": ["·", "✧", "✦", "✧", "·", " "],
    
    # Radiant pulse - for important operations
    "radiant": ["✦", "★", "✦", "✧"],
    
    # Rising effect - particles ascending
    "rising": ["⋆", "✧", "✦", "✧", "⋆", "·"],
    
    # Diamond pulse - for validation
    "diamond": ["◇", "◈", "◆", "◈"],
    
    # Constellation - complex operations
    "constellation": [
        "·  ✧  ·",
        "✧  ·  ✧",
        "·  ✦  ·",
        "✧  ·  ✧",
    ],
    
    # Deep spiral - thinking with depth indicator
    "spiral_deep": ["◜ ·", "◝ ○", "◞ ◎", "◟ ◉"],
}
```

### Usage Examples

```python
from rich.spinner import Spinner

# Custom Sunwell spinner
class MoteSpinner(Spinner):
    """Sunwell-branded spinner using star characters."""
    
    def __init__(self, style: str = "mote", speed: float = 0.15):
        frames = SPINNERS.get(style, SPINNERS["mote"])
        super().__init__(
            name="custom",
            frames=frames,
            speed=speed,
            style="bold yellow",
        )
```

### Visual

```
Before (generic):
  ⠋ Understanding goal...
  
After (Sunwell):
  ✦ Understanding goal...
  ✧ Understanding goal...
  · Understanding goal...
```

---

## 2. Holy Light Color Theme

### Rich Theme Definition

The color spectrum is constrained to **Holy ↔ Void magic** — no generic corporate colors.

```python
from rich.theme import Theme

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
    "sunwell.success": "holy.success",            # Light triumphs
    "sunwell.warning": "void.indigo",             # Shadow creeping in
    "sunwell.error": "void.purple",               # Void corruption
    "sunwell.critical": "void.deep",              # Full void
    
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
})
```

### Color Rationale

| Semantic | Spectrum | Why |
|----------|----------|-----|
| Success | Holy (gold/green) | Light triumphs over darkness |
| Progress | Holy (gold) | Illuminating the path forward |
| Warning | Void (indigo) | Shadow creeping in |
| Error | Void (purple) | Void corruption |
| Critical | Void (deep red-purple) | Full void consuming |
| Unknown | Void (blue-shadow) | Unilluminated space |

### Console Setup

```python
from rich.console import Console

console = Console(theme=SUNWELL_THEME)

# Usage
console.print("✦ [sunwell.radiant]Goal understood[/]")
console.print("  [sunwell.gold]├─[/] complexity: medium")
console.print("  [sunwell.gold]└─[/] route: harmonic")
```

---

## 3. Sparkle Indicators

Key moments deserve visual celebration:

### Sparkle Animation Class

```python
import asyncio
import sys

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
```

### When to Sparkle

| Event | Animation | Example |
|-------|-----------|---------|
| Goal understood | Single sparkle | `✦ Understanding goal...` |
| Plan ready | Sparkle burst | `✦ Plan ready (harmonic)` |
| Task complete | Brief twinkle | `✧ Task complete` |
| All gates pass | Radiant burst | `★ All validations passed` |
| Goal complete | Full celebration | `✦✧✦ Goal achieved!` |

---

## 4. Rising Motes Animation

For extended thinking states, show rising particles:

### ASCII Rising Motes

```python
import asyncio
import random
from dataclasses import dataclass

@dataclass
class Mote:
    x: int
    y: int
    char: str
    age: int = 0

class RisingMotes:
    """Terminal animation of rising star particles."""
    
    CHARS = ["✦", "✧", "⋆", "·"]
    WIDTH = 20
    HEIGHT = 4
    
    def __init__(self):
        self.motes: list[Mote] = []
        self.grid: list[list[str]] = []
        
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
        import sys
        
        start = asyncio.get_event_loop().time()
        frame = 0
        
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
```

### Visual Example

```
         ·        ✧
      ✧     ·
   ·     ✦     ·
     ✧     ·
  ✦ Thinking deeply...
```

---

## 5. Personality & Voice

### Tone Guidelines

| Aspect | Guideline | Example |
|--------|-----------|---------|
| **Confidence** | State facts, don't hedge | "Plan ready" not "Plan might be ready" |
| **Warmth** | Supportive, not cold | "Understanding your goal..." |
| **Magical** | Touch of wonder | "✦ Illuminating codebase..." |
| **Concise** | Every word earns its place | No "Successfully completed" |

### Phase Headers

```python
PHASE_HEADERS = {
    "signal": "✦ Understanding",
    "plan": "✦ Illuminating", 
    "execute": "✦ Crafting",
    "validate": "✦ Verifying",
    "complete": "★ Complete",
}
```

### Message Examples

```python
# Before (generic)
"Extracting signals..."
"Planning with harmonic technique..."
"Running validation gate..."
"Done."

# After (Sunwell voice)
"✦ Understanding your goal..."
"✦ Illuminating the path forward..."
"✦ Verifying the light holds..."
"★ Goal achieved"
```

### Error Messages

```python
# Before
"Error: File not found"

# After
"✗ [sunwell.error]The path fades into shadow[/]"
"  [sunwell.muted]Could not find: {path}[/]"
```

---

## 6. Information Taxonomy

A comprehensive system for displaying different types of information consistently.

### 6.1 Agent States

Every state has a distinct visual signature:

| State | Icon | Color | Animation | Example |
|-------|------|-------|-----------|---------|
| **Thinking** | `✦` | `sunwell.radiant` | Mote spinner | `✦ Understanding your goal...` |
| **Executing** | `✧` | `sunwell.gold` | Progress bar | `✧ [2/7] Creating auth.py...` |
| **Waiting** | `◇` | `sunwell.gold.dim` | Pulse | `◇ Awaiting approval...` |
| **Paused** | `◈` | `sunwell.muted` | None | `◈ Paused at checkpoint` |
| **Complete** | `★` | `sunwell.success` | Sparkle burst | `★ Goal achieved` |
| **Failed** | `✗` | `sunwell.error` | None | `✗ Execution failed` |

```python
STATE_INDICATORS = {
    "thinking": ("✦", "sunwell.radiant", "mote"),
    "executing": ("✧", "sunwell.gold", "progress"),
    "waiting": ("◇", "sunwell.gold.dim", "pulse"),
    "paused": ("◈", "sunwell.muted", None),
    "complete": ("★", "sunwell.success", "sparkle"),
    "failed": ("✗", "sunwell.error", None),
}
```

### 6.2 Semantic Levels

Severity-based messaging with consistent visual treatment:

```
┌─────────────────────────────────────────────────────────────────────┐
│ LEVEL      │ ICON │ COLOR           │ SOUND │ USE CASE              │
├─────────────────────────────────────────────────────────────────────┤
│ DEBUG      │  ·   │ dim white       │ none  │ Verbose internals     │
│ INFO       │  ✧   │ sunwell.gold    │ none  │ Progress updates      │
│ SUCCESS    │  ✓   │ green           │ none  │ Completion            │
│ WARNING    │  ⚠   │ yellow          │ none  │ Non-blocking issues   │
│ ERROR      │  ✗   │ red             │ none  │ Blocking failures     │
│ CRITICAL   │  ⛔  │ bold red        │ bell? │ Data loss risk        │
└─────────────────────────────────────────────────────────────────────┘
```

```python
from enum import Enum

class Level(Enum):
    DEBUG = ("·", "dim white", False)
    INFO = ("✧", "sunwell.gold", False)
    SUCCESS = ("✓", "green", False)
    WARNING = ("⚠", "yellow", False)
    ERROR = ("✗", "red", False)
    CRITICAL = ("⛔", "bold red", True)  # May trigger bell

def emit(level: Level, message: str) -> None:
    icon, style, urgent = level.value
    prefix = f"[{style}]{icon}[/]"
    console.print(f"  {prefix} {message}")
```

### 6.3 Content Types

Different content needs different formatting:

#### Code Blocks

```python
def render_code(code: str, language: str = "python", context: str = "") -> None:
    """Render code with syntax highlighting and context."""
    console.print()
    if context:
        console.print(f"  [sunwell.muted]# {context}[/]")
    console.print(Syntax(code, language, theme="monokai", line_numbers=True))
```

**Visual:**
```
  # Creating OAuth provider
  ┌────────────────────────────────────────────┐
  │  1 │ class OAuthProvider:                  │
  │  2 │     def __init__(self, client_id):    │
  │  3 │         self.client_id = client_id    │
  └────────────────────────────────────────────┘
```

#### Diffs

```python
def render_diff(old: str, new: str, file_path: str) -> None:
    """Render file diff with additions/deletions."""
    console.print(f"\n  [sunwell.gold]┌─ {file_path}[/]")
    for line in diff_lines:
        if line.startswith("+"):
            console.print(f"  [green]│ {line}[/]")
        elif line.startswith("-"):
            console.print(f"  [red]│ {line}[/]")
        else:
            console.print(f"  [dim]│ {line}[/]")
    console.print(f"  [sunwell.gold]└─[/]")
```

**Visual:**
```
  ┌─ src/auth/oauth.py
  │   def authenticate(self):
  │ -     return None
  │ +     token = self.provider.get_token()
  │ +     return Token(value=token)
  └─
```

#### Tables

```python
def render_table(data: list[dict], title: str = "") -> None:
    """Render data table with Sunwell styling."""
    table = Table(
        title=f"[sunwell.phase]{title}[/]" if title else None,
        border_style="sunwell.gold.dim",
        header_style="sunwell.gold",
    )
    # ... populate table
    console.print(table)
```

**Visual:**
```
  ┌─────────────────────────────────────────────┐
  │  ✦ Confidence Scores                        │
  ├──────────────┬───────────┬─────────────────┤
  │ File         │ Score     │ Status          │
  ├──────────────┼───────────┼─────────────────┤
  │ auth.py      │ 94%  🟢   │ High            │
  │ billing.py   │ 72%  🟡   │ Moderate        │
  │ config.py    │ 45%  🔴   │ Review needed   │
  └──────────────┴───────────┴─────────────────┘
```

### 6.4 Confidence Display

Confidence scores use color + icon + bar:

```python
def render_confidence(score: float, label: str = "") -> None:
    """Render confidence score with visual indicator."""
    if score >= 0.9:
        color, icon, level = "green", "🟢", "High"
    elif score >= 0.7:
        color, icon, level = "yellow", "🟡", "Moderate"
    elif score >= 0.5:
        color, icon, level = "rgb(255,165,0)", "🟠", "Low"
    else:
        color, icon, level = "red", "🔴", "Uncertain"
    
    bar_width = 10
    filled = int(score * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    
    console.print(f"  {label}: [{color}]{bar}[/] {score:.0%} {icon} {level}")
```

**Visual:**
```
  Confidence: ████████░░ 82% 🟡 Moderate
```

### 6.5 User Interactions

Different interaction types have distinct patterns:

#### Prompts (Requiring Input)

```python
def prompt_input(question: str, default: str = "") -> str:
    """Prompt for text input."""
    console.print(f"\n  [sunwell.gold]?[/] {question}")
    if default:
        console.print(f"    [dim](default: {default})[/]")
    return Prompt.ask("    [sunwell.gold]›[/]", default=default)
```

**Visual:**
```
  ? What should the API endpoint be called?
    (default: /api/auth)
    › _
```

#### Confirmations (Yes/No)

```python
def confirm(question: str, default: bool = True) -> bool:
    """Ask for confirmation."""
    hint = "[Y/n]" if default else "[y/N]"
    console.print(f"\n  [sunwell.gold]?[/] {question} [dim]{hint}[/]")
    return Confirm.ask("    [sunwell.gold]›[/]", default=default)
```

**Visual:**
```
  ? Ready to implement? [Y/n]
    › _
```

#### Choices (Selection)

```python
def choose(question: str, options: list[str]) -> str:
    """Present multiple choice."""
    console.print(f"\n  [sunwell.gold]?[/] {question}")
    for i, opt in enumerate(options, 1):
        console.print(f"    [sunwell.gold]{i}.[/] {opt}")
    console.print()
    return options[IntPrompt.ask("    [sunwell.gold]›[/]", choices=[str(i) for i in range(1, len(options)+1)]) - 1]
```

**Visual:**
```
  ? Which approach do you prefer?
    1. Minimal — Smallest change, maximum reuse
    2. Clean — Best architecture, more refactoring
    3. Pragmatic — Balanced (recommended)
    
    › _
```

### 6.6 File Operations

Clear visual treatment for file system changes:

| Operation | Icon | Color | Format |
|-----------|------|-------|--------|
| Create | `+` | `green` | `+ src/auth/oauth.py` |
| Modify | `~` | `yellow` | `~ src/auth/handler.py (12 lines)` |
| Delete | `-` | `red` | `- src/auth/legacy.py` |
| Move | `→` | `cyan` | `→ old/path.py → new/path.py` |
| Read | `◦` | `dim` | `◦ Reading config.py...` |

```python
def render_file_operation(op: str, path: str, details: str = "") -> None:
    ops = {
        "create": ("+", "green"),
        "modify": ("~", "yellow"),
        "delete": ("-", "red"),
        "move": ("→", "cyan"),
        "read": ("◦", "dim"),
    }
    icon, color = ops.get(op, ("?", "white"))
    detail_str = f" [dim]({details})[/]" if details else ""
    console.print(f"  [{color}]{icon}[/] {path}{detail_str}")
```

**Visual:**
```
  Files changed:
    + src/auth/oauth.py (new)
    ~ src/auth/handler.py (12 lines)
    - src/auth/legacy.py
```

### 6.7 Validation Results

Gates and checks use consistent pass/fail indicators:

```python
def render_validation(name: str, passed: bool, details: str = "") -> None:
    """Render a validation result."""
    if passed:
        icon, color = "✧", "green"
    else:
        icon, color = "✗", "red"
    
    detail_str = f" [dim]{details}[/]" if details else ""
    console.print(f"    ├─ {name.ljust(12)} [{color}]{icon}[/]{detail_str}")
```

**Visual:**
```
  ══════════════════════════════════════════════════════
  GATE: quality
  ══════════════════════════════════════════════════════
    ├─ ruff         ✧ passed
    ├─ ty           ✧ passed
    ├─ mypy         ✗ 2 errors
    │     └─ auth.py:45 — Incompatible return type
    │     └─ auth.py:67 — Missing type annotation
    └─ pytest       ✧ 24 passed
```

### 6.8 Memory & Learning

Surfacing agent knowledge and learnings:

```python
def render_learning(fact: str, source: str = "") -> None:
    """Show a fact the agent learned."""
    source_str = f" [dim]({source})[/]" if source else ""
    console.print(f"  📚 [sunwell.gold.dim]Learned:[/] {fact}{source_str}")

def render_decision(decision: str, rationale: str = "") -> None:
    """Show a decision made."""
    console.print(f"  📋 [sunwell.gold]Decision:[/] {decision}")
    if rationale:
        console.print(f"       [dim]↳ {rationale}[/]")

def render_memory_recall(fact: str, relevance: float) -> None:
    """Show recalled memory."""
    bar = "█" * int(relevance * 5) + "░" * (5 - int(relevance * 5))
    console.print(f"  🧠 [dim]{bar}[/] {fact}")
```

**Visual:**
```
  📚 Learned: OAuth provider pattern for this codebase
  
  📋 Decision: Using Google OAuth as primary provider
       ↳ User specified Google in requirements
  
  🧠 ████░ Previous session used JWT tokens
  🧠 ███░░ Team prefers explicit error handling
```

### 6.9 Thinking & Reasoning

Extended thinking gets special treatment:

```python
def render_thinking(thought: str, depth: int = 0) -> None:
    """Show agent reasoning."""
    indent = "  " * depth
    console.print(f"  💭 [dim]{indent}{thought}[/]")

def render_reasoning_trace(steps: list[str]) -> None:
    """Show full reasoning trace in collapsible format."""
    console.print("\n  [sunwell.gold.dim]┌─ Reasoning[/]")
    for i, step in enumerate(steps, 1):
        connector = "├" if i < len(steps) else "└"
        console.print(f"  [sunwell.gold.dim]│[/] {i}. {step}")
    console.print()
```

**Visual:**
```
  💭 Analyzing codebase structure...
  💭   Found existing auth module at src/auth/
  💭   Checking for OAuth dependencies...
  💭   No existing OAuth implementation found
  
  ┌─ Reasoning
  │ 1. Goal requires authentication with external providers
  │ 2. Existing auth/ module uses JWT for internal auth
  │ 3. OAuth is complementary, not replacement
  │ 4. Best approach: Add OAuth alongside existing JWT
  └─
```

### 6.10 Progress & Metrics

Real-time metrics display:

```python
def render_metrics(metrics: dict) -> None:
    """Show execution metrics."""
    console.print("\n  [sunwell.gold]Metrics[/]")
    console.print(f"    ├─ Duration:    {metrics['duration_s']:.1f}s")
    console.print(f"    ├─ Tokens:      {metrics['total_tokens']:,}")
    console.print(f"    ├─ Cost:        ${metrics['cost']:.4f}")
    console.print(f"    └─ Efficiency:  {metrics['tokens_per_second']:.1f} tok/s")
```

**Visual:**
```
  Metrics
    ├─ Duration:    45.2s
    ├─ Tokens:      12,345
    ├─ Cost:        $0.0000 (local)
    └─ Efficiency:  273.1 tok/s
```

### 6.11 Summary: Information Type Quick Reference

```
┌────────────────────────────────────────────────────────────────────────────┐
│ TYPE              │ ICON  │ COLOR            │ EXAMPLE                     │
├────────────────────────────────────────────────────────────────────────────┤
│ Thinking          │ ✦     │ sunwell.radiant  │ ✦ Understanding...          │
│ Progress          │ ✧     │ sunwell.gold     │ ✧ [2/7] Creating...         │
│ Complete          │ ★     │ green            │ ★ Goal achieved             │
│ Error             │ ✗     │ red              │ ✗ Build failed              │
│ Warning           │ ⚠     │ yellow           │ ⚠ Missing tests             │
│ Info              │ ✧     │ sunwell.gold     │ ✧ Found 3 files             │
│ Debug             │ ·     │ dim              │ · Loading cache...          │
├────────────────────────────────────────────────────────────────────────────┤
│ File Create       │ +     │ green            │ + src/new.py                │
│ File Modify       │ ~     │ yellow           │ ~ src/existing.py           │
│ File Delete       │ -     │ red              │ - src/old.py                │
├────────────────────────────────────────────────────────────────────────────┤
│ Gate Pass         │ ✧     │ green            │ ✧ lint passed               │
│ Gate Fail         │ ✗     │ red              │ ✗ type 2 errors             │
│ Gate Skip         │ ◦     │ dim              │ ◦ test skipped              │
├────────────────────────────────────────────────────────────────────────────┤
│ Confidence High   │ 🟢    │ green            │ 94% 🟢                      │
│ Confidence Med    │ 🟡    │ yellow           │ 72% 🟡                      │
│ Confidence Low    │ 🟠    │ orange           │ 58% 🟠                      │
│ Confidence Unc    │ 🔴    │ red              │ 34% 🔴                      │
├────────────────────────────────────────────────────────────────────────────┤
│ Learning          │ 📚    │ sunwell.gold.dim │ 📚 Learned: pattern...      │
│ Decision          │ 📋    │ sunwell.gold     │ 📋 Decision: using...       │
│ Memory            │ 🧠    │ dim              │ 🧠 Previous: ...            │
│ Thinking          │ 💭    │ dim              │ 💭 Analyzing...             │
├────────────────────────────────────────────────────────────────────────────┤
│ Prompt            │ ?     │ sunwell.gold     │ ? What endpoint?            │
│ Input marker      │ ›     │ sunwell.gold     │ › _                         │
│ Approval          │ ◇     │ sunwell.gold     │ ◇ Awaiting approval...      │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Branded Progress Display

### Sunwell Progress Bar

```python
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

def create_sunwell_progress() -> Progress:
    """Create Sunwell-branded progress display."""
    return Progress(
        SpinnerColumn(spinner_name="dots", style="sunwell.gold"),
        TextColumn("[sunwell.phase]{task.description}"),
        BarColumn(
            complete_style="sunwell.progress.complete",
            finished_style="sunwell.radiant",
            pulse_style="sunwell.gold",
        ),
        TaskProgressColumn(),
        console=console,
    )
```

### Phase Progress Display

```
┌─────────────────────────────────────────────────────┐
│  ✦ Sunwell                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ✧ Understanding...     ████████████████████ 100%   │
│  ✦ Illuminating...      ████████░░░░░░░░░░░░  40%   │
│  · Crafting             ░░░░░░░░░░░░░░░░░░░░   0%   │
│  · Verifying            ░░░░░░░░░░░░░░░░░░░░   0%   │
│                                                     │
│  ✧ auth.py:45 → Creating OAuth provider...          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 8. Complete Example

### Full Session Output

```
$ sunwell "Add OAuth authentication"

  ✦ Sunwell v0.3.0

┌─────────────────────────────────────────────────────┐
│  ✦ Understanding                                    │
└─────────────────────────────────────────────────────┘
  ✧ complexity: medium
  ✧ needs_tools: true  
  ✧ confidence: 87%
  └─ route: harmonic

┌─────────────────────────────────────────────────────┐
│  ✦ Illuminating                                     │
└─────────────────────────────────────────────────────┘
         ·    ✧        
      ✧     ·     ✦
   ·     ✦     ·
     ✧     ·
  ✦ Exploring 3 perspectives...

  ✧ Plan ready (harmonic)
    ├─ 7 tasks
    └─ 3 validation gates

┌─────────────────────────────────────────────────────┐
│  ✦ Crafting                                         │
└─────────────────────────────────────────────────────┘

  [1/7] ✧ auth/oauth.py              ████████████████████ ✓
  [2/7] ✧ auth/providers/google.py   ████████████████████ ✓
  [3/7] ✦ auth/providers/github.py   ████████░░░░░░░░░░░░ 42%
        └─ 🧠 gemma3:4b generating... 234 tok (12.3 tok/s)

┌─────────────────────────────────────────────────────┐
│  ✦ Verifying                                        │
└─────────────────────────────────────────────────────┘

  ══════════════════════════════════════════════════════
  GATE: lint
  ══════════════════════════════════════════════════════
    ├─ ruff       ✧ passed
    ├─ ty         ✧ passed
    └─ mypy       ✧ passed

  ══════════════════════════════════════════════════════
  GATE: test  
  ══════════════════════════════════════════════════════
    ├─ unit       ✧ 12 passed
    └─ coverage   ✧ 94%

┌─────────────────────────────────────────────────────┐
│  ★ Complete                                         │
└─────────────────────────────────────────────────────┘

  ✦ 7 tasks completed in 45.2s
  
  Files created:
    ✧ src/auth/oauth.py
    ✧ src/auth/providers/google.py
    ✧ src/auth/providers/github.py
    ✧ tests/auth/test_oauth.py

  📚 Learned: OAuth provider pattern for this codebase
  
  ✦✧✦ Goal achieved
```

---

## 9. Implementation

### Types

```python
from dataclasses import dataclass
from enum import Enum

class SpinnerStyle(Enum):
    MOTE = "mote"
    RADIANT = "radiant"
    RISING = "rising"
    DIAMOND = "diamond"
    CONSTELLATION = "constellation"

class PhaseStyle(Enum):
    UNDERSTANDING = "understanding"
    ILLUMINATING = "illuminating"
    CRAFTING = "crafting"
    VERIFYING = "verifying"
    COMPLETE = "complete"

@dataclass
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
    
    # Accessibility
    reduced_motion: bool = False  # Disable animations
```

### Renderer Updates

```python
class SunwellRenderer(RichRenderer):
    """Enhanced renderer with Holy Light aesthetic."""
    
    def __init__(self, config: SunwellRendererConfig | None = None):
        super().__init__()
        self.sunwell_config = config or SunwellRendererConfig()
        
        # Apply theme
        self.console = Console(theme=SUNWELL_THEME)
        
        # Create branded progress
        self.progress = self._create_branded_progress()
    
    def _render_phase_header(self, phase: PhaseStyle) -> None:
        """Render a branded phase header."""
        header = PHASE_HEADERS.get(phase.value, phase.value)
        
        self.console.print()
        self.console.print(f"┌{'─' * 53}┐")
        self.console.print(f"│  [sunwell.phase]{header:<51}│")
        self.console.print(f"└{'─' * 53}┘")
    
    def _render_sparkle_complete(self, message: str) -> None:
        """Render completion with sparkle animation."""
        if self.sunwell_config.enable_sparkles and not self.sunwell_config.reduced_motion:
            asyncio.create_task(Sparkle.burst(message))
        else:
            self.console.print(f"  ✦ [sunwell.radiant]{message}[/]")
```

---

## 10. CLI Help with Personality

### Brand Banner

```python
SUNWELL_BANNER = """
[sunwell.gold]
   ✦ ✧ ✦
  ✧     ✧
 ✦   ☀   ✦   [sunwell.radiant]Sunwell[/]
  ✧     ✧    [sunwell.muted]AI agent for software tasks[/]
   ✦ ✧ ✦
[/]
"""
```

### Help Text

```python
@click.group(cls=GoalFirstGroup, invoke_without_command=True)
def main():
    """✦ Sunwell — AI agent for software tasks.

    \b
    USAGE:
        sunwell [GOAL]           Run a goal
        sunwell -s [SHORTCUT]    Quick skills
        sunwell [COMMAND]        Subcommands

    \b
    EXAMPLES:
        sunwell "Build a REST API with auth"
        sunwell -s a-2 docs/api.md
        sunwell config model

    \b
    The light illuminates the path. ✧
    """
```

---

## 11. Accessibility

### Reduced Motion Mode

```python
# Check terminal capabilities
import os

def should_reduce_motion() -> bool:
    """Check if animations should be disabled."""
    # Respect user preference
    if os.environ.get("SUNWELL_REDUCED_MOTION"):
        return True
    
    # Check for screen readers
    if os.environ.get("TERM_PROGRAM") == "Apple_Terminal":
        # Check accessibility settings
        pass
    
    # Check NO_COLOR standard
    if os.environ.get("NO_COLOR"):
        return True
    
    return False
```

### Fallback Rendering

```python
# When animations are disabled
if config.reduced_motion:
    # Use static sparkles instead of animations
    console.print("  ✦ Understanding goal...")
    
    # Use simple progress instead of spinners
    console.print("  [1/7] ✓ auth/oauth.py")
```

---

## 12. Configuration

### User Config

```yaml
# ~/.sunwell/config.yaml
cli:
  theme: "holy-light"  # or "minimal", "plain"
  animations:
    motes: true
    sparkles: true
    reduced_motion: false
  spinner: "mote"  # mote, radiant, rising, diamond
  verbosity: "normal"  # quiet, normal, verbose
```

### Environment Variables

```bash
# Disable all animations
export SUNWELL_REDUCED_MOTION=1

# Force plain output (for CI)
export SUNWELL_PLAIN=1

# Use minimal theme
export SUNWELL_THEME=minimal
```

---

## 13. Migration Path

### Phase 1: Theme & Colors (Week 1)
- [ ] Create `SUNWELL_THEME` with Holy Light colors
- [ ] Update `Console` initialization in all CLI modules
- [ ] Replace hardcoded colors with theme tokens

### Phase 2: Spinners & Progress (Week 2)  
- [ ] Implement `MoteSpinner` class
- [ ] Create `SunwellProgress` component
- [ ] Update renderer to use branded progress

### Phase 3: Sparkle Animations (Week 3)
- [ ] Implement `Sparkle` class
- [ ] Add sparkle triggers at key events
- [ ] Add rising motes for extended thinking

### Phase 4: Voice & Messaging (Week 4)
- [ ] Define phase headers and messages
- [ ] Update all user-facing strings
- [ ] Add banner and help text personality

### Phase 5: Polish & Accessibility (Week 5)
- [ ] Implement reduced motion mode
- [ ] Add configuration options
- [ ] Test across terminal types

---

## 14. Success Metrics

| Metric | Target |
|--------|--------|
| Brand recognition | Users identify Sunwell by CLI output |
| Developer delight | >90% prefer branded output |
| Performance impact | <5ms added latency for animations |
| Accessibility | Full reduced-motion support |
| Terminal compatibility | Works in 95% of modern terminals |

---

## Open Questions

1. **Sound effects?** — Terminal bells for completion? (probably no)
2. **Color detection** — How to detect true color vs 256 support?
3. **Emoji fallbacks** — What if terminal doesn't support Unicode?
4. **CI mode** — Auto-detect and disable animations?

---

## References

- Sunwell Studio Design System: `studio/src/styles/variables.css`
- RisingMotes Component: `studio/src/components/RisingMotes.svelte`
- Sparkle Component: `studio/src/components/ui/Sparkle.svelte`
- Current Renderer: `src/sunwell/agent/renderer.py`
- Rich Library: https://rich.readthedocs.io/
