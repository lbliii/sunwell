# RFC-112: Observatory — Cinematic AI Cognition Visualizations

**Status**: Draft  
**Created**: 2026-01-23  
**Author**: @llane  
**Depends on**: RFC-097 (Holy Light Theme)  
**Soft dependency**: RFC-084 (Simulacrum v2) — MemoryLattice uses facts/decisions directly; ConceptGraph optional

---

## Summary

Add an **Observatory** tab to Sunwell Studio that visualizes AI cognition in ways that make r/dataisbeautiful weep. Five signature visualizations transform agent events into cinematic, shareable artifacts.

**The thesis**: We have data nobody else has — the inside of structured AI cognition. Visualize the *transformation*, not just the result.

---

## Motivation

### The Problem

Sunwell captures 35+ event types during agent execution:
- Plan candidates, scoring, refinement
- Resonance iterations with quality deltas
- Memory facts, dead ends, decisions
- Task execution, validation cascades
- Harmonic synthesis with multi-candidate voting

This data is **gold** but currently invisible. The Studio shows functional UI, not the magic happening underneath.

### The Opportunity

**r/dataisbeautiful criteria**:
1. Novel visualizations of interesting data
2. Distinctive aesthetics (not generic charts)
3. Animated/real-time data
4. A "wait, WHAT?" moment

**Sunwell's edge**: Nobody visualizes AI thinking. We can own this space.

### Goals

1. Create 5 signature visualizations that showcase Sunwell's cognition
2. Make them shareable (export GIF/video, embed in docs)
3. Integrate with existing agent event stream
4. Maintain Holy Light aesthetic consistency

### Non-Goals

1. **Custom visualization builder** — Users cannot create their own visualizations; we provide 5 curated experiences
2. **Data editing** — Observatory is read-only; no modifying memory, events, or execution state
3. **Historical playback across sessions** — Visualizations show current/recent runs, not arbitrary past sessions
4. **Mobile-first design** — Desktop experience prioritized; mobile is functional but not optimized
5. **Real-time collaboration** — Single-user viewing; no shared cursors or live sync between users

---

## User Journeys

### Persona 1: The Curious Developer

**Who**: Developer using Sunwell for their project  
**Trigger**: "Why did that take so long?" / "What's happening in there?"

```
JOURNEY: Understanding Execution
────────────────────────────────────────────────────────────────

1. Developer runs: sunwell "Build auth system"
2. Notices it's taking a while, wants to see progress
3. Clicks "🔭 Observatory" button (or it auto-opens during execution)
4. Sees ExecutionCinema showing:
   - 4 tasks running in parallel
   - 2 blocked waiting on dependencies
   - Particles flowing along completed edges
5. Developer understands the bottleneck is "database schema" task
6. Continues working while watching progress visually

OUTCOME: Anxiety reduced, progress visible, trust increased
```

### Persona 2: The Skeptic

**Who**: Senior dev evaluating whether Sunwell is worth adopting  
**Trigger**: "Is this snake oil or does it actually work?"

```
JOURNEY: Proving the Thesis
────────────────────────────────────────────────────────────────

1. Skeptic opens Observatory → ModelParadox tab
2. Sees animated chart:
   - 3B raw: flat at 1.0 quality
   - 3B + Sunwell: rockets to 8.5 (+750%)
   - 20B raw: mediocre 6.0
   - 20B + Sunwell: 9.5
3. Skeptic thinks "okay, show me"
4. Clicks "▶ Run Live Demo" button
5. Watches ResonanceWave in real-time:
   - R0: terrible code (score: 1.0)
   - R1: adds type hints (score: 3.2)
   - R2: adds docstring (score: 5.5)
   - R3: adds error handling (score: 7.8)
   - R4: polish (score: 8.5)
6. Code morphs on screen — they watch the transformation

OUTCOME: Skeptic convinced by visual proof, not marketing claims
```

### Persona 3: The Content Creator

**Who**: DevRel, blogger, or developer who wants to share on Reddit/Twitter  
**Trigger**: "This is cool, I want to show people"

```
JOURNEY: Creating Shareable Content
────────────────────────────────────────────────────────────────

1. User runs a goal, sees beautiful execution flow
2. Clicks "🔭 Observatory" 
3. Selects visualization (e.g., PrismFracture)
4. Enables "Demo Mode" with sample data
5. Clicks "📹 Export" → GIF (10 seconds, perfect loop)
6. Downloads sunwell-prism-fracture.gif
7. Posts to r/dataisbeautiful:
   "I visualized what happens inside an AI agent's mind [OC]"
8. Front page, 5K upvotes

OUTCOME: Organic marketing, community growth, user evangelism
```

### Persona 4: The Debugger

**Who**: Developer whose execution failed or produced unexpected results  
**Trigger**: "Why did it make that choice?" / "What went wrong?"

```
JOURNEY: Debugging a Decision
────────────────────────────────────────────────────────────────

1. Developer's execution produced weird code
2. Opens Observatory → PrismFracture tab
3. Replays the harmonic synthesis:
   - Architect proposed 6-file solution (score: 72)
   - Critic proposed 2-file solution (score: 85) ← Winner
   - Simplifier proposed 1-file monolith (score: 91)
4. Developer sees: "Oh, Simplifier won because it scored highest"
5. Realizes: the scoring favored simplicity over modularity
6. Adjusts their prompt or lens to weight modularity higher
7. Reruns with better result

OUTCOME: Transparency into AI decisions, user learns to guide better
```

