# RFC-095: Demo Command — The "Holy Shit" Experience

**Status**: Implemented  
**Author**: Lawrence Lane  
**Created**: 2026-01-22  
**Evaluated**: 2026-01-22  
**Implemented**: 2026-01-22  
**Target Version**: v1.x  
**Confidence**: 92% 🟢

---

## Summary

Add a `sunwell demo` command that proves the Prism Principle in under 2 minutes. The demo runs a side-by-side comparison of single-shot prompting vs Sunwell's cognitive architecture on the same model, making the quality difference undeniable.

**Goal**: Anyone who runs `sunwell demo` should immediately understand why cognitive architecture matters.

---

## Goals and Non-Goals

### Goals

1. **Prove value in < 2 minutes** — Zero-friction demonstration of the Prism Principle
2. **Undeniable comparison** — Same model, same prompt, different architecture → different quality
3. **Shareable output** — Terminal output that screenshots well for social proof
4. **No setup friction** — Works immediately after `sunwell setup`

### Non-Goals

1. **Comprehensive benchmarking** — Use `sunwell benchmark` for rigorous evaluation
2. **Model comparison** — Demo compares architecture, not models
3. **Production metrics** — Demo uses simple feature detection, not full evaluation rubrics
4. **Offline mode** — Requires a running model (Ollama or cloud)

---

## Motivation

### Problem Statement

THESIS-VERIFICATION.md shows +467% quality improvement (1.5 → 8.5 score on the divide task), but this requires users to:
1. Read documentation
2. Trust benchmark numbers
3. Set up their own tests to verify

Most users won't do this. The value proposition remains abstract.

### Why This Matters

- **Skeptics need proof**: "Cognitive architecture" sounds like marketing until you see it work
- **First impressions matter**: If the first experience is compelling, users explore further
- **The proof exists**: THESIS-VERIFICATION.md has concrete examples — we just need to make them runnable

### Current State

```bash
sunwell "Build a REST API"  # Requires goal, context, time investment
sunwell chat                # Open-ended, no guided "aha" moment
sunwell benchmark           # Developer-focused, outputs JSON, not compelling
```

**Missing**: A zero-friction command that demonstrates value in < 2 minutes.

---

## Proposal

### Core Experience

```bash
$ sunwell demo

🔮 Sunwell Demo — See the Prism Principle in action

Using model: llama3.2:3b (local)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Single-shot (what you'd get from raw prompting)

Prompt: "Write a Python function to divide two numbers"

⏳ Generating... (2.3s)

Result (Score: 1.5/10):
┌────────────────────────────────────────────────────────────┐
│ def divide(a, b): return a / b                             │
└────────────────────────────────────────────────────────────┘

Issues: No types, no docstring, no error handling, crashes on zero

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2: Sunwell + Resonance (same model, structured cognition)

⏳ Generating... (2.1s)
⏳ Judge evaluating... (1.8s)
⏳ Resonance refining... (3.2s)

Result (Score: 8.5/10):
┌────────────────────────────────────────────────────────────┐
│ def divide(a: float, b: float) -> float:                   │
│     """Divide two numbers.                                 │
│                                                            │
│     Args:                                                  │
│         a: The dividend.                                   │
│         b: The divisor.                                    │
│                                                            │
│     Returns:                                               │
│         The quotient of a and b.                           │
│                                                            │
│     Raises:                                                │
│         ZeroDivisionError: If b is zero.                   │
│         TypeError: If inputs aren't numeric.               │
│     """                                                    │
│     if not isinstance(a, (int, float)):                    │
│         raise TypeError(f"Expected number, got {type(a)}") │
│     if not isinstance(b, (int, float)):                    │
│         raise TypeError(f"Expected number, got {type(b)}") │
│     if b == 0:                                             │
│         raise ZeroDivisionError("Cannot divide by zero")   │
│     return a / b                                           │
└────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 COMPARISON

                Single-shot    Sunwell
Lines:          1              20
Score:          1.5/10         8.5/10
Types:          ❌             ✅
Docstring:      ❌             ✅
Error handling: ❌             ✅
Production-ready: ❌           ✅

Improvement: +467%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔮 Same model. Same prompt. Different architecture.

   The capability was already there. Sunwell revealed it.

Next steps:
  sunwell "your goal here"    Run your own task
  sunwell --help              See all commands

```

### CLI Interface

```bash
# Basic usage
sunwell demo                        # Default demo (divide function)

# Task selection
sunwell demo --task divide          # Division function (default)
sunwell demo --task add             # Addition function  
sunwell demo --task sort            # Sorting function
sunwell demo --task fibonacci       # Fibonacci sequence
sunwell demo --task "custom task"   # User-provided task

# Model selection
sunwell demo --model gemma3:4b      # Use specific model
sunwell demo --model gpt-4o         # Cloud model (if configured)

# Output control
sunwell demo --verbose              # Show judge feedback, resonance iterations
sunwell demo --json                 # Machine-readable output
sunwell demo --quiet                # Minimal output, just scores

# Comparison modes
sunwell demo --skip-single-shot     # Only show Sunwell result
sunwell demo --iterations 3         # Run multiple times, show consistency
```

### Built-in Demo Tasks

