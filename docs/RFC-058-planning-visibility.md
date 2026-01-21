# RFC-058: Planning Visibility — Surfacing Harmonic Details and Reasoning

**Status**: Draft  
**Created**: 2026-01-20  
**Updated**: 2026-01-20 (Added design alternatives, evidence references)  
**Authors**: Sunwell Team  
**Confidence**: 88% 🟢  
**Depends on**: 
- RFC-038 (Harmonic Planning) — Multi-candidate optimization ✅ Implemented
- RFC-053 (Studio Agent Bridge) — Event streaming ✅ Implemented
- RFC-040 (Plan Persistence) — Execution state storage ✅ Implemented

**Enables**:
- Better understanding of planning decisions
- Debugging poor plan quality
- Learning from planning patterns
- User trust through transparency

---

## Summary

Currently, planning happens "behind the scenes" with minimal visibility. Users see `plan_start` → `plan_winner` with only a task count, missing rich information about:

1. **Harmonic planning details** — Multiple candidates are generated and scored, but only the winner is shown
2. **Plan metrics** — Depth, parallelism, balance factors are computed but not exposed
3. **Refinement rounds** — Improvements are identified and applied silently
4. **Reasoning/thinking** — LLM reasoning during planning is not captured or displayed

This RFC adds comprehensive planning visibility by:
1. Emitting detailed events for harmonic candidate generation and scoring
2. Showing real-time progress bars during candidate generation and scoring
3. Surfacing plan metrics and selection rationale
4. Capturing and displaying refinement improvements
5. Optionally capturing LLM reasoning (chain-of-thought)

**One-liner**: Transform planning from a "black box" into a transparent, debuggable process with full visibility into candidate generation, scoring, and selection.

---

## Motivation

### The Current State

**What's working**:
- Harmonic planning generates multiple candidates and selects the best ✅
- Plan metrics (depth, parallelism, balance) are computed ✅
- Refinement rounds improve plans iteratively ✅
- Event system supports streaming to Studio ✅

**What's missing**:
- Only `plan_winner` event with minimal info (task count)
- No visibility into candidate generation process
- Plan metrics computed but not exposed
- Refinement improvements happen silently
- No reasoning/thinking capture

### The Problem

**1. Planning is a Black Box**

Users can't understand why a plan was selected:

```
User: "Why did Sunwell create 12 artifacts instead of 8?"
System: "Plan selected" (no explanation)
User: "Was this the best plan? Were alternatives considered?"
System: [silence]
```

**2. Debugging Poor Plans**

When plans are suboptimal, there's no way to diagnose:

```
User: "This plan has a 5-step critical path, can't we parallelize more?"
System: "Plan selected" (no metrics shown)
User: "What were the alternatives? What was the scoring?"
System: [no information available]
```

**3. Harmonic Planning Value Hidden**

Harmonic planning generates multiple candidates and scores them, but users never see:
- How many candidates were considered
- What the scores were
- Why one was selected over others
- What variance strategies were used

**4. Refinement Happens Silently**

When plans are refined, users don't know:
- What improvements were identified
- Whether refinement helped
- How many rounds were applied

### The Opportunity

**Benefits of planning visibility**:
- **Transparency** — Users understand planning decisions
- **Debugging** — Diagnose poor plan quality
- **Learning** — See patterns in good vs bad plans
- **Trust** — Show that Sunwell is making informed decisions
- **Optimization** — Identify opportunities to improve planning

### Non-Goals

This RFC does **not** aim to:
- Change planning algorithms (only expose existing data)
- Add new planning strategies (only surface current ones)
- Require LLM reasoning capture (optional enhancement)
- Replace existing events (extend them)

---

## Design Alternatives

Before presenting the recommended approach, we considered three alternatives:

### Alternative A: Batch Events (Single Aggregated Event)

**Approach**: Emit a single `PLAN_DETAILS` event after all candidates are generated and scored, containing nested candidate/refinement data.

**Pros**:
- Lower event volume (1 event vs. N+3 events for N candidates)
- Atomic updates (all data arrives together)
- Simpler UI updates (single state change)
- Better for high candidate counts (>10)

