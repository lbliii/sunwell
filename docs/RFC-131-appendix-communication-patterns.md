# RFC-131 Appendix: Complete Communication Patterns

**Parent RFC**: RFC-131 Holy Light CLI  
**Purpose**: Exhaustive mapping of every state, action, and information type Sunwell communicates  
**Status**: Draft — Pending alignment with `src/sunwell/agent/events.py`

---

## Design Principles

### Character Map Only (Terminal Layer)

All CLI visual indicators use **Unicode character map shapes** — no emojis. This ensures:
- Consistent rendering across all terminals (emojis render inconsistently)
- Cleaner aesthetic aligned with the "Holy Light" design
- Better accessibility and screen reader support
- Monospace alignment

> **Implementation Note**: The `EventUIHints` in `events.py` currently uses emojis for Studio/frontend rendering. This appendix defines the **CLI-specific** rendering that `RichRenderer` should use. The two layers (CLI vs Studio) may diverge intentionally.

### Migration from Existing UI Hints

The existing `_DEFAULT_UI_HINTS` in `events.py` uses emojis (⚡, 🧠, 💭, etc.). This appendix proposes replacing them with character-map equivalents for CLI:

| Existing (events.py) | Proposed (CLI) | Rationale |
|---------------------|----------------|-----------|
| `⚡` (task_start) | `✧` | Cleaner, aligns with mote aesthetic |
| `🧠` (model_start) | `◎` | Concentric circle = generation |
| `💭` (model_thinking) | `◜` | Spiral/Uzumaki for deep thought |
| `🔧` (fix_start) | `⚙` | Gear = mechanical fix process |
| `✨` (complete) | `★` | Radiant star = holy light triumph |

### Core Character Set

```
Stars:    ✦ ✧ ⋆ · ★
Diamonds: ◆ ◇ ◈
Circles:  ● ◉ ○ ◌ ◎ ⊙ ◐ ◔
Spirals:  ◜ ◝ ◞ ◟  (quarter arcs — for "thinking" rotation)
Squares:  ■ □ ▢ ▣ ▤ ▥
Arrows:   → ← ↑ ↓ ↻ ⟳
Checks:   ✓ ✗
Lines:    ═ ─ │ ├ └ ┌ ┐ ┘
Math:     ± ≡ ※ ⊕ ⊗ ⊘ ¤
Shapes:   △ ▲ ▽ ▼
```

### Spiral/Uzumaki Animation (Thinking States)

The "thinking" state uses quarter-arc characters rotating to create a spiral/vortex feel:

```
Frame 1:  ◜     (top-left arc)
Frame 2:  ◝     (top-right arc)
Frame 3:  ◞     (bottom-right arc)
Frame 4:  ◟     (bottom-left arc)
```

Animation sequence: `◜ → ◝ → ◞ → ◟ → ◜ ...`

For deeper/longer thinking, combine with concentric growth:

```
Phase 1 (shallow):    ◜ ◝ ◞ ◟
Phase 2 (deeper):     ◜◌ ◝◌ ◞◌ ◟◌
Phase 3 (deepest):    ◜◎ ◝◎ ◞◎ ◟◎
```

Visual effect:
```
  ◜ Thinking...         (spiral drawing)
  ◝ Thinking...         (rotation continues)
  ◞ Thinking...         (hypnotic)
  ◟ Thinking...         (Uzumaki)
```

---

## Holy ↔ Void Color Spectrum

The color palette is constrained to a **Holy vs Void magic** spectrum — no generic corporate colors.

### Holy Spectrum (Light, Positive, Active)

| Token | Hex | Use Case |
|-------|-----|----------|
| `radiant` | `#ffd700` | Active thinking, primary accent, success glow |
| `gold` | `#c9a227` | Standard UI, progress, secondary accent |
| `gold.light` | `#ffe566` | Highlights, sparkle effects |
| `gold.dim` | `#8a7235` | Muted, disabled, background accent |
| `warm` | `#fff4d4` | Warm backgrounds, subtle glow |
| `success` | `#22c55e` | Completion, pass, good (green-gold tint) |

### Void Spectrum (Shadow, Danger, Unknown)

| Token | Hex | Use Case |
|-------|-----|----------|
| `void` | `#1e1b4b` | Deep shadow, unknown states |
| `void.purple` | `#7c3aed` | Errors, violations, danger |
| `void.indigo` | `#4f46e5` | Warnings, caution, approval needed |
| `void.deep` | `#2e1065` | Critical errors, fatal states |
| `shadow` | `#3730a3` | Muted void, disabled danger |

### Neutral Spectrum (The Canvas)

| Token | Hex | Use Case |
|-------|-----|----------|
| `obsidian` | `#0d0d0d` | Primary background (the void itself) |
| `surface` | `#1a1a1a` | Cards, panels |
| `elevated` | `#262626` | Hover, emphasis |
| `text` | `#e5e5e5` | Primary text |
| `muted` | `#a8a8a8` | Secondary text |
| `neutral.dim` | `#525252` | Tertiary, hints |

### Semantic Mapping

| Semantic | Holy/Void | Color | Rationale |
|----------|-----------|-------|-----------|
| Success | Holy | `radiant` / `success` | Light triumphs |
| Progress | Holy | `gold` | Illuminating the path |
| Info | Holy | `gold.dim` | Neutral light |
| Warning | Void | `void.indigo` | Shadow creeping in |
| Error | Void | `void.purple` | Void corruption |
| Critical | Void | `void.deep` | Full void |
| Unknown | Void | `void` | Unilluminated |
| Muted | Neutral | `neutral.dim` | Neither light nor dark |

### CLI Color Constants