| Task | Prompt | Why It Works |
|------|--------|--------------|
| `divide` (default) | "Write a Python function to divide two numbers" | Classic example, clear failure modes (zero division) |
| `add` | "Write a Python function to add two numbers" | Simplest case, dramatic quality difference |
| `sort` | "Write a Python function to sort a list" | Shows algorithm choice, complexity handling |
| `fibonacci` | "Write a Python function to calculate fibonacci" | Shows recursion vs iteration, memoization |
| `validate_email` | "Write a Python function to validate an email address" | Shows regex, edge cases, error handling |

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DemoRunner                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ TaskLoader  │    │ Executor    │    │ Presenter   │     │
│  │             │    │             │    │             │     │
│  │ - builtin   │───▶│ - single    │───▶│ - terminal  │     │
│  │ - custom    │    │ - resonance │    │ - json      │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                            │                                │
│                            ▼                                │
│                     ┌─────────────┐                         │
│                     │   Scorer    │                         │
│                     │             │                         │
│                     │ - quality   │                         │
│                     │ - features  │                         │
│                     └─────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. TaskLoader

```python
@dataclass(frozen=True, slots=True)
class DemoTask:
    """A pre-defined demo task."""
    
    name: str
    prompt: str
    description: str
    expected_features: frozenset[str]  # What good output should have
    
BUILTIN_TASKS: dict[str, DemoTask] = {
    "divide": DemoTask(
        name="divide",
        prompt="Write a Python function to divide two numbers",
        description="Division with error handling",
        expected_features=frozenset([
            "type_hints",
            "docstring", 
            "zero_division_handling",
            "type_validation",
        ]),
    ),
    # ... other tasks
}
```

#### 2. DemoJudge (NEW)

A lightweight judge specifically for demo purposes. Unlike `benchmark/evaluator.py` which uses LLM-as-judge with multiple runs and position bias correction, the DemoJudge uses the model once to identify missing features.

```python
@dataclass(frozen=True, slots=True)
class DemoJudgment:
    """Result from demo judge evaluation."""
    
    score: float                    # 0-10
    feedback: list[str]             # Specific issues found
    features_missing: frozenset[str]  # Which expected features are absent

@dataclass
class DemoJudge:
    """Lightweight judge for demo feedback generation.
    
    Uses a single LLM call to identify missing features, optimized for
    speed and clarity rather than benchmark-grade accuracy.
    
    Evidence: This pattern is validated in THESIS-VERIFICATION.md:399-468
    where judge feedback drives Resonance refinement.
    """
    
    model: GenerativeModel
    
    async def evaluate(
        self,
        code: str,
        expected_features: frozenset[str],
    ) -> DemoJudgment:
        """Evaluate code and generate feedback for Resonance."""
        prompt = f"""Evaluate this Python code for quality:

```python
{code}
```

Check for these features: {', '.join(expected_features)}

Return JSON:
{{"score": 0-10, "missing": ["feature1", ...], "feedback": ["issue1", ...]}}
"""
        response = await self.model.generate(prompt)
        parsed = json.loads(response)
        
        return DemoJudgment(
            score=parsed["score"],
            feedback=parsed["feedback"],
            features_missing=frozenset(parsed["missing"]),
        )
```

**Why not reuse `benchmark/evaluator.py`?**
- Evaluator uses 3+ LLM calls with randomized ordering for position bias
- Demo needs speed (< 2 seconds for judge step)
- Demo feedback needs to be human-readable, not statistical
- Coupling to benchmark would slow demo and add complexity

#### 3. Executor

```python
@dataclass
class DemoExecutor:
    """Runs single-shot and Sunwell comparisons."""
    
    model: GenerativeModel
    resonance: Resonance  # From sunwell.naaru.resonance
    judge: DemoJudge
    
    async def run_single_shot(self, task: DemoTask) -> DemoResult:
        """Run the task with raw single-shot prompting."""
        prompt = f"You are a Python developer. {task.prompt}"
        start = time.perf_counter()
        response = await self.model.generate(prompt)
        elapsed = int((time.perf_counter() - start) * 1000)
        
        return DemoResult(
            code=response,
            time_ms=elapsed,
            method="single_shot",
        )
    
    async def run_sunwell(self, task: DemoTask) -> DemoResult:
        """Run the task through Sunwell's cognitive architecture.
        
        Uses the Resonance loop from sunwell.naaru.resonance (RFC-042).
        """
        start = time.perf_counter()
        
        # 1. Initial generation
        initial = await self.model.generate(task.prompt)
        
        # 2. Judge evaluation
        judgment = await self.judge.evaluate(initial, task.expected_features)
        
        # 3. Resonance refinement (if needed)
        if judgment.score < 8.0:
            # Resonance.refine() expects proposal/rejection dicts
            # See: src/sunwell/naaru/resonance.py:140-150
            result = await self.resonance.refine(
                proposal={"diff": initial, "proposal_id": str(uuid.uuid4())},
                rejection={"issues": judgment.feedback, "score": judgment.score},
            )
            elapsed = int((time.perf_counter() - start) * 1000)
            return DemoResult(
                code=result.refined_code,
                time_ms=elapsed,
                method="sunwell",
                iterations=len(result.attempts),
            )
        
        elapsed = int((time.perf_counter() - start) * 1000)
        return DemoResult(code=initial, time_ms=elapsed, method="sunwell")
```

#### 4. Scorer

Deterministic scoring via feature detection. Uses AST parsing where possible for robustness, with regex fallback.

