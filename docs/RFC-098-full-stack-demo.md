# RFC-098: Evaluation Framework — Real Metrics, Real Transparency

**Status**: Draft  
**Author**: Lawrence Lane  
**Created**: 2026-01-23  
**Target Version**: v1.x  
**Confidence**: 88% 🟢  
**Depends On**: RFC-095 (Demo Command), RFC-096 (Project Manager)  
**Evidence**: `src/sunwell/demo/executor.py`, `src/sunwell/naaru/resonance.py`, `examples/forum_app/`

---

## Summary

Build a **real evaluation framework** that honestly measures Sunwell's performance against baseline single-shot generation. This isn't a marketing demo — it's a tool for:

1. **Transparent comparison** — Fair side-by-side with identical capabilities
2. **Lens evaluation** — Which lens configurations work best?
3. **Model comparison** — How do different models perform with Sunwell?
4. **Regression testing** — Did architecture changes make us better or worse?
5. **Continuous improvement** — Data-driven optimization of the cognitive stack

**Principle**: 100% real. If we fail, we show it. Honest results drive honest improvement.

---

## Goals and Non-Goals

### Goals

1. **100% real evaluation** — No canned data, no rigged comparisons, no fake scores
2. **Fair comparison** — Both sides get identical model capabilities and tools
3. **Honest transparency** — If single-shot wins, show it clearly with appropriate colors
4. **Historical tracking** — Store results for trend analysis and regression detection
5. **Configuration testing** — Evaluate lenses, models, and architecture changes
6. **Actionable insights** — Surface data that drives real improvements

### Non-Goals

1. **Marketing theater** — No cherry-picked results or misleading visualizations
2. **Handicap single-shot** — No artificial limitations on baseline
3. **Quick feedback** — Full evaluation takes 5-30 minutes (use RFC-095 for quick demos)
4. **Offline mode** — Requires substantial LLM capacity

---

## Strategic Context: The Unfilled Gap

### Why No One Has Built This

The question "does cognitive architecture add value over single-shot?" is obvious. Any major player could answer it:

- OpenAI has the resources
- LangChain has the users  
- Anthropic has the research chops

**But no one will.** It's not a technical problem — it's an **incentive problem**.

| Company | Why they won't build this |
|---------|--------------------------|
| **Model providers** | "Buy our better model" > "Orchestrate our cheap model better" |
| **Agent frameworks** | "Our framework is magic" > "Any framework with these patterns works" |
| **Agent startups** | "Our agent is special" > "It's just orchestration you could replicate" |

**Everyone benefits from opacity.** If users can't see what's happening, they can't:
- Replicate results with cheaper models
- Compare architecture value vs model value
- Make informed build-vs-buy decisions

### Why Sunwell Should Build This

We have the inverse incentive structure:

1. **Our thesis IS architecture value** — Proving it helps us, not hurts us
2. **Transparency is our moat** — We win by showing everything, including failures
3. **We're not selling models** — We don't care if users pick GPT-4 or Llama

### The Opportunity

By being the first to **honestly, transparently** answer "does orchestration add value?":

| Outcome | Impact |
|---------|--------|
| **Category creation** | We define "architecture evaluation" as a thing |
| **Trust moat** | "The only ones who show you when they fail" |
| **Research credibility** | Publish findings, become the authority |
| **Enterprise appeal** | Prove ROI on architecture, not just model upgrades |
| **Developer love** | Engineers hate black boxes; transparency = respect |

### The Thesis

> **Cognitive architecture is the multiplier. Models are commoditizing. The value is in how you orchestrate them.**

This RFC isn't just a feature. It's **proof of the thesis** — reproducible, transparent, honest.

---

## Motivation

### Problem Statement

RFC-095's demo proves the Prism Principle on simple tasks (single functions), but critics can argue:
- "That's a trivial task, any model can do that"
- "Real work involves multiple files, dependencies, architecture decisions"
- "Show me something I'd actually build"

### Why This Matters

The full Sunwell stack (Lenses + Tools + Memory + Judge + Resonance) shines on complex tasks where:
- Context must be preserved across many operations
- Quality gates prevent cascading errors
- Specialized knowledge (Lenses) guides architecture decisions
- Feedback loops fix mistakes the model makes

### The Fairness Question

**What should single-shot get?**

| Level | Single-shot capabilities | What we're testing |
|-------|--------------------------|-------------------|
| 0 | Raw text output only | Sunwell vs ChatGPT copy-paste |
| 1 | Structured output (JSON) | Sunwell vs formatted prompting |
| 2 | Tool calling (file creation) | Sunwell vs capable single-shot |
| 3 | Multi-turn + tools | Comparing agent architectures |

**Our position**: Level 2 is the fairest comparison.

Sunwell's value isn't "we have tools" — it's cognitive architecture:
- **Lenses**: Specialized knowledge and heuristics
- **Judge**: Quality evaluation and feedback
- **Resonance**: Iterative refinement based on feedback
- **Memory**: Context preservation across iterations

A single-shot with tools can create 10 files in one turn. But it doesn't get:
- A second chance when something is wrong
- Evaluation of what it produced
- Specialized domain knowledge
- Context that builds across iterations

---

## Design Alternatives

### Alternative A: Extend Existing Demo Command

Extend `sunwell demo` with `--full-stack` flag, reusing existing `DemoExecutor` infrastructure.

| Pros | Cons |
|------|------|
| Leverages proven code (`src/sunwell/demo/executor.py`) | Demo command becomes overloaded |
| Consistent UX with existing demo | Full-stack runs are 10-30 min vs 2 min |
| Minimal new code | May confuse users expecting quick demo |

**Decision**: Rejected for primary. Demo is for quick proof-of-concept (2 min). Evaluation is for rigorous testing (10-30 min).

### Alternative B: Dedicated `sunwell eval` Command (Selected)

Create dedicated evaluation command with different UX expectations.

| Pros | Cons |
|------|------|
| Clear separation of concerns | Some shared code with demo |
| Users expect longer runtime | Two entry points to maintain |
| CI-focused design | Need to keep comparison logic in sync |
| Historical tracking, regression detection | More infrastructure |

**Decision**: **`sunwell eval` is the primary interface.** This RFC is about rigorous evaluation, not quick demos. The demo (`sunwell demo`) remains for the 2-minute "holy shit" experience (RFC-095). Evaluation is for:
- CI/CD quality gates
- Regression detection
- Lens/model optimization
- Historical tracking

