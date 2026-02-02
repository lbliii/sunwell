# Holy Light CLI Theme Reference (RFC-131)

> *"Golden accents radiating from the void — sacred light emerging from darkness."*

Complete reference for Sunwell's terminal visual identity system.

---

## Quick Import

```python
from sunwell.interface.cli.core.theme import (
    # Console & Progress
    create_sunwell_console,
    create_sunwell_progress,
    
    # Core Rendering Functions
    emit,
    render_phase_header,
    render_confidence,
    render_validation,
    render_gate_header,
    render_file_operation,
    render_learning,
    render_decision,
    render_thinking,
    render_metrics,
    render_code,
    render_table,
    render_complete,
    render_error,
    print_banner,
    holy_print,
    
    # Extended Components (RFC-131 Extended)
    render_streaming,
    render_step_progress,
    render_alert,
    render_quote,
    render_separator,
    render_timeline,
    render_breadcrumb,
    render_budget_bar,
    render_countdown,
    render_diff,
    render_collapsible,
    render_toast,
    
    # Character Sets
    CHARS_STARS,
    CHARS_DIAMONDS,
    CHARS_CIRCLES,
    CHARS_CHECKS,
    CHARS_MISC,
    CHARS_PROGRESS,
    CHARS_LAYOUT,
    
    # Animations
    Sparkle,
    RisingMotes,
    MoteSpinner,
    SpiralSpinner,
    SpinnerStyle,
    
    # Utilities
    Level,
    should_reduce_motion,
    is_plain_mode,
    migrate_icons,
    migrate_styles,
)
```

---

## Color Spectrum

### Holy Spectrum (Positive States)

| Style | Rich Markup | Hex | Use For |
|-------|-------------|-----|---------|
| `holy.radiant` | `bold bright_yellow` | `#ffd700` | Active, magical moments, primary actions |
| `holy.gold` | `yellow` | `#c9a227` | Standard UI accent, progress |
| `holy.gold.dim` | `dim yellow` | `#8a7235` | Muted, disabled, secondary |
| `holy.success` | `bold green` | `#22c55e` | Completion, pass, success |

### Void Spectrum (Negative States)

| Style | Rich Markup | Hex | Use For |
|-------|-------------|-----|---------|
| `void.purple` | `bold magenta` | `#7c3aed` | Error, violation |
| `void.indigo` | `bright_magenta` | `#4f46e5` | Warning, caution |
| `void.deep` | `bold red` | `#2e1065` | Critical, fatal |
| `void.shadow` | `dim magenta` | `#3730a3` | Muted danger |

### Neutral (Canvas)

| Style | Rich Markup | Use For |
|-------|-------------|---------|
| `neutral.text` | `white` | Primary text |
| `neutral.muted` | `dim white` | Secondary text |
| `neutral.dim` | `dim` | Tertiary, hints |

### Semantic Aliases

| Style | Maps To | Use For |
|-------|---------|---------|
| `sunwell.success` | `holy.success` | Light triumphs |
| `sunwell.warning` | `void.indigo` | Shadow creeping in |
| `sunwell.error` | `void.purple` | Void corruption |
| `sunwell.critical` | `void.deep` | Full void |
| `sunwell.heading` | `bold white` | Headings |
| `sunwell.phase` | `bold yellow` | Phase headers |

---

## Character Sets

### Stars (`CHARS_STARS`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `radiant` | ✦ | U+2726 | Active, important, primary |
| `progress` | ✧ | U+2727 | Secondary, in-progress |
| `complete` | ★ | U+2605 | Success, completion |
| `cache` | ⋆ | U+22C6 | Fast, cached |
| `dim` | · | U+00B7 | Pending, debug |

### Diamonds (`CHARS_DIAMONDS`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `solid` | ◆ | U+25C6 | Ready, active |
| `hollow` | ◇ | U+25C7 | Waiting, available |
| `inset` | ◈ | U+25C8 | Paused |