### Persona 5: The Learner

**Who**: New Sunwell user trying to understand concepts  
**Trigger**: "What even is 'harmonic synthesis'?"

```
JOURNEY: Learning by Watching
────────────────────────────────────────────────────────────────

1. User reads about "Harmonic Synthesis" in docs
2. Concept is abstract, hard to grasp
3. Opens Observatory → PrismFracture tab
4. Watches animation:
   - Single beam enters prism
   - Refracts into 5 colored beams (personas)
   - Each beam shows what that persona generated
   - Beams converge into final output
5. User has "aha!" moment — visual makes it click

OUTCOME: Faster learning, reduced documentation burden
```

### Persona 6: The Project Analyst

**Who**: Developer returning to a project after time away  
**Trigger**: "What does Sunwell know about this codebase?"

```
JOURNEY: Reviewing Project Memory
────────────────────────────────────────────────────────────────

1. Developer opens Observatory → MemoryLattice tab
2. Sees force-directed graph of everything Sunwell learned:
   - 89 facts (blue nodes)
   - 23 decisions (gold nodes, anchored)
   - 12 dead ends (red nodes, drifting to edges)
3. Clicks on "OAuth" decision node:
   - Shows: "Decided to use OAuth over JWT"
   - Reason: "JWT approach failed 3 times"
   - Related facts connected by edges
4. Scrubs timeline slider to see how knowledge grew over 4 weeks
5. Understands project history at a glance

OUTCOME: Context recovery, institutional knowledge visible
```

---

## Use Case Matrix

| Visualization | Primary Use Case | Secondary Use Cases |
|---|---|---|
| **ResonanceWave** | Watch quality improvement live | Debug refinement, prove thesis |
| **PrismFracture** | Understand multi-perspective synthesis | Debug selection, learn concepts |
| **MemoryLattice** | Review project knowledge | Recover context, spot dead ends |
| **ExecutionCinema** | Monitor live execution | Debug bottlenecks, reduce anxiety |
| **ModelParadox** | Prove small models work | Convince skeptics, shareable content |

---

## Entry Points

| Entry Point | When | Destination |
|---|---|---|
| "🔭 Observatory" button on Home | Anytime | Default to last used viz |
| Auto-open during long execution | Execution > 30s | ExecutionCinema (live) |
| "🔍 Why this?" button on result | After execution completes | PrismFracture (replay) |
| "📊 Show improvement" on code | After resonance completes | ResonanceWave (replay) |
| `sunwell observatory` CLI | Anytime | Opens Studio to Observatory |

---

## Design

### Architecture

The Observatory follows existing Studio patterns:

1. **Route constant** in `lib/constants.ts`
2. **State/navigation** in `stores/app.svelte.ts`
3. **Route component** in `routes/Observatory.svelte`
4. **Feature components** in `components/observatory/` (following `demo/`, `coordinator/` pattern)
5. **Primitives** in `components/primitives/` (new animation primitives)

```
┌─────────────────────────────────────────────────────────────────┐
│                         STUDIO                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  App.svelte routing:                                            │
│  ─────────────────────────────────────────────────────────────  │
│  HOME │ PROJECT │ PLANNING │ DEMO │ GALLERY │ OBSERVATORY       │
│                                                     ↑ NEW       │
└─────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │      routes/Observatory.svelte        │
                    │                                       │
                    │  ┌─────────────────────────────────┐  │
                    │  │   ObservatoryPanel (from demo/) │  │
                    │  │   pattern — wraps the content   │  │
                    │  └─────────────────────────────────┘  │
                    │                                       │
                    │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐     │
                    │  │Reson│ │Prism│ │Latti│ │Parad│ ... │
                    │  └─────┘ └─────┘ └─────┘ └─────┘     │
                    │      └── viz selector tabs ──┘       │
                    └───────────────────────────────────────┘
```

### Component Hierarchy

Following existing patterns (`components/demo/`, `components/coordinator/`):

```
src/
├── lib/
│   └── constants.ts                  # ADD: Route.OBSERVATORY
│
├── stores/
│   └── app.svelte.ts                 # ADD: goToObservatory(), isObservatory
│
├── routes/
│   └── Observatory.svelte            # NEW: Route (like Demo.svelte)
│
├── components/
│   ├── observatory/                  # NEW: Feature module
│   │   ├── index.ts
│   │   ├── ObservatoryPanel.svelte   # Main container (like DemoPanel)
│   │   ├── ResonanceWave.svelte      # Quality emergence visualization
│   │   ├── PrismFracture.svelte      # Multi-perspective synthesis
│   │   ├── MemoryLattice.svelte      # Force-directed knowledge graph
│   │   ├── ExecutionCinema.svelte    # Enhanced DAG with particles
│   │   └── ModelParadox.svelte       # Quality vs. cost/params chart
│   │
│   ├── primitives/                   # Existing primitives dir
│   │   ├── AnimatedPath.svelte       # NEW: SVG path draw animation
│   │   ├── GlowingNode.svelte        # NEW: Node with pulse/glow
│   │   ├── ParticleStream.svelte     # NEW: Particles along path
│   │   └── ... existing primitives
│   │
│   └── index.ts                      # ADD: export * from './observatory'
```

---

## The Five Visualizations

### 1. Resonance Wave