### Alternative C: Evaluation as Library Only (No CLI)

Expose evaluation purely as Python API for integration testing.

| Pros | Cons |
|------|------|
| Maximum flexibility | No interactive experience |
| Easy to embed in CI | Misses marketing opportunity |
| Simple implementation | Doesn't prove thesis to users |

**Decision**: Rejected. We need the interactive experience for category creation and trust building. Library API will exist but CLI is primary.

### Storage Backend Decision

| Option | When to use |
|--------|-------------|
| **SQLite** (default) | Local development, single user, `~/.sunwell/evaluations.db` |
| **PostgreSQL** | Team usage via `SUNWELL_EVAL_DB` env var (future) |

**Decision**: SQLite for v1. PostgreSQL support is a future enhancement when team/cloud features arrive.

---

## Proposal

### Core Experience

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 Evaluation — Build a Forum App                                   │
│                                                                     │
│  Model: llama3.2:3b | Task: forum_app | Est. time: ~10 min          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐     ┌─────────────────────────────────┐   │
│  │ ⚫ Single-shot       │     │ 🔮 Sunwell                       │   │
│  │                     │     │                                 │   │
│  │ 📁 output/          │     │ 📁 forum_app/                   │   │
│  │ ├── app.py          │     │ ├── src/                        │   │
│  │ ├── models.py       │     │ │   ├── app.py                  │   │
│  │ └── (3 files)       │     │ │   ├── models/                 │   │
│  │                     │     │ │   │   ├── user.py             │   │
│  │ Status: Complete    │     │ │   │   ├── post.py             │   │
│  │ Time: 45s           │     │ │   │   └── comment.py          │   │
│  │ Turns: 1            │     │ │   ├── routes/                 │   │
│  │                     │     │ │   │   └── ...                 │   │
│  │                     │     │ │   └── tests/                  │   │
│  │                     │     │ │       └── ...                 │   │
│  │                     │     │ ├── requirements.txt            │   │
│  │                     │     │ └── README.md                   │   │
│  │                     │     │                                 │   │
│  │                     │     │ Status: Refining (turn 4/6)     │   │
│  │                     │     │ Time: 4m 32s                    │   │
│  │                     │     │ Judge: 7.2/10 → refining...     │   │
│  └─────────────────────┘     └─────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ 🔮 Sunwell Activity                                              ││
│  │ ├─ Lens: coder.lens applied (Python best practices)             ││
│  │ ├─ Created: src/models/user.py                                  ││
│  │ ├─ Created: src/models/post.py                                  ││
│  │ ├─ Judge: Missing foreign key relationships (6.8/10)            ││
│  │ ├─ Resonance: Fixing relationships...                           ││
│  │ └─ Updated: src/models/post.py (added user_id FK)               ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Completion State

```
┌─────────────────────────────────────────────────────────────────────┐
│  ✅ Evaluation Complete                                              │
│                                                                     │
│  ┌───────────────────────────┬───────────────────────────────────┐ │
│  │ ⚫ Single-shot             │ 🔮 Sunwell                         │ │
│  ├───────────────────────────┼───────────────────────────────────┤ │
│  │ Files: 3                  │ Files: 12                         │ │
│  │ Lines: 180                │ Lines: 540                        │ │
│  │ Time: 45s                 │ Time: 8m 12s                      │ │
│  │ Turns: 1                  │ Turns: 6                          │ │
│  │ Tests: 0                  │ Tests: 8                          │ │
│  │ Runnable: ❌ ImportError  │ Runnable: ✅ Server starts         │ │
│  │ Score: 4.2/10             │ Score: 8.7/10                     │ │
│  └───────────────────────────┴───────────────────────────────────┘ │
│                                                                     │
│  📊 What Made the Difference                                        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ 👓 Lens: coder.lens                                             ││
│  │    → Type safety first (strict typing)                          ││
│  │    → Error handling patterns                                    ││
│  │    → Immutability by default                                    ││
│  │                                                                 ││
│  │ ⚖️ Judge: 3 rejections                                          ││
│  │    → Missing FK relationships (fixed)                           ││
│  │    → No error handling in routes (fixed)                        ││
│  │    → Tests not covering edge cases (fixed)                      ││
│  │                                                                 ││
│  │ 🔮 Resonance: 3 refinement cycles                               ││
│  │    → Added proper relationships                                 ││
│  │    → Added try/except blocks                                    ││
│  │    → Expanded test coverage                                     ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  🔮 +107% improvement — Same model. Same tools. Different results.  │
│                                                                     │
│  [View Single-shot Code]  [View Sunwell Code]  [Run Again ↻]        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Technical Design

### Task Definition

```python
@dataclass(frozen=True, slots=True)
class FullStackTask:
    """A complex multi-file demo task."""
    
    name: str
    prompt: str
    description: str
    
    # What tools both sides get
    available_tools: frozenset[str]  # {"create_file", "read_file", "run_command"}
    
    # Expected outputs for evaluation
    expected_structure: dict[str, Any]  # File tree expectations
    expected_features: frozenset[str]   # Quality features
    
    # Optional: reference implementation for comparison
    reference_path: str | None = None
    
    # Estimated runtime
    estimated_minutes: int = 10