```python
HOLY_LIGHT = {
    "radiant": "#ffd700",      # Active, thinking, primary
    "gold": "#c9a227",         # Progress, standard accent
    "gold_light": "#ffe566",   # Sparkle, highlight
    "gold_dim": "#8a7235",     # Muted, disabled
    "warm": "#fff4d4",         # Warm background
    "success": "#22c55e",      # Complete, pass
}

VOID_SHADOW = {
    "void": "#1e1b4b",         # Deep unknown
    "purple": "#7c3aed",       # Error, violation
    "indigo": "#4f46e5",       # Warning, caution
    "deep": "#2e1065",         # Critical, fatal
    "shadow": "#3730a3",       # Muted danger
}

NEUTRAL = {
    "obsidian": "#0d0d0d",     # Background
    "surface": "#1a1a1a",      # Cards
    "elevated": "#262626",     # Hover
    "text": "#e5e5e5",         # Primary text
    "muted": "#a8a8a8",        # Secondary text
    "dim": "#525252",          # Tertiary
}
```

---

## 1. Agent Lifecycle Events

> **Proposed Addition**: These events are not yet in `events.py`. This RFC proposes adding them to `EventType` for richer session/goal lifecycle visibility.

### 1.1 Session States

| State | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `SESSION_START` | `✦` | `holy.radiant` | `fade-in` | "Awakening" | `✦ Sunwell awakening...` |
| `SESSION_READY` | `✧` | `holy.gold` | none | "Ready" | `✧ Ready for your goal` |
| `SESSION_END` | `★` | `holy.success` | `sparkle` | "Resting" | `★ Session complete` |
| `SESSION_CRASH` | `⊗` | `void.purple` | `shake` | "Interrupted" | `⊗ Session interrupted` |

### 1.2 Goal States

| State | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `GOAL_RECEIVED` | `✦` | `holy.radiant` | `pulse` | "Understanding" | `✦ Understanding your goal...` |
| `GOAL_ANALYZING` | `✧` | `holy.gold` | `mote` | "Illuminating" | `✧ Illuminating the path...` |
| `GOAL_READY` | `◆` | `holy.gold` | none | "Path clear" | `◆ Path illuminated` |
| `GOAL_COMPLETE` | `★` | `holy.success` | `sparkle` | "Achieved" | `★ Goal achieved` |
| `GOAL_FAILED` | `✗` | `void.purple` | `shake` | "Could not complete" | `✗ Goal could not be achieved` |
| `GOAL_PAUSED` | `◈` | `neutral.muted` | none | "Paused" | `◈ Paused at checkpoint` |

**Implementation**: Add to `src/sunwell/agent/events.py`:

```python
# Session lifecycle (proposed)
SESSION_START = "session_start"
SESSION_READY = "session_ready"
SESSION_END = "session_end"
SESSION_CRASH = "session_crash"

# Goal lifecycle (proposed)
GOAL_RECEIVED = "goal_received"
GOAL_ANALYZING = "goal_analyzing"
GOAL_READY = "goal_ready"
GOAL_COMPLETE = "goal_complete"  # Already exists as COMPLETE
GOAL_FAILED = "goal_failed"      # Already exists as ERROR
GOAL_PAUSED = "goal_paused"
```

---

## 2. Planning Events

### 2.1 Plan Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `PLAN_START` | `✦` | `holy.radiant` | `pulse` | "Illuminating" | `✦ Illuminating the path...` |
| `PLAN_CANDIDATE_START` | `◇` | `holy.gold.dim` | `pulse` | "Exploring" | `◇ Exploring {n} perspectives...` |
| `PLAN_CANDIDATE_GENERATED` | `✧` | `holy.gold` | `fade-in` | "Perspective" | `  ✧ Perspective {i}/{n}` |
| `PLAN_CANDIDATES_COMPLETE` | `◆` | `holy.gold` | none | "Perspectives gathered" | `◆ {n} perspectives gathered` |
| `PLAN_CANDIDATE_SCORED` | `·` | `neutral.dim` | none | "Scoring" | `  · Scoring perspective {i}...` |
| `PLAN_SCORING_COMPLETE` | `✧` | `holy.gold` | none | "Scores ready" | `✧ All perspectives scored` |
| `PLAN_WINNER` | `★` | `holy.success` | `sparkle` | "Plan ready" | `★ Plan ready ({technique})` |
| `PLAN_EXPANDED` | `✧` | `holy.gold` | `fade-in` | "Expanding" | `✧ Expanding plan (+{n} tasks)` |
| `PLAN_ASSESS` | `◇` | `holy.gold.dim` | none | "Assessing" | `◇ Assessing completion...` |

### 2.2 Plan Refinement

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `PLAN_REFINE_START` | `◇` | `holy.gold.dim` | `pulse` | "Refining" | `◇ Refining plan (round {i}/{n})` |
| `PLAN_REFINE_ATTEMPT` | `·` | `neutral.dim` | none | "Attempting" | `  · Attempting improvement...` |
| `PLAN_REFINE_COMPLETE` | `✧` | `holy.gold` | none | "Improved" | `✧ Round {i} complete` |
| `PLAN_REFINE_FINAL` | `◆` | `holy.gold` | `fade-in` | "Refined" | `◆ Plan refined ({n} rounds)` |

---

## 3. Execution Events

### 3.1 Task States

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `TASK_START` | `✧` | `holy.gold` | `pulse` | "Crafting" | `✧ [{i}/{n}] Crafting {name}...` |
| `TASK_PROGRESS` | `·` | `neutral.dim` | none | "Progress" | `  · {progress}%` |
| `TASK_COMPLETE` | `✓` | `holy.success` | `fade-in` | "Complete" | `✓ [{i}/{n}] {name}` |
| `TASK_OUTPUT` | `◦` | `neutral.muted` | none | "Output" | (shows output content) |
| `TASK_FAILED` | `✗` | `void.purple` | `shake` | "Failed" | `✗ [{i}/{n}] {name} failed` |

### 3.2 Task Progress Detail