```python
@dataclass(frozen=True, slots=True)
class DemoScore:
    """Scoring result for demo output."""
    
    score: float  # 0-10
    features: dict[str, bool]  # Which expected features are present
    issues: list[str]  # What's missing or wrong
    
class DemoScorer:
    """Scores demo outputs via deterministic feature detection.
    
    Uses AST parsing for reliable detection, with regex fallback for
    edge cases where AST parsing fails (e.g., incomplete code).
    
    This is intentionally simpler than benchmark/evaluator.py which uses
    LLM-as-judge. For demo purposes, deterministic scoring is more
    transparent and reproducible.
    """
    
    def score(self, code: str, expected_features: frozenset[str]) -> DemoScore:
        """Score code against expected features."""
        features = {
            "type_hints": self._has_type_hints(code),
            "docstring": self._has_docstring(code),
            "error_handling": self._has_error_handling(code),
            "zero_division_handling": self._has_zero_check(code),
            "type_validation": self._has_isinstance_check(code),
        }
        
        present = sum(1 for f in expected_features if features.get(f, False))
        score = (present / len(expected_features)) * 10
        
        issues = [f for f in expected_features if not features.get(f, False)]
        
        return DemoScore(score=score, features=features, issues=issues)
    
    def _has_type_hints(self, code: str) -> bool:
        """Check for type annotations using AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check for return annotation or any arg annotation
                    if node.returns or any(arg.annotation for arg in node.args.args):
                        return True
            return False
        except SyntaxError:
            # Fallback to regex for malformed code
            return bool(re.search(r'def \w+\([^)]*:\s*\w+', code))
    
    def _has_docstring(self, code: str) -> bool:
        """Check for docstring using AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return ast.get_docstring(node) is not None
            return False
        except SyntaxError:
            return '"""' in code or "'''" in code
```

#### 5. Presenter

```python
class DemoPresenter:
    """Renders demo results to terminal using Rich."""
    
    def __init__(self) -> None:
        self.console = Console()
    
    def present(
        self,
        task: DemoTask,
        single_shot: DemoResult,
        sunwell: DemoResult,
        single_score: DemoScore,
        sunwell_score: DemoScore,
    ) -> None:
        """Render the full demo comparison."""
        # Header
        self.console.print(Panel("🔮 Sunwell Demo — See the Prism Principle in action"))
        
        # Single-shot section
        self._render_result("STEP 1: Single-shot", single_shot, single_score)
        
        # Sunwell section
        self._render_result("STEP 2: Sunwell + Resonance", sunwell, sunwell_score)
        
        # Comparison table
        self._render_comparison(single_score, sunwell_score)
        
        # Tagline
        self.console.print("\n🔮 Same model. Same prompt. Different architecture.\n")
        self.console.print("   The capability was already there. Sunwell revealed it.\n")
```

### File Structure

```
src/sunwell/
├── cli/
│   └── demo_cmd.py          # CLI command handler
└── demo/
    ├── __init__.py
    ├── tasks.py             # Built-in demo tasks  
    ├── judge.py             # Lightweight judge for feedback (NEW)
    ├── executor.py          # Single-shot and Sunwell execution
    ├── scorer.py            # AST-based feature detection
    └── presenter.py         # Rich terminal output formatting
```

---

## Implementation Plan

### Phase 1: Core Demo (MVP)

| Task | Effort | Description |
|------|--------|-------------|
| CLI command | 2h | `sunwell demo` with basic options |
| TaskLoader | 1h | Built-in tasks (divide, add) |
| DemoJudge | 2h | Lightweight judge for feedback generation |
| Executor | 3h | Single-shot and Resonance comparison (integrates with `naaru/resonance.py`) |
| Scorer | 2h | AST-based feature detection |
| Presenter | 3h | Rich terminal output with boxes, colors |
| **Total** | **13h** | |

### Phase 2: Enhanced Demo

| Task | Effort | Description |
|------|--------|-------------|
| More tasks | 2h | sort, fibonacci, validate_email |
| Custom tasks | 2h | `--task "your prompt"` support |
| Verbose mode | 2h | Show judge feedback, resonance iterations |
| JSON output | 1h | Machine-readable output |
| Demo history | 1h | Save results to `.sunwell/demo_history/` |
| **Total** | **8h** | |

### Phase 3: Advanced Features

| Task | Effort | Description |
|------|--------|-------------|
| Interactive mode | 3h | `--interactive` for trying multiple tasks |
| Cloud comparison | 2h | `--compare claude` side-by-side |
| Consistency mode | 2h | `--iterations 3` for variance analysis |
| **Total** | **7h** | |

### Dependencies

- `sunwell.naaru.resonance.Resonance` — Already exists (`src/sunwell/naaru/resonance.py:104`)
- `sunwell.providers` — For model access
- `rich` — Already a dependency for terminal output

---

## Success Criteria

### Quantitative

- [ ] Demo completes in < 2 minutes on default model
- [ ] Single-shot score consistently < 3/10 on default task
- [ ] Sunwell score consistently > 7/10 on default task
- [ ] Improvement always > 100% (ideally > 300%)

### Qualitative