**What it shows**: Quality score emergence through resonance iterations.

**Data contract**:
```typescript
interface ResonanceData {
  iterations: Array<{
    round: number;
    score: number;
    delta: number;
    improvements: string[];
    code_snapshot?: string;
  }>;
  model: string;
  final_improvement_pct: number;
}
```

**Visual design**:
```
┌────────────────────────────────────────────────────────────────┐
│  RESONANCE WAVE                                    ⬚ ↗ 📹      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  QUALITY                                                       │
│    10 ┤                                    ╭──────● 9.5        │
│       │                                ╭───╯                   │
│     8 ┤                            ╭───╯         ✦ +850%       │
│       │                        ╭───╯               ✧           │
│     6 ┤                    ╭───╯                   ⋆            │
│       │                ╭───╯                                   │
│     4 ┤            ╭───╯                                       │
│       │        ╭───╯                                           │
│     2 ┤    ╭───╯                                               │
│       │╭───╯                                                   │
│     1 ●────────────────────────────────────────────────────────│
│       └──┬────┬────┬────┬────┬────┬────┬────────────────────── │
│         R0   R1   R2   R3   R4   R5   R6                       │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ def add(a, b): return a + b                             │   │
│  │ ────────────────────── R0 ───────────────────────────── │   │
│  │ def add(a: int | float, b: int | float) -> int | float: │   │
│  │     """Returns the sum of two numbers.                  │   │
│  │     ...                                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  llama3.2:3b │ 7 iterations │ 12.4s total                      │
└────────────────────────────────────────────────────────────────┘
```

**Animation sequence**:
1. Wave draws from left to right, tracking mouse/time
2. Each iteration pulses with golden glow
3. Code panel morphs between snapshots
4. Motes rise from the final peak
5. Improvement percentage animates (counter)

**Events consumed**:
- `plan_refine_start`
- `plan_refine_attempt`
- `plan_refine_complete`
- `plan_refine_final`

---

### 2. Prism Fracture

**What it shows**: Single prompt refracting into multiple perspectives, then converging.

**Data contract**:
```typescript
interface PrismData {
  input_prompt: string;
  candidates: Array<{
    index: number;
    persona?: string;        // "architect", "critic", "simplifier", etc.
    variance_config?: object;
    artifact_count: number;
    score: number;
    description?: string;
  }>;
  winner: {
    index: number;
    selection_reason: string;
    final_score: number;
  };
  technique: string;         // "harmonic_5", "variance_3", etc.
}
```

**Visual design**:
```
┌────────────────────────────────────────────────────────────────┐
│  PRISM FRACTURE                                    ⬚ ↗ 📹      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                              ╱╲                                │
│                             ╱  ╲                               │
│                            ╱    ╲                              │
│     ━━━━━━━━━━━━━━━━━━━━━╱      ╲━━━━━● architect (score: 85) │
│     "Build a REST API    ╱   🔮   ╲━━━━● critic (score: 72)    │
│      with auth"         ╱ SUNWELL  ╲━━━● simplifier (score: 91)│
│     ━━━━━━━━━━━━━━━━━━╱   PRISM    ╲━━● user (score: 78)      │
│                       ╱              ╲━● adversary (score: 65) │
│                      ╱________________╲                        │
│                              │                                 │
│                              ▼                                 │
│                      ┌──────────────┐                          │
│                      │   WINNER:    │                          │
│                      │  simplifier  │                          │
│                      │   score: 91  │                          │
│                      └──────────────┘                          │
│                                                                │
│  harmonic_5 │ 5 candidates │ best: simplifier (+19% vs median) │
└────────────────────────────────────────────────────────────────┘
```

**Animation sequence**:
1. Input beam enters from left (golden line)
2. Hits prism, refracts into 5 colored beams
3. Each beam shows candidate card (slides in)
4. Scores appear with staggered timing
5. Winner beam glows brightest, others fade
6. Beams converge into output
7. Rising motes celebrate completion

**Events consumed**:
- `plan_candidate_start`
- `plan_candidate_generated`
- `plan_candidate_scored`
- `plan_winner`

---

### 3. Memory Lattice

**What it shows**: Project knowledge graph growing over time.

**Data contract**:
```typescript
interface LatticeData {
  nodes: Array<{
    id: string;
    label: string;
    category: 'fact' | 'decision' | 'pattern' | 'dead_end';
    timestamp: number;
    recall_count: number;
  }>;
  edges: Array<{
    source: string;
    target: string;
    relation: 'elaborates' | 'contradicts' | 'depends_on' | 'supersedes';
    confidence: number;
  }>;
  timeline?: {
    start: number;
    end: number;
  };
}
```

**Visual design**:
```
┌────────────────────────────────────────────────────────────────┐
│  MEMORY LATTICE                                    ⬚ ↗ 📹      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│            ┌──────┐                                            │
│            │OAuth │◄──contradicts──┐                           │
│            │  ◉   │                │                           │
│            └──┬───┘                │                           │
│        decided│on                  │                           │
│               ▼                    │                           │
│     ┌────────────────┐        ┌────┴───┐                       │
│     │  auth module   │────────│  JWT   │ ← DEAD END            │
│     │  ◉ (recalled)  │        │  ◎     │   (3 failures)        │
│     └───────┬────────┘        └────────┘                       │
│             │ depends_on                                       │
│             ▼                                                  │
│       ┌───────────┐          ┌─────────────┐                   │
│       │billing.py │◄─────────│  patterns   │                   │
│       │   ◎       │          │ snake_case  │                   │
│       │  fragile  │          │ type hints  │                   │
│       └───────────┘          └─────────────┘                   │
│                                                                │
│  ─────────────────────────────────────────────────────────────│
│  ▸ ──────────────────────●────────────────────────────── NOW   │
│    Jan 1                 │                          Jan 23     │
│                     [playback]                                 │
│                                                                │
│  Facts: 89 │ Dead Ends: 12 │ Decisions: 23 │ Age: 4 weeks      │
└────────────────────────────────────────────────────────────────┘
```