### Circles (`CHARS_CIRCLES`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `filled` | ● | U+25CF | High confidence |
| `target` | ◉ | U+25C9 | Moderate confidence |
| `empty` | ○ | U+25CB | Low confidence |
| `dotted` | ◌ | U+25CC | Uncertain |
| `double` | ◎ | U+25CE | Model indicator |
| `half` | ◐ | U+25D0 | Lens indicator |
| `quarter` | ◔ | U+25D4 | Timeout |

### Checks (`CHARS_CHECKS`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `pass` | ✓ | U+2713 | Validation passed |
| `fail` | ✗ | U+2717 | Validation failed |

### Misc (`CHARS_MISC`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `gear` | ⚙ | U+2699 | Fixing, tools |
| `warning` | △ | U+25B3 | Warning, stub |
| `approval` | ⊗ | U+2297 | Approval needed |
| `violation` | ⊘ | U+2298 | Policy violation |
| `refresh` | ↻ | U+21BB | Refresh, retry |
| `learning` | ≡ | U+2261 | Learning extracted |
| `insight` | ※ | U+203B | Insight, suggestion |
| `decision` | ▣ | U+25A3 | Decision made |
| `save` | ▤ | U+25A4 | Save, checkpoint |
| `workspace` | ▢ | U+25A2 | Workspace |
| `budget` | ¤ | U+00A4 | Budget, cost |
| `prompt` | ? | - | Question |
| `input` | › | U+203A | Input marker |

### Progress (`CHARS_PROGRESS`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `step_done` | ◆ | U+25C6 | Completed step |
| `step_current` | ◈ | U+25C8 | Current step |
| `step_pending` | ◇ | U+25C7 | Pending step |
| `connector` | ─── | U+2500 | Step connector |
| `arrow` | › | U+203A | Breadcrumb separator |

### Layout (`CHARS_LAYOUT`)

| Key | Char | Unicode | Use For |
|-----|------|---------|---------|
| `quote` | ┃ | U+2503 | Quote bar |
| `expand` | ▶ | U+25B6 | Collapsed section |
| `collapse` | ▼ | U+25BC | Expanded section |
| `corner_tl` | ╭ | U+256D | Top-left rounded |
| `corner_tr` | ╮ | U+256E | Top-right rounded |
| `corner_bl` | ╰ | U+2570 | Bottom-left rounded |
| `corner_br` | ╯ | U+256F | Bottom-right rounded |
| `h_line` | ─ | U+2500 | Horizontal line |
| `v_line` | │ | U+2502 | Vertical line |
| `tree_branch` | ├─ | - | Tree branch |
| `tree_last` | └─ | - | Tree last branch |

---

## Rendering Functions

### `emit(console, level, message)`

Quick message output at a semantic level.

```python
emit(console, Level.DEBUG, "Checking cache...")      # · dim
emit(console, Level.INFO, "Loading model...")        # ✧ gold
emit(console, Level.SUCCESS, "Task complete")        # ✓ green
emit(console, Level.WARNING, "Deprecated API")       # △ indigo
emit(console, Level.ERROR, "File not found")         # ✗ purple
emit(console, Level.CRITICAL, "Out of memory")       # ⊗ red (+ bell)
```

**When to use**: Quick status messages, logging-style output

---

### `render_phase_header(console, phase)`

Box-drawn phase transition header.

```
┌─────────────────────────────────────────────────────┐
│  ✦ Understanding                                    │
└─────────────────────────────────────────────────────┘
```

**Phases**: `understanding`, `illuminating`, `crafting`, `verifying`, `complete`

**When to use**: Major workflow transitions (signal → plan → execute → validate)

---

### `render_confidence(console, score, label="")`

Visual confidence bar with level indicator.

```
  Route → planning: █████████░ 90% ● High
```

**Levels**: High (90%+), Moderate (70-89%), Low (50-69%), Uncertain (<50%)

**When to use**: Routing decisions, model confidence, classification results

---

### `render_validation(console, name, passed, details="")`

Tree-structured validation result.

```
    ├─ Syntax       ✧
    ├─ Types        ✓
    ├─ Tests        ✗ 3 failures
```

**When to use**: Gate checks, linting results, test outcomes