```
  ✧ [2/7] Creating auth/oauth.py...
    ├─ ◎ gemma3:4b generating... 234 tok (12.3 tok/s)
    └─ Progress: ████████░░░░░░░░░░░░ 42%
```

---

## 4. Validation Events

### 4.1 Gate Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `GATE_START` | `═` | `holy.gold` | none | "Verifying" | `══ GATE: {name} ══` |
| `GATE_STEP` | `├` | varies | none | step name | `├─ {step} {icon}` |
| `GATE_PASS` | `✧` | `holy.success` | `fade-in` | "Passed" | `✧ Gate passed` |
| `GATE_FAIL` | `✗` | `void.purple` | none | "Failed" | `✗ Gate failed ({n} errors)` |

### 4.2 Gate Steps

| Step | Pass Icon | Fail Icon | Example |
|------|-----------|-----------|---------|
| `syntax` | `✧` | `✗` | `├─ syntax      ✧` |
| `lint` | `✧` | `✗` | `├─ lint        ✗ 3 issues` |
| `type` | `✧` | `✗` | `├─ type        ✧` |
| `test` | `✧` | `✗` | `├─ test        ✧ 24 passed` |
| `runtime` | `✧` | `✗` | `├─ runtime     ✧` |

### 4.3 Validation Cascade

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `VALIDATE_START` | `◇` | `holy.gold.dim` | `pulse` | "Validating" | `◇ Validating {level}...` |
| `VALIDATE_LEVEL` | `·` | `neutral.dim` | none | level name | `  · Checking {level}...` |
| `VALIDATE_ERROR` | `✗` | `void.purple` | none | "Error" | `✗ {file}:{line} — {message}` |
| `VALIDATE_PASS` | `✧` | `holy.success` | none | "Passed" | `✧ {level} passed` |

---

## 5. Fix Events

### 5.1 Auto-Fix Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `FIX_START` | `⚙` | `void.indigo` | `pulse` | "Fixing" | `⚙ Auto-fixing...` |
| `FIX_PROGRESS` | `·` | `neutral.dim` | none | "Scanning" | `  · Scanning for fix...` |
| `FIX_ATTEMPT` | `◇` | `holy.gold.dim` | none | "Attempting" | `  ◇ Attempting fix #{n}...` |
| `FIX_COMPLETE` | `✓` | `holy.success` | `fade-in` | "Fixed" | `✓ Fix applied` |
| `FIX_FAILED` | `✗` | `void.purple` | none | "Could not fix" | `✗ Could not auto-fix` |

---

## 6. Convergence Events

### 6.1 Convergence Loop

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `CONVERGENCE_START` | `↻` | `holy.gold` | `pulse` | "Converging" | `↻ Starting convergence...` |
| `CONVERGENCE_ITERATION_START` | `◇` | `holy.gold.dim` | none | "Iteration" | `◇ Iteration {i}/{max}` |
| `CONVERGENCE_ITERATION_COMPLETE` | `✧` | `holy.gold` | none | "Checked" | `✧ Iteration complete` |
| `CONVERGENCE_FIXING` | `⚙` | `void.indigo` | `pulse` | "Fixing" | `⚙ Fixing {n} errors...` |
| `CONVERGENCE_STABLE` | `★` | `holy.success` | `sparkle` | "Stable" | `★ Code is stable` |
| `CONVERGENCE_TIMEOUT` | `◔` | `void.purple` | none | "Timeout" | `◔ Convergence timeout` |
| `CONVERGENCE_STUCK` | `⟳` | `void.purple` | `shake` | "Stuck" | `⟳ Same error recurring — escalating` |
| `CONVERGENCE_MAX_ITERATIONS` | `△` | `void.indigo` | none | "Max reached" | `△ Max iterations reached` |
| `CONVERGENCE_BUDGET_EXCEEDED` | `¤` | `void.purple` | none | "Budget exceeded" | `¤ Token budget exhausted` |

---

## 7. Memory Events

### 7.1 Memory Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `MEMORY_LOAD` | `◎` | `holy.gold.dim` | `pulse` | "Remembering" | `◎ Remembering...` |
| `MEMORY_LOADED` | `✧` | `holy.gold` | `fade-in` | "Remembered" | `✧ Loaded {n} learnings` |
| `MEMORY_NEW` | `✦` | `holy.radiant` | `fade-in` | "Fresh start" | `✦ New session (no history)` |
| `MEMORY_CHECKPOINT` | `▤` | `holy.gold` | none | "Checkpointed" | `▤ Memory checkpointed` |
| `MEMORY_SAVED` | `✓` | `holy.success` | none | "Saved" | `✓ Memory saved` |

### 7.2 Memory Content

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `MEMORY_LEARNING` | `≡` | `holy.gold.dim` | `fade-in` | "Learned" | `≡ Learned: {fact}` |
| `MEMORY_DEAD_END` | `⊘` | `void.indigo` | none | "Dead end" | `⊘ Recorded: {approach} doesn't work` |
| `ORIENT` | `◐` | `holy.gold` | `fade-in` | "Oriented" | `◐ Found {n} constraints` |
| `LEARNING_ADDED` | `※` | `holy.success` | `fade-in` | "Insight" | `※ Insight: {learning}` |
| `DECISION_MADE` | `▣` | `holy.gold` | none | "Decision" | `▣ Decision: {choice}` |
| `FAILURE_RECORDED` | `✗` | `void.indigo` | none | "Failure recorded" | `✗ Recorded: {approach} failed` |
| `BRIEFING_UPDATED` | `▢` | `holy.success` | none | "Briefing saved" | `▢ Briefing saved for next session` |

### 7.3 Memory Display

```
  ◎ Memory
    ├─ {n} learnings
    ├─ {n} decisions  
    ├─ {n} dead ends
    └─ Last session: {date}
    
  ◐ Constraints from memory:
    ├─ △ OAuth refresh fails with provider X
    ├─ ▣ Team prefers explicit error handling
    └─ ※ Similar goal succeeded with approach Y
```