**Animation modes**:
1. **Live mode**: Nodes pulse when recalled, appear when learned
2. **Playback mode**: Scrub timeline to see graph grow over time
3. **Focus mode**: Click node to highlight connections

**Force-directed physics**:
- Facts attract related facts
- Dead ends repel (drift to edges)
- Decisions anchor (heavier mass)
- Recently recalled nodes glow

**Events consumed**:
- `memory_learning` — new facts appear as nodes
- `memory_dead_end` — failed approaches appear as red nodes
- `memory_loaded` — initial state on session load

**Data sources** (graceful degradation):
1. **Primary**: Facts and decisions from `.sunwell/memory/` (always available)
2. **Optional**: ConceptGraph edges from RFC-084 (if populated — adds relation edges)
3. **Fallback**: If no ConceptGraph, edges are inferred from co-occurrence in same turn

---

### 4. Execution Cinema

**What it shows**: Enhanced DAG with cinematic particle effects.

**Data contract**: Existing `DagNode[]` + `DagEdge[]` from `stores/dag.svelte`

**Visual enhancements over current DAG**:

```
┌────────────────────────────────────────────────────────────────┐
│  EXECUTION CINEMA                                  ⬚ ↗ 📹      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│      ┌─────────┐              ┌─────────┐         ┌─────────┐ │
│      │ models/ │──────────────│  auth/  │─────────│  api/   │ │
│      │ ▓▓▓▓▓▓▓ │ ●●●●●●●●●●●▸│ ▓▓▓▓░░░ │ ○○○○○○▸│ ░░░░░░░ │ │
│      │ 100%  ✓ │              │  70%    │         │   0%    │ │
│      └────┬────┘              └────┬────┘         └────┬────┘ │
│           │                        │                   │      │
│           │    ●●●●●●●●●●●▸        │                   │      │
│           └────────────────────────┴───────────────────┘      │
│                                    │                          │
│                                    ▼                          │
│                              ┌───────────┐                    │
│                              │  tests/   │    ✦ ✧             │
│                              │ ░░░░░░░░░ │   ✧  ✦             │
│                              │   0%      │  ⋆   ✧             │
│                              └───────────┘  (motes)           │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░  45% complete    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [LIVE] auth/middleware.py: Adding OAuth verification... │   │
│  │ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░  generating...                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  2 parallel │ 5/12 tasks │ 34s elapsed │ ~45s remaining        │
└────────────────────────────────────────────────────────────────┘

LEGEND:
  ●●●●▸  = Particles flowing (data dependency being satisfied)
  ○○○○▸  = Particles waiting (blocked dependency)
  ✦ ✧ ⋆  = Rising motes (task completed)
  ▓▓▓░░░ = Progress bar within node
```

**New effects**:
1. **Particle streams**: Golden dots flow along edges (→ complete), dim dots wait (→ blocked)
2. **Active node glow**: Currently executing node pulses with Holy Light aura
3. **Completion celebration**: Motes rise from node, ripple propagates to children
4. **Camera follow**: Auto-pan to active work (optional)
5. **Edge labels**: Show artifact being transferred

**Events consumed**:
- `task_start`, `task_progress`, `task_complete`, `task_failed`
- `gate_start`, `gate_pass`, `gate_fail`
- `validate_*` events

---

### 5. Model Paradox

**What it shows**: Quality vs. cost/parameters — proving small models + structure beats big models raw.

**Data contract**:
```typescript
interface ParadoxData {
  comparisons: Array<{
    model: string;
    params: string;              // "3.2B", "20.9B"
    cost_per_run: number;        // $0, $0.02, etc.
    conditions: Array<{
      technique: 'bare' | 'sunwell' | 'harmonic' | 'resonance';
      score: number;
      improvement_pct?: number;
    }>;
  }>;
  thesis_claim: string;
}
```