**Cons**:
- No real-time progress feedback during generation
- Larger payloads (may impact Studio performance)
- Less granular visibility (can't show "generating candidate 3/5")

**Tradeoff**: Progress visibility vs. event simplicity

**Verdict**: ❌ Rejected — Real-time feedback is core value proposition

---

### Alternative B: Lazy Event Emission (Opt-In Verbose Mode)

**Approach**: Only emit detailed events if `--verbose` flag is set or Studio is connected (detect via callback presence).

**Pros**:
- Zero overhead when not needed (backward compatible)
- Conditional logic keeps code clean
- Terminal users don't get overwhelmed

**Cons**:
- Conditional logic adds complexity
- Need to detect "verbose mode" (callback presence check)
- May miss events if callback added mid-execution

**Tradeoff**: Performance vs. simplicity

**Verdict**: ⚠️ Partial — Use callback presence as signal (if callback exists, emit detailed events)

---

### Alternative C: Event Aggregation (Hybrid Approach)

**Approach**: Emit progress events during generation (for UI feedback), but aggregate final results into single `PLAN_DETAILS` event.

**Pros**:
- Best of both worlds (progress + atomic results)
- Lower final event volume
- Easier to reason about final state

**Cons**:
- More complex event schema (progress vs. final)
- Need to handle both event types in Studio
- Progress events may be redundant if final event arrives quickly

**Tradeoff**: Progress visibility vs. event simplicity

**Verdict**: ❌ Rejected — Full granularity needed for debugging

---

### Recommended Approach: Per-Candidate Streaming with Callback Pattern

**Rationale**: 
- Real-time feedback is essential for user trust
- Event callback pattern already exists in codebase (`naaru.py:191-207`, `executor.py:194`)
- Backward compatible (callback is optional)
- Matches existing event emission patterns

**Evidence**:
- `Naaru._emit_event()` already uses optional callback (`naaru.py:191-207`)
- `ArtifactExecutor.on_event` shows callback pattern (`executor.py:194`)
- `run.py` wires callback for JSON mode (`run.py:335-340`)

---

## Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLANNING VISIBILITY FLOW                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HarmonicPlanner.plan_with_metrics()                            │
│  ├── _generate_candidates()                                    │
│  │   ├── Emit PLAN_CANDIDATE_START                            │
│  │   ├── For each candidate:                                  │
│  │   │   ├── Emit PLAN_CANDIDATE_GENERATED                    │
│  │   │   └── (variance strategy, config)                      │
│  │   └── Emit PLAN_CANDIDATES_COMPLETE                        │
│  │                                                             │
│  ├── _score_plans_parallel()                                   │
│  │   ├── For each candidate:                                  │
│  │   │   └── Emit PLAN_CANDIDATE_SCORED                       │
│  │   │       (metrics: depth, parallelism, balance, score)    │
│  │   └── Emit PLAN_SCORING_COMPLETE                           │
│  │                                                             │
│  ├── Selection                                                 │
│  │   └── Emit PLAN_WINNER (enhanced)                          │
│  │       (selected_index, metrics, selection_reason)          │
│  │                                                             │
│  └── _refine_plan() (if enabled)                              │
│      ├── For each round:                                       │
│      │   ├── Emit PLAN_REFINE_START                           │
│      │   │   (round, current_score, improvements_identified) │
│      │   ├── Emit PLAN_REFINE_ATTEMPT                         │
│      │   │   (improvements_applied)                           │
│      │   └── Emit PLAN_REFINE_COMPLETE                        │
│      │       (improved, new_score)                           │
│      └── Emit PLAN_REFINE_FINAL                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    EVENT STREAM (RFC-053)                        │
│  NDJSON events → Studio frontend                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    STUDIO UI COMPONENTS                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  PlanningPanel.svelte                                    │  │
│  │  ├── CandidateComparison (side-by-side metrics)         │  │
│  │  ├── RefinementTimeline (round-by-round improvements)   │  │
│  │  └── MetricsVisualization (charts, graphs)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Event Callback Pattern

**Evidence**: The event callback pattern already exists in the codebase:

- `Naaru._emit_event()` uses optional callback (`naaru.py:191-207`)
- `ArtifactExecutor.on_event` shows callback pattern (`executor.py:194`)
- `run.py` wires callback for JSON mode (`run.py:335-340`)

**Callback Signature**: 
```python
from typing import Callable
from sunwell.adaptive.events import AgentEvent

EventCallback = Callable[[AgentEvent], None]
```

**Integration Pattern**:
- Optional callback parameter (backward compatible)
- Sync callback (not async) — matches existing pattern
- Fire-and-forget (errors don't block planning)
- Callback presence signals "verbose mode" (emit detailed events)

### Event Enhancements

#### New Event Types

```python
# In sunwell/adaptive/events.py

class EventType(Enum):
    # ... existing events ...
    
    # Planning visibility (RFC-058)
    PLAN_CANDIDATE_START = "plan_candidate_start"
    """Starting harmonic candidate generation."""
    
    PLAN_CANDIDATE_GENERATED = "plan_candidate_generated"
    """Generated a single candidate plan."""
    
    PLAN_CANDIDATES_COMPLETE = "plan_candidates_complete"
    """All candidates generated, starting scoring."""
    
    PLAN_CANDIDATE_SCORED = "plan_candidate_scored"
    """Scored a candidate with metrics."""
    
    PLAN_SCORING_COMPLETE = "plan_scoring_complete"
    """All candidates scored, selecting winner."""
    
    PLAN_REFINE_START = "plan_refine_start"
    """Starting refinement round."""
    
    PLAN_REFINE_ATTEMPT = "plan_refine_attempt"
    """Attempting refinement improvements."""
    
    PLAN_REFINE_COMPLETE = "plan_refine_complete"
    """Refinement round completed."""
    
    PLAN_REFINE_FINAL = "plan_refine_final"
    """All refinement rounds complete."""
```

**Evidence**: EventType enum exists and is extensible (`events.py:23-135`). New types follow existing naming convention.

#### Enhanced PLAN_WINNER Event

```python
# Current (minimal)
AgentEvent(EventType.PLAN_WINNER, {
    "tasks": len(graph),
})

# Enhanced (RFC-058)
AgentEvent(EventType.PLAN_WINNER, {
    "tasks": len(graph),
    "artifact_count": len(graph),
    "selected_index": 0,  # Which candidate won
    "total_candidates": 5,
    "metrics": {
        "score": 87.3,
        "depth": 3,
        "width": 4,
        "leaf_count": 8,
        "parallelism_factor": 0.67,
        "balance_factor": 1.33,
        "file_conflicts": 0,
        "estimated_waves": 3,
    },
    "selection_reason": "Highest composite score (parallelism + balance - depth penalty)",
    "variance_strategy": "prompting",
    "refinement_rounds": 1,
    "final_score_improvement": 5.2,  # Score improvement from refinement
})
```

### Harmonic Planning Integration

**Evidence**: HarmonicPlanner exists (`harmonic.py:179-223`) with:
- `plan_with_metrics()` method (`harmonic.py:254-307`)
- `_generate_candidates()` method (`harmonic.py:325-362`)
- `_score_plans_parallel()` method (`harmonic.py:487-506`)
- `_refine_plan()` method (`harmonic.py:512-547`)

**Current State**: HarmonicPlanner does not currently accept event callbacks. This RFC adds:
- Optional `event_callback` parameter to `HarmonicPlanner.__init__()`
- `_emit_event()` helper method (similar to `Naaru._emit_event()`)
- Event emission at key points in planning flow

#### Candidate Generation Events

```python
# In HarmonicPlanner._generate_candidates()

async def _generate_candidates(
    self,
    goal: str,
    context: dict[str, Any] | None,
) -> list[ArtifactGraph]:
    """Generate N candidate plans in parallel."""
    
    # Emit start event
    self._emit_event(EventType.PLAN_CANDIDATE_START, {
        "total_candidates": self.candidates,
        "variance_strategy": self.variance.value,
    })
    
    configs = self._get_variance_configs()
    
    async def discover_with_config(config: dict, index: int) -> ArtifactGraph | None:
        try:
            varied_goal = self._apply_variance(goal, config)
            graph = await base_planner.discover_graph(varied_goal, context)
            
            # Emit candidate generated (with progress)
            self._emit_event(EventType.PLAN_CANDIDATE_GENERATED, {
                "candidate_index": index,
                "artifact_count": len(graph),
                "progress": index + 1,  # Current count
                "total_candidates": len(configs),  # Total expected
                "variance_config": {
                    "prompt_style": config.get("prompt_style", "default"),
                    "temperature": config.get("temperature", 0.2),
                    "constraint": config.get("constraint"),
                },
            })
            
            return graph
        except Exception:
            return None
    
    results = await asyncio.gather(
        *[discover_with_config(c, i) for i, c in enumerate(configs)],
        return_exceptions=True,
    )
    
    candidates = [g for g in results if isinstance(g, ArtifactGraph)]
    
    # Emit completion
    self._emit_event(EventType.PLAN_CANDIDATES_COMPLETE, {
        "successful_candidates": len(candidates),
        "failed_candidates": len(configs) - len(candidates),
    })
    
    return candidates
```

**Helper Method** (add to HarmonicPlanner):
```python
def _emit_event(self, event_type: EventType, data: dict[str, Any]) -> None:
    """Emit event via callback if configured.
    
    Matches pattern from Naaru._emit_event() (naaru.py:191-207).
    """
    if self.event_callback is None:
        return
    
    try:
        from sunwell.adaptive.events import AgentEvent
        event = AgentEvent(event_type, data)
        self.event_callback(event)
    except Exception:
        # Don't let event emission errors break planning
        pass
```

#### Scoring Events

**Evidence**: `_score_plans_parallel()` exists (`harmonic.py:487-506`). PlanMetrics includes all claimed fields (`harmonic.py:47-101`).

```python
# In HarmonicPlanner.plan_with_metrics()

# Score each candidate
scores = await self._score_plans_parallel(candidates)

# Emit scored events (with progress)
for i, (graph, metrics) in enumerate(zip(candidates, scores, strict=True)):
    self._emit_event(EventType.PLAN_CANDIDATE_SCORED, {
        "candidate_index": i,
        "score": metrics.score,
        "progress": i + 1,  # Current count
        "total_candidates": len(candidates),  # Total being scored
        "metrics": {
            "depth": metrics.depth,
            "width": metrics.width,
            "leaf_count": metrics.leaf_count,
            "artifact_count": metrics.artifact_count,
            "parallelism_factor": metrics.parallelism_factor,
            "balance_factor": metrics.balance_factor,
            "file_conflicts": metrics.file_conflicts,
            "estimated_waves": metrics.estimated_waves,
        },
    })

# Emit scoring complete
self._emit_event(EventType.PLAN_SCORING_COMPLETE, {
    "total_scored": len(scores),
})

# Select winner
scored = list(zip(candidates, scores, strict=True))
scored.sort(key=lambda x: x[1].score, reverse=True)
best_graph, best_metrics = scored[0][0], scored[0][1]

# Emit enhanced winner event
self._emit_event(EventType.PLAN_WINNER, {
    "tasks": len(best_graph),
    "artifact_count": len(best_graph),
    "selected_index": 0,
    "total_candidates": len(candidates),
    "metrics": {
        "score": best_metrics.score,
        "depth": best_metrics.depth,
        "width": best_metrics.width,
        "leaf_count": best_metrics.leaf_count,
        "parallelism_factor": best_metrics.parallelism_factor,
        "balance_factor": best_metrics.balance_factor,
        "file_conflicts": best_metrics.file_conflicts,
        "estimated_waves": best_metrics.estimated_waves,
    },
    "selection_reason": self._format_selection_reason(best_metrics, scored),
    "variance_strategy": self.variance.value,
})
```

#### Refinement Events

**Evidence**: `_refine_plan()` exists (`harmonic.py:512-547`). Refinement logic iterates through rounds and accepts improvements only if score increases.

```python
# In HarmonicPlanner._refine_plan()

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
    initial_score = metrics.score
    
    for round_num in range(self.refinement_rounds):
        # Identify improvements
        feedback = self._identify_improvements(current_metrics)
        
        if not feedback:
            break
        
        # Emit refine start
        self._emit_event(EventType.PLAN_REFINE_START, {
            "round": round_num + 1,
            "total_rounds": self.refinement_rounds,
            "current_score": current_metrics.score,
            "improvements_identified": feedback,
        })
        
        # Refine
        refined = await self._refine_with_feedback(
            goal, current_graph, feedback, context
        )
        
        if refined is None:
            break
        
        refined_metrics = self._score_plan(refined)
        
        # Emit attempt
        self._emit_event(EventType.PLAN_REFINE_ATTEMPT, {
            "round": round_num + 1,
            "improvements_applied": self._extract_applied_improvements(refined, current_graph),
        })
        
        # Accept if improved
        if refined_metrics.score > current_metrics.score:
            current_graph = refined
            current_metrics = refined_metrics
            
            # Emit complete
            self._emit_event(EventType.PLAN_REFINE_COMPLETE, {
                "round": round_num + 1,
                "improved": True,
                "old_score": current_metrics.score,
                "new_score": refined_metrics.score,
                "improvement": refined_metrics.score - current_metrics.score,
            })
        else:
            # No improvement, stop
            self._emit_event(EventType.PLAN_REFINE_COMPLETE, {
                "round": round_num + 1,
                "improved": False,
                "reason": "Score did not improve",
            })
            break
    
    # Emit final
    self._emit_event(EventType.PLAN_REFINE_FINAL, {
        "total_rounds": round_num + 1,
        "initial_score": initial_score,
        "final_score": current_metrics.score,
        "total_improvement": current_metrics.score - initial_score,
    })
    
    return current_graph, current_metrics
```

### Studio UI Components

#### PlanningPanel Component

```svelte
<!-- studio/src/components/PlanningPanel.svelte -->
<script lang="ts">
  import { agentState } from '../stores/agent';
  import CandidateComparison from './planning/CandidateComparison.svelte';
  import RefinementTimeline from './planning/RefinementTimeline.svelte';
  import MetricsVisualization from './planning/MetricsVisualization.svelte';
  import PlanningProgress from './planning/PlanningProgress.svelte';
  
  // Derived from agent events
  let candidates = $derived($agentState.planningCandidates || []);
  let selectedCandidate = $derived($agentState.selectedCandidate);
  let refinementRounds = $derived($agentState.refinementRounds || []);
  let planningProgress = $derived($agentState.planningProgress);
</script>

<div class="planning-panel">
  <h3>Planning Details</h3>
  
  <!-- Progress bar during candidate generation -->
  {#if planningProgress && planningProgress.total_candidates > 0}
    <PlanningProgress 
      current={planningProgress.current_candidates}
      total={planningProgress.total_candidates}
      phase={planningProgress.phase}
    />
  {/if}
  
  {#if candidates.length > 0}
    <CandidateComparison 
      candidates={candidates} 
      selected={selectedCandidate}
    />
  {/if}
  
  {#if refinementRounds.length > 0}
    <RefinementTimeline rounds={refinementRounds} />
  {/if}
  
  {#if selectedCandidate}
    <MetricsVisualization metrics={selectedCandidate.metrics} />
  {/if}
</div>
```

#### Candidate Comparison View

```svelte
<!-- studio/src/components/planning/CandidateComparison.svelte -->
<script lang="ts">
  interface Candidate {
    index: number;
    artifact_count: number;
    score: number;
    metrics: {
      depth: number;
      parallelism_factor: number;
      balance_factor: number;
    };
    variance_config: {
      prompt_style: string;
      temperature?: number;
    };
  }
  
  export let candidates: Candidate[];
  export let selected: Candidate;
</script>

<div class="candidate-comparison">
  <h4>Plan Candidates ({candidates.length} generated)</h4>
  
  <table class="candidates-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Artifacts</th>
        <th>Score</th>
        <th>Depth</th>
        <th>Parallelism</th>
        <th>Balance</th>
        <th>Strategy</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {#each candidates as candidate}
        <tr class:selected={candidate.index === selected.index}>
          <td>{candidate.index + 1}</td>
          <td>{candidate.artifact_count}</td>
          <td class="score">{candidate.score.toFixed(1)}</td>
          <td>{candidate.metrics.depth}</td>
          <td>{(candidate.metrics.parallelism_factor * 100).toFixed(0)}%</td>
          <td>{candidate.metrics.balance_factor.toFixed(2)}</td>
          <td class="strategy">{candidate.variance_config.prompt_style}</td>
          <td>
            {#if candidate.index === selected.index}
              <span class="badge selected">Selected</span>
            {:else}
              <span class="badge">Considered</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
  
  {#if selected}
    <div class="selection-reason">
      <strong>Selection reason:</strong> {selected.selection_reason || "Highest composite score"}
    </div>
  {/if}
</div>
```

#### Planning Progress Component

```svelte
<!-- studio/src/components/planning/PlanningProgress.svelte -->
<script lang="ts">
  export let current: number;
  export let total: number;
  export let phase: 'generating' | 'scoring' | 'refining' | 'complete';
  
  const progress = $derived(Math.min((current / total) * 100, 100));
  const percentage = $derived(Math.round(progress));
  
  const phaseLabels = {
    generating: 'Generating candidates',
    scoring: 'Scoring candidates',
    refining: 'Refining plan',
    complete: 'Complete',
  };
</script>

<div class="planning-progress">
  <div class="progress-header">
    <span class="phase-label">{phaseLabels[phase]}</span>
    <span class="progress-text">{current} / {total}</span>
  </div>
  
  <div class="progress-bar-container">
    <div 
      class="progress-bar" 
      style="width: {percentage}%"
      role="progressbar"
      aria-valuenow={current}
      aria-valuemin={0}
      aria-valuemax={total}
    >
      <div class="progress-fill"></div>
    </div>
  </div>
  
  {#if phase === 'generating'}
    <div class="progress-detail">
      Generating plan candidates with different strategies...
    </div>
  {:else if phase === 'scoring'}
    <div class="progress-detail">
      Evaluating candidates for parallelism and efficiency...
    </div>
  {:else if phase === 'refining'}
    <div class="progress-detail">
      Refining selected plan to improve quality...
    </div>
  {/if}
</div>

<style>
  .planning-progress {
    padding: 16px;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    margin-bottom: 16px;
  }
  
  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: var(--text-sm);
  }
  
  .phase-label {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .progress-text {
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  
  .progress-bar-container {
    width: 100%;
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
  }
  
  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    transition: width 0.3s ease;
    position: relative;
  }
  
  .progress-fill {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.2),
      transparent
    );
    animation: shimmer 1.5s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  
  .progress-detail {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-style: italic;
  }
</style>
```

#### Refinement Timeline

```svelte
<!-- studio/src/components/planning/RefinementTimeline.svelte -->
<script lang="ts">
  interface RefinementRound {
    round: number;
    current_score: number;
    improvements_identified: string;
    improved: boolean;
    new_score?: number;
    improvement?: number;
  }
  
  export let rounds: RefinementRound[];
</script>

<div class="refinement-timeline">
  <h4>Refinement Rounds ({rounds.length})</h4>
  
  <div class="timeline">
    {#each rounds as round}
      <div class="timeline-item">
        <div class="round-number">Round {round.round}</div>
        <div class="round-content">
          <div class="score-change">
            {#if round.improved}
              <span class="improved">
                {round.current_score.toFixed(1)} → {round.new_score.toFixed(1)}
                (+{round.improvement.toFixed(1)})
              </span>
            {:else}
              <span class="no-change">
                {round.current_score.toFixed(1)} (no improvement)
              </span>
            {/if}
          </div>
          <div class="improvements">
            {round.improvements_identified}
          </div>
        </div>
      </div>
    {/each}
  </div>
</div>
```

### Optional: Reasoning Capture

**Phase 2 Enhancement**: Capture LLM reasoning during planning.

#### Chain-of-Thought Prompting

```python
# In ArtifactPlanner.discover_graph()

async def discover_graph(self, goal: str, context: dict) -> ArtifactGraph:
    """Discover artifacts with reasoning capture."""
    
    prompt = f"""
    GOAL: {goal}
    
    Think step by step:
    1. What artifacts must exist when this goal is complete?
    2. What are the dependencies between artifacts?
    3. Which artifacts can be created in parallel?
    
    Show your reasoning, then output the artifact list.
    """
    
    result = await self.model.generate(prompt, ...)
    
    # Parse reasoning and artifacts
    reasoning = self._extract_reasoning(result.content)
    artifacts = self._parse_artifacts(result.content)
    
    # Emit reasoning event
    if event_callback:
        emit(AgentEvent(EventType.PLAN_REASONING, {
            "goal": goal,
            "reasoning": reasoning,
            "artifacts_discovered": len(artifacts),
        }))
    
    return self._build_graph(artifacts)
```

**Note**: This is optional and can be added in Phase 2 if users request it.

---

## Implementation Plan

### Phase 1: Event Emission (Core)

**Goal**: Emit all planning visibility events from HarmonicPlanner.

**Tasks**:
1. Add new event types to `EventType` enum (`events.py:23-135`)
2. Add optional `event_callback` parameter to `HarmonicPlanner.__init__()` (`harmonic.py:179-223`)
3. Add `_emit_event()` helper method to `HarmonicPlanner` (pattern from `naaru.py:191-207`)
4. Emit candidate generation events in `_generate_candidates()` (`harmonic.py:325-362`)
5. Emit scoring events in `plan_with_metrics()` (`harmonic.py:254-307`)
6. Enhance `PLAN_WINNER` event with metrics (currently minimal in `agent.py:411-418`, `run.py:624`)
7. Emit refinement events in `_refine_plan()` (`harmonic.py:512-547`)
8. Wire events through `Naaru` → `run.py` → Studio:
   - Pass callback from `run.py` to `HarmonicPlanner` (`run.py:784`)
   - Ensure `Naaru._emit_event()` forwards events (`naaru.py:191-207`)

**Files to modify**:
- `src/sunwell/adaptive/events.py` — Add event types (reference: `events.py:23-135`)
- `src/sunwell/naaru/planners/harmonic.py` — Add callback parameter and emit events (reference: `harmonic.py:179-223`)
- `src/sunwell/cli/agent/run.py` — Pass event callback to HarmonicPlanner (reference: `run.py:784`, `run.py:335-340`)
- `src/sunwell/naaru/naaru.py` — Ensure events forward correctly (reference: `naaru.py:191-207`)

**Event Propagation Path**:
```
HarmonicPlanner._emit_event() 
  → event_callback(event) 
  → Naaru._emit_event() (if called from Naaru context)
  → run.py emit_json() 
  → stdout (NDJSON)
  → Rust bridge
  → Studio agent.ts handleAgentEvent()
```

**Estimated effort**: 4-6 hours

### Phase 2: Studio UI (Display)

**Goal**: Display planning details in Studio.

**Tasks**:
1. Update `agent.ts` store to handle new events and track progress
2. Create `PlanningPanel.svelte` component
3. Create `PlanningProgress.svelte` component (progress bar)
4. Create `CandidateComparison.svelte` component
5. Create `RefinementTimeline.svelte` component
6. Create `MetricsVisualization.svelte` component
7. Integrate into `Project.svelte` (new "Planning" tab or expandable section)

**Files to create**:
- `studio/src/components/PlanningPanel.svelte`
- `studio/src/components/planning/PlanningProgress.svelte`
- `studio/src/components/planning/CandidateComparison.svelte`
- `studio/src/components/planning/RefinementTimeline.svelte`
- `studio/src/components/planning/MetricsVisualization.svelte`

**Files to modify**:
- `studio/src/stores/agent.ts` — Add event handlers for new planning events (reference: `agent.ts:346-506`)
- `studio/src/routes/Project.svelte` — Add planning panel

**Event Handling Pattern** (reference `agent.ts:346-506`):
```typescript
case 'plan_candidate_start':
  // Update planning progress state
  break;
case 'plan_candidate_generated':
  // Add candidate to list, update progress
  break;
case 'plan_candidate_scored':
  // Update candidate with metrics
  break;
// ... etc
```

**Estimated effort**: 6-8 hours

### Phase 3: Reasoning Capture (Optional)

**Goal**: Capture and display LLM reasoning during planning.

**Tasks**:
1. Add `PLAN_REASONING` event type
2. Modify planning prompts to request chain-of-thought
3. Parse reasoning from LLM responses
4. Emit reasoning events
5. Display reasoning in Studio UI

**Estimated effort**: 4-6 hours (if implemented)

---

## Testing

### Unit Tests

```python
# tests/test_harmonic_planning_visibility.py

async def test_candidate_generation_events():
    """Test that candidate generation emits events."""
    events = []
    
    def capture(event):
        events.append(event)
    
    planner = HarmonicPlanner(
        model=mock_model,
        candidates=3,
        event_callback=capture,
    )
    
    await planner.plan_with_metrics("Build API")
    
    # Verify events emitted
    assert any(e.type == EventType.PLAN_CANDIDATE_START for e in events)
    assert sum(1 for e in events if e.type == EventType.PLAN_CANDIDATE_GENERATED) == 3
    assert any(e.type == EventType.PLAN_CANDIDATES_COMPLETE for e in events)

async def test_scoring_events():
    """Test that scoring emits events with metrics."""
    events = []
    
    planner = HarmonicPlanner(
        model=mock_model,
        candidates=2,
        event_callback=lambda e: events.append(e),
    )
    
    await planner.plan_with_metrics("Build API")
    
    # Verify scored events
    scored_events = [e for e in events if e.type == EventType.PLAN_CANDIDATE_SCORED]
    assert len(scored_events) == 2
    
    # Verify metrics present
    for event in scored_events:
        assert "score" in event.data
        assert "metrics" in event.data
        assert "depth" in event.data["metrics"]

async def test_refinement_events():
    """Test that refinement emits events."""
    events = []
    
    planner = HarmonicPlanner(
        model=mock_model,
        candidates=1,
        refinement_rounds=2,
        event_callback=lambda e: events.append(e),
    )
    
    await planner.plan_with_metrics("Build API")
    
    # Verify refinement events
    refine_starts = [e for e in events if e.type == EventType.PLAN_REFINE_START]
    refine_completes = [e for e in events if e.type == EventType.PLAN_REFINE_COMPLETE]
    
    assert len(refine_starts) > 0
    assert len(refine_completes) > 0
```

### Integration Tests

```python
# tests/test_planning_visibility_integration.py

async def test_full_planning_flow_with_events():
    """Test full planning flow emits all expected events."""
    from sunwell.naaru import Naaru
    
    events = []
    
    naaru = Naaru(
        planner=HarmonicPlanner(model=mock_model, candidates=3),
        event_callback=lambda e: events.append(e),
    )
    
    await naaru.run("Build API", ...)
    
    # Verify event sequence
    event_types = [e.type for e in events]
    
    assert EventType.PLAN_CANDIDATE_START in event_types
    assert EventType.PLAN_CANDIDATE_GENERATED in event_types
    assert EventType.PLAN_CANDIDATE_SCORED in event_types
    assert EventType.PLAN_WINNER in event_types
    
    # Verify winner event has metrics
    winner = next(e for e in events if e.type == EventType.PLAN_WINNER)
    assert "metrics" in winner.data
    assert "selection_reason" in winner.data
```

---

## Risks and Mitigations

### Risk 1: Event Volume

**Risk**: Emitting many events could overwhelm the event stream or Studio UI.

**Mitigation**:
- Use callback presence as signal (if callback exists, emit detailed events)
- Studio can collapse/expand detailed views (progressive disclosure)
- Events are lightweight (just dict construction, no I/O)
- Consider batching if >10 candidates (future optimization)
- Progress updates are lightweight (just numbers)

### Risk 2: Performance Impact

**Risk**: Event emission adds overhead to planning.

**Mitigation**:
- Events are lightweight (just dict construction, no I/O)
- Event callback is optional (no-op if not provided) — matches existing pattern (`naaru.py:200-201`)
- Sync callback (not async) — minimal overhead
- Errors in callback don't break planning (try/except in `_emit_event()`)
- Benchmark: Estimate <5% overhead (needs verification)

### Risk 3: UI Complexity

**Risk**: Too much information could confuse users.

**Mitigation**:
- Collapsible sections (default collapsed)
- Summary view by default, details on demand
- Progressive disclosure (show more as user explores)

---

## Success Metrics

### Phase 1 (Event Emission)
- ✅ All planning events emitted correctly
- ✅ Events include required metrics
- ✅ No performance regression (<5% overhead)

### Phase 2 (Studio UI)
- ✅ Planning panel displays candidate comparison
- ✅ Refinement timeline shows rounds
- ✅ Metrics visualization renders correctly
- ✅ UI responsive (<100ms update latency)

### User Value
- Users can see why plans were selected
- Users can debug poor plan quality
- Users understand harmonic planning value

---

## Future Enhancements

### Phase 2+ Ideas

1. **Plan Comparison Tool** — Compare plans side-by-side
2. **Plan History** — View past plans and their outcomes
3. **Plan Suggestions** — Suggest improvements based on metrics
4. **Reasoning Playback** — Animate reasoning steps
5. **Export Planning Report** — PDF/JSON export of planning details

---

## References

- RFC-038: Harmonic Planning — Multi-candidate optimization
- RFC-053: Studio Agent Bridge — Event streaming
- RFC-040: Plan Persistence — Execution state storage
- RFC-055: Planning View — DAG visualization

---

## Appendix: Event Schema

### PLAN_CANDIDATE_START
```json
{
  "type": "plan_candidate_start",
  "data": {
    "total_candidates": 5,
    "variance_strategy": "prompting"
  }
}
```

### PLAN_CANDIDATE_GENERATED
```json
{
  "type": "plan_candidate_generated",
  "data": {
    "candidate_index": 0,
    "artifact_count": 8,
    "progress": 1,
    "total_candidates": 5,
    "variance_config": {
      "prompt_style": "parallel_first",
      "temperature": 0.2
    }
  }
}
```

### PLAN_CANDIDATE_SCORED
```json
{
  "type": "plan_candidate_scored",
  "data": {
    "candidate_index": 0,
    "score": 87.3,
    "progress": 1,
    "total_candidates": 5,
    "metrics": {
      "depth": 3,
      "width": 4,
      "leaf_count": 8,
      "artifact_count": 12,
      "parallelism_factor": 0.67,
      "balance_factor": 1.33,
      "file_conflicts": 0,
      "estimated_waves": 3
    }
  }
}
```

### PLAN_WINNER (Enhanced)
```json
{
  "type": "plan_winner",
  "data": {
    "tasks": 12,
    "artifact_count": 12,
    "selected_index": 0,
    "total_candidates": 5,
    "metrics": {
      "score": 87.3,
      "depth": 3,
      "width": 4,
      "leaf_count": 8,
      "parallelism_factor": 0.67,
      "balance_factor": 1.33,
      "file_conflicts": 0,
      "estimated_waves": 3
    },
    "selection_reason": "Highest composite score (parallelism + balance - depth penalty)",
    "variance_strategy": "prompting",
    "refinement_rounds": 1,
    "final_score_improvement": 5.2
  }
}
```

### PLAN_REFINE_START
```json
{
  "type": "plan_refine_start",
  "data": {
    "round": 1,
    "total_rounds": 2,
    "current_score": 87.3,
    "improvements_identified": "Critical path is 3 steps. Can any artifacts be parallelized?"
  }
}
```

### PLAN_REFINE_COMPLETE
```json
{
  "type": "plan_refine_complete",
  "data": {
    "round": 1,
    "improved": true,
    "old_score": 87.3,
    "new_score": 92.5,
    "improvement": 5.2
  }
}
```