---

## 8. Model/Inference Events

### 8.1 Model Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `MODEL_START` | `◎` | `holy.gold.dim` | `pulse` | model name | `◎ {model} generating...` |
| `MODEL_TOKENS` | `◎` | `holy.gold.dim` | none | token count | `◎ {n} tokens ({tps} tok/s)` |
| `MODEL_THINKING` | `◜` | `neutral.dim` | `spiral` | "Thinking" | `◜ {phase}: {preview}...` |
| `MODEL_HEARTBEAT` | `·` | `neutral.dim` | none | none | (keeps progress alive) |
| `MODEL_COMPLETE` | `✓` | `holy.success` | none | "Generated" | `✓ {n} tokens in {time}s` |

### 8.2 Model Display

```
  ◎ gemma3:4b generating...
    ├─ Tokens: 234 (12.3 tok/s)
    ├─ TTFT: 89ms
    └─ ○ Analyzing authentication flow...
    
  ✓ Generated 1,234 tokens in 45.2s (27.3 tok/s)
```

---

## 9. Skill Events

### 9.1 Skill Compilation

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `SKILL_COMPILE_START` | `⚙` | `holy.gold` | `pulse` | "Compiling" | `⚙ Compiling skill graph...` |
| `SKILL_COMPILE_COMPLETE` | `✓` | `holy.success` | `fade-in` | "Compiled" | `✓ {n} tasks in {w} waves` |
| `SKILL_COMPILE_CACHE_HIT` | `⋆` | `holy.success` | none | "Cache hit" | `⋆ Skill graph from cache` |
| `SKILL_SUBGRAPH_EXTRACTED` | `◆` | `holy.gold` | none | "Extracted" | `◆ Subgraph: {n} skills` |

### 9.2 Skill Execution

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `SKILL_GRAPH_RESOLVED` | `◆` | `holy.gold` | `fade-in` | "Resolved" | `◆ {n} skills in {w} waves` |
| `SKILL_WAVE_START` | `◇` | `holy.gold.dim` | none | "Wave" | `◇ Wave {i}/{n}` |
| `SKILL_WAVE_COMPLETE` | `✧` | `holy.gold` | none | "Wave done" | `✧ Wave complete ({s} passed)` |
| `SKILL_CACHE_HIT` | `⋆` | `holy.success` | none | "Cached" | `⋆ {skill} (cached)` |
| `SKILL_EXECUTE_START` | `✧` | `holy.gold` | `pulse` | skill name | `✧ Executing {skill}...` |
| `SKILL_EXECUTE_COMPLETE` | `✓` | `holy.success` | none | "Done" | `✓ {skill}` |

---

## 10. Security Events

### 10.1 Security Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `SECURITY_APPROVAL_REQUESTED` | `⊗` | `void.indigo` | `pulse` | "Approval needed" | `⊗ This action requires approval` |
| `SECURITY_APPROVAL_RECEIVED` | `✓` | `holy.success` | `fade-in` | "Approved" | `✓ Approved` |
| `SECURITY_VIOLATION` | `⊘` | `void.purple` | `shake` | "Violation" | `⊘ Security violation: {reason}` |
| `SECURITY_SCAN_COMPLETE` | `✓` | `holy.success` | none | "Scanned" | `✓ Security scan passed` |
| `AUDIT_LOG_ENTRY` | `·` | `neutral.dim` | none | none | (silent logging) |

### 10.2 Approval Display

```
  ⊗ This action requires approval
    
    ┌─────────────────────────────────────────────────────┐
    │  Action: Delete 3 files                             │
    │  Risk: MEDIUM                                       │
    │                                                     │
    │  Files:                                             │
    │    - src/auth/legacy.py                             │
    │    - src/auth/old_handler.py                        │
    │    - tests/auth/test_legacy.py                      │
    └─────────────────────────────────────────────────────┘
    
  ? Approve this action? [y/N]
    › _
```

---

## 11. Recovery Events

### 11.1 Recovery Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `RECOVERY_SAVED` | `▤` | `void.indigo` | none | "Saved for review" | `▤ Progress saved — review needed` |
| `RECOVERY_LOADED` | `▼` | `holy.gold` | `fade-in` | "Resuming" | `▼ Resuming from checkpoint...` |
| `RECOVERY_RESOLVED` | `✓` | `holy.success` | `sparkle` | "Recovered" | `✓ Recovery complete` |
| `RECOVERY_ABORTED` | `✗` | `neutral.muted` | none | "Aborted" | `✗ Recovery aborted` |

---

## 12. Backlog Events

### 12.1 Backlog Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `BACKLOG_REFRESHED` | `↻` | `holy.gold` | none | "Refreshed" | `↻ Backlog refreshed ({n} goals)` |
| `BACKLOG_GOAL_ADDED` | `+` | `holy.success` | `fade-in` | "Discovered" | `+ Discovered: {goal}` |
| `BACKLOG_GOAL_STARTED` | `✧` | `holy.gold` | `pulse` | "Starting" | `✧ Starting: {goal}` |
| `BACKLOG_GOAL_COMPLETED` | `✓` | `holy.success` | `sparkle` | "Completed" | `✓ Completed: {goal}` |
| `BACKLOG_GOAL_FAILED` | `✗` | `void.purple` | none | "Failed" | `✗ Failed: {goal}` |

### 12.2 Backlog Display

```
  ▢ Backlog ({n} goals)
  
    HIGH   [BUG]  ✗ Fix race condition in cache.py:89
    HIGH   [TEST] · Add test coverage for auth
    MEDIUM [TODO] · Address TODO in routes.py:156
    LOW    [DEBT] · Refactor billing module
    
  Legend: ✓ complete  ✧ in progress  · pending  ✗ failed
```

---