**Visual design**:
```
┌────────────────────────────────────────────────────────────────┐
│  MODEL PARADOX                                     ⬚ ↗ 📹      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  "Small models contain hidden capability.                      │
│   Structured cognition reveals it."                            │
│                                                                │
│  QUALITY                                                       │
│    10 ┤                                    ╭●━━━● 20B+Sunwell  │
│       │                                ╭━━━╯       (9.5)       │
│     9 ┤                            ╭━━━╯                       │
│       │                                    ╭●━━● 3B+Sunwell    │
│     8 ┤                                ╭━━━╯      (8.5)        │
│       │                            ╭━━━╯                       │
│     7 ┤                        ╭━━━╯                           │
│       │                                                        │
│     6 ┤                        ●───────────────● 20B (raw)     │
│       │                    ●───                                │
│     5 ┤                ●───                                    │
│       │                                                        │
│     4 ┤                                                        │
│       │                                                        │
│     3 ┤                                                        │
│       │                                                        │
│     2 ┤    ●───●───●───●───●───●───●───●───● 3B (raw)         │
│       │●───                                                    │
│     1 ┤    └───────────────────────────────────────────────── │
│       └──┬─────┬─────┬─────┬─────┬─────┬─────┬──────────────  │
│         $0   $0.01  $0.05  $0.10  $0.50  $1    $5   COST/run   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ● 3B raw: 1.0    ━━▶  3B+Sunwell: 8.5   (+750%)       │   │
│  │  ● 20B raw: 6.0   ━━▶  20B+Sunwell: 9.5  (+58%)        │   │
│  │                                                         │   │
│  │  💡 $0 beats $50 with the right architecture.          │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

**Animation sequence**:
1. Raw model lines draw first (flat, unimpressive)
2. "SUNWELL ACTIVATES" flash
3. +Sunwell lines rocket upward
4. Delta percentages counter-animate
5. Punchline fades in: "$0 beats $50..."

**Data source**: `benchmark/results/thesis_verification.json`

---

## Integration Changes

### 1. Add Route Constant

```typescript
// lib/constants.ts — add to Route object

export const Route = {
  HOME: 'home',
  PROJECT: 'project',
  PROJECTS: 'projects',
  PREVIEW: 'preview',
  PLANNING: 'planning',
  LIBRARY: 'library',
  INTERFACE: 'interface',
  WRITER: 'writer',
  DEMO: 'demo',
  GALLERY: 'gallery',
  EVALUATION: 'evaluation',
  OBSERVATORY: 'observatory',  // ← NEW
} as const;
```

### 2. Add App Store Navigation

```typescript
// stores/app.svelte.ts — add getter and action

export const app = {
  // ... existing getters
  get isObservatory() { return _route === Route.OBSERVATORY; },  // ← NEW
};

export function goToObservatory(): void {  // ← NEW
  _route = Route.OBSERVATORY;
}
```

### 3. Add Route to App.svelte

```svelte
<!-- App.svelte — add import and route -->
<script lang="ts">
  // ... existing imports
  import Observatory from './routes/Observatory.svelte';  // ← NEW
</script>