- [ ] First-time user understands the value proposition after running demo
- [ ] No setup required beyond `sunwell setup` (which pulls models)
- [ ] Output is visually compelling and shareable (screenshots work)
- [ ] Verbose mode explains the cognitive architecture without being overwhelming

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model produces good code single-shot | Medium | High | Use tasks known to produce poor single-shot results; fall back to different task; show warning if single-shot scores > 5 |
| Demo takes too long | Low | Medium | Use fast models by default; show progress indicators; target < 15s total |
| Scores seem arbitrary | Medium | Medium | Use deterministic AST-based feature detection; explain scoring in verbose mode |
| User doesn't have model | Low | High | Auto-suggest `ollama pull` if model missing; clear error message |
| AST parsing fails on malformed output | Low | Low | Regex fallback for all feature detection methods |
| Resonance doesn't improve score | Low | Medium | Tasks are pre-validated in THESIS-VERIFICATION.md; show raw improvement even if < expected |

---

## Design Options

### Option A: Standalone Demo Module (Recommended)

Create a new `src/sunwell/demo/` module with dedicated components.

**Pros**:
- Clean separation of concerns
- Demo-specific scoring optimized for UX, not accuracy
- No coupling to benchmark infrastructure
- Easier to iterate on demo experience

**Cons**:
- Some code duplication with benchmark evaluator
- New module to maintain

**Architecture**:
```
src/sunwell/demo/
├── __init__.py
├── tasks.py        # Built-in demo tasks
├── executor.py     # Single-shot and Sunwell execution
├── judge.py        # Lightweight judge for demo (NEW)
├── scorer.py       # Feature detection and scoring
└── presenter.py    # Terminal output formatting
```

### Option B: Benchmark Extension

Extend `sunwell benchmark` with a `--demo` flag for rich terminal output.

**Pros**:
- Reuses existing evaluator infrastructure
- Single source of truth for scoring
- Less code to maintain

**Cons**:
- Benchmark module has different goals (accuracy vs UX)
- Would need significant refactoring for rich output
- Couples demo UX to benchmark evolution
- JSON-first design doesn't fit demo use case

**Why not chosen**: The benchmark module optimizes for reproducibility and accuracy with JSON output. Demo optimizes for first impressions and visual impact. Coupling them would compromise both.

### Option C: Hybrid Approach

Use benchmark's evaluator but with demo-specific presentation layer.

**Pros**:
- Reuses scoring logic
- Maintains separation of presentation

**Cons**:
- Benchmark evaluator is heavyweight for demo purposes
- Still need new presentation layer
- Creates awkward dependency

**Why not chosen**: The evaluator complexity (multiple judge runs, position bias correction) is overkill for demo. Simple feature detection is more transparent and faster.

---

## Alternatives Rejected

### Interactive Playground

**Idea**: Web UI where users paste prompts and see comparisons.

**Rejected because**: Requires more infrastructure, loses "just run this command" simplicity.

### Video/GIF Demo

**Idea**: Record demo, embed in README.

**Accepted as complement**: Good for README, but doesn't replace hands-on experience.

---

## Decisions (Resolved Open Questions)

### 1. Should demo save results?

**Decision**: Yes, in Phase 2.

Save to `.sunwell/demo_history/<timestamp>.json` with:
- Task name and prompt
- Both outputs with scores
- Model used
- Timestamps

**Rationale**: Enables sharing demo results and tracking improvements over time. Low effort (1h) for good UX value.

### 2. Should demo work offline?

**Decision**: No, not in scope.

**Rationale**: 
- Adds complexity for edge case (who demos without a model?)
- Cached output defeats the "see it yourself" value proposition
- Users without Ollama get clear error message with `ollama pull` suggestion

### 3. Should demo support non-Python tasks?

**Decision**: No, Python only for MVP and Phase 2. Revisit in Phase 3+.

**Rationale**:
- Python is the primary audience (ML/AI developers)
- AST-based scoring only works for Python
- Adding languages requires language-specific scorers
- Keep scope tight for compelling v1

---

## References

### Evidence Sources

| Reference | Location | What It Provides |
|-----------|----------|------------------|
| THESIS-VERIFICATION.md | `docs/THESIS-VERIFICATION.md:399-468` | Concrete demo examples, +467% improvement data |
| Resonance implementation | `src/sunwell/naaru/resonance.py:104-150` | `Resonance.refine()` API for feedback loop |
| Resonance tests | `tests/thesis/test_resonance.py` | 11 tests validating refinement loop |

### Related RFCs

- [RFC-042: Adaptive Agent](RFC-042-adaptive-agent.md) — Resonance architecture design
- [README.md](../README.md) — Current positioning that demo supports

---

## Studio UI Design

### Design Philosophy: The Reveal

**No tabs. No empty states. One progressive surface.**

The demo should feel like watching a magic trick unfold. The user presses one button and the entire experience unrolls cinematically—no navigation required.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ████████████████████████████████████████████████████████████████████████   │
│                                                                             │
│              🔮  T H E   P R I S M   P R I N C I P L E                      │
│                                                                             │
│          "Write a Python function to divide two numbers"                    │
│                                                                             │
│                           [ ▶ Run Demo ]                                    │
│                                                                             │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│      Using: llama3.2:3b (local)     •     Task: divide     •     ~15s       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### State Machine

```
READY  →  GENERATING  →  COMPARING  →  REVEALED
  │           │              │            │
  │           │              │            └─ Final reveal with metrics
  │           │              └─ Side-by-side code comparison
  │           └─ Live streaming both approaches
  └─ Hero with CTA
```

### State 1: Ready (Hero)

Single call-to-action. The prompt is the star. Everything else is secondary context.

```svelte
<div class="demo-hero">
  <div class="prism-glow" />
  
  <h1>🔮 The Prism Principle</h1>
  
  <p class="task-prompt">
    "{task.prompt}"
  </p>
  
  <button class="run-demo" onclick={startDemo}>
    <Sparkle style="star" />
    Run Demo
  </button>
  
  <div class="context-bar">
    <span>Using: {model}</span>
    <span>•</span>
    <span>Task: {task.name}</span>
    <span>•</span>
    <span>~15s</span>
  </div>
</div>
```

**Visual treatment**:
- Subtle radial gradient emanating from the 🔮
- Task prompt in a distinct quote treatment (larger, italicized)
- Run button with gold gradient, subtle pulse animation
- Context bar uses `--text-tertiary`, unobtrusive

### State 2: Generating (Side-by-Side Race)

Both approaches run simultaneously. The viewer watches them "race".

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│                   "Write a Python function to divide two numbers"              │
│                                                                                │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐         │
│  │  ⚫ Single-shot              │    │  🔮 Sunwell + Resonance       │         │
│  │                              │    │                               │         │
│  │  def divide(a, b):           │    │  def divide(a, b):            │         │
│  │      return a / b            │    │      return a / b             │         │
│  │  ▊                           │    │  ▊                            │         │
│  │                              │    │                               │         │
│  │                              │    │                               │         │
│  │                              │    │                               │         │
│  │                              │    │                               │         │
│  │                              │    │                               │         │
│  └──────────────────────────────┘    └──────────────────────────────┘         │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  ✦ Generating...                                                         │ │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Progressive phases** (shown in unified progress bar):

1. **"Generating..."** — Both panes stream code simultaneously
2. **"Judging..."** — Left pane freezes, right pane shows judge icon
3. **"Refining..."** — Right pane code transforms/updates

**Visual treatment**:
- Left pane has a subtle red/gray tint (impending failure)
- Right pane has a subtle gold halo (growing success)
- Code streams character-by-character with cursor blink
- Progress bar uses `--gradient-progress` with shimmer animation
- Phase labels rotate with `<Sparkle style="star" />`

```svelte
<div class="demo-race">
  <p class="task-prompt">"{task.prompt}"</p>
  
  <div class="race-grid">
    <CodePane 
      title="⚫ Single-shot"
      code={singleShotCode}
      streaming={phase === 'generating'}
      dimmed={phase !== 'generating'}
      variant="baseline"
    />
    <CodePane 
      title="🔮 Sunwell + Resonance"
      code={sunwellCode}
      streaming={phase === 'generating' || phase === 'refining'}
      variant="prism"
    />
  </div>
  
  <ProgressBar phase={phase} progress={progress} />
</div>
```

### State 3: Revealed (The Payoff)

