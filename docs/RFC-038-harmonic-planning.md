# RFC-038: Harmonic Planning — Iterative DAG Shape Optimization

| Field | Value |
|-------|-------|
| **RFC** | 038 |
| **Title** | Harmonic Planning — Iterative DAG Shape Optimization |
| **Status** | Draft |
| **Created** | 2026-01-18 |
| **Author** | llane |
| **Builds on** | RFC-036 (Artifact-First Planning), RFC-019 (Harmonic Synthesis) |

---

## Abstract

RFC-036 introduced artifact-first planning: discover what must exist, let dependency resolution determine execution order. But a single discovery pass produces one DAG shape, which may not be optimal for parallelization, depth, or resource efficiency.

This RFC proposes **Harmonic Planning**: generate multiple plan candidates, evaluate them against performance metrics, and either select the best or iteratively refine toward an optimal shape.

**The key insight**: Just as Harmonic Synthesis uses structured variance (personas) to improve output quality, Harmonic Planning uses structured variance (temperature, prompting strategies) to improve plan quality. The same "generate → evaluate → select" pattern applies.

```
CURRENT (RFC-036):       Goal → [Discover] → [Single DAG] → Execute

HARMONIC PLANNING:       Goal → [Discover N] → [Evaluate] → [Best DAG] → Execute
                                    ↑              │
                                    └── Refine ────┘ (optional)
```

**Why now?** With local models, LLM calls are cheap (time, not money). Spending 3-5x more planning calls to get a 2x faster execution is a good trade. Better plans compound across all downstream work.

---

## Goals and Non-Goals

### Goals

1. **Multi-candidate plan generation** — Generate N artifact graphs from the same goal
2. **Quantitative plan evaluation** — Score plans on parallelism, depth, resource efficiency
3. **Selection or refinement** — Pick the best plan, or iteratively improve via feedback
4. **Transparent metrics** — Users see why a plan was chosen
5. **Composable with RFC-036** — Harmonic Planning wraps ArtifactPlanner, doesn't replace it

### Non-Goals

1. **Replace RFC-036** — This enhances it, doesn't change the artifact-first paradigm
2. **Deterministic optimization** — LLM-based variance means plans differ non-deterministically
3. **Exhaustive search** — We're sampling the plan space, not enumerating it
4. **Runtime optimization** — This optimizes plan shape, not execution runtime

---

## Motivation

### The Single-Shot Problem

RFC-036's discovery prompt produces a single artifact graph. The LLM makes arbitrary choices:

```
Goal: "Build a REST API with auth and database"

Plan A (discovered):                    Plan B (equally valid):
  UserProtocol ─┐                         DBConfig ────────┐
  AuthInterface ┼─→ UserModel             UserProtocol ────┼─→ Everything
  DBConfig ─────┘     ↓                   AuthInterface ───┘
                   AuthService
                      ↓
                     App

Depth: 4, Leaves: 3                      Depth: 2, Leaves: 3
Critical path: 4 steps                   Critical path: 2 steps
```

Both plans are **correct** (same artifacts, valid dependencies), but Plan B executes faster because its critical path is shorter.

### The Harmonic Insight

Harmonic Synthesis (RFC-019) solves a similar problem for outputs:

```
Problem: Single generation may not be optimal
Solution: Generate with N personas, vote on winner

Result: Better outputs through structured variance
```

The same pattern applies to plans:

```
Problem: Single discovery may not produce optimal shape
Solution: Generate N plans with variance, score and select

Result: Better plans through structured variance
```

### Local Model Economics

With cloud APIs, more calls = more cost. With local models:

| Metric | Cloud | Local |
|--------|-------|-------|
| **Cost per call** | $0.01-0.10 | $0 |
| **Latency per call** | 200-1000ms | 50-500ms |
| **Throughput** | Rate limited | GPU bound |

**Implication**: Spending 5 planning calls to get a 2x better plan is always profitable with local models. The "cost" is ~2 seconds; the "gain" is potentially minutes saved in execution.

---

## Core Concepts

### Plan Quality Metrics

A plan's "performance" is measurable:

```python
@dataclass(frozen=True, slots=True)
class PlanMetrics:
    """Quantitative measures of plan quality."""
    
    # Structure metrics
    depth: int
    """Critical path length (longest dependency chain)."""
    
    width: int
    """Maximum parallel artifacts at any level."""
    
    leaf_count: int
    """Artifacts with no dependencies (can start immediately)."""
    
    artifact_count: int
    """Total artifacts in the graph."""
    
    # Efficiency metrics
    parallelism_factor: float
    """leaf_count / artifact_count — higher is more parallel."""
    
    balance_factor: float
    """width / depth — higher means more balanced tree."""
    
    # Resource metrics
    file_conflicts: int
    """Pairs of artifacts that modify the same file."""
    
    estimated_waves: int
    """Minimum execution waves (topological levels)."""
    
    @property
    def score(self) -> float:
        """Composite score (higher is better).
        
        Formula balances parallelism against complexity:
        - Reward: high parallelism_factor, high balance_factor
        - Penalize: deep graphs, many file conflicts
        """
        return (
            self.parallelism_factor * 40 +
            self.balance_factor * 30 +
            (1 / self.depth) * 20 +
            (1 / (1 + self.file_conflicts)) * 10
        )
```

### Plan Variance Strategies

How to generate meaningfully different plans:

```python
class VarianceStrategy(Enum):
    """Strategies for generating plan variance."""
    
    TEMPERATURE = "temperature"
    """Vary temperature (0.2, 0.4, 0.6) for different exploration."""
    
    PROMPTING = "prompting"
    """Vary the discovery prompt emphasis (parallel-first, minimal, thorough)."""
    
    SEEDING = "seeding"
    """Provide different example artifacts as seeds."""
    
    CONSTRAINTS = "constraints"
    """Add different constraints (max depth, min parallelism)."""
```

### Variance Prompt Templates

Different prompts bias toward different plan shapes:

```python
VARIANCE_PROMPTS = {
    "parallel_first": """
    OPTIMIZATION GOAL: MAXIMUM PARALLELISM
    
    Prioritize:
    1. Many leaf artifacts (no dependencies) that can execute in parallel
    2. Shallow dependency chains (prefer wide over deep)
    3. Split large artifacts into smaller, independent pieces
    
    Ask: "Can this artifact be split? Can this dependency be removed?"
    """,
    
    "minimal": """
    OPTIMIZATION GOAL: MINIMUM ARTIFACTS
    
    Prioritize:
    1. Combine related artifacts where possible
    2. Only essential artifacts (no nice-to-haves)
    3. Direct paths from leaves to root
    
    Ask: "Is this artifact truly necessary? Can two artifacts merge?"
    """,
    
    "thorough": """
    OPTIMIZATION GOAL: COMPLETE COVERAGE
    
    Prioritize:
    1. All edge cases and error handling
    2. Complete test coverage as artifacts
    3. Documentation and validation artifacts
    
    Ask: "What could go wrong? What's missing for production-ready?"
    """,
    
    "balanced": """
    OPTIMIZATION GOAL: BALANCED STRUCTURE
    
    Prioritize:
    1. Consistent depth across branches
    2. No single bottleneck artifact
    3. Clear separation of concerns
    
    Ask: "Is one branch deeper than others? Is there a bottleneck?"
    """,
}
```

---

## Architecture

### HarmonicPlanner

Wraps `ArtifactPlanner` with multi-candidate generation:

```python
@dataclass
class HarmonicPlanner:
    """Plans by generating multiple candidates and selecting the best.
    
    Implements Harmonic Planning: structured variance in plan generation
    followed by quantitative evaluation and selection.
    
    Example:
        >>> planner = HarmonicPlanner(
        ...     model=my_model,
        ...     candidates=5,
        ...     variance=VarianceStrategy.PROMPTING,
        ... )
        >>> graph, metrics = await planner.plan_with_metrics(goal)
        >>> print(f"Selected plan: depth={metrics.depth}, parallelism={metrics.parallelism_factor:.2f}")
    """
    
    model: ModelProtocol
    """Model for artifact discovery."""
    
    candidates: int = 5
    """Number of plan candidates to generate."""
    
    variance: VarianceStrategy = VarianceStrategy.PROMPTING
    """Strategy for generating plan variance."""
    
    refinement_rounds: int = 0
    """Optional: rounds of iterative refinement after selection."""
    
    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    """Artifact limits passed to underlying ArtifactPlanner."""
    
    # RFC-035: Schema-aware planning
    project_schema: ProjectSchema | None = None
    """Project schema for domain-specific artifact types."""
```

### Planning Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      HARMONIC PLANNING                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Goal: "Build REST API with auth"                               │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              PARALLEL DISCOVERY (N=5)                    │   │
│  │                                                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────┐│   │
│  │  │parallel │ │ minimal │ │thorough │ │balanced │ │temp ││   │
│  │  │ -first  │ │         │ │         │ │         │ │=0.6 ││   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └──┬──┘│   │
│  │       │           │           │           │          │   │   │
│  │       ▼           ▼           ▼           ▼          ▼   │   │
│  │    Plan A      Plan B      Plan C      Plan D     Plan E │   │
│  │   depth=4     depth=2     depth=5     depth=3    depth=3 │   │
│  │  leaves=3    leaves=2    leaves=6    leaves=4   leaves=4 │   │
│  │  score=62    score=71    score=58    score=75   score=68 │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    EVALUATION                            │   │
│  │                                                          │   │
│  │  Scoring: parallelism(40) + balance(30) + depth(20)     │   │
│  │           + conflicts(10) = composite score              │   │
│  │                                                          │   │
│  │  Winner: Plan D (score=75)                               │   │
│  │  - depth=3 (shallow critical path)                       │   │
│  │  - leaves=4 (good parallelism)                           │   │
│  │  - balanced structure                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              OPTIONAL: REFINEMENT                        │   │
│  │                                                          │   │
│  │  "Plan D is good but depth=3. Can we make it depth=2?"  │   │
│  │                                                          │   │
│  │  Refinement prompt → Plan D' (depth=2, score=78)        │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│       Final Plan → Execute                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation

### Core Planning Method