<div class="app-container">
  {#if app.route === Route.HOME}
    <Home />
  <!-- ... existing routes ... -->
  {:else if app.route === Route.OBSERVATORY}
    <Observatory />
  {/if}
</div>
```

### 4. Create Observatory Route

Following the `Demo.svelte` pattern (simple wrapper):

```svelte
<!--
  Observatory.svelte — AI Cognition Visualizations (RFC-112)
  
  Standalone route to showcase Sunwell's thinking processes.
  Access via: goToObservatory() or future nav integration.
-->
<script lang="ts">
  import { ObservatoryPanel } from '../components';
  import { goHome } from '../stores/app.svelte';
</script>

<div class="observatory-route">
  <button class="back-button" onclick={goHome}>
    ← Back
  </button>
  
  <ObservatoryPanel />
</div>

<style>
  .observatory-route {
    min-height: 100vh;
    background: var(--bg-primary);
    position: relative;
  }
  
  .back-button {
    position: fixed;
    top: var(--space-4);
    left: var(--space-4);
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    z-index: 10;
  }
  
  .back-button:hover {
    color: var(--text-primary);
    border-color: var(--border-default);
  }
</style>
```

### 5. Add Entry Point from Home

Similar to the "🔮 Try Demo" button:

```svelte
<!-- Home.svelte — add Observatory trigger -->
<button class="observatory-trigger" onclick={goToObservatory} title="Watch AI cognition in real-time">
  🔭 Observatory
</button>
```

### 6. Export Components

```typescript
// components/index.ts — add export
export * from './observatory';
```

---

## ObservatoryPanel Component

The main container (following `DemoPanel` pattern):

```svelte
<!--
  ObservatoryPanel — Main container for visualizations (RFC-112)
  
  Usage: <ObservatoryPanel />
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import ResonanceWave from './ResonanceWave.svelte';
  import PrismFracture from './PrismFracture.svelte';
  import MemoryLattice from './MemoryLattice.svelte';
  import ExecutionCinema from './ExecutionCinema.svelte';
  import ModelParadox from './ModelParadox.svelte';
  
  type Viz = 'resonance' | 'prism' | 'lattice' | 'cinema' | 'paradox';
  
  const visualizations = [
    { id: 'resonance', icon: '📈', label: 'Resonance', desc: 'Quality emergence' },
    { id: 'prism', icon: '🔮', label: 'Prism', desc: 'Multi-perspective' },
    { id: 'lattice', icon: '🧠', label: 'Memory', desc: 'Knowledge graph' },
    { id: 'cinema', icon: '🎬', label: 'Execution', desc: 'Live DAG' },
    { id: 'paradox', icon: '⚡', label: 'Paradox', desc: 'Model comparison' },
  ] as const;
  
  let activeViz = $state<Viz>('resonance');
  let isLive = $state(true);
</script>

<div class="observatory" in:fade={{ duration: 200 }}>
  <header class="observatory-header">
    <div class="title-section">
      <h1 class="title">🔭 Observatory</h1>
      <p class="subtitle">Watch AI cognition in real-time</p>
    </div>
    
    <div class="controls">
      <label class="live-toggle">
        <input type="checkbox" bind:checked={isLive} />
        <span>Live</span>
      </label>
      <button class="export-btn">📹 Export</button>
    </div>
  </header>
  
  <nav class="viz-tabs">
    {#each visualizations as viz, i}
      <button
        class="viz-tab"
        class:active={activeViz === viz.id}
        onclick={() => activeViz = viz.id}
        in:fly={{ y: 20, delay: i * 50, duration: 200 }}
      >
        <span class="tab-icon">{viz.icon}</span>
        <span class="tab-label">{viz.label}</span>
        <span class="tab-desc">{viz.desc}</span>
      </button>
    {/each}
  </nav>
  
  <main class="viz-canvas">
    {#if activeViz === 'resonance'}
      <ResonanceWave {isLive} />
    {:else if activeViz === 'prism'}
      <PrismFracture {isLive} />
    {:else if activeViz === 'lattice'}
      <MemoryLattice {isLive} />
    {:else if activeViz === 'cinema'}
      <ExecutionCinema {isLive} />
    {:else if activeViz === 'paradox'}
      <ModelParadox />
    {/if}
  </main>
  
  <footer class="observatory-footer">
    <span class="branding">sunwell.ai</span>
  </footer>
</div>

<style>
  .observatory {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-6);
  }
  
  .observatory-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
  }
  
  .title {
    font-family: var(--font-serif);
    font-size: var(--text-3xl);
    color: var(--text-gold);
    margin: 0;
  }
  
  .subtitle {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: var(--space-1) 0 0;
  }
  
  .controls {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }
  
  .live-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    cursor: pointer;
  }
  
  .export-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .export-btn:hover {
    background: var(--accent-hover);
    color: var(--text-gold);
    border-color: var(--border-emphasis);
  }
  
  .viz-tabs {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
  }
  
  .viz-tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .viz-tab:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
  }
  
  .viz-tab.active {
    background: var(--accent-hover);
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .tab-icon {
    font-size: var(--text-2xl);
  }
  
  .tab-label {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .viz-tab.active .tab-label {
    color: var(--text-gold);
  }
  
  .tab-desc {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .viz-canvas {
    flex: 1;
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    min-height: 500px;
    overflow: hidden;
  }
  
  .observatory-footer {
    padding-top: var(--space-4);
    text-align: center;
  }
  
  .branding {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
</style>
```

---

## Animation Primitives

New primitives added to `components/primitives/` (alongside existing `CodeBlock.svelte`, `Chart.svelte`, etc.):

### AnimatedPath.svelte

```svelte
<!--
  AnimatedPath — SVG path that draws itself
  
  Location: components/primitives/AnimatedPath.svelte
  
  Usage:
    <AnimatedPath 
      d="M 0,50 Q 50,0 100,50" 
      duration={1000} 
      color="var(--radiant-gold)"
      strokeWidth={2}
    />
-->
<script lang="ts">
  interface Props {
    d: string;
    duration?: number;
    delay?: number;
    color?: string;
    strokeWidth?: number;
    glow?: boolean;
  }
  
  let { 
    d, 
    duration = 1000, 
    delay = 0,
    color = 'var(--ui-gold)',
    strokeWidth = 2,
    glow = false
  }: Props = $props();
  
  let pathRef: SVGPathElement;
  let pathLength = $state(0);
  
  $effect(() => {
    if (pathRef) {
      pathLength = pathRef.getTotalLength();
    }
  });
</script>

<path
  bind:this={pathRef}
  {d}
  fill="none"
  stroke={color}
  stroke-width={strokeWidth}
  stroke-linecap="round"
  class:glow
  style="
    stroke-dasharray: {pathLength};
    stroke-dashoffset: {pathLength};
    animation: draw {duration}ms ease-out {delay}ms forwards;
  "
/>

<style>
  @keyframes draw {
    to {
      stroke-dashoffset: 0;
    }
  }
  
  .glow {
    filter: drop-shadow(0 0 4px var(--radiant-gold-30));
  }
</style>
```

### ParticleStream.svelte

```svelte
<!--
  ParticleStream — Particles flowing along a path
  
  Usage:
    <ParticleStream 
      path="M 0,0 L 100,100" 
      count={10}
      speed={2000}
      active={true}
    />
-->
<script lang="ts">
  interface Props {
    path: string;
    count?: number;
    speed?: number;
    active?: boolean;
    color?: string;
  }
  
  let { 
    path, 
    count = 10, 
    speed = 2000,
    active = true,
    color = 'var(--radiant-gold)'
  }: Props = $props();
  
  let particles = $derived(
    Array(count).fill(null).map((_, i) => ({
      delay: (i / count) * speed,
      size: 3 + Math.random() * 2,
    }))
  );
</script>

{#if active}
  <g class="particle-stream">
    <!-- Invisible path for motion reference -->
    <path id="stream-path" d={path} fill="none" stroke="none" />
    
    {#each particles as particle, i}
      <circle
        r={particle.size}
        fill={color}
        class="particle"
        style="
          --delay: {particle.delay}ms;
          --duration: {speed}ms;
        "
      >
        <animateMotion
          dur="{speed}ms"
          repeatCount="indefinite"
          begin="{particle.delay}ms"
        >
          <mpath href="#stream-path" />
        </animateMotion>
      </circle>
    {/each}
  </g>
{/if}

<style>
  .particle {
    opacity: 0;
    animation: particleFade var(--duration) ease-in-out var(--delay) infinite;
    filter: drop-shadow(0 0 3px var(--radiant-gold-40));
  }
  
  @keyframes particleFade {
    0%, 100% { opacity: 0; }
    20%, 80% { opacity: 1; }
  }
</style>
```

### GlowingNode.svelte

```svelte
<!--
  GlowingNode — Node with pulse/active/complete states
  
  Usage:
    <GlowingNode 
      x={100} y={100} 
      status="active"
      label="auth/"
      progress={0.7}
    />
-->
<script lang="ts">
  interface Props {
    x: number;
    y: number;
    width?: number;
    height?: number;
    label: string;
    status: 'pending' | 'active' | 'complete' | 'failed';
    progress?: number;
  }
  
  let { x, y, width = 120, height = 60, label, status, progress = 0 }: Props = $props();
  
  let statusColor = $derived({
    pending: 'var(--text-tertiary)',
    active: 'var(--info)',
    complete: 'var(--success)',
    failed: 'var(--error)',
  }[status]);
</script>

<g class="glowing-node" class:active={status === 'active'} class:complete={status === 'complete'}>
  <!-- Glow effect (active only) -->
  {#if status === 'active'}
    <rect
      x={x - width/2 - 4}
      y={y - height/2 - 4}
      width={width + 8}
      height={height + 8}
      rx="12"
      fill="none"
      stroke="var(--info)"
      stroke-width="2"
      class="pulse-ring"
    />
  {/if}
  
  <!-- Main node -->
  <rect
    x={x - width/2}
    y={y - height/2}
    {width}
    {height}
    rx="8"
    fill="var(--bg-secondary)"
    stroke={statusColor}
    stroke-width="1.5"
  />
  
  <!-- Progress bar -->
  {#if progress > 0 && progress < 1}
    <rect
      x={x - width/2 + 8}
      y={y + height/2 - 12}
      width={(width - 16) * progress}
      height="4"
      rx="2"
      fill={statusColor}
    />
  {/if}
  
  <!-- Label -->
  <text
    {x}
    y={y}
    text-anchor="middle"
    dominant-baseline="middle"
    fill="var(--text-primary)"
    font-size="12"
    font-family="var(--font-mono)"
  >
    {label}
  </text>
</g>

<style>
  .pulse-ring {
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% {
      opacity: 0.3;
      transform: scale(1);
    }
    50% {
      opacity: 0.8;
      transform: scale(1.02);
    }
  }
  
  .complete {
    animation: completeCelebrate 0.5s ease-out;
  }
  
  @keyframes completeCelebrate {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }
</style>
```

---

## Export System

### GIF/Video Export

```typescript
// lib/export.ts
import { toPng } from 'html-to-image';

interface ExportOptions {
  format: 'gif' | 'webm' | 'png-sequence';
  fps: number;
  duration: number;     // seconds
  width: number;
  height: number;
}

export async function exportVisualization(
  element: HTMLElement,
  options: ExportOptions
): Promise<Blob> {
  const frames: string[] = [];
  const frameCount = options.fps * options.duration;
  const frameDelay = 1000 / options.fps;
  
  // Capture frames
  for (let i = 0; i < frameCount; i++) {
    const dataUrl = await toPng(element, {
      width: options.width,
      height: options.height,
      backgroundColor: '#0d0d0d',
    });
    frames.push(dataUrl);
    await new Promise(r => setTimeout(r, frameDelay));
  }
  
  // Encode based on format
  if (options.format === 'gif') {
    return encodeGif(frames, options);
  } else if (options.format === 'webm') {
    return encodeWebM(frames, options);
  }
  // ... etc
}
```

### Shareable Embed

```svelte
<!-- ObservatoryCard.svelte -->
<script lang="ts">
  interface Props {
    title: string;
    subtitle?: string;
    onExport?: () => void;
    children: Snippet;
  }
  
  let { title, subtitle, onExport, children }: Props = $props();
  let isRecording = $state(false);
</script>

<div class="observatory-card">
  <header class="card-header">
    <div class="card-title">
      <h2>{title}</h2>
      {#if subtitle}<p>{subtitle}</p>{/if}
    </div>
    
    <div class="card-actions">
      <button onclick={() => {}} title="Fullscreen">⬚</button>
      <button onclick={() => {}} title="Share">↗</button>
      <button 
        onclick={onExport} 
        title="Export GIF"
        class:recording={isRecording}
      >
        📹
      </button>
    </div>
  </header>
  
  <div class="card-canvas">
    {@render children()}
  </div>
  
  <footer class="card-footer">
    <span class="branding">sunwell.ai</span>
    <span class="timestamp">{new Date().toLocaleDateString()}</span>
  </footer>
</div>
```

---

## Design Alternatives Considered

### Option A: Cinematic Visualizations (Recommended)

**Approach**: Custom SVG/Canvas animations with particles, glows, and physics simulations.

**Pros**:
- Differentiated aesthetic — nobody else has this
- Shareable artifacts drive organic growth
- Emotional connection through motion

**Cons**:
- Higher implementation effort (5 weeks)
- Performance tuning required
- Export encoding adds complexity

### Option B: Enhanced Charts

**Approach**: Use existing charting library (Chart.js, Recharts) with Holy Light theming.

**Pros**:
- Faster implementation (2 weeks)
- Proven libraries, fewer bugs
- Better accessibility out of box

**Cons**:
- Looks like every other dashboard
- No "wow" factor for viral potential
- Harder to differentiate

### Decision

**Option A selected** because Sunwell's thesis is that we expose what others hide. Generic charts don't communicate that. The extra effort is justified by:
1. Marketing leverage (r/dataisbeautiful potential)
2. User trust through transparency
3. Educational value (concepts become visual)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **60fps not achievable with 100+ nodes** | Medium | High | Use SVG for <50 nodes, WebGL (via PixiJS) for larger graphs. Benchmark in Phase 2. |
| **GIF export too slow/large** | Medium | Medium | Cap at 10s duration, 720p resolution. Use WebM as alternative. Lazy-load encoder. |
| **ConceptGraph not populated** | High | Low | MemoryLattice uses facts/decisions directly; edges inferred from co-occurrence. ConceptGraph optional. |
| **Animations cause motion sickness** | Low | Medium | Add "Reduce Motion" toggle respecting `prefers-reduced-motion`. Disable particles, use fades. |
| **Event stream overwhelms UI** | Medium | Medium | Throttle updates to 30fps max. Batch events. Drop frames gracefully. |
| **Visualization not useful for debugging** | Low | High | Include data export button (JSON). Add click-to-inspect on nodes. |

---

## Implementation Plan

### Phase 1: Foundation (Week 1) ✅
- [x] Add `OBSERVATORY` to `Route` const in `lib/constants.ts`
- [x] Add `goToObservatory()` and `isObservatory` to `stores/app.svelte.ts`
- [x] Add Observatory route handling to `App.svelte`
- [x] Create `routes/Observatory.svelte` (simple wrapper)
- [x] Create `components/observatory/` directory with `index.ts`
- [x] Implement `ObservatoryPanel.svelte` (main container)
- [x] Add "🔭 Observatory" button to `Home.svelte` (next to "🔮 Try Demo")

### Phase 2: Animation Primitives (Week 1-2) ✅
- [x] Create `AnimatedPath.svelte` in `components/primitives/`
- [x] Create `GlowingNode.svelte` in `components/primitives/`
- [x] Create `ParticleStream.svelte` in `components/primitives/`
- [x] Export new primitives from `components/primitives/index.ts`
- [ ] **Performance gate**: Verify 60fps with 50 nodes + 100 particles on M1 MacBook Air (baseline device)

### Phase 3: First Visualization (Week 2) ✅
- [x] Implement `ResonanceWave.svelte` in `components/observatory/`
- [x] Wire to resonance events from agent stream
- [x] Add playback controls (scrub, speed)
- [x] Test with demo data

### Phase 4: Remaining Visualizations (Weeks 3-4) ✅
- [x] `PrismFracture.svelte` — harmonic candidate visualization
- [x] `MemoryLattice.svelte` — knowledge graph (simplified, not force-directed yet)
- [x] `ExecutionCinema.svelte` — enhanced DAG with particles
- [x] `ModelParadox.svelte` — animated comparison chart

### Phase 5: Polish & Export (Week 5) ✅
- [x] PNG/GIF export with `html2canvas` (`lib/export.ts`)
- [x] Shareable embed URLs with base64 encoding
- [x] Export modal with format selection (PNG/GIF/JSON)
- [x] Mobile-responsive layouts throughout

---

## Success Criteria

| Criterion | Metric | Target |
|-----------|--------|--------|
| **Visual impact** | Team subjective rating | 8/10 or higher from 3 reviewers |
| **Data fidelity** | Event-to-visual mapping accuracy | 100% of events render correctly |
| **Performance** | Frame rate on M1 MacBook Air | ≥55fps sustained with 50 nodes |
| **Export quality** | GIF file size / duration | <5MB for 10s clip at 720p |
| **Shareability** | Export flow completion | ≤3 clicks from visualization to file |

**Stretch goal**: r/dataisbeautiful post gets >1000 upvotes 😏

---

## Open Questions

1. ~~**WebGL vs SVG**~~ → Resolved: SVG for <50 nodes, WebGL for larger (see Risks)
2. **Live vs Replay**: Recommend both for ResonanceWave/ExecutionCinema; replay-only for PrismFracture/ModelParadox
3. **Benchmark data**: Yes, `ModelParadox` should watch `benchmark/results/` and auto-refresh on change
4. **Sound design**: Defer to Phase 6 or separate RFC — not blocking for initial release

---

## Appendix: Event-to-Visualization Mapping

| Event Type | Visualization | Effect |
|---|---|---|
| `plan_candidate_start` | PrismFracture | Beam enters prism |
| `plan_candidate_generated` | PrismFracture | Refracted beam appears |
| `plan_candidate_scored` | PrismFracture | Score label animates |
| `plan_winner` | PrismFracture | Winner glows, others fade |
| `plan_refine_start` | ResonanceWave | New iteration marker |
| `plan_refine_complete` | ResonanceWave | Wave segment draws |
| `task_start` | ExecutionCinema | Node activates |
| `task_progress` | ExecutionCinema | Progress bar fills |
| `task_complete` | ExecutionCinema | Motes rise, particles flow |
| `memory_learning` | MemoryLattice | Node appears |
| `memory_dead_end` | MemoryLattice | Node turns red, drifts |

---

## References

- RFC-097: Holy Light Theme System
- RFC-084: ConceptGraph (Memory Lattice data source)
- `benchmark/results/thesis_verification.json` (Model Paradox data)
- `schemas/agent-events.schema.json` (Event definitions)