The comparison fades in. Metrics animate up. The improvement percentage is the hero.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│                              ✅ Demo Complete                                  │
│                                                                                │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐         │
│  │  ⚫ Single-shot              │    │  🔮 Sunwell + Resonance       │         │
│  │  Score: 1.5/10              │    │  Score: 8.5/10               │         │
│  │                              │    │                               │         │
│  │  def divide(a, b):           │    │  def divide(a: float, b: ...  │         │
│  │      return a / b            │    │      """Divide two numbers.   │         │
│  │                              │    │                               │         │
│  │  ────────────────────────    │    │      Args:                    │         │
│  │  ❌ No types                 │    │          a: The dividend.     │         │
│  │  ❌ No docstring             │    │          b: The divisor.      │         │
│  │  ❌ No error handling        │    │      ...                      │         │
│  │  ❌ Crashes on zero          │    │      if b == 0:               │         │
│  │                              │    │          raise ZeroDivision...│         │
│  │                              │    │      return a / b             │         │
│  │                              │    │  ────────────────────────     │         │
│  │                              │    │  ✅ Types   ✅ Docstring      │         │
│  │                              │    │  ✅ Errors  ✅ Production     │         │
│  └──────────────────────────────┘    └──────────────────────────────┘         │
│                                                                                │
│  ═══════════════════════════════════════════════════════════════════════════  │
│                                                                                │
│                              🔮 +467%                                          │
│                                                                                │
│               Same model. Same prompt. Different architecture.                 │
│                                                                                │
│        ┌─────────────────────┐    ┌─────────────────────┐                     │
│        │ Run Your Own Task → │    │     Run Again ↻     │                     │
│        └─────────────────────┘    └─────────────────────┘                     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Visual treatment**:
- Improvement percentage animates (counts up from 0% to 467%)
- Feature checkmarks fade in sequentially (staggered `animation-delay`)
- Tagline fades in last
- Buttons use `--gradient-ui-gold` and `--glow-gold-subtle`
- The entire reveal has a gentle scale-in animation (0.97 → 1.0)

### Component: DemoPanel.svelte

```svelte
<!--
  DemoPanel — The Prism Principle demonstration (Svelte 5, RFC-095)
  
  Single-surface progressive reveal: READY → GENERATING → REVEALED
  No tabs. No empty states. One cinematic experience.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import Sparkle from '../ui/Sparkle.svelte';
  
  type DemoPhase = 'ready' | 'generating' | 'judging' | 'refining' | 'revealed';
  
  interface Props {
    task?: DemoTask;
    model?: string;
  }
  
  let { 
    task = BUILTIN_TASKS.divide,
    model = 'llama3.2:3b',
  }: Props = $props();
  
  let phase: DemoPhase = $state('ready');
  let singleShotCode = $state('');
  let sunwellCode = $state('');
  let singleShotScore = $state<DemoScore | null>(null);
  let sunwellScore = $state<DemoScore | null>(null);
  let progress = $state(0);
  let improvementDisplay = $state(0);
  
  async function startDemo() {
    phase = 'generating';
    // ... orchestrate the demo execution
  }
  
  function reset() {
    phase = 'ready';
    singleShotCode = '';
    sunwellCode = '';
    singleShotScore = null;
    sunwellScore = null;
    progress = 0;
    improvementDisplay = 0;
  }
</script>

<div class="demo-panel" data-phase={phase}>
  <!-- Ready State: Hero CTA -->
  {#if phase === 'ready'}
    <div class="demo-hero" in:fade>
      <div class="prism-glow" aria-hidden="true" />
      
      <h1>
        <span class="prism-icon">🔮</span>
        The Prism Principle
      </h1>
      
      <blockquote class="task-prompt">
        "{task.prompt}"
      </blockquote>
      
      <button class="run-cta" onclick={startDemo}>
        <Sparkle style="star" speed={200} />
        <span>Run Demo</span>
      </button>
      
      <div class="context-meta">
        <span>Using: {model}</span>
        <span class="dot">•</span>
        <span>Task: {task.name}</span>
        <span class="dot">•</span>
        <span>~15s</span>
      </div>
    </div>
  {/if}
  
  <!-- Generating State: Side-by-Side Race -->
  {#if phase === 'generating' || phase === 'judging' || phase === 'refining'}
    <div class="demo-race" in:fade>
      <p class="task-prompt-compact">"{task.prompt}"</p>
      
      <div class="race-grid">
        <div class="code-pane baseline" class:dimmed={phase !== 'generating'}>
          <div class="pane-header">
            <span class="pane-icon">⚫</span>
            <span class="pane-title">Single-shot</span>
          </div>
          <pre class="code-content"><code>{singleShotCode}</code>{#if phase === 'generating'}<span class="cursor">▊</span>{/if}</pre>
        </div>
        
        <div class="code-pane prism">
          <div class="pane-header">
            <span class="pane-icon">🔮</span>
            <span class="pane-title">Sunwell + Resonance</span>
            {#if phase === 'judging'}
              <span class="phase-badge">Judging...</span>
            {:else if phase === 'refining'}
              <span class="phase-badge">Refining...</span>
            {/if}
          </div>
          <pre class="code-content"><code>{sunwellCode}</code>{#if phase !== 'generating' && phase !== 'revealed'}<span class="cursor">▊</span>{/if}</pre>
        </div>
      </div>
      
      <div class="progress-track">
        <div class="progress-header">
          <Sparkle style="star" speed={120} />
          <span class="progress-label">
            {#if phase === 'generating'}Generating...
            {:else if phase === 'judging'}Evaluating quality...
            {:else if phase === 'refining'}Refining with feedback...
            {/if}
          </span>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar" style="width: {progress}%">
            <div class="progress-shimmer" />
          </div>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- Revealed State: The Payoff -->
  {#if phase === 'revealed'}
    <div class="demo-revealed" in:scale={{ start: 0.97, duration: 400 }}>
      <div class="completion-badge">✅ Demo Complete</div>
      
      <p class="task-prompt-compact">"{task.prompt}"</p>
      
      <div class="comparison-grid">
        <div class="result-pane baseline">
          <div class="pane-header">
            <span class="pane-icon">⚫</span>
            <span class="pane-title">Single-shot</span>
            <span class="score bad">{singleShotScore?.score.toFixed(1)}/10</span>
          </div>
          <pre class="code-content"><code>{singleShotCode}</code></pre>
          <div class="feature-list">
            {#each singleShotScore?.issues ?? [] as issue, i}
              <div class="feature missing" style="animation-delay: {i * 100}ms">
                <span class="icon">❌</span>
                <span>{formatFeature(issue)}</span>
              </div>
            {/each}
          </div>
        </div>
        
        <div class="result-pane prism">
          <div class="pane-header">
            <span class="pane-icon">🔮</span>
            <span class="pane-title">Sunwell + Resonance</span>
            <span class="score good">{sunwellScore?.score.toFixed(1)}/10</span>
          </div>
          <pre class="code-content"><code>{sunwellCode}</code></pre>
          <div class="feature-list">
            {#each Object.entries(sunwellScore?.features ?? {}).filter(([,v]) => v) as [feature], i}
              <div class="feature present" style="animation-delay: {i * 100 + 400}ms">
                <span class="icon">✅</span>
                <span>{formatFeature(feature)}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>
      
      <div class="improvement-reveal">
        <div class="improvement-number">
          🔮 +{improvementDisplay.toFixed(0)}%
        </div>
        <p class="tagline">Same model. Same prompt. Different architecture.</p>
        <p class="subtagline">The capability was already there. Sunwell revealed it.</p>
      </div>
      
      <div class="action-buttons">
        <button class="action-primary" onclick={() => { /* navigate to main app */ }}>
          Run Your Own Task →
        </button>
        <button class="action-secondary" onclick={reset}>
          Run Again ↻
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .demo-panel {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: var(--space-8);
    position: relative;
    overflow: hidden;
  }
  
  /* ═══════════════════════════════════════════════════════════
     READY STATE: Hero CTA
     ═══════════════════════════════════════════════════════════ */
  
  .demo-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 600px;
    position: relative;
  }
  
  .prism-glow {
    position: absolute;
    top: -100px;
    width: 400px;
    height: 400px;
    background: radial-gradient(
      circle,
      rgba(201, 162, 39, 0.15) 0%,
      rgba(201, 162, 39, 0.05) 40%,
      transparent 70%
    );
    pointer-events: none;
    animation: pulse-glow 4s ease-in-out infinite;
  }
  
  @keyframes pulse-glow {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.7; }
  }
  
  .demo-hero h1 {
    font-family: var(--font-display);
    font-size: var(--text-3xl);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-6);
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .prism-icon {
    font-size: 1.5em;
  }
  
  .task-prompt {
    font-family: var(--font-serif, Georgia, serif);
    font-size: var(--text-xl);
    font-style: italic;
    color: var(--text-secondary);
    margin: 0 0 var(--space-8);
    padding: var(--space-4) var(--space-6);
    border-left: 3px solid var(--ui-gold);
    background: rgba(201, 162, 39, 0.05);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
  }
  
  .run-cta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-4) var(--space-8);
    font-size: var(--text-lg);
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--bg-primary);
    background: var(--gradient-ui-gold);
    border: none;
    border-radius: var(--radius-lg);
    cursor: pointer;
    box-shadow: var(--glow-gold-subtle), 0 4px 12px rgba(0, 0, 0, 0.2);
    transition: transform 0.15s, box-shadow 0.15s;
  }
  
  .run-cta:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold), 0 8px 24px rgba(0, 0, 0, 0.3);
  }
  
  .run-cta:active {
    transform: translateY(0);
  }
  
  .context-meta {
    margin-top: var(--space-6);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    display: flex;
    gap: var(--space-3);
  }
  
  .dot { opacity: 0.4; }
  
  /* ═══════════════════════════════════════════════════════════
     GENERATING STATE: Side-by-Side Race
     ═══════════════════════════════════════════════════════════ */
  
  .demo-race {
    width: 100%;
    max-width: 1000px;
  }
  
  .task-prompt-compact {
    font-family: var(--font-serif, Georgia, serif);
    font-size: var(--text-base);
    font-style: italic;
    color: var(--text-secondary);
    text-align: center;
    margin-bottom: var(--space-6);
  }
  
  .race-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }
  
  .code-pane {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border-color);
    transition: opacity 0.3s, border-color 0.3s;
  }
  
  .code-pane.baseline {
    border-color: var(--border-color);
  }
  
  .code-pane.baseline.dimmed {
    opacity: 0.6;
  }
  
  .code-pane.prism {
    border-color: rgba(201, 162, 39, 0.3);
    box-shadow: 0 0 20px rgba(201, 162, 39, 0.1);
  }
  
  .pane-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-color);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .pane-title {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .phase-badge {
    margin-left: auto;
    padding: var(--space-1) var(--space-2);
    background: rgba(201, 162, 39, 0.2);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    color: var(--text-gold);
  }
  
  .code-content {
    padding: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.6;
    min-height: 200px;
    max-height: 300px;
    overflow-y: auto;
    margin: 0;
    white-space: pre-wrap;
    color: var(--text-secondary);
  }
  
  .cursor {
    animation: blink 1s step-end infinite;
    color: var(--ui-gold);
  }
  
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  
  .progress-track {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }
  
  .progress-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .progress-bar-container {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
  }
  
  .progress-bar {
    height: 100%;
    background: var(--gradient-progress);
    transition: width 0.3s ease;
    position: relative;
    box-shadow: var(--glow-gold-subtle);
  }
  
  .progress-shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    animation: shimmer 1.5s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  
  /* ═══════════════════════════════════════════════════════════
     REVEALED STATE: The Payoff
     ═══════════════════════════════════════════════════════════ */
  
  .demo-revealed {
    width: 100%;
    max-width: 1000px;
  }
  
  .completion-badge {
    text-align: center;
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--success);
    margin-bottom: var(--space-4);
  }
  
  .comparison-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin-bottom: var(--space-8);
  }
  
  .result-pane {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border-color);
  }
  
  .result-pane.prism {
    border-color: rgba(201, 162, 39, 0.3);
    box-shadow: 0 0 30px rgba(201, 162, 39, 0.15);
  }
  
  .score {
    margin-left: auto;
    font-weight: 600;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }
  
  .score.bad {
    background: rgba(var(--error-rgb), 0.2);
    color: var(--error);
  }
  
  .score.good {
    background: rgba(var(--success-rgb), 0.2);
    color: var(--success);
  }
  
  .feature-list {
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  
  .feature {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    animation: fade-in 0.3s ease forwards;
    opacity: 0;
  }
  
  @keyframes fade-in {
    to { opacity: 1; }
  }
  
  .feature.missing {
    background: rgba(var(--error-rgb), 0.1);
    color: var(--error);
  }
  
  .feature.present {
    background: rgba(var(--success-rgb), 0.1);
    color: var(--success);
  }
  
  /* The Big Number */
  .improvement-reveal {
    text-align: center;
    padding: var(--space-8) 0;
    border-top: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    margin-bottom: var(--space-6);
  }
  
  .improvement-number {
    font-family: var(--font-display);
    font-size: var(--text-5xl);
    font-weight: 700;
    background: var(--gradient-ui-gold);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: var(--space-4);
    animation: count-up 1.5s ease-out;
  }
  
  .tagline {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .subtagline {
    font-family: var(--font-serif, Georgia, serif);
    font-size: var(--text-base);
    font-style: italic;
    color: var(--text-tertiary);
    margin: 0;
  }
  
  /* CTAs */
  .action-buttons {
    display: flex;
    justify-content: center;
    gap: var(--space-4);
  }
  
  .action-primary {
    padding: var(--space-3) var(--space-6);
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--bg-primary);
    background: var(--gradient-ui-gold);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    box-shadow: var(--glow-gold-subtle);
    transition: transform 0.15s, box-shadow 0.15s;
  }
  
  .action-primary:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold);
  }
  
  .action-secondary {
    padding: var(--space-3) var(--space-6);
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  
  .action-secondary:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
</style>
```

### Animation Choreography

The reveal state has a carefully choreographed animation sequence:

| Time | Element | Animation |
|------|---------|-----------|
| 0ms | Container | Scale in (0.97 → 1.0) |
| 0ms | Completion badge | Fade in |
| 100ms | Code panes | Slide up + fade in |
| 400ms | Baseline features | Stagger fade (100ms each) |
| 800ms | Prism features | Stagger fade (100ms each) |
| 1200ms | Improvement number | Count up animation |
| 1800ms | Tagline | Fade in |
| 2000ms | Action buttons | Fade in |

```typescript
async function animateReveal() {
  // 1. Start container transition (handled by Svelte)
  phase = 'revealed';
  
  // 2. Animate improvement percentage
  await delay(1200);
  const targetImprovement = calculateImprovement(singleShotScore, sunwellScore);
  
  // Count up animation
  const duration = 600;
  const start = performance.now();
  
  function tick(now: number) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    improvementDisplay = eased * targetImprovement;
    
    if (progress < 1) {
      requestAnimationFrame(tick);
    }
  }
  
  requestAnimationFrame(tick);
}
```

### Why This UX is S-Tier

1. **Zero empty states** — Every phase has meaningful content
2. **Progressive revelation** — Information appears when relevant, not before
3. **Cinematic pacing** — The experience has rhythm and build-up
4. **Single surface** — No tabs, no navigation, no cognitive load
5. **Hero moment** — The +467% is the climax, not buried in a table
6. **Clear CTAs** — Next steps are obvious and prominent
7. **Memorable** — The prism glow and choreographed reveal stick

---

## Appendix: Example Terminal Session

```bash
$ sunwell demo --verbose

🔮 Sunwell Demo — See the Prism Principle in action

Model: llama3.2:3b via Ollama
Task: divide — "Write a Python function to divide two numbers"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Single-shot

Prompt: "You are a Python developer. Write a Python function to divide two numbers"

⏳ Generating... done (2.3s)

Result:
┌────────────────────────────────────────────────────────────┐
│ def divide(a, b): return a / b                             │
└────────────────────────────────────────────────────────────┘

Scoring:
  ❌ type_hints: No type annotations found
  ❌ docstring: No docstring found
  ❌ zero_division_handling: No check for b == 0
  ❌ type_validation: No isinstance() check

Score: 1.5/10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2: Sunwell + Resonance

⏳ Initial generation... done (2.1s)

Initial result:
┌────────────────────────────────────────────────────────────┐
│ def divide(a, b):                                          │
│     return a / b                                           │
└────────────────────────────────────────────────────────────┘

⏳ Judge evaluating... done (1.8s)

Judgment: 2.0/10
Feedback:
  - Missing type hints for parameters and return value
  - No docstring explaining function purpose
  - No handling for division by zero
  - No validation of input types

⏳ Resonance refining (iteration 1)... done (3.2s)

Refined result:
┌────────────────────────────────────────────────────────────┐
│ def divide(a: float, b: float) -> float:                   │
│     """Divide two numbers.                                 │
│     ...                                                    │
│     """                                                    │
│     if not isinstance(a, (int, float)):                    │
│         raise TypeError(...)                               │
│     if b == 0:                                             │
│         raise ZeroDivisionError(...)                       │
│     return a / b                                           │
└────────────────────────────────────────────────────────────┘

Scoring:
  ✅ type_hints: Found `a: float, b: float` and `-> float`
  ✅ docstring: Found docstring with Args, Returns, Raises
  ✅ zero_division_handling: Found `if b == 0` check
  ✅ type_validation: Found `isinstance()` check

Score: 8.5/10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 COMPARISON

                Single-shot    Sunwell      Delta
Lines:          1              20           +19
Score:          1.5/10         8.5/10       +7.0
Time:           2.3s           7.1s         +4.8s
type_hints:     ❌             ✅           
docstring:      ❌             ✅           
error_handling: ❌             ✅           

Improvement: +467%
Cost: +4.8s latency for +467% quality

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔮 Same model. Same prompt. Different architecture.

   The capability was already there. Sunwell revealed it.

What happened:
  1. Single-shot collapsed to minimal implementation
  2. Judge identified missing quality signals
  3. Resonance fed structured feedback to the same model
  4. Model revealed the production-quality code it always knew

This is the Prism Principle: small models contain multitudes.
Sunwell's cognitive architecture reveals what's already there.

Next steps:
  sunwell "your goal here"    Run your own task
  sunwell chat                Interactive conversation
  sunwell --help              See all commands
```