```python
async def plan(
    self,
    goals: list[str],
    context: dict[str, Any] | None = None,
) -> list[Task]:
    """Plan with harmonic optimization, return RFC-034 tasks."""
    goal = goals[0] if goals else "No goal specified"
    graph, _ = await self.plan_with_metrics(goal, context)
    return artifacts_to_tasks(graph)

async def plan_with_metrics(
    self,
    goal: str,
    context: dict[str, Any] | None = None,
) -> tuple[ArtifactGraph, PlanMetrics]:
    """Plan with harmonic optimization, return graph and metrics.
    
    This is the main entry point that:
    1. Generates N candidate plans in parallel
    2. Scores each plan
    3. Selects the best
    4. Optionally refines
    
    Returns:
        Tuple of (best_graph, metrics)
    """
    # Generate candidates in parallel
    candidates = await self._generate_candidates(goal, context)
    
    # Score each candidate
    scored = [(graph, self._score_plan(graph)) for graph in candidates]
    
    # Sort by score (descending)
    scored.sort(key=lambda x: x[1].score, reverse=True)
    
    best_graph, best_metrics = scored[0]
    
    # Optional refinement
    if self.refinement_rounds > 0:
        best_graph, best_metrics = await self._refine_plan(
            goal, best_graph, best_metrics, context
        )
    
    return best_graph, best_metrics
```

### Parallel Candidate Generation

```python
async def _generate_candidates(
    self,
    goal: str,
    context: dict[str, Any] | None,
) -> list[ArtifactGraph]:
    """Generate N candidate plans in parallel."""
    
    # Create base planner
    base_planner = ArtifactPlanner(
        model=self.model,
        limits=self.limits,
        project_schema=self.project_schema,
    )
    
    # Generate variance configurations
    configs = self._get_variance_configs()
    
    # Discover all plans in parallel
    async def discover_with_config(config: dict) -> ArtifactGraph | None:
        try:
            # Apply variance to goal prompt
            varied_goal = self._apply_variance(goal, config)
            return await base_planner.discover_graph(varied_goal, context)
        except Exception:
            return None  # Skip failed discoveries
    
    results = await asyncio.gather(
        *[discover_with_config(c) for c in configs],
        return_exceptions=True,
    )
    
    # Filter successful plans
    return [g for g in results if isinstance(g, ArtifactGraph)]

def _get_variance_configs(self) -> list[dict]:
    """Get variance configurations based on strategy."""
    
    if self.variance == VarianceStrategy.PROMPTING:
        return [
            {"prompt_style": "parallel_first"},
            {"prompt_style": "minimal"},
            {"prompt_style": "thorough"},
            {"prompt_style": "balanced"},
            {"prompt_style": "default", "temperature": 0.5},
        ][:self.candidates]
    
    elif self.variance == VarianceStrategy.TEMPERATURE:
        temps = [0.2, 0.3, 0.4, 0.5, 0.6][:self.candidates]
        return [{"temperature": t} for t in temps]
    
    elif self.variance == VarianceStrategy.CONSTRAINTS:
        return [
            {"constraint": "max_depth=2"},
            {"constraint": "min_leaves=5"},
            {"constraint": "max_artifacts=8"},
            {"constraint": "no_bottlenecks"},
            {"constraint": None},  # Unconstrained
        ][:self.candidates]
    
    else:
        # Default: mix of strategies
        return [{"prompt_style": "default"}] * self.candidates
```

### Plan Scoring

```python
def _score_plan(self, graph: ArtifactGraph) -> PlanMetrics:
    """Compute metrics for a plan."""
    
    depth = graph.max_depth()
    leaves = graph.get_leaves()
    artifacts = list(graph.artifacts.values())
    waves = graph.execution_waves()
    
    # Compute width (max artifacts in any wave)
    width = max(len(w) for w in waves) if waves else 1
    
    # Count file conflicts
    file_artifacts: dict[str, list[str]] = {}
    for a in artifacts:
        if a.produces_file:
            file_artifacts.setdefault(a.produces_file, []).append(a.id)
    conflicts = sum(
        len(ids) * (len(ids) - 1) // 2  # Combinations
        for ids in file_artifacts.values()
        if len(ids) > 1
    )
    
    return PlanMetrics(
        depth=depth,
        width=width,
        leaf_count=len(leaves),
        artifact_count=len(artifacts),
        parallelism_factor=len(leaves) / max(len(artifacts), 1),
        balance_factor=width / max(depth, 1),
        file_conflicts=conflicts,
        estimated_waves=len(waves),
    )
```

### Iterative Refinement