FULL_STACK_TASKS: dict[str, FullStackTask] = {
    "forum_app": FullStackTask(
        name="forum_app",
        prompt="Build a forum app with users, posts, comments, and upvotes",
        description="Full-stack Flask forum application",
        available_tools=frozenset(["create_file", "read_file", "list_dir", "run_command"]),
        expected_structure={
            "src/": {
                "app.py": "required",
                "models/": "required",
                "routes/": "required",
            },
            "requirements.txt": "required",
            "tests/": "optional",
            "README.md": "optional",
        },
        expected_features=frozenset([
            "app_factory_pattern",
            "database_models",
            "crud_routes",
            "error_handling",
            "input_validation",
            "foreign_key_relationships",
        ]),
        reference_path="examples/forum_app",
        estimated_minutes=10,
    ),
    "cli_tool": FullStackTask(
        name="cli_tool",
        prompt="Build a CLI tool for managing todo items with file persistence",
        description="Click-based CLI with JSON storage",
        available_tools=frozenset(["create_file", "read_file", "run_command"]),
        expected_structure={
            "cli.py": "required",
            "storage.py": "required",
            "tests/": "optional",
        },
        expected_features=frozenset([
            "click_commands",
            "file_persistence",
            "error_handling",
            "help_text",
        ]),
        estimated_minutes=5,
    ),
    "rest_api": FullStackTask(
        name="rest_api",
        prompt="Build a REST API for a bookstore inventory system",
        description="FastAPI REST API with Pydantic validation",
        available_tools=frozenset(["create_file", "read_file", "list_dir", "run_command"]),
        expected_structure={
            "main.py": "required",
            "models.py": "required",
            "routes/": "optional",
            "requirements.txt": "required",
        },
        expected_features=frozenset([
            "fastapi_app",
            "pydantic_models",
            "crud_endpoints",
            "error_handling",
            "input_validation",
        ]),
        estimated_minutes=8,
    ),
}
```

### Single-Shot Executor

```python
class SingleShotFullStackExecutor:
    """Execute a single-turn generation with tools."""
    
    def __init__(self, model: ModelProtocol, tools: list[Tool]) -> None:
        self.model = model
        self.tools = tools
    
    async def run(
        self,
        task: FullStackTask,
        output_dir: Path,
        *,
        on_file_created: Callable[[str], None] | None = None,
    ) -> SingleShotResult:
        """Run single-shot generation with tool calling.
        
        The model gets ONE turn to:
        1. Generate a plan
        2. Create all files using tools
        3. No feedback, no second chances
        
        Raises:
            EvaluationError: If model doesn't support tool calling.
        """
        # Fail fast if model can't use tools (per decision)
        if not self.model.supports_tools():
            raise EvaluationError(
                f"Model {self.model.name} doesn't support tool calling. "
                "Use a model with tool support (e.g., gpt-4o, claude-3, llama3.2)."
            )
        prompt = f"""You are building a software project.

Task: {task.prompt}

You have access to these tools:
{self._format_tools()}

Create a complete, working implementation. You have ONE turn.
Output all files needed for a working application."""

        start_time = time.monotonic()
        
        # Single generation with tool calls
        result = await self.model.generate(
            prompt,
            tools=self.tools,
            tool_choice="auto",
        )
        
        # Execute tool calls (file creation)
        files_created = []
        for tool_call in result.tool_calls:
            if tool_call.name == "create_file":
                path = output_dir / tool_call.args["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(tool_call.args["content"])
                files_created.append(str(tool_call.args["path"]))
                if on_file_created:
                    on_file_created(tool_call.args["path"])
        
        elapsed = time.monotonic() - start_time
        
        return SingleShotResult(
            files=files_created,
            output_dir=output_dir,
            time_seconds=elapsed,
            turns=1,
            tokens=result.usage,
        )
```

### Sunwell Executor (Uses Naaru)

```python
from sunwell.naaru import Naaru, ProcessInput, ProcessMode, ProcessOptions
from sunwell.naaru.types import NaaruEventType
from sunwell.lens import detect_lens


class SunwellFullStackExecutor:
    """Execute using full Sunwell cognitive architecture via Naaru.
    
    DOGFOODING: Routes through Naaru.process() — the unified entry point.
    This ensures we use:
    - Convergence (shared working memory)
    - Resonance (feedback refinement)
    - Lens (specialized knowledge)
    - All routing/sharding infrastructure
    """
    
    def __init__(self, naaru: Naaru, lens_name: str | None = None) -> None:
        self.naaru = naaru
        self.lens_name = lens_name
    
    async def run(
        self,
        task: FullStackTask,
        output_dir: Path,
        *,
        on_file_created: Callable[[str], None] | None = None,
        on_judge: Callable[[float, list[str]], None] | None = None,
        on_resonance: Callable[[int], None] | None = None,
    ) -> SunwellResult:
        """Run full Sunwell stack via Naaru.process().
        
        Uses the unified Naaru entry point (RFC-083) which coordinates:
        - Routing (RoutingWorker) — What kind of request?
        - Context (Shards) — Gather context in parallel
        - Execute (ExecutionCoordinator) — Run tasks/tools
        - Validate (ValidationWorker) — Check quality via Judge
        - Refine (Resonance) — Improve based on feedback
        - Learn (Consolidator) — Persist learnings
        """
        start_time = time.monotonic()
        
        # Auto-detect lens if not specified
        lens = self.lens_name or await detect_lens(task.prompt)
        
        # Build Naaru input
        input = ProcessInput(
            content=task.prompt,
            mode=ProcessMode.AGENT,
            options=ProcessOptions(
                lens=lens,
                workspace=output_dir,
                tools=list(task.available_tools),
            ),
        )
        
        # Track results from event stream
        files_created: list[str] = []
        judge_scores: list[float] = []
        resonance_count = 0
        total_tokens = 0
        
        # Process through Naaru — the unified entry point
        async for event in self.naaru.process(input):
            match event.type:
                case NaaruEventType.FILE_CREATED:
                    files_created.append(event.data["path"])
                    if on_file_created:
                        on_file_created(event.data["path"])
                        
                case NaaruEventType.JUDGE_RESULT:
                    judge_scores.append(event.data["score"])
                    if on_judge:
                        on_judge(event.data["score"], event.data.get("issues", []))
                        
                case NaaruEventType.RESONANCE_ITERATION:
                    resonance_count += 1
                    if on_resonance:
                        on_resonance(resonance_count)
                        
                case NaaruEventType.TOKENS_USED:
                    total_tokens += event.data["tokens"]
        
        elapsed = time.monotonic() - start_time
        
        return SunwellResult(
            files=files_created,
            output_dir=output_dir,
            time_seconds=elapsed,
            turns=len(judge_scores),
            tokens=total_tokens,
            lens_used=lens,
            judge_scores=tuple(judge_scores),
            resonance_iterations=resonance_count,
        )
```

### Evaluation

```python
class FullStackEvaluator:
    """Evaluate multi-file project outputs."""
    
    def evaluate(
        self,
        output_dir: Path,
        task: FullStackTask,
    ) -> FullStackScore:
        """Score a generated project."""
        
        scores = {}
        
        # 1. Structure score: Does it have expected files?
        scores["structure"] = self._score_structure(output_dir, task.expected_structure)
        
        # 2. Runnable score: Does it actually run?
        scores["runnable"] = self._score_runnable(output_dir)
        
        # 3. Feature score: Does it have expected features?
        scores["features"] = self._score_features(output_dir, task.expected_features)
        
        # 4. Quality score: Code quality metrics
        scores["quality"] = self._score_quality(output_dir)
        
        # Weighted average
        final_score = (
            scores["structure"] * 0.2 +
            scores["runnable"] * 0.3 +
            scores["features"] * 0.3 +
            scores["quality"] * 0.2
        )
        
        return FullStackScore(
            final_score=final_score,
            subscores=scores,
            runnable=scores["runnable"] >= 8.0,
            files_count=len(list(output_dir.rglob("*.py"))),
            lines_count=sum(
                len(f.read_text().splitlines())
                for f in output_dir.rglob("*.py")
            ),
        )
    
    def _score_runnable(self, output_dir: Path) -> float:
        """Check if the project actually runs."""
        # Try to import/run the main file
        # Check for syntax errors
        # Check for import errors
        # Optionally run tests if present
        ...
```

---

## CLI Interface

```bash
# Run evaluation (primary command)
sunwell eval

# Specific task and model
sunwell eval --task forum_app --model gpt-4o

# Specific lens to test
sunwell eval --task forum_app --lens coder.lens

# Compare two lens configurations
sunwell eval --task forum_app --lens coder.lens --compare-lens team-dev.lens

# View history
sunwell eval --history
sunwell eval --history --task forum_app
sunwell eval --history --model llama3.2

# CI mode (exit code reflects pass/fail, JSON output)
sunwell eval --ci --task forum_app --min-score 7.0

# Multiple runs for statistical validity (default: 3)
sunwell eval --task forum_app --runs 5

# Export results
sunwell eval --export results.json
sunwell eval --export results.csv
sunwell eval --export results.xml  # JUnit XML for CI tools

# Regression check against baseline
sunwell eval --regression --baseline v1.1.0

# Show cost breakdown
sunwell eval --task forum_app --show-cost
```

**CI Integration Example (GitHub Actions):**

```yaml
- name: Evaluate Sunwell Quality
  run: |
    sunwell eval --ci --task forum_app --min-score 7.0
    sunwell eval --ci --task cli_tool --min-score 6.5
  env:
    SUNWELL_MODEL: gpt-4o-mini
```

---

## Studio Integration

### Evaluation Cockpit Vision

The evaluation framework evolves into a full **Evaluation Cockpit** in Studio:

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 Evaluation Dashboard                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Recent Runs                          Performance Over Time         │
│  ┌─────────────────────────────┐     ┌─────────────────────────┐   │
│  │ forum_app  gpt-4o  8.7 ✅   │     │ Sunwell ───────╱        │   │
│  │ cli_tool   llama3  6.2 ⚠️   │     │              ╱          │   │
│  │ forum_app  llama3  5.1 ❌   │     │ Baseline ───────        │   │
│  │ rest_api   gpt-4o  9.1 ✅   │     │                         │   │
│  └─────────────────────────────┘     └─────────────────────────┘   │
│                                                                     │
│  Lens Performance                     Model × Lens Matrix           │
│  ┌─────────────────────────────┐     ┌─────────────────────────┐   │
│  │ coder.lens      8.2 avg     │     │        gpt-4o  llama3   │   │
│  │ team-dev.lens   7.4 avg     │     │ coder    8.9    6.2     │   │
│  │ helper.lens     7.1 avg     │     │ team-dev 8.1    5.8     │   │
│  │ (none)          5.8 avg     │     │ (none)   6.4    4.1     │   │
│  └─────────────────────────────┘     └─────────────────────────┘   │
│                                                                     │
│  Win Rate: Sunwell 73% | Tie 12% | Single-shot 15%                  │
│                                                                     │
│  [Run Evaluation]  [Compare Configs]  [Export]  [CI Integration]    │
└─────────────────────────────────────────────────────────────────────┘
```

**Use Cases**:

| Who | Uses it for |
|-----|-------------|
| **New users** | One-click demo to see Sunwell in action |
| **Developers** | Regression testing after architecture changes |
| **Lens authors** | A/B testing lens configurations |
| **Ops** | Model comparison (which models work best?) |
| **CI/CD** | Automated quality gates before releases |

### Data Model for Historical Tracking

```python
@dataclass(frozen=True, slots=True)
class EvaluationRun:
    """A single evaluation run with full provenance."""
    
    id: str  # UUID
    timestamp: datetime
    
    # Configuration
    task: str
    model: str
    lens: str | None
    sunwell_version: str
    
    # Results
    single_shot_score: float
    sunwell_score: float
    improvement_percent: float
    winner: Literal["sunwell", "single_shot", "tie"]
    
    # Details
    single_shot_result: SingleShotResult
    sunwell_result: SunwellResult
    evaluation_details: EvaluationDetails
    
    # Cost tracking (per decision)
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    
    # Provenance
    git_commit: str | None
    config_hash: str  # Hash of lens + model config for reproducibility
    prompts_snapshot: dict[str, str]  # Full prompts for replay


class EvaluationStore:
    """SQLite-backed evaluation storage.
    
    Follows existing patterns from:
    - `incremental/cache.py` (ExecutionCache)
    - `security/approval_cache.py` (SQLiteApprovalCache)
    
    Storage: ~/.sunwell/evaluations.db
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS evaluation_runs (
        id TEXT PRIMARY KEY,
        timestamp REAL NOT NULL,
        task TEXT NOT NULL,
        model TEXT NOT NULL,
        lens TEXT,
        sunwell_version TEXT NOT NULL,
        single_shot_score REAL NOT NULL,
        sunwell_score REAL NOT NULL,
        improvement_percent REAL NOT NULL,
        winner TEXT NOT NULL CHECK (winner IN ('sunwell', 'single_shot', 'tie')),
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        estimated_cost_usd REAL NOT NULL,
        git_commit TEXT,
        config_hash TEXT NOT NULL,
        details_json TEXT NOT NULL
    );
    
    CREATE INDEX IF NOT EXISTS idx_runs_task ON evaluation_runs(task);
    CREATE INDEX IF NOT EXISTS idx_runs_model ON evaluation_runs(model);
    CREATE INDEX IF NOT EXISTS idx_runs_lens ON evaluation_runs(lens);
    CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON evaluation_runs(timestamp DESC);
    """
    
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (Path.home() / ".sunwell" / "evaluations.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._lock = threading.Lock()  # Same pattern as ExecutionCache
    
    def save(self, run: EvaluationRun) -> None: ...
    def load_recent(self, limit: int = 50) -> list[EvaluationRun]: ...
    def load_by_task(self, task: str) -> list[EvaluationRun]: ...
    def load_by_lens(self, lens: str) -> list[EvaluationRun]: ...
    def load_by_model(self, model: str) -> list[EvaluationRun]: ...
    def aggregate_stats(self) -> EvaluationStats: ...
```

### Configuration Transparency — "Show Your Work"

The evaluation UI exposes **everything**. No black boxes. Users can inspect:

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔬 Evaluation: forum_app                                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Configuration Inspector ────────────────────────────────────┐  │
│  │                                                               │  │
│  │  📋 Sunwell Config                                            │  │
│  │  ├─ Model: llama3.2:3b                                        │  │
│  │  ├─ Temperature: 0.7                                          │  │
│  │  ├─ Max tokens: 4096                                          │  │
│  │  ├─ Resonance max iterations: 3                               │  │
│  │  └─ Judge threshold: 8.0                                      │  │
│  │                                                               │  │
│  │  👓 Lens: coder.lens                                          │  │
│  │  ├─ Description: "Expert Python code generation"              │  │
│  │  ├─ Heuristics:                                               │  │
│  │  │   • Type safety first (strict typing)                      │  │
│  │  │   • Async patterns for I/O operations                      │  │
│  │  │   • Error handling with context                            │  │
│  │  │   • Immutability by default (frozen dataclasses)           │  │
│  │  │   • Resource management with context managers              │  │
│  │  └─ Quality Policy:                                           │  │
│  │      • min_confidence: 0.8                                    │  │
│  │      • retry_limit: 2                                         │  │
│  │                                                               │  │
│  │  ⚖️ Judge Config                                              │  │
│  │  ├─ Model: same as generation                                 │  │
│  │  ├─ Pass threshold: 8.0/10                                    │  │
│  │  └─ Evaluation criteria:                                      │  │
│  │      • Code correctness                                       │  │
│  │      • Error handling                                         │  │
│  │      • Type safety                                            │  │
│  │      • Documentation                                          │  │
│  │      • Test coverage                                          │  │
│  │                                                               │  │
│  │  🔮 Resonance Config                                          │  │
│  │  ├─ Max iterations: 3                                         │  │
│  │  ├─ Feedback strategy: specific_issues                        │  │
│  │  └─ Early exit: on score >= 9.0                               │  │
│  │                                                               │  │
│  │  🛠️ Tools Available (both sides get these)                    │  │
│  │  ├─ create_file(path, content)                                │  │
│  │  ├─ read_file(path)                                           │  │
│  │  ├─ list_dir(path)                                            │  │
│  │  └─ run_command(cmd)                                          │  │
│  │                                                               │  │
│  │  [View Full Config JSON]  [View Lens Source]  [View Prompts]  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this matters:**

1. **Trust through transparency** — Users see we're not hiding anything
2. **Learning opportunity** — Users understand HOW Sunwell works
3. **Debugging** — When it fails, users can see what config to adjust
4. **Reproducibility** — Full config = can reproduce exact run
5. **Competitive advantage** — "Show me what Claude/Cursor are doing under the hood. Oh, they won't?"

**Viewable Artifacts:**

| Artifact | What user can see |
|----------|------------------|
| **Full config** | Complete sunwell.toml as JSON/YAML |
| **Lens source** | The actual .lens file contents |
| **Skill definitions** | What each skill contributes |
| **System prompts** | Exact prompts sent to the model |
| **Judge rubric** | How the judge evaluates code |
| **Tool schemas** | What tools are available and their signatures |
| **Resonance feedback** | The actual feedback sent for refinement |

**"View Prompts" Modal:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  📝 Prompts Used in This Evaluation                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Single-shot Prompt ─────────────────────────────────────────┐  │
│  │ You are building a software project.                          │  │
│  │                                                               │  │
│  │ Task: Build a forum app with users, posts, comments...        │  │
│  │                                                               │  │
│  │ You have access to these tools: [create_file, read_file...]   │  │
│  │                                                               │  │
│  │ Create a complete, working implementation. You have ONE turn. │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Sunwell Prompt (with Lens) ─────────────────────────────────┐  │
│  │ You are an expert Python developer.                           │  │
│  │                                                               │  │
│  │ HEURISTICS (from coder.lens):                                 │  │
│  │ • Use type hints throughout (strict typing)                   │  │
│  │ • Use async patterns for I/O-bound operations                 │  │
│  │ • Fail explicitly with useful error context                   │  │
│  │ • Prefer immutable data structures                            │  │
│  │ • Use context managers for all resources                      │  │
│  │                                                               │  │
│  │ Task: Build a forum app with users, posts, comments...        │  │
│  │                                                               │  │
│  │ You have access to these tools: [create_file, read_file...]   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Judge Prompt ───────────────────────────────────────────────┐  │
│  │ Evaluate this code for a Flask forum application.             │  │
│  │                                                               │  │
│  │ Score 1-10 based on:                                          │  │
│  │ • Correctness: Does it work?                                  │  │
│  │ • Error handling: Graceful failures?                          │  │
│  │ • Types: Proper annotations?                                  │  │
│  │ • Structure: Well-organized?                                  │  │
│  │ • Tests: Coverage present?                                    │  │
│  │                                                               │  │
│  │ If score < 8, list specific issues to fix.                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  [Copy All]  [Download]  [Close]                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**The transparency message:**

> "We're not hiding anything. Here's the exact config, the exact lens, the exact prompts. 
> Both sides get the same tools. The only difference is cognitive architecture.
> If we lose, we show you. If we win, you know exactly why."

### Honest Color Signals

Colors must be **truthful**, not optimistic:

```python
def score_to_color(score: float) -> str:
    """Map score to honest color signal."""
    if score >= 8.0:
        return "success"   # ✅ Green - genuinely good
    elif score >= 5.0:
        return "warning"   # ⚠️ Yellow - mediocre, needs work
    else:
        return "error"     # ❌ Red - failed, be honest

def comparison_to_color(sunwell: float, baseline: float) -> str:
    """Color based on comparison outcome."""
    if sunwell > baseline + 0.5:
        return "success"   # ✅ Sunwell won
    elif sunwell >= baseline - 0.5:
        return "neutral"   # ➖ Tie (within margin)
    else:
        return "error"     # ❌ Single-shot won - be honest about it
```

### Feedback Loop for Improvement

Evaluation results feed back into improvement:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Continuous Improvement Loop                     │
│                                                                      │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│   │ Evaluate │───►│ Analyze  │───►│ Improve  │───►│ Validate │──┐  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │  │
│        ▲                                                         │  │
│        └─────────────────────────────────────────────────────────┘  │
│                                                                      │
│   • Evaluate: Run tasks against current config                      │
│   • Analyze: Identify weak spots (which lens? which task?)          │
│   • Improve: Tune lens heuristics, adjust prompts                   │
│   • Validate: Re-run to confirm improvement                         │
└─────────────────────────────────────────────────────────────────────┘
```

**Example insights from evaluation data:**
- "coder.lens scores 2.1 points higher than team-dev.lens on Flask tasks"
- "Resonance adds +1.8 avg on tasks where initial judge score < 6.0"
- "gpt-4o-mini matches gpt-4o quality at 10% the cost on simple tasks"
- "v1.2.0 regressed -0.5 points on cli_tool vs v1.1.0"

### New Route: `/evaluation`

The evaluation UI in Studio includes:

1. **Dashboard**: Overview of recent runs, win rates, trends
2. **Run evaluation**: Select task, model, lens → watch real-time execution
3. **Split view**: File trees for both outputs side-by-side
4. **Activity log**: Real-time updates as files are created
5. **Code viewer**: Click any file to see its contents with syntax highlighting
6. **Diff view**: Compare specific files between outputs
7. **History browser**: Filter by task, model, lens, date range
8. **Analytics**: Lens performance charts, model comparison matrix
9. **Export**: Download results as JSON/CSV for external analysis

### Streaming Events

```typescript
interface FullStackDemoEvent {
  type: 'file_created' | 'judge' | 'resonance' | 'complete' | 'error';
  side: 'single_shot' | 'sunwell';
  data: {
    path?: string;
    score?: number;
    issues?: string[];
    iteration?: number;
    result?: FullStackComparison;
  };
}
```

### Studio ↔ Python Architecture

Follows the existing Tauri↔Python subprocess pattern:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Studio (Svelte + Tauri)                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Svelte UI                    Rust (Tauri)                         │
│  ┌──────────────────┐        ┌──────────────────┐                  │
│  │ EvaluationPanel  │◄──────►│ eval.rs          │                  │
│  │ - Dashboard      │  IPC   │ - list_evals()   │                  │
│  │ - RunView        │        │ - get_eval()     │                  │
│  │ - History        │        │ - run_eval()     │                  │
│  └──────────────────┘        └────────┬─────────┘                  │
│                                       │                             │
│                                       │ subprocess + streaming      │
│                                       ▼                             │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Python Backend                                                │ │
│  │  ┌─────────────────┐    ┌─────────────────┐                   │ │
│  │  │ eval_cmd.py     │───►│ EvaluationStore │                   │ │
│  │  │ (CLI commands)  │    │ (SQLite)        │                   │ │
│  │  └─────────────────┘    └────────┬────────┘                   │ │
│  │                                  │                             │ │
│  │                                  ▼                             │ │
│  │                         ~/.sunwell/evaluations.db              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**New Rust commands** (in `studio/src-tauri/src/eval.rs`):

```rust
#[tauri::command]
pub async fn list_evaluations(limit: Option<u32>) -> Result<Vec<EvalSummary>, String> {
    // Calls: sunwell eval --history --json --limit N
}

#[tauri::command]
pub async fn run_evaluation(
    task: String,
    model: Option<String>,
    lens: Option<String>,
) -> Result<(), String> {
    // Calls: sunwell eval --task {task} --model {model} --lens {lens} --stream
    // Streams events via app.emit("eval-event", ...)
}

#[tauri::command]
pub async fn get_evaluation_stats() -> Result<EvalStats, String> {
    // Calls: sunwell eval --stats --json
}
```

This follows the same pattern as:
- `demo.rs` → `sunwell demo` (RFC-095)
- `dag.rs` → reads `.sunwell/plans/` JSON files
- `memory.rs` → reads `.sunwell/memory/` JSON files

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Long runtime frustrates users | High | Clear time estimates, progress UI, "quick demo" fallback |
| Single-shot actually wins | Medium | Show honestly; this proves we're being fair |
| Model can't use tools properly | High | Validate tool-calling capability before starting |
| Evaluation is subjective | Medium | Multiple objective checks (runnable, structure, tests) |
| Output too large to display | Low | Collapsible file trees, lazy loading |

---

## Success Criteria

1. **100% honest**: No one can accuse us of rigging the comparison
2. **Fairness acknowledged**: Users agree both sides had equal capabilities
3. **Data-driven improvement**: Evaluation results lead to measurable improvements
4. **Regression detection**: Architecture changes that hurt quality are caught
5. **Lens optimization**: Clear data on which lens configs work best
6. **Honest failures**: When single-shot wins, we show it clearly with red indicators

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/eval/test_evaluator.py

def test_score_structure_all_required_present():
    """Structure score is 10 when all required files exist."""
    ...

def test_score_structure_missing_required():
    """Structure score penalizes missing required files."""
    ...

def test_score_runnable_syntax_error():
    """Runnable score is 0 for syntax errors."""
    ...

def test_score_runnable_import_error():
    """Runnable score is low for import errors."""
    ...

def test_score_features_detects_app_factory():
    """Feature detection finds app factory pattern."""
    ...
```

### Integration Tests

```python
# tests/integration/test_eval_flow.py

@pytest.mark.slow
async def test_full_evaluation_flow():
    """End-to-end evaluation produces valid results."""
    # Uses mocked model with deterministic responses
    ...

@pytest.mark.slow
async def test_evaluation_store_persistence():
    """Evaluation results persist and can be queried."""
    ...
```

### Fixture Tasks

Create minimal fixture tasks that run fast but exercise all code paths:

```yaml
# benchmark/tasks/eval/fixture_minimal.yaml
name: fixture_minimal
prompt: "Create a single Python file that prints hello world"
expected_structure:
  "main.py": required
expected_features: ["print_statement"]
estimated_minutes: 1
```

### CI Integration Tests

```yaml
# .github/workflows/eval-tests.yml
- name: Test Evaluation Framework
  run: |
    sunwell eval --ci --task fixture_minimal --min-score 5.0 --runs 1
  env:
    SUNWELL_MODEL: mock  # Uses deterministic mock model
```

### What We Test vs What We Don't

| Test | In Scope | Out of Scope |
|------|----------|--------------|
| Evaluator scoring logic | ✅ | |
| Task definition parsing | ✅ | |
| Store persistence | ✅ | |
| CLI argument handling | ✅ | |
| Studio event streaming | ✅ | |
| Actual LLM quality | | ❌ (too slow, non-deterministic) |
| Full 10-min tasks in CI | | ❌ (use fixtures) |

---

## Implementation Plan

### Phase 1: Core Evaluation Infrastructure (4 days)
- [ ] `EvaluationTask` data model (replaces demo-only thinking)
- [ ] `SingleShotExecutor` with real tool calling + capability check
- [ ] `SunwellExecutor` **routes through `Naaru.process()`** — dogfoods unified API
- [ ] Reuse `DemoJudge` from `demo/judge.py` — don't duplicate
- [ ] Reuse `Resonance` from `naaru/resonance.py` — already working
- [ ] `Evaluator` with structure/runnable/feature/quality scoring
- [ ] `EvaluationRun` data model with full provenance + cost tracking
- [ ] `EvaluationStore` following `ExecutionCache` pattern (SQLite, threading)
- [ ] Unit tests for evaluator scoring logic

### Phase 2: CLI Integration (2 days)
- [ ] `sunwell eval` command — dedicated evaluation CLI
- [ ] `sunwell eval --task forum_app --model gpt-4o`
- [ ] `sunwell eval --runs N` for statistical validity (default: 3)
- [ ] `sunwell eval --history` to show past runs
- [ ] Output formats: JSON, CSV, JUnit XML
- [ ] `sunwell eval --ci` for CI-friendly exit codes
- [ ] `sunwell eval --show-cost` for token/cost breakdown

### Phase 3: Studio Evaluation UI (4 days)
- [ ] `studio/src-tauri/src/eval.rs` — Rust commands following existing pattern
  - [ ] `list_evaluations()` → calls `sunwell eval --history --json`
  - [ ] `run_evaluation()` → calls `sunwell eval --stream` with event emission
  - [ ] `get_evaluation_stats()` → calls `sunwell eval --stats --json`
- [ ] `studio/src/routes/Evaluation.svelte` — Dashboard route
- [ ] `studio/src/stores/evaluation.svelte.ts` — Svelte 5 runes store
- [ ] Single evaluation runner with real-time streaming (follows `demo.rs` pattern)
- [ ] Historical results table with filtering
- [ ] Lens performance chart
- [ ] Model comparison matrix
- [ ] Win rate tracker

### Phase 4: Analysis and Insights (3 days)
- [ ] Aggregate statistics computation
- [ ] Regression detection (compare against baseline commits)
- [ ] Lens recommendation engine (suggest best lens for task type)
- [ ] **Intelligence integration** — store evaluation learnings in `.sunwell/intelligence/`
  - [ ] Record winning lens/model combinations as decisions
  - [ ] Record failure patterns for future improvement
- [ ] Export to CSV/JSON for external analysis
- [ ] GitHub Actions integration example

### Phase 5: Tasks and Tuning (2 days)
- [ ] `forum_app` task with reference implementation (`examples/forum_app/`)
- [ ] `cli_tool` task
- [ ] `rest_api` task
- [ ] `fixture_minimal` task for fast CI testing
- [ ] Documentation on creating custom evaluation tasks
- [ ] Integration tests with fixture tasks

---

## Decisions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Storage backend** | **Extend existing SQLite** (`~/.sunwell/evaluations.db`) | Follows existing pattern: `~/.sunwell/security/approvals.db` for user-level data, `.sunwell/cache/execution.db` for project-level. Evaluation history is user-level (cross-project). |
| **Built-in tasks** | 3 tasks: `forum_app`, `cli_tool`, `rest_api` | Covers web, CLI, and API domains. Diverse enough for meaningful comparison. |
| **Determinism** | 3 runs, geometric mean, `--runs N` flag | Handles LLM variance. Geometric mean is robust to outliers. |
| **CI format** | JUnit XML + JSON | JUnit for CI tool integration, JSON for programmatic analysis. |
| **Tool calling fallback** | Fail fast with helpful error | Check `model.supports_tools()` before run. No silent degradation. |
| **Cost tracking** | Yes, include token costs | Track `input_tokens`, `output_tokens`, `estimated_cost_usd` per run. Essential for ROI analysis. |
| **Reproducibility** | Save full prompts + pin model versions | Store in `EvaluationRun.config_hash` for exact replay capability. |

### Dogfooding Sunwell Subsystems

This RFC **must** use existing Sunwell infrastructure, not reinvent it:

| Subsystem | Location | How RFC-098 Uses It |
|-----------|----------|---------------------|
| **Naaru** | `naaru/coordinator.py` | `SunwellExecutor` routes through `Naaru.process()` for full cognitive stack |
| **Resonance** | `naaru/resonance.py` | Already used by `DemoExecutor` — reuse for full-stack refinement |
| **Convergence** | `naaru/convergence.py` | Shared working memory during multi-turn evaluation |
| **Judge** | `demo/judge.py`, `benchmark/evaluator.py` | Reuse `DemoJudge` for quality scoring |
| **Lens** | `lens/manager.py` | Auto-detect lens via existing `detect_lens()` |
| **ExecutionCache** | `incremental/cache.py` | Pattern for `EvaluationStore` (SQLite, threading, provenance) |
| **Intelligence** | `intelligence/decisions.py` | Store evaluation decisions in `.sunwell/intelligence/` |
| **Security** | `security/approval_cache.py` | Pattern for user-level SQLite storage |

**Key dogfooding requirements:**

1. **`SunwellFullStackExecutor` MUST use `Naaru.process()`**:
   ```python
   async def run(self, task: FullStackTask, ...) -> SunwellResult:
       # Route through Naaru — the unified entry point
       async for event in self.naaru.process(ProcessInput(
           content=task.prompt,
           mode=ProcessMode.AGENT,
           options=ProcessOptions(
               lens=self.lens,
               workspace=output_dir,
           ),
       )):
           # Handle events (file_created, judge, resonance, etc.)
           ...
   ```

2. **Reuse existing components, don't duplicate**:
   - ❌ Don't create new `FullStackJudge` — use `DemoJudge`
   - ❌ Don't create new refinement loop — use `Resonance`
   - ❌ Don't create new cache pattern — follow `ExecutionCache`

3. **Store learnings in existing Intelligence system**:
   ```python
   # After evaluation, persist learnings
   intelligence.record_decision(
       decision="coder.lens outperforms team-dev.lens on Flask tasks by 2.1 points",
       context={"task": "forum_app", "delta": 2.1},
   )
   ```

### Architecture Alignment

**Existing storage patterns in Sunwell:**

| Location | Format | Used for |
|----------|--------|----------|
| `.sunwell/cache/execution.db` | SQLite | Execution cache, provenance (RFC-074) |
| `~/.sunwell/security/approvals.db` | SQLite | Security approvals (RFC-089) |
| `.sunwell/intelligence/` | JSONL | Decisions, failures |
| `.sunwell/memory/` | JSON | Simulacrum, concept graphs |
| `~/.sunwell/lenses/` | YAML | User lens files |

**Evaluation storage decision:**
- **User-level** (`~/.sunwell/evaluations.db`) for cross-project history
- **Follows existing Python SQLite patterns** from `incremental/cache.py` and `security/approval_cache.py`
- **Rust/Studio accesses via Python commands** (existing Tauri↔Python subprocess pattern)

### Deferred Decisions

| Question | Deferral Reason |
|----------|-----------------|
| **Automated lens tuning** | Complex feature. Future enhancement after v1 data collection proves patterns. |
| **PostgreSQL support** | No team/cloud features yet. Revisit when collaboration features arrive. |

---

## Prior Art: Evaluation Tool Landscape

### What Exists

| Category | Tools | What they evaluate |
|----------|-------|-------------------|
| **Model Benchmarks** | HELM, MMLU, HumanEval, BigBench | Raw model capability on standardized tasks |
| **Coding Benchmarks** | SWE-bench, HumanEval, MBPP | Code generation accuracy |
| **Prompt Evaluation** | Promptfoo, LangSmith, Braintrust | Single prompt → response quality |
| **RAG Evaluation** | RAGAS, TruLens, DeepEval | Retrieval quality + generation faithfulness |
| **Agent Benchmarks** | SWE-bench, WebArena, AgentBench | End-to-end agent task completion |
| **Fine-tuning Eval** | W&B, MLflow, Determined | Training metrics, downstream task performance |
| **LLM Ops** | LangSmith, Humanloop, Parea | Production monitoring, A/B testing prompts |

### What's Missing (Our Opportunity)

None of these tools answer the question:

> **"Given the same model and same tools, does cognitive architecture produce better results?"**

Existing tools evaluate:
- Model A vs Model B (different models)
- Prompt A vs Prompt B (different prompts, same structure)
- RAG vs no-RAG (different retrieval)
- Fine-tuned vs base (different training)

**Sunwell's evaluation answers a different question:**
- Same model
- Same tools
- Same prompt (goal)
- **Different orchestration**: one-shot vs multi-turn with Lenses + Judge + Resonance

### How We Differ

| Aspect | Existing Tools | Sunwell Eval |
|--------|---------------|--------------|
| **Unit of evaluation** | Single output | Multi-file project |
| **Comparison** | Model A vs B | Architecture A vs B (same model) |
| **Transparency** | Varies (often black box) | Full config, prompts, lens visible |
| **Feedback loops** | Not evaluated | Core differentiator |
| **Configuration testing** | Manual A/B | Built-in lens/skill comparison |
| **Use case** | "Is this model good?" | "Does orchestration add value?" |

### Inspiration to Draw From

**From Promptfoo:**
- YAML-based test case definition
- Assertion system (contains, regex, LLM-graded)
- CI/CD integration patterns
- Side-by-side comparison UI

**From SWE-bench:**
- Real-world task complexity
- Pass/fail on actual execution
- Standardized task definitions
- Reproducibility focus

**From LangSmith:**
- Trace visualization
- Cost tracking
- Historical comparison
- Dashboard UX patterns

**From RAGAS:**
- Multiple evaluation dimensions (faithfulness, relevance, etc.)
- Composite scoring
- Confidence intervals

### What We Should Build

1. **Task definitions** like Promptfoo (YAML, reproducible)
2. **Execution verification** like SWE-bench (does it actually run?)
3. **Trace visibility** like LangSmith (see every step)
4. **Multi-dimensional scoring** like RAGAS (structure, quality, features)
5. **Full transparency** (unique to us — show everything)

---

## References

- RFC-095: Demo Command (current simple demo)
- RFC-096: Project Manager (project orchestration)
- `examples/forum_app/` - Reference forum implementation
- THESIS-VERIFICATION.md - Quality improvement evidence

### External References

- [Promptfoo](https://promptfoo.dev/) - Prompt evaluation framework
- [SWE-bench](https://www.swebench.com/) - Software engineering benchmark
- [LangSmith](https://smith.langchain.com/) - LLM observability platform
- [RAGAS](https://docs.ragas.io/) - RAG evaluation framework
- [DeepEval](https://docs.confident-ai.com/) - LLM testing framework
- [HELM](https://crfm.stanford.edu/helm/) - Holistic model evaluation

---

## Appendix: Sample Full-Stack Tasks

### Task: forum_app
```
Build a forum app with users, posts, comments, and upvotes.

Requirements:
- User registration and authentication
- Create, read, update, delete posts
- Nested comments on posts
- Upvote/downvote system
- Flask + SQLAlchemy + SQLite
```

### Task: cli_tool
```
Build a CLI tool for managing todo items with file persistence.

Requirements:
- Add, list, complete, delete todos
- Priority levels (low, medium, high)
- Due dates
- JSON file storage
- Click for CLI framework
```

### Task: rest_api
```
Build a REST API for a bookstore inventory system.

Requirements:
- CRUD operations for books
- Search by title, author, ISBN
- Stock management
- FastAPI + Pydantic
- SQLite database
```