## 13. Lens Events

### 13.1 Lens Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `LENS_SELECTED` | `◐` | `holy.gold` | `fade-in` | "Lens applied" | `◐ Using {lens} lens` |
| `LENS_CHANGED` | `↻` | `holy.gold` | none | "Lens changed" | `↻ Switched to {lens} lens` |
| `LENS_SUGGESTED` | `※` | `holy.gold.dim` | none | "Suggested" | `※ Suggested lens: {lens}` |

---

## 14. Integration Events

### 14.1 Integration Verification

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `INTEGRATION_CHECK_START` | `⊕` | `holy.gold` | `pulse` | "Checking" | `⊕ Checking integration...` |
| `INTEGRATION_CHECK_PASS` | `✧` | `holy.success` | none | "Connected" | `✧ {component} integrated` |
| `INTEGRATION_CHECK_FAIL` | `✗` | `void.purple` | none | "Disconnected" | `✗ {component} not integrated` |
| `STUB_DETECTED` | `△` | `void.indigo` | none | "Stub found" | `△ Stub: {file}:{line}` |
| `ORPHAN_DETECTED` | `⊘` | `void.indigo` | none | "Orphan found" | `⊘ Orphan: {component}` |
| `WIRE_TASK_GENERATED` | `+` | `holy.gold` | none | "Wire task" | `+ Wire task: Connect {a} → {b}` |

---

## 15. Prefetch/Briefing Events

### 15.1 Briefing Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `BRIEFING_LOADED` | `▢` | `holy.gold` | `fade-in` | "Briefing ready" | `▢ Briefing from last session` |
| `BRIEFING_SAVED` | `✓` | `holy.success` | none | "Briefing saved" | `✓ Briefing saved` |
| `PREFETCH_START` | `✦` | `holy.gold.dim` | `pulse` | "Prefetching" | `✦ Prefetching context...` |
| `PREFETCH_COMPLETE` | `✓` | `holy.success` | none | "Context warm" | `✓ Context warm ({n} files)` |
| `PREFETCH_TIMEOUT` | `◔` | `void.indigo` | none | "Timeout" | `◔ Prefetch timeout — proceeding` |

---

## 16. Agent Constellation Events (RFC-130)

Events for multi-agent coordination, checkpointing, and autonomous operation.

### 16.1 Specialist Lifecycle

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `SPECIALIST_SPAWNED` | `◈` | `holy.gold` | `pulse` | "Spawning" | `◈ Spawning {role} specialist...` |
| `SPECIALIST_COMPLETED` | `✧` | `holy.success` | `fade-in` | "Specialist done" | `✧ Specialist complete: {summary}` |
| `SPECIALIST_FAILED` | `✗` | `void.purple` | none | "Specialist failed" | `✗ Specialist failed: {error}` |

### 16.2 Checkpoint Events

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `CHECKPOINT_FOUND` | `▼` | `holy.gold` | `fade-in` | "Resuming" | `▼ Found checkpoint at {phase}` |
| `CHECKPOINT_SAVED` | `▤` | `holy.success` | none | "Checkpointed" | `▤ Checkpoint saved: {phase}` |
| `PHASE_COMPLETE` | `◆` | `holy.gold` | `fade-in` | "Phase done" | `◆ Phase complete: {phase}` |

### 16.3 Autonomous Operation

| Event | Icon | Color | Animation | Voice | Example |
|-------|------|-------|-----------|-------|---------|
| `AUTONOMOUS_ACTION_BLOCKED` | `⊗` | `void.purple` | `shake` | "Blocked" | `⊗ Action blocked: {reason}` |
| `GUARD_EVOLUTION_SUGGESTED` | `※` | `void.indigo` | none | "Guard suggestion" | `※ Suggest: {evolution_type}` |

### 16.4 Specialist Display

```
  ◈ Spawning code_reviewer specialist...
    ├─ Focus: Review OAuth implementation
    ├─ Budget: 5,000 tokens
    └─ Parent: main-agent
    
  ✧ Specialist complete
    ├─ Summary: Found 2 issues, suggested fixes
    ├─ Tokens: 3,421 / 5,000
    └─ Duration: 12.3s

  ▼ Found checkpoint at implementation_complete
    ├─ Goal: Add OAuth authentication
    ├─ Tasks: 5/7 complete
    └─ ? Resume from checkpoint? [Y/n]
```

---

## 17. File Operations

### 17.1 File CRUD

| Operation | Icon | Color | Voice | Example |
|-----------|------|-------|-------|---------|
| `CREATE` | `+` | `holy.success` | "Creating" | `+ src/auth/oauth.py` |
| `MODIFY` | `~` | `void.indigo` | "Modifying" | `~ src/auth/handler.py` |
| `DELETE` | `-` | `void.purple` | "Deleting" | `- src/auth/legacy.py` |
| `MOVE` | `→` | `holy.gold.dim` | "Moving" | `→ old.py → new.py` |
| `READ` | `◦` | `neutral.dim` | "Reading" | `◦ Reading config.py...` |
| `COPY` | `⎘` | `holy.gold.dim` | "Copying" | `⎘ template.py → new.py` |

### 17.2 File Operations Display

```
  Files changed:
    + src/auth/oauth.py (new, 145 lines)
    + src/auth/providers/google.py (new, 89 lines)
    ~ src/auth/handler.py (+23, -5 lines)
    - src/auth/legacy.py (deleted)
```

---

## 18. User Interactions

### 18.1 Input Types

| Type | Icon | Color | Example |
|------|------|-------|---------|
| `TEXT_PROMPT` | `?` | `holy.gold` | `? What should the endpoint be called?` |
| `CONFIRM` | `?` | `holy.gold` | `? Ready to implement? [Y/n]` |
| `CHOICE` | `?` | `holy.gold` | `? Which approach? (1/2/3)` |
| `MULTI_SELECT` | `?` | `holy.gold` | `? Select files: (space to select)` |
| `PASSWORD` | `?` | `holy.gold` | `? API key: ****` |

### 18.2 Input Marker

| State | Icon | Color | Example |
|-------|------|-------|---------|
| `AWAITING` | `›` | `holy.gold` | `› _` |
| `PROCESSING` | `◇` | `holy.gold.dim` | `◇ Processing...` |
| `ACCEPTED` | `✓` | `holy.success` | `✓ Accepted` |
| `REJECTED` | `✗` | `void.purple` | `✗ Invalid input` |

### 18.3 Approval States

| State | Icon | Color | Animation | Example |
|-------|------|-------|-----------|---------|
| `PENDING` | `◇` | `holy.gold.dim` | `pulse` | `◇ Awaiting approval...` |
| `APPROVED` | `✓` | `holy.success` | `fade-in` | `✓ Approved` |
| `DENIED` | `✗` | `void.purple` | none | `✗ Denied` |
| `TIMEOUT` | `◔` | `void.indigo` | none | `◔ Approval timeout` |

---

## 19. Confidence & Trust

### 19.1 Confidence Levels

| Level | Icon | Color | Bar | Example |
|-------|------|-------|-----|---------|
| `HIGH` (90-100%) | `●` | `holy.success` | `████████████` | `94% ● High` |
| `MODERATE` (70-89%) | `◉` | `void.indigo` | `████████░░░░` | `72% ◉ Moderate` |
| `LOW` (50-69%) | `○` | `void.shadow` | `██████░░░░░░` | `58% ○ Low` |
| `UNCERTAIN` (0-49%) | `◌` | `void.purple` | `███░░░░░░░░░` | `34% ◌ Uncertain` |

### 19.2 Trust Levels

| Level | Icon | Color | Example |
|-------|------|-------|---------|
| `READ_ONLY` | `◔` | `neutral.dim` | `Trust: read-only` |
| `WORKSPACE` | `▢` | `holy.gold` | `Trust: workspace` |
| `SHELL` | `✦` | `void.indigo` | `Trust: shell (dangerous)` |

---

## 20. Progress Indicators

### 20.1 Progress Types

| Type | Visual | Use Case |
|------|--------|----------|
| `SPINNER` | `✦ ✧ · ✧ ✦` | Indeterminate duration |
| `BAR` | `████████░░░░` | Known percentage |
| `COUNTER` | `[3/7]` | Discrete steps |
| `PHASE` | `Phase 2 of 4` | Major milestones |
| `TOKEN` | `234 tok (12.3/s)` | Model generation |

### 20.2 Progress Display

```
  ┌─────────────────────────────────────────────────────┐
  │  Phase 2/4: Crafting                                │
  ├─────────────────────────────────────────────────────┤
  │  ✧ [3/7] auth/handler.py    ████████░░░░ 67%       │
  │    └─ ◎ 234 tok (12.3 tok/s)                       │
  └─────────────────────────────────────────────────────┘
```

---

## 21. Errors & Warnings

### 21.1 Error Severity

| Severity | Icon | Color | Animation | Dismissible | Example |
|----------|------|-------|-----------|-------------|---------|
| `INFO` | `✧` | `holy.gold` | none | yes | `✧ Using default config` |
| `WARNING` | `△` | `void.indigo` | none | yes | `△ No tests found` |
| `ERROR` | `✗` | `void.purple` | none | no | `✗ Build failed` |
| `CRITICAL` | `⊗` | `void.deep` | `shake` | no | `⊗ Data loss possible` |

### 21.2 Error Display

```
  ✗ Validation failed
    
    ┌─ auth/oauth.py
    │ 45 │     def get_token(self) -> Token:
    │    │                          ~~~~~~
    │    │ Error: Incompatible return type
    │    │ Expected: Token | None
    │    │ Got: Token
    └─
    
    ※ Suggestion: Add `| None` to return type
```

---

## 22. Help & Documentation

### 22.1 Help Elements

| Type | Icon | Color | Example |
|------|------|-------|---------|
| `TIP` | `※` | `holy.gold` | `※ Tip: Use --plan to preview` |
| `HINT` | `·` | `neutral.dim` | `· Press Ctrl+C to cancel` |
| `EXAMPLE` | `≡` | `neutral.muted` | `≡ Example: sunwell "Add auth"` |
| `LINK` | `→` | `holy.gold.dim` | `→ See: docs.sunwell.dev/auth` |
| `WARNING` | `△` | `void.indigo` | `△ This will modify files` |

---

## 23. Session/Context Information

### 23.1 Session Info

| Info | Icon | Color | Example |
|------|------|-------|---------|
| `WORKSPACE` | `▢` | `holy.gold` | `▢ ~/projects/myapp` |
| `PROJECT_TYPE` | `·` | `neutral.dim` | `· Python (FastAPI)` |
| `SESSION_ID` | `·` | `neutral.dim` | `· Session: abc123` |
| `MODEL` | `◎` | `neutral.dim` | `◎ gemma3:4b` |
| `LENS` | `◐` | `neutral.dim` | `◐ Lens: tech-writer` |

### 23.2 Context Display

```
  ✦ Sunwell v0.3.0
  
    ▢ ~/projects/myapp
    · Python (FastAPI)
    · Session: abc123
    ◎ gemma3:4b
    ◐ Lens: coder
```

---

## 24. Completion Summary

### 24.1 Success Summary

```
  ★ Goal achieved
  
    Duration:    45.2s
    Tasks:       7 completed
    Files:       4 created, 1 modified
    Tokens:      12,345 (273 tok/s)
    Cost:        $0.0000 (local)
    
    Files created:
      + src/auth/oauth.py
      + src/auth/providers/google.py
      + src/auth/providers/github.py
      + tests/auth/test_oauth.py
    
    ≡ Learned: OAuth provider pattern for this codebase
    ▢ Briefing saved for next session
    
  ✦✧✦
```

### 24.2 Failure Summary

```
  ✗ Goal could not be achieved
  
    Duration:    23.4s
    Tasks:       3/7 completed
    Errors:      2
    
    Errors:
      ✗ auth/oauth.py:45 — Type mismatch
      ✗ auth/oauth.py:67 — Missing import
    
    ▤ Progress saved — run `sunwell review` to continue
    
  ✗✗✗
```

---

## 25. Animation Types

### 25.1 Available Animations

| Animation | Use Case | Duration | Interruptible |
|-----------|----------|----------|---------------|
| `pulse` | Active state | 2s loop | yes |
| `fade-in` | New element | 0.15s | no |
| `fade-out` | Removing | 0.15s | no |
| `shake` | Error | 0.3s | no |
| `sparkle` | Celebration | 0.5s | no |
| `shimmer` | Loading | 2s loop | yes |
| `mote` | Progress | continuous | yes |
| `spiral` | Thinking (Uzumaki) | continuous | yes |

### 25.2 Mote Animation (ASCII)

```
Frame 1:        Frame 2:        Frame 3:        Frame 4:
    ·    ✧          ✧    ·      ·     ✧            ✧    
 ✧     ·         ·    ✦            ✦     ·     ·        
   ✦     ·          ✧        ✧     ·        ✦     ✧
  ✧     ·       ·     ✧         ·    ✧      ✧     ·
```

### 25.3 Spiral Animation (Uzumaki)

Quarter-arc rotation creates a hypnotic vortex effect for deep thinking:

```
Frame 1:  ◜     Frame 2:  ◝     Frame 3:  ◞     Frame 4:  ◟
```

**Python implementation**:

```python
SPIRAL_FRAMES = ["◜", "◝", "◞", "◟"]

# Deep thinking variant (with depth indicator)
SPIRAL_DEEP_FRAMES = [
    "◜ ·",  # shallow
    "◝ ○", 
    "◞ ◎",  # deeper
    "◟ ◉",  # deepest
]
```

**Usage**:

```
  ◜ Reasoning about auth flow...
  ◝ Reasoning about auth flow...
  ◞ Reasoning about auth flow...
  ◟ Reasoning about auth flow...
```

The spiral (Uzumaki) conveys:
- **Depth** — drawing inward, concentrating
- **Process** — something is happening inside
- **Hypnotic focus** — the model is "in the zone"

**Implementation Required**:

1. Add `"spiral"` to `EventUIHints.animation` options in `events.py`
2. Implement `SpiralSpinner` in `renderer.py`:

```python
class SpiralSpinner:
    """Uzumaki-style spiral spinner for deep thinking."""
    
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
```

3. Wire to `MODEL_THINKING` events in `RichRenderer._render_simple()`

---

## 26. Sound/Bell Events

### 26.1 Sound Triggers (Optional)

| Event | Sound | Default | Configurable |
|-------|-------|---------|--------------|
| `GOAL_COMPLETE` | soft chime | off | yes |
| `CRITICAL_ERROR` | alert | on | yes |
| `APPROVAL_NEEDED` | notification | on | yes |
| `SESSION_END` | none | off | yes |

---

## 27. Accessibility Modes

### 27.1 Reduced Motion

When `SUNWELL_REDUCED_MOTION=1` or `prefers-reduced-motion`:

| Normal | Reduced |
|--------|---------|
| `✦ ✧ · ✧ ✦` spinner | `✦` static |
| Mote animation | Disabled |
| Sparkle burst | Single `✦` |
| Fade animations | Instant |

### 27.2 Plain Mode

When `SUNWELL_PLAIN=1` or `NO_COLOR`:

```
[INFO] Understanding goal...
[INFO] Plan ready (harmonic) — 7 tasks
[TASK] [1/7] Creating auth/oauth.py...
[DONE] [1/7] auth/oauth.py
[PASS] Gate: lint
[DONE] Goal complete — 45.2s
```

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────────────────────┐
│ SUNWELL COMMUNICATION PATTERNS — QUICK REFERENCE                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ STATES                          OPERATIONS                                 │
│   ◜  Thinking (spiral)            +  Create                                │
│   ✦  Active                       ~  Modify                                │
│   ✧  Progress                     -  Delete                                │
│   ★  Complete                     →  Move                                  │
│   ✗  Failed                       ◦  Read                                  │
│   ◇  Waiting                                                               │
│   ◈  Paused                                                                │
│                                                                            │
│ VALIDATION                      CONFIDENCE                                 │
│   ✧  Pass                         ●  High (90%+)                           │
│   ✗  Fail                         ◉  Moderate (70-89%)                     │
│   ·  Skip                         ○  Low (50-69%)                          │
│                                   ◌  Uncertain (<50%)                      │
│                                                                            │
│ MEMORY                          SECURITY                                   │
│   ◎  Recall                       ⊗  Approval needed                       │
│   ≡  Learning                     ⊘  Violation                             │
│   ▣  Decision                     ✓  Approved                              │
│   ※  Insight                                                               │
│   ✗  Failure                    INTERACTIONS                               │
│                                   ?  Prompt                                │
│ SEVERITY                          ›  Input                                 │
│   ·  Debug                        ✓  Accepted                              │
│   ✧  Info                         ✗  Rejected                              │
│   △  Warning                                                               │
│   ✗  Error                      PHASES                                     │
│   ⊗  Critical                     ✦ Understanding                          │
│                                   ✦ Illuminating                           │
│ MODEL                             ✦ Crafting                               │
│   ◎  Generating                   ✦ Verifying                              │
│   ○  Thinking                     ★ Complete                               │
│   ✓  Complete                                                              │
│                                                                            │
│ OTHER                                                                      │
│   ↻  Refresh/Loop               ▢  Workspace/Briefing                      │
│   ⚙  Fixing                     ▤  Save/Checkpoint                         │
│   ◐  Lens                       ⊕  Integration                             │
│   ◔  Timeout                    ¤  Budget                                  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Icon Reference