```python
async def _refine_plan(
    self,
    goal: str,
    graph: ArtifactGraph,
    metrics: PlanMetrics,
    context: dict[str, Any] | None,
) -> tuple[ArtifactGraph, PlanMetrics]:
    """Iteratively refine the best plan."""
    
    current_graph = graph
    current_metrics = metrics
    
    for round_num in range(self.refinement_rounds):
        # Identify improvement opportunities
        feedback = self._identify_improvements(current_metrics)
        
        if not feedback:
            break  # No improvements identified
        
        # Ask LLM to refine
        refined = await self._refine_with_feedback(
            goal, current_graph, feedback, context
        )
        
        if refined is None:
            break  # Refinement failed
        
        refined_metrics = self._score_plan(refined)
        
        # Only accept if improved
        if refined_metrics.score > current_metrics.score:
            current_graph = refined
            current_metrics = refined_metrics
        else:
            break  # No improvement, stop
    
    return current_graph, current_metrics

def _identify_improvements(self, metrics: PlanMetrics) -> str | None:
    """Identify what could be improved in the plan."""
    
    suggestions = []
    
    if metrics.depth > 3:
        suggestions.append(
            f"Critical path is {metrics.depth} steps. "
            "Can any artifacts be parallelized instead of sequential?"
        )
    
    if metrics.parallelism_factor < 0.3:
        suggestions.append(
            f"Only {metrics.leaf_count}/{metrics.artifact_count} artifacts are leaves. "
            "Can more artifacts have no dependencies?"
        )
    
    if metrics.file_conflicts > 0:
        suggestions.append(
            f"Found {metrics.file_conflicts} file conflicts. "
            "Can artifacts write to different files?"
        )
    
    if metrics.balance_factor < 0.5:
        suggestions.append(
            "Graph is unbalanced (deep and narrow). "
            "Can the structure be flattened?"
        )
    
    return " ".join(suggestions) if suggestions else None

async def _refine_with_feedback(
    self,
    goal: str,
    graph: ArtifactGraph,
    feedback: str,
    context: dict[str, Any] | None,
) -> ArtifactGraph | None:
    """Ask LLM to refine a plan based on feedback."""
    
    artifacts_desc = "\n".join(
        f"- {a.id}: requires {list(a.requires)}"
        for a in graph.artifacts.values()
    )
    
    prompt = f"""GOAL: {goal}

CURRENT PLAN:
{artifacts_desc}

METRICS:
- Depth (critical path): {graph.max_depth()}
- Leaves (parallel start): {len(graph.get_leaves())}
- Total artifacts: {len(graph.artifacts)}

IMPROVEMENT FEEDBACK:
{feedback}

=== REFINEMENT TASK ===

Restructure the artifact graph to address the feedback.
Keep the same essential artifacts but reorganize dependencies
for better parallelism and shallower depth.

Consider:
1. Can sequential artifacts become parallel (remove a dependency)?
2. Can a deep chain be split into parallel branches?
3. Can a bottleneck artifact be split into independent pieces?

Output the COMPLETE revised artifact list as JSON array:"""

    from sunwell.models.protocol import GenerateOptions
    
    result = await self.model.generate(
        prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=3000),
    )
    
    # Parse and build graph
    artifacts = self._parse_artifacts(result.content or "")
    if not artifacts:
        return None
    
    refined_graph = ArtifactGraph()
    for artifact in artifacts:
        refined_graph.add(artifact)
    
    # Validate no cycles introduced
    if refined_graph.detect_cycle():
        return None
    
    return refined_graph
```

---

## CLI Integration

### New Flags

```bash
# Enable harmonic planning (default candidates=5)
sunwell do "Build REST API" --harmonic

# Specify candidate count
sunwell do "Build REST API" --harmonic --candidates 7

# Enable refinement rounds
sunwell do "Build REST API" --harmonic --refine 2

# Verbose: show all candidates and scores
sunwell do "Build REST API" --harmonic --verbose
```

### Verbose Output

```
$ sunwell do "Build REST API with auth" --harmonic --verbose

🎵 Harmonic Planning: Generating 5 candidates...

  Plan A (parallel-first):  depth=4, leaves=3, score=62
  Plan B (minimal):         depth=2, leaves=2, score=71
  Plan C (thorough):        depth=5, leaves=6, score=58
  Plan D (balanced):        depth=3, leaves=4, score=75 ←─ BEST
  Plan E (temp=0.5):        depth=3, leaves=4, score=68

📊 Selected: Plan D
  - Critical path: 3 steps
  - Parallelism: 57% (4/7 are leaves)
  - Estimated waves: 3
  - File conflicts: 0

⚡ Executing Plan D...
```

---

## Integration with Existing Components

### PlanningStrategy Extension

```python
class PlanningStrategy(Enum):
    """How to plan task execution."""
    
    SEQUENTIAL = "sequential"        # RFC-032: Linear task list
    CONTRACT_FIRST = "contract_first"  # RFC-034: Phases with parallelism
    RESOURCE_AWARE = "resource_aware"  # RFC-034: Minimize file conflicts
    ARTIFACT_FIRST = "artifact_first"  # RFC-036: Artifact discovery
    HARMONIC = "harmonic"            # RFC-038: Multi-candidate optimization
```

### Planner Selection

```python
def create_planner(
    model: ModelProtocol,
    strategy: PlanningStrategy,
    **kwargs,
) -> TaskPlanner:
    """Create appropriate planner for strategy."""
    
    if strategy == PlanningStrategy.HARMONIC:
        return HarmonicPlanner(
            model=model,
            candidates=kwargs.get("candidates", 5),
            variance=kwargs.get("variance", VarianceStrategy.PROMPTING),
            refinement_rounds=kwargs.get("refinement_rounds", 0),
        )
    
    elif strategy == PlanningStrategy.ARTIFACT_FIRST:
        return ArtifactPlanner(model=model)
    
    else:
        return AgentPlanner(model=model, strategy=strategy)
```

### Naaru Integration

```python
# In NaaruConfig (types/config.py)
@dataclass
class NaaruConfig:
    # ... existing fields ...
    
    # RFC-038: Harmonic Planning
    harmonic_planning: bool = True
    """Enable multi-candidate plan generation.
    
    Default True because:
    - With Naaru, overhead is <50ms (negligible)
    - Quality improvement is significant (>15% better plans)
    - Users get better plans without thinking about it
    
    Use --no-harmonic to disable explicitly.
    """
    
    harmonic_candidates: int = 5
    """Number of plan candidates to generate.
    
    5 is the sweet spot: enough diversity, near-zero marginal cost with Naaru.
    Benchmarks show diminishing returns beyond 7.
    """
    
    harmonic_refinement: int = 1
    """Rounds of iterative plan refinement.
    
    Default 1 (single refinement pass) because:
    - Cheap with Naaru (context cached in Convergence)
    - Often improves score by 5-10%
    - Second pass rarely improves further
    
    Set to 0 for fastest planning, 2 for quality-critical work.
    """
```