---

### `render_gate_header(console, gate_id)`

Double-line bordered gate section.

```
  ══════════════════════════════════════════════════════
  GATE: type_check
  ══════════════════════════════════════════════════════
```

**When to use**: Validation gate boundaries

---

### `render_file_operation(console, op, path, details="")`

File change indicator.

```
  + src/new_file.py
  ~ src/existing.py (+15/-3)
  - src/old_file.py
  → src/moved.py
  ◦ src/read_file.py
  ⎘ src/copied.py
```

**Operations**: `create`, `modify`, `delete`, `move`, `read`, `copy`

**When to use**: File system changes, git-style diffs

---

### `render_learning(console, fact, source="")`

Learning extraction display.

```
  ≡ Learned: API requires auth token (from api/client.py)
```

**When to use**: Agent learnings, knowledge extraction

---

### `render_decision(console, decision, rationale="")`

Decision with rationale.

```
  ▣ Decision: Use async implementation
       ↳ Better performance for I/O-bound tasks
```

**When to use**: Agent choices, plan selection, strategy decisions

---

### `render_thinking(console, thought, depth=0)`

Agent reasoning indicator.

```
  ◜ Analyzing dependencies...
    ◜ Checking for circular imports...
```

**When to use**: Model thinking, reasoning steps

---

### `render_metrics(console, metrics)`

Execution statistics tree.

```
  Metrics
    ├─ Duration:    2.3s
    ├─ Tokens:      4,521
    ├─ Cost:        $0.0045
    └─ Efficiency:  1,965 tok/s
```

**Keys**: `duration_s`, `total_tokens`, `cost`, `tokens_per_second`

**When to use**: Post-execution summaries, cost tracking

---

### `render_code(console, code, language="python", context="")`

Syntax-highlighted code block.

**When to use**: Generated code, code examples

---

### `render_table(console, data, columns, title="")`

Holy Light styled data table.

**When to use**: Structured data display, comparisons

---

### `render_complete(console, tasks_completed, gates_passed, duration_s, ...)`

Full completion summary with files and learnings.

```
┌─────────────────────────────────────────────────────┐
│  ★ Complete                                         │
└─────────────────────────────────────────────────────┘

  ✦ 3 tasks completed in 2.3s

  Files created:
    + src/new_feature.py
    + tests/test_feature.py

  Files modified:
    ~ src/__init__.py

  ≡ Extracted 2 learnings

  ✦✧✦ Goal achieved
```

**When to use**: Goal completion, workflow end

---

### `render_error(console, message, details=None, suggestion=None)`

Error display with suggestion.

```
  ✗ Failed to load config
    File not found: config.toml
    ※ Suggestion: Run `sunwell init` to create config
```

**When to use**: Errors, failures, exceptions

---

## Extended Components (RFC-131 Extended)

### `render_streaming(console, text, complete=False)`

Streaming text with trailing mote indicator.

```
  ✧ The model is thinking... ·
```

When `complete=True`, shows ★ instead of trailing mote.

**When to use**: Model output streaming, progressive text display

---

### `render_step_progress(console, current, total, labels=None, description="")`

Multi-step progress indicator with visual chain.

```
  ◆───◈───◇───◇  Step 2/4: Planning
```

**When to use**: Multi-task workflows, installation steps, wizard flows

---

### `render_alert(console, message, severity="info", title=None)`

Bordered alert box with severity-based styling.

```
╭─ △ Warning ──────────────────────────────────────────╮
│  This operation will modify 15 files                 │
│  Run with --dry-run first to preview changes         │
╰──────────────────────────────────────────────────────╯
```

**Severities**: `info` (gold), `warning` (indigo), `error` (purple), `critical` (deep red)

**When to use**: Important confirmations, warnings, error dialogs

---

### `render_quote(console, text, attribution=None)`

Quoted text with vertical bar.

```
  ┃ "Fix the authentication bug in login.py"
  ┃                              — User
```

**When to use**: Echoing user input, citations, quoted content

---

### `render_separator(console, style="mote", width=40)`

Themed horizontal separator.

```
  ─────────── ✦ ───────────     (mote style)
  ═══════════════════════════   (double style)
  · · · · · · · · · · · · · ·   (dots style)
  ───────────────────────────   (light style)
```

**When to use**: Visual breaks between sections, response endings

---

### `render_timeline(console, events)`

Event timeline with connected nodes.

```
  ◆ 12:04:15  Signal extracted
  │
  ◆ 12:04:18  Plan created (3 tasks)
  │
  ◇ 12:04:20  Executing task 1...
```

Events are tuples of `(timestamp, description, is_complete)`.

**When to use**: Session history, event logs, progress tracking

---

### `render_breadcrumb(console, steps, current_index)`

Workflow breadcrumb with current indicator.

```
  Understanding › Illuminating › Crafting
                                    ↑
```

**When to use**: Workflow navigation, phase indicators

---

### `render_budget_bar(console, used, total, label="Budget")`

Token budget bar with percentage.

```
  Budget: ████████░░ 80% (16,000 / 20,000 tokens)
```

Color changes based on usage: gold (<70%), indigo (70-90%), purple (>90%).

**When to use**: Token tracking, budget warnings, usage displays

---

### `render_countdown(console, seconds_remaining)`

Countdown timer display.

```
  ◔ Timeout in 28s...
```

**When to use**: Timeout displays, countdown timers

---

### `render_diff(console, old_lines, new_lines, context_lines=2)`

Diff with +/- line styling.

```
  - def old_function():
  + def new_function(param):
      return param
```

**When to use**: File changes, code modifications, version comparisons

---

### `render_collapsible(console, title, content, expanded=False, item_count=None)`

Collapsible section (static representation).

```
  ▶ Full error trace (3 frames)
```

Or expanded:

```
  ▼ Full error trace (3 frames)
    │ Line 45: TypeError: 'NoneType' has no attribute 'foo'
    │ Line 23: Called from process_data()
    │ Line 12: Called from main()
```

**When to use**: Error traces, verbose output, optional details

---

### `async render_toast(console, message, icon=None, duration=2.0)`

Transient toast notification (async, fades after duration).

```
  ╭─────────────────────────────╮
  │  ★ Session saved            │
  ╰─────────────────────────────╯
```

Respects `reduced_motion` preference.

**When to use**: Quick acknowledgments, non-blocking notifications

---

### `print_banner(console, version="0.3.0", small=False)`

Branded startup banner.

```
   ✦ ✧ ✦
  ✧     ✧
 ✦   ☀   ✦   Sunwell
  ✧     ✧    AI agent for software tasks
   ✦ ✧ ✦

  v0.3.0
```

**When to use**: Application startup, about screens

---

## Animations

### `Sparkle`

Quick celebration burst.

```python
# Async burst animation
await Sparkle.burst("Goal achieved", duration=0.5)

# Static prefix
text = Sparkle.static("Success")  # "✦ Success"
```

**When to use**: Completions, celebrations, achievements

---

### `RisingMotes`

Particle animation of rising stars.

```python
motes = RisingMotes()
await motes.animate("Processing...", duration=3.0)
```

**When to use**: Major completions, dramatic moments, startup

---

### `MoteSpinner` / `SpiralSpinner`

Branded spinners for async operations.

```python
# With Rich Progress
spinner = MoteSpinner(SpinnerStyle.SPIRAL)

# Manual iteration
spiral = SpiralSpinner(deep=True)
for frame in spiral:
    print(f"\r{frame} Thinking...", end="")
```

**Styles**: `MOTE`, `SPIRAL`, `RADIANT`, `RISING`, `DIAMOND`, `SPIRAL_DEEP`

**When to use**: Model calls, long operations, loading states

---

### `create_sunwell_progress(console)`

Holy Light branded progress bar.

```python
progress = create_sunwell_progress(console)
with progress:
    task = progress.add_task("Processing...", total=100)
    for i in range(100):
        progress.update(task, advance=1)
```

**When to use**: Multi-step operations with known progress

---

## State Mapping

| State | Icon | Style | Animation | Use |
|-------|------|-------|-----------|-----|
| Thinking | ✦ | `holy.radiant` | mote | Model reasoning |
| Executing | ✧ | `holy.gold` | progress | Task running |
| Waiting | ◇ | `holy.gold.dim` | pulse | User input needed |
| Paused | ◈ | `neutral.muted` | - | Suspended |
| Complete | ★ | `holy.success` | sparkle | Success |
| Failed | ✗ | `void.purple` | - | Error |

---

## Accessibility

### Environment Variables

| Variable | Effect |
|----------|--------|
| `SUNWELL_REDUCED_MOTION` | Disable all animations |
| `SUNWELL_PLAIN` | Plain text mode |
| `NO_COLOR` | Standard no-color mode |

### Checking Preferences

```python
if should_reduce_motion():
    # Skip animation, use static indicator
    console.print(Sparkle.static("Complete"))
else:
    await Sparkle.burst("Complete")

if is_plain_mode():
    # Use simple text output
    print("Complete")
```

---

## Migration Helpers

### `migrate_icons(text)`

Replace emojis with Holy Light Unicode.

```python
text = migrate_icons("✅ Success! 🔥 Hot!")
# Result: "★ Success! ✦ Hot!"
```

### `migrate_styles(text)`

Replace hardcoded colors with theme styles.

```python
text = migrate_styles("[red]Error[/red]")
# Result: "[void.purple]Error[/void.purple]"
```

### `holy_print(console, text, **kwargs)`

Auto-migrate both icons and styles.

```python
holy_print(console, "[red]✅ Done![/red]")
# Outputs with void.purple style and ★ icon
```

---

## Usage by Scenario

| Scenario | Primary Function | Supporting |
|----------|------------------|------------|
| **Chat startup** | `print_banner()` | - |
| **User prompt** | Manual with `CHARS_STARS['radiant']` | `render_quote()` |
| **Model thinking** | `render_thinking()` | `render_streaming()` |
| **Model response** | Markdown rendering | `render_separator()` |
| **Signal extraction** | `render_phase_header("understanding")` | `emit(Level.INFO)` |
| **Planning** | `render_phase_header("illuminating")` | `render_confidence()` |
| **Routing decision** | `render_confidence()` | `render_decision()` |
| **Multi-task workflow** | `render_step_progress()` | `render_breadcrumb()` |
| **Task execution** | `render_phase_header("crafting")` | `CHARS_DIAMONDS['hollow']` |
| **Task complete** | `render_validation(passed=True)` | - |
| **Validation gate** | `render_gate_header()` | `render_validation()` |
| **Gate pass** | `render_validation(passed=True)` | - |
| **Gate fail** | `render_validation(passed=False)` | `render_collapsible()` |
| **File change** | `render_file_operation()` | `render_diff()` |
| **Learning** | `render_learning()` | - |
| **Token tracking** | `render_metrics()` | `render_budget_bar()` |
| **Goal complete** | `render_complete()` | `Sparkle.burst()`, `render_toast()` |
| **Error** | `render_error()` | `render_alert()` |
| **Confirmation** | `render_alert(severity="info")` | - |
| **Warning** | `render_alert(severity="warning")` | - |
| **Checkpoint** | `CHARS_MISC['save']` | `render_toast()` |
| **User input needed** | `CHARS_DIAMONDS['hollow']` | - |
| **Timeout display** | `render_countdown()` | - |
| **Session history** | `render_timeline()` | - |

---

## Design Philosophy

1. **Holy = Positive**: Golden spectrum for success, progress, activity
2. **Void = Negative**: Purple/indigo spectrum for errors, warnings
3. **Stars for Status**: ✦ active, ✧ progress, ★ complete, · pending
4. **Diamonds for State**: ◆ ready, ◇ waiting, ◈ paused
5. **Phase Headers**: Clear visual boundaries between workflow stages
6. **Trees for Structure**: Validation results, metrics use tree notation
7. **Animations for Delight**: Sparkles and motes celebrate achievements
8. **Accessibility First**: All animations respect reduced motion preferences