Complete mapping of all icons used:

```
STARS & SPARKLES
  ✦  Radiant/Active/Important    (U+2726)
  ✧  Progress/Secondary          (U+2727)  
  ★  Complete/Success            (U+2605)
  ⋆  Cache/Fast                  (U+22C6)
  ·  Dim/Pending/Debug           (U+00B7)

SPIRALS (Uzumaki — for thinking)
  ◜  Upper-left arc              (U+25DC)
  ◝  Upper-right arc             (U+25DD)
  ◞  Lower-right arc             (U+25DE)
  ◟  Lower-left arc              (U+25DF)

DIAMONDS
  ◆  Solid/Ready                 (U+25C6)
  ◇  Hollow/Waiting              (U+25C7)
  ◈  Inset/Paused                (U+25C8)

CIRCLES
  ●  Filled/High                 (U+25CF)
  ◉  Target/Moderate             (U+25C9)
  ○  Empty/Low                   (U+25CB)
  ◌  Dotted/Uncertain            (U+25CC)
  ◎  Double/Model                (U+25CE)
  ⊙  Circled dot                 (U+2299)
  ◐  Half/Lens                   (U+25D0)
  ◔  Quarter/Timeout             (U+25D4)

SQUARES
  ■  Filled                      (U+25A0)
  □  Empty                       (U+25A1)
  ▢  Rounded/Workspace           (U+25A2)
  ▣  Inset/Decision              (U+25A3)
  ▤  Horizontal/Save             (U+25A4)

CHECKS & CROSSES
  ✓  Check/Pass                  (U+2713)
  ✗  Cross/Fail                  (U+2717)

ARROWS
  →  Right/Move                  (U+2192)
  ←  Left                        (U+2190)
  ↑  Up                          (U+2191)
  ↓  Down                        (U+2193)
  ↻  Clockwise/Refresh           (U+21BB)
  ⟳  Circular/Loop               (U+27F3)
  ▼  Down triangle/Load          (U+25BC)
  ▲  Up triangle                 (U+25B2)

MATH & SYMBOLS
  ±  Plus-minus                  (U+00B1)
  ≡  Equivalent/Learning         (U+2261)
  ※  Reference/Insight           (U+203B)
  ⊕  Circle plus/Integration     (U+2295)
  ⊗  Circle cross/Approval       (U+2297)
  ⊘  Circle slash/Violation      (U+2298)
  ¤  Currency/Budget             (U+00A4)
  ⚙  Gear/Fix                    (U+2699)

TRIANGLES
  △  Warning/Stub                (U+25B3)
  ▲  Solid up                    (U+25B2)
  ▽  Down                        (U+25BD)
  ▼  Solid down                  (U+25BC)

BOX DRAWING
  ═  Double horizontal           (U+2550)
  ─  Single horizontal           (U+2500)
  │  Vertical                    (U+2502)
  ├  T-right                     (U+251C)
  └  Corner                      (U+2514)
  ┌  Top corner                  (U+250C)
  ┐  Top right                   (U+2510)
  ┘  Bottom right                (U+2518)

PROGRESS BAR
  █  Full block                  (U+2588)
  ░  Light shade                 (U+2591)

MISC
  ?  Question (ASCII)
  ›  Right angle quote/Input     (U+203A)
  +  Plus (ASCII)
  ~  Tilde (ASCII)
  -  Minus (ASCII)
  ◦  Bullet/Read                 (U+25E6)
  ⎘  Copy                        (U+2398)
```

---

## Implementation Requirements

### Summary of Required Changes

| File | Change | Priority |
|------|--------|----------|
| `events.py` | Add session/goal lifecycle events | HIGH |
| `events.py` | Update `_DEFAULT_UI_HINTS` to use character shapes | HIGH |
| `events.py` | Add `"spiral"` to `EventUIHints.animation` | MEDIUM |
| `renderer.py` | Implement `SpiralSpinner` class | MEDIUM |
| `renderer.py` | Add `SUNWELL_THEME` Rich theme | HIGH |
| `renderer.py` | Update spinners to use mote/radiant patterns | MEDIUM |

### New EventType Additions (Proposed)

```python
# Session lifecycle
SESSION_START = "session_start"
SESSION_READY = "session_ready"
SESSION_END = "session_end"
SESSION_CRASH = "session_crash"

# Goal lifecycle
GOAL_RECEIVED = "goal_received"
GOAL_ANALYZING = "goal_analyzing"
GOAL_READY = "goal_ready"
GOAL_PAUSED = "goal_paused"
```

### UI Hints Migration

Replace emoji-based hints with character shapes:

```python
_DEFAULT_UI_HINTS = {
    "task_start": EventUIHints(icon="✧", severity="info", animation="pulse"),
    "task_complete": EventUIHints(icon="✓", severity="success", animation="fade-in"),
    "task_failed": EventUIHints(icon="✗", severity="error", animation="shake"),
    "model_start": EventUIHints(icon="◎", severity="info", animation="pulse"),
    "model_thinking": EventUIHints(icon="◜", severity="info", animation="spiral"),
    "model_complete": EventUIHints(icon="✓", severity="success"),
    "fix_start": EventUIHints(icon="⚙", severity="warning", animation="pulse"),
    "complete": EventUIHints(icon="★", severity="success", animation="sparkle"),
    # ... etc
}
```

### Compatibility Note

The `EventUIHints` structure serves **two audiences**:
1. **CLI** (`RichRenderer`) — Uses character shapes from this appendix
2. **Studio** (frontend) — May use emojis for richer visual display

This RFC proposes CLI-specific rendering. Studio may choose to maintain emoji hints separately via frontend mapping.