---

## Naaru + Free Threading Synergies

Harmonic Planning isn't just "generate N plans" — it integrates with Naaru's architecture and Python 3.14t free threading for **zero-overhead parallelism**.

### The Key Insight

```
NAIVE APPROACH:     Generate plan 1 → Generate plan 2 → ... → Score all → Select
                    (N × latency)

NAARU APPROACH:     ┌─ GPU: Generate plan 1 ─┐
                    │  GPU: Generate plan 2  │  ← Parallel LLM calls (if multi-GPU)
                    │  GPU: Generate plan 3  │
                    └────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  WHILE GPU WORKS: │
                    │  ┌─────────────┐  │
                    │  │ CPU Shard 1 │──│── Score completed plans
                    │  │ CPU Shard 2 │──│── Pre-fetch project context
                    │  │ CPU Shard 3 │──│── Cache common artifacts
                    │  └─────────────┘  │
                    └───────────────────┘
                              │
                              ▼
                         Best plan ready
```

### Shard Integration

While GPU generates plan candidates, CPU-bound Shards do useful work:

```python
class HarmonicPlanningShards:
    """Shards optimized for plan generation."""
    
    SHARD_TYPES = {
        ShardType.PLAN_SCORER: "Score completed plan candidates",
        ShardType.CONTEXT_PREPARER: "Pre-fetch project structure for all candidates",
        ShardType.ARTIFACT_CACHE: "Cache common artifacts across candidates",
        ShardType.METRIC_COMPUTER: "Compute graph metrics (depth, parallelism)",
    }

async def plan_with_shards(
    self,
    goal: str,
    context: dict[str, Any] | None,
) -> tuple[ArtifactGraph, PlanMetrics]:
    """Generate candidates with shard assistance."""
    
    # Start context preparation immediately (Shard)
    context_task = self.shard_pool.run_parallel([
        (ShardType.CONTEXT_PREPARER, {"goal": goal}, context),
    ])
    
    # Generate candidates (GPU) — shards work in parallel
    candidates: list[ArtifactGraph] = []
    scoring_tasks: list[asyncio.Task] = []
    
    async for candidate in self._stream_candidates(goal, context):
        candidates.append(candidate)
        
        # Score immediately in background (CPU Shard) while GPU continues
        task = asyncio.create_task(
            self._score_in_background(candidate)
        )
        scoring_tasks.append(task)
    
    # All candidates generated, all scores computed in parallel
    scores = await asyncio.gather(*scoring_tasks)
    
    # Select best (already computed!)
    best_idx = max(range(len(scores)), key=lambda i: scores[i].score)
    return candidates[best_idx], scores[best_idx]
```

### Free Threading: True Parallel Scoring

With Python 3.14t (no GIL), plan scoring runs in **true parallel threads**:

```python
def _score_plans_parallel(
    self,
    candidates: list[ArtifactGraph],
) -> list[PlanMetrics]:
    """Score all candidates in parallel threads.
    
    With free-threading:
    - Each thread computes metrics for one candidate
    - No GIL contention — true parallelism
    - CPU-bound work (graph traversal, metric computation)
    """
    from concurrent.futures import ThreadPoolExecutor
    
    def score_one(graph: ArtifactGraph) -> PlanMetrics:
        # Pure CPU work — graph traversal, counting, math
        depth = graph.max_depth()
        leaves = graph.get_leaves()
        waves = graph.execution_waves()
        
        return PlanMetrics(
            depth=depth,
            width=max(len(w) for w in waves) if waves else 1,
            leaf_count=len(leaves),
            artifact_count=len(graph.artifacts),
            # ... compute all metrics
        )
    
    # With free-threading: 5 candidates score in ~1x time, not 5x
    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        return list(executor.map(score_one, candidates))
```

### Convergence: Shared Context

The `Convergence` component (shared working memory) avoids redundant work:

```python
from sunwell.naaru.convergence import Convergence, Slot, SlotSource

async def _generate_with_convergence(
    self,
    goal: str,
    configs: list[dict],
) -> list[ArtifactGraph]:
    """Generate candidates with shared context via Convergence."""
    
    # Pre-populate convergence with common context (once)
    # Note: Convergence uses Slot objects with add(), not set()
    await self.convergence.add(Slot(
        id="project:structure",
        content=await self._discover_project_structure(),
        relevance=1.0,  # High relevance - keep in memory
        source=SlotSource.CONTEXT_PREPARER,
        ttl=300,  # 5 minutes
    ))
    await self.convergence.add(Slot(
        id="project:existing_artifacts",
        content=await self._find_existing_artifacts(),
        relevance=1.0,
        source=SlotSource.CONTEXT_PREPARER,
        ttl=300,
    ))
    
    # All candidates read from convergence (no redundant work)
    async def discover_with_shared_context(config: dict) -> ArtifactGraph:
        # Context comes from convergence, not re-computed
        structure_slot = await self.convergence.get("project:structure")
        existing_slot = await self.convergence.get("project:existing_artifacts")
        shared_context = {
            "structure": structure_slot.content if structure_slot else None,
            "existing": existing_slot.content if existing_slot else None,
        }
        return await self._discover_one(goal, config, shared_context)
    
    return await asyncio.gather(*[
        discover_with_shared_context(c) for c in configs
    ])
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HARMONIC PLANNING + NAARU                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         CONVERGENCE                                  │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │   │
│  │  │ project:     │ │ project:     │ │ scored:      │  ← Shared      │   │
│  │  │ structure    │ │ existing     │ │ candidates   │    across all  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         │                          │                          │            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐    │
│  │   GPU #1    │            │   GPU #2    │            │   GPU #3    │    │
│  │ parallel-   │            │  minimal    │            │  thorough   │    │
│  │ first plan  │            │   plan      │            │   plan      │    │
│  └──────┬──────┘            └──────┬──────┘            └──────┬──────┘    │
│         │                          │                          │            │
│         └──────────────────────────┼──────────────────────────┘            │
│                                    │                                        │
│  ┌─────────────────────────────────┼───────────────────────────────────┐   │
│  │                    SHARDS (CPU, parallel)                            │   │
│  │                                                                      │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │   │
│  │  │ SCORER #1  │  │ SCORER #2  │  │ SCORER #3  │  │ LOOKAHEAD  │    │   │
│  │  │ (thread 1) │  │ (thread 2) │  │ (thread 3) │  │ (thread 4) │    │   │
│  │  │            │  │            │  │            │  │            │    │   │
│  │  │ Score plan │  │ Score plan │  │ Score plan │  │ Prepare    │    │   │
│  │  │ A as soon  │  │ B as soon  │  │ C as soon  │  │ refinement │    │   │
│  │  │ as ready   │  │ as ready   │  │ as ready   │  │ context    │    │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │   │
│  │                                                                      │   │
│  │  With FREE THREADING: All 4 threads run in TRUE PARALLEL            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│                         ┌──────────────────┐                               │
│                         │  SELECT BEST     │                               │
│                         │  (already scored)│                               │
│                         └──────────────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Latency Breakdown: Naaru vs Naive

| Operation | Naive | Naaru + Free Threading |
|-----------|-------|------------------------|
| **Generate 5 candidates** | 5 × 500ms = 2500ms | 1 × 500ms (parallel) = 500ms |
| **Score 5 candidates** | 5 × 10ms = 50ms | 1 × 10ms (parallel threads) = 10ms |
| **Pre-fetch context** | 200ms (sequential) | 0ms (overlapped with generation) |
| **Total planning** | ~2750ms | ~510ms |
| **Speedup** | 1x | **~5.4x** |

**Key**: Free threading makes scoring truly parallel (not GIL-limited), and Shards overlap CPU work with GPU work.

### Implementation: HarmonicPlanner with Naaru

```python
@dataclass
class HarmonicPlanner:
    """Plans with multi-candidate optimization via Naaru integration."""
    
    model: ModelProtocol
    candidates: int = 5
    variance: VarianceStrategy = VarianceStrategy.PROMPTING
    refinement_rounds: int = 0
    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    project_schema: ProjectSchema | None = None
    
    # Naaru integration
    convergence: Convergence | None = None
    """Shared working memory for context caching."""
    
    shard_pool: ShardPool | None = None
    """CPU helpers for parallel scoring and context prep."""
    
    use_free_threading: bool = True
    """Use ThreadPoolExecutor for parallel scoring (requires 3.14t)."""
    
    async def plan_with_metrics(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[ArtifactGraph, PlanMetrics]:
        """Plan with full Naaru integration."""
        
        # 1. Pre-populate convergence (if available)
        if self.convergence:
            await self._warm_convergence(goal, context)
        
        # 2. Generate candidates with streaming scores
        candidates, scores = await self._generate_and_score_streaming(goal, context)
        
        # 3. Select best
        best_idx = max(range(len(scores)), key=lambda i: scores[i].score)
        best_graph, best_metrics = candidates[best_idx], scores[best_idx]
        
        # 4. Optional refinement (Resonance pattern)
        if self.refinement_rounds > 0:
            best_graph, best_metrics = await self._refine_plan(
                goal, best_graph, best_metrics, context
            )
        
        return best_graph, best_metrics
    
    async def _generate_and_score_streaming(
        self,
        goal: str,
        context: dict[str, Any] | None,
    ) -> tuple[list[ArtifactGraph], list[PlanMetrics]]:
        """Generate candidates and score as they complete."""
        
        configs = self._get_variance_configs()
        candidates: list[ArtifactGraph | None] = [None] * len(configs)
        scores: list[PlanMetrics | None] = [None] * len(configs)
        
        async def generate_and_score(idx: int, config: dict):
            """Generate one candidate and score immediately."""
            graph = await self._discover_one(goal, config, context)
            candidates[idx] = graph
            
            # Score in thread (free-threading: true parallel)
            if self.use_free_threading:
                scores[idx] = await asyncio.to_thread(self._score_plan, graph)
            else:
                scores[idx] = self._score_plan(graph)
        
        # All generation + scoring in parallel
        await asyncio.gather(*[
            generate_and_score(i, c) for i, c in enumerate(configs)
        ])
        
        # Filter failures
        valid = [(c, s) for c, s in zip(candidates, scores, strict=True) if c and s]
        return [c for c, _ in valid], [s for _, s in valid]
```

---

## Performance Considerations

### Latency Analysis

| Phase | Single Plan | Harmonic (N=5) | Harmonic + Naaru |
|-------|-------------|----------------|------------------|
| **Discovery** | 500ms | 500ms (parallel async) | 500ms |
| **Context prep** | 200ms | 200ms × 5 = 1000ms | 0ms (overlapped via Shards) |
| **Scoring** | N/A | 50ms (sequential) | 10ms (parallel threads) |
| **Refinement** | N/A | 0-1000ms | 0-1000ms |
| **Total Planning** | ~700ms | ~1550ms | ~510ms |

**With Naaru + free threading**:
- Context preparation overlaps with generation (Shards)
- Scoring runs in true parallel threads (no GIL)
- Convergence caches common context (no redundant work)
- **Net result: 5 candidates for the cost of ~1**

### When to Use Harmonic Planning

**With Naaru integration**, harmonic planning has near-zero overhead. Recommendations:

| Scenario | Recommendation |
|----------|----------------|
| Small goals (<5 artifacts) | Enable — overhead is ~10ms, why not? |
| Medium goals (5-20 artifacts) | Enable — significant parallelism gains |
| Large goals (20+ artifacts) | Enable + refinement — critical for deep graphs |
| Time-critical | Enable (Naaru makes it free) |
| Quality-critical | Enable + 2 refinement rounds |

**Bottom line**: With Naaru + free threading, always enable Harmonic Planning. The cost is negligible; the quality improvement is not.

### Empirical Validation Required

The latency figures above are **estimates** based on architecture analysis. Phase 6 includes a benchmark to validate:

```python
# benchmark/tasks/harmonic_planning_bench.yaml
- id: harmonic_vs_single_shot
  description: "Compare single-shot vs harmonic planning"
  goals:
    - "Build REST API with auth"
    - "Add user settings with dark mode"
    - "Create file upload system"
  metrics:
    - planning_time_ms
    - execution_waves
    - parallelism_factor
    - total_execution_time_ms
  variants:
    - name: single_shot
      harmonic: false
    - name: harmonic_5
      harmonic: true
      candidates: 5
    - name: harmonic_5_naaru
      harmonic: true
      candidates: 5
      use_convergence: true
      use_free_threading: true
```

**Success criteria**: Harmonic + Naaru should achieve <50ms overhead vs single-shot while improving plan quality by >15%.

### Default Configuration

```python
# Suggested defaults (Naaru-aware)
HARMONIC_DEFAULTS = {
    "candidates": 5,              # 5 candidates for ~0 extra latency
    "variance": "prompting",      # Most structural diversity
    "refinement_rounds": 1,       # One refinement pass (cheap with Naaru)
    "use_convergence": True,      # Cache common context
    "use_free_threading": True,   # Parallel scoring (3.14t)
}
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Scoring formula suboptimal** | Medium | Medium | Start with intuitive weights; add ensemble scoring in v2; benchmark validates |
| **Candidates too similar** | Medium | Low | Prompting variance strategy produces structural differences; add diversity metric |
| **Latency regression** | Low | High | Naaru integration makes it near-zero; benchmark gates Phase 5 |
| **Convergence capacity exceeded** | Low | Low | Project context uses 2 slots of 7; eviction policy handles overflow |
| **Free-threading unavailable** | Medium | Low | Graceful fallback to asyncio.to_thread(); still faster than sequential |
| **LLM returns invalid plans** | Medium | Low | Existing recovery in ArtifactPlanner handles cycles, empty graphs |

### ShardType Extensions

This RFC proposes **no new ShardTypes**. Scoring uses pure CPU computation (graph traversal), not Shards. The architecture diagram shows "SCORER" threads, but these are `ThreadPoolExecutor` workers, not Naaru Shards.

However, if LLM-based scoring is added later (e.g., "is this plan sensible?"), a new ShardType may be warranted:

```python
# Future (not in this RFC):
class ShardType(Enum):
    # ... existing types ...
    PLAN_SCORER = "plan_scorer"  # Only if LLM-based scoring added
```

Current implementation uses existing infrastructure:
- `CONTEXT_PREPARER`: Pre-fetch project structure (already exists)
- `LOOKAHEAD`: Prepare refinement context (already exists)
- `ThreadPoolExecutor`: Parallel metric computation (stdlib, no Shard needed)

---

## Future Extensions

### Learned Scoring

Train a lightweight model to predict plan execution time from structure:

```python
# Future: ML-based scoring
class LearnedScorer:
    """Predict execution time from plan structure."""
    
    async def score(self, graph: ArtifactGraph) -> float:
        features = self._extract_features(graph)
        return self.model.predict(features)
```

### Plan Caching

Cache successful plans by goal similarity:

```python
# Future: Plan cache
class PlanCache:
    """Cache plans by goal embedding similarity."""
    
    async def get_similar(self, goal: str) -> ArtifactGraph | None:
        embedding = await self._embed(goal)
        similar = self._find_similar(embedding, threshold=0.9)
        return similar.graph if similar else None
```

### Ensemble Selection

Use multiple scoring functions and vote:

```python
# Future: Ensemble scoring
SCORERS = [
    ParallelismScorer(weight=0.4),
    DepthScorer(weight=0.3),
    ResourceScorer(weight=0.2),
    ComplexityScorer(weight=0.1),
]

def ensemble_score(graph: ArtifactGraph) -> float:
    return sum(s.score(graph) * s.weight for s in SCORERS)
```

---

## Implementation Plan

### Phase 1: Core HarmonicPlanner (2-3 days)

- [ ] `PlanMetrics` dataclass with scoring formula
- [ ] `HarmonicPlanner` with parallel candidate generation
- [ ] Basic scoring and selection
- [ ] Unit tests for metrics and selection

### Phase 2: Variance Strategies (1-2 days)

- [ ] `VarianceStrategy` enum and configurations
- [ ] Variance prompt templates
- [ ] Temperature-based variance
- [ ] Constraint-based variance

### Phase 3: Naaru Integration (2-3 days)

- [ ] Convergence integration for shared context
- [ ] ShardPool integration for parallel scoring
- [ ] Free-threading parallel scoring with `ThreadPoolExecutor`
- [ ] Streaming score computation (score as candidates complete)
- [ ] Tests for parallel correctness

### Phase 4: Iterative Refinement (2-3 days)

- [ ] Improvement identification logic
- [ ] Refinement prompt and parsing
- [ ] Refinement loop with score tracking
- [ ] Tests for refinement effectiveness

### Phase 5: CLI & Config Integration (1-2 days)

- [ ] Add `HARMONIC` to `PlanningStrategy`
- [ ] CLI flags (`--harmonic`, `--candidates`, `--refine`)
- [ ] `NaaruConfig` fields for harmonic planning
- [ ] Integration tests

### Phase 6: Benchmarks & Validation (1-2 days)

- [ ] Create `benchmark/tasks/harmonic_planning_bench.yaml`
- [ ] Run benchmark: single-shot vs harmonic (N=5) vs harmonic+naaru
- [ ] Validate latency claims (<50ms overhead with Naaru)
- [ ] Validate quality claims (>15% better parallelism_factor)
- [ ] Tune scoring weights if correlation with execution is poor
- [ ] Gate Phase 7 on benchmark success

### Phase 7: Documentation & Release (1 day)

- [ ] Update CLI docs with `--harmonic`, `--candidates`, `--refine`
- [ ] Add examples to README
- [ ] Document free-threading requirements
- [ ] Add troubleshooting for fallback modes

---

## Success Metrics

### Quality Metrics (Phase 6 Benchmark Gates)

| Metric | Target | With Naaru | Gate |
|--------|--------|------------|------|
| **Plan quality improvement** | >15% better parallelism_factor | >25% | Hard gate |
| **Execution time reduction** | >10% faster critical path | >20% | Hard gate |
| **Planning overhead** | <1s additional latency | **<50ms** | Hard gate |
| **Refinement effectiveness** | >40% of plans improve | >50% | Soft gate |
| **Scoring correlation** | Score correlates with execution (r>0.6) | r>0.7 | Soft gate |

### Operational Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| **Parallel efficiency** | >4x speedup on 5 candidates | Free-threading required |
| **Convergence hit rate** | >90% cache hits | Context reuse across candidates |
| **Candidate diversity** | >3 unique structures per run | Prompting variance working |
| **Failure rate** | <5% discovery failures | Existing recovery handles most |

**Hard gates** must pass for Phase 7. **Soft gates** inform weight tuning but don't block release.

---

## Open Questions (with Recommendations)

1. **Scoring weights** — Current formula is intuitive. Should we tune empirically?
   
   **Recommendation**: Ship intuitive weights (`parallelism×40 + balance×30 + depth×20 + conflicts×10`). Add weight tuning in Phase 6 benchmarks. If execution metrics correlate poorly with scores, adjust.

2. **Candidate count** — 5 feels right. Worth A/B testing 3 vs 5 vs 7?
   
   **Recommendation**: Default to 5. With Naaru, marginal cost is near-zero. Benchmarks will show diminishing returns — expect 5-7 to plateau. Expose `--candidates` for power users.

3. **When to auto-enable** — Should Harmonic be default for goals with >N expected artifacts?
   
   **Recommendation**: **Enable by default when Naaru is active**. The <50ms overhead is negligible, and users get better plans without thinking about it. Expose `--no-harmonic` for explicit opt-out.

   ```python
   # In NaaruConfig, default to True when Naaru features active
   harmonic_planning: bool = True  # Changed from False
   ```

4. **Plan diversity metric** — Should we ensure candidates are structurally different, not just scored differently?
   
   **Recommendation**: Defer to v2. Prompting variance already produces structural differences (parallel-first vs minimal vs thorough). If benchmarks show candidate clustering, add a diversity check:
   
   ```python
   # Future: Reject candidate if too similar to existing
   def _is_diverse(new: ArtifactGraph, existing: list[ArtifactGraph]) -> bool:
       for e in existing:
           if _structural_similarity(new, e) > 0.9:
               return False
       return True
   ```

---

## References

- **RFC-019**: Harmonic Synthesis — Multi-persona generation with voting
- **RFC-036**: Artifact-First Planning — Discover what must exist
- **RFC-034**: Contract-Aware Planning — Task dependencies and parallel execution
- Build systems (Make, Bazel): Dependency-driven execution order
- Beam search: Generate multiple candidates, score, prune

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-18 | Initial draft |
| 2026-01-18 | Fixed Convergence API (use `add(Slot)` not `set()`) |
| 2026-01-18 | Added explicit Risks and Mitigations section |
| 2026-01-18 | Added ShardType extensions clarification (no new types needed) |
| 2026-01-18 | Resolved Open Questions with recommendations |
| 2026-01-18 | Changed `harmonic_planning` default to `True` (near-zero overhead) |
| 2026-01-18 | Changed `harmonic_refinement` default to `1` (cheap improvement) |
| 2026-01-18 | Added Empirical Validation section with benchmark spec |
| 2026-01-18 | Split Phase 6 into Benchmarks (6) + Documentation (7) |
| 2026-01-18 | Added hard/soft gates to Success Metrics |