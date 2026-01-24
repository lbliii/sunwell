# RFC-115: Hierarchical Goal Decomposition — Epic → Milestone → Artifact

**Status**: Draft  
**Created**: 2026-01-23  
**Author**: @llane  
**Depends on**: RFC-038 (Harmonic Planning), RFC-046 (Autonomous Backlog), RFC-067 (Integration-Aware DAG)  
**Priority**: P0 — Enables ambitious goals (games, novels, full apps)

---

## Summary

Add **hierarchical decomposition** so ambitious goals like "build an RTS game" or "write a mystery novel" are first broken into **milestones**, then each milestone is planned with HarmonicPlanner when reached.

**The thesis**: You can't plan 200 tasks upfront. But you can plan 8 milestones, then plan 25 tasks when you reach each one.

---

## Problem Statement

### Current Behavior

When user submits "build an RTS game":

```
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT: Flat Planning (Fails)                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User: "Build an RTS game"                                      │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  HarmonicPlanner tries to generate ALL tasks            │   │
│  │  - Context window exhausted                             │   │
│  │  - Tasks are shallow/incomplete                         │   │
│  │  - Early tasks become stale as reality diverges         │   │
│  │  - No visibility into total scope                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  😵 Overwhelmed planner, poor results                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why Flat Planning Fails for Ambitious Goals

| Problem | Impact |
|---------|--------|
| Context window exhaustion | Planner can't hold 200 task descriptions |
| Plans go stale | What you learn building Milestone 1 changes Milestone 5 |
| No progress visibility | "50/200 tasks" doesn't tell you where you are |
| Compounding errors | Early mistakes propagate through entire plan |
| Domain mismatch | Planning chapters before characters exist |

### The Insight

Ambitious goals have **natural hierarchy**:

```
Epic
 └── Milestones (5-15 high-level phases)
      └── Artifacts (foundational elements built in each phase)
           └── Tasks (HarmonicPlanner output — detailed work)
```

**Plan the hierarchy first, detail each phase when reached.**

---

## Goals

1. **Decompose first**: Epic → Milestones before any detailed planning
2. **Artifact-first within milestones**: Build foundations, then consumers
3. **Sliding window**: Only detailed-plan the current milestone
4. **Adapt to reality**: Milestone N+1 plan incorporates Milestone N learnings
5. **Domain-agnostic**: Works for code, novels, research, any multi-phase endeavor

## Non-Goals

1. **Full project management** — Not a Jira replacement
2. **Rigid milestone boundaries** — Milestones can be re-planned if scope changes
3. **Waterfall enforcement** — Parallelism within milestones still encouraged
4. **Automated milestone completion** — Human confirms milestone done (for now)

---

## Design

### The Hierarchy

```
┌────────────────────────────────────────────────────────────────┐
│  EPIC: "Build an RTS game"                                     │
│  (parent_goal_id: null)                                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  MILESTONES (goal_type: "milestone", parent_goal_id: epic_id)  │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ M1: Core     │  │ M2: Entity   │  │ M3: Map      │  ...    │
│  │ Game Loop    │──│ System       │──│ System       │         │
│  │              │  │              │  │              │         │
│  │ produces:    │  │ requires:    │  │ requires:    │         │
│  │ - Window     │  │ - GameLoop   │  │ - GameLoop   │         │
│  │ - Renderer   │  │ produces:    │  │ - Entities   │         │
│  │ - Input      │  │ - Entity     │  │ produces:    │         │
│  │ - GameState  │  │ - Movement   │  │ - Tilemap    │         │
│  └──────────────┘  │ - Selection  │  │ - Pathfinding│         │
│         │          └──────────────┘  └──────────────┘         │
│         │                                                      │
│         ▼ (when M1 reached, detail-plan with HarmonicPlanner)  │
│                                                                │
│  ARTIFACTS (within current milestone)                          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Window ──► Renderer ──► InputHandler ──► GameState     │  │
│  │    │                          │               │         │  │
│  │    └──────────────────────────┴───────────────┘         │  │
│  │                    MainLoop                             │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  TASKS (HarmonicPlanner output — create, wire, verify)         │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  T1: Create Window class                                │  │
│  │  T2: Create Renderer with Window dependency             │  │
│  │  T3: Wire Renderer to Window                            │  │
│  │  T4: Create InputHandler                                │  │
│  │  ...                                                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Novel Example (Artifact-First)

```
┌────────────────────────────────────────────────────────────────┐
│  EPIC: "Write a mystery novel"                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  MILESTONES:                                                   │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ M1: World    │  │ M2: Cast     │  │ M3: Plot     │         │
│  │ Building     │──│ & Characters │──│ Architecture │         │
│  │              │  │              │  │              │         │
│  │ produces:    │  │ requires:    │  │ requires:    │         │
│  │ - Setting    │  │ - Setting    │  │ - Characters │         │
│  │ - Era/Tech   │  │ produces:    │  │ - Setting    │         │
│  │ - Tone/Voice │  │ - Detective  │  │ produces:    │         │
│  │ - Locations  │  │ - Victim     │  │ - Timeline   │         │
│  └──────────────┘  │ - Suspects   │  │ - Clue Map   │         │
│                    │ - Witnesses  │  │ - Red Herrings│        │
│                    └──────────────┘  └──────────────┘         │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ M4: Act 1    │  │ M5: Act 2    │  │ M6: Act 3    │         │
│  │ (Ch 1-5)     │──│ (Ch 6-15)    │──│ (Ch 16-20)   │         │
│  │              │  │              │  │              │         │
│  │ requires:    │  │ requires:    │  │ requires:    │         │
│  │ - ALL M1-M3  │  │ - Act 1      │  │ - Act 2      │         │
│  │ produces:    │  │ produces:    │  │ produces:    │         │
│  │ - Chapter 1  │  │ - Chapters   │  │ - Resolution │         │
│  │ - Chapter 2  │  │   6-15       │  │ - Denouement │         │
│  │ - ...        │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                │
│  KEY INSIGHT: Chapters (M4-M6) depend on artifacts (M1-M3)    │
│  You build world, characters, plot BEFORE writing chapters.   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Data Model Changes

### Goal Extensions

```python
@dataclass(frozen=True, slots=True)
class Goal:
    # ... existing fields ...
    
    # NEW: Hierarchy fields
    goal_type: Literal["epic", "milestone", "task"] = "task"
    """What level of the hierarchy this goal represents."""
    
    parent_goal_id: str | None = None
    """Epic or milestone this belongs to (None for top-level epics)."""
    
    milestone_produces: tuple[str, ...] = ()
    """High-level artifacts this milestone will create (for dependency inference)."""
    
    milestone_index: int | None = None
    """Order within parent (0-indexed). None for epics and tasks."""
```

### Backlog Extensions

```python
@dataclass
class Backlog:
    # ... existing fields ...
    
    # NEW: Hierarchy tracking
    active_epic: str | None = None
    """Currently executing epic."""
    
    active_milestone: str | None = None
    """Currently executing milestone within active epic."""
    
    def get_epic(self, epic_id: str) -> Goal | None:
        """Get epic by ID."""
        
    def get_milestones(self, epic_id: str) -> list[Goal]:
        """Get all milestones for an epic, in order."""
        
    def get_current_milestone(self) -> Goal | None:
        """Get the milestone currently being executed."""
        
    def advance_milestone(self) -> Goal | None:
        """Mark current milestone complete, return next one."""
```

---

## Decomposition Flow

### Phase 1: Epic Decomposition (Cheap, ~500 tokens)

When user submits ambitious goal:

```python
async def decompose_epic(goal: str, context: dict) -> list[Milestone]:
    """Break epic into milestones (high-level, cheap).
    
    This is NOT detailed planning — just milestone identification.
    Each milestone has:
    - Title and description
    - What it produces (high-level artifacts)
    - What it requires (other milestones)
    """
    prompt = EPIC_DECOMPOSITION_PROMPT.format(goal=goal)
    result = await model.generate(prompt, options=GenerateOptions(max_tokens=1000))
    return parse_milestones(result.text)
```

**Decomposition prompt focuses on**:
- Natural phase boundaries
- What each phase produces (artifacts, not tasks)
- Dependencies between phases
- Domain-appropriate structure (acts for novels, systems for games)

### Phase 2: Milestone Planning (When Reached)

Only when a milestone becomes active:

```python
async def plan_milestone(milestone: Goal, context: dict) -> ArtifactGraph:
    """Detailed planning for active milestone using HarmonicPlanner.
    
    Context includes:
    - What previous milestones produced (actual artifacts, not planned)
    - Learnings from previous milestones
    - Updated project state
    """
    # Enrich context with completed milestone outputs
    context["completed_artifacts"] = get_completed_artifacts(milestone.parent_goal_id)
    context["learnings"] = get_milestone_learnings(milestone.parent_goal_id)
    
    # HarmonicPlanner with 5 candidates (existing flow)
    planner = HarmonicPlanner(model=model, candidates=5)
    return await planner.plan_with_metrics(milestone.description, context)
```

### Phase 3: Sliding Window Execution

```
┌────────────────────────────────────────────────────────────────┐
│  EXECUTION WINDOW                                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │   M1    │  │   M2    │  │   M3    │  │   M4    │   ...    │
│  │ ✅ Done │  │ 🔄 Active│  │ ⏳ Next │  │ 📋 Queued│         │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘          │
│       │            │                                          │
│       │            ▼                                          │
│       │     ┌──────────────────────────────────────┐         │
│       │     │  Detail-planned with HarmonicPlanner │         │
│       │     │  (5 candidates, artifact DAG)        │         │
│       │     └──────────────────────────────────────┘         │
│       │            │                                          │
│       │            ▼                                          │
│       │     ┌──────────────────────────────────────┐         │
│       │     │  Executing tasks within milestone    │         │
│       │     └──────────────────────────────────────┘         │
│       │                                                       │
│       └─────► Context flows forward (learnings, artifacts)   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## New Components

### 1. EpicDecomposer

```python
@dataclass
class EpicDecomposer:
    """Decomposes ambitious goals into milestones."""
    
    model: ModelProtocol
    domain_hints: dict[str, str] = field(default_factory=dict)
    """Domain-specific decomposition hints (e.g., "novel" → "acts")."""
    
    async def decompose(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> list[Goal]:
        """Break epic into milestones.
        
        Returns list of Goal objects with:
        - goal_type = "milestone"
        - parent_goal_id = epic_id
        - milestone_produces = high-level artifacts
        - requires = other milestone IDs
        """
        
    async def detect_domain(self, goal: str) -> str:
        """Detect domain for appropriate decomposition strategy.
        
        Returns: "software", "novel", "research", "general"
        """
```

### 2. MilestoneTracker

```python
@dataclass
class MilestoneTracker:
    """Tracks milestone progress and handles transitions."""
    
    backlog: BacklogManager
    learning_store: LearningStore
    
    def get_progress(self, epic_id: str) -> MilestoneProgress:
        """Get progress summary for an epic."""
        
    async def complete_milestone(self, milestone_id: str) -> Goal | None:
        """Mark milestone complete, extract learnings, return next."""
        
    def get_context_for_next(self, epic_id: str) -> dict[str, Any]:
        """Build context for planning next milestone.
        
        Includes completed artifacts, learnings, updated project state.
        """
```

### 3. Integration with AdaptiveSignals

```python
@property
def planning_route(self) -> str:
    """Extended routing for hierarchical goals."""
    if self.is_dangerous == "YES":
        return "STOP"
    if self.is_ambiguous == "YES":
        return "DIALECTIC"
    
    # NEW: Route ambitious goals to hierarchical decomposition
    if self.is_epic == "YES":
        return "HIERARCHICAL"
    
    # Existing HARMONIC/SINGLE_SHOT logic
    if self.complexity == "NO" and self.confidence >= 0.8:
        return "SINGLE_SHOT"
    return "HARMONIC"
```

**Epic detection signals**:
- Multiple distinct components/systems mentioned
- Words like "full", "complete", "entire", "build a"
- Estimated scope > 50 tasks
- Multi-domain (UI + backend + infra)

---

## UI Integration (Studio)

### Epic Progress View

```
┌────────────────────────────────────────────────────────────────┐
│  🎯 Build an RTS Game                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 25% (2/8 milestones) │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ✅ M1: Core Game Loop                     completed 2h ago    │
│     └─ Window, Renderer, Input, GameState                      │
│                                                                │
│  ✅ M2: Entity System                      completed 45m ago   │
│     └─ Entity, Movement, Selection, Collision                  │
│                                                                │
│  🔄 M3: Map System                         in progress         │
│     └─ Tilemap, Terrain, Pathfinding, Fog of War              │
│     ┌──────────────────────────────────────────────────────┐  │
│     │  Task Progress: ████████░░░░░░░░ 8/15 tasks          │  │
│     │  Current: Implementing A* pathfinding                │  │
│     └──────────────────────────────────────────────────────┘  │
│                                                                │
│  ⏳ M4: Unit System                        up next             │
│  ⏳ M5: Combat System                      queued              │
│  ⏳ M6: AI Opponents                       queued              │
│  ⏳ M7: UI/HUD                             queued              │
│  ⏳ M8: Polish & Balance                   queued              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Events

```typescript
// New event types for hierarchy
interface EpicDecomposedEvent {
  type: "epic_decomposed";
  data: {
    epic_id: string;
    epic_title: string;
    milestones: MilestoneSummary[];
    total_milestones: number;
  };
}

interface MilestoneStartedEvent {
  type: "milestone_started";
  data: {
    epic_id: string;
    milestone_id: string;
    milestone_title: string;
    milestone_index: number;
    total_milestones: number;
  };
}

interface MilestoneCompletedEvent {
  type: "milestone_completed";
  data: {
    epic_id: string;
    milestone_id: string;
    artifacts_produced: string[];
    learnings_extracted: number;
    next_milestone_id: string | null;
  };
}
```

---

## CLI Integration

```bash
# Submit epic (auto-detected and decomposed)
sunwell run "build an RTS game"

# Explicit epic submission
sunwell run --epic "write a mystery novel"

# View epic progress
sunwell epic status
sunwell epic status <epic_id>

# View milestones
sunwell epic milestones <epic_id>

# Skip to next milestone (abandon current)
sunwell epic skip-milestone

# Re-plan current milestone (if stuck)
sunwell epic replan
```

---

## Implementation Plan

### Phase 1: Data Model (1 day)
- [ ] Add `goal_type`, `parent_goal_id`, `milestone_produces`, `milestone_index` to Goal
- [ ] Add `active_epic`, `active_milestone` to Backlog
- [ ] Add hierarchy methods to BacklogManager
- [ ] Tests for hierarchy operations

### Phase 2: Decomposition (2 days)
- [ ] Create `EpicDecomposer` class
- [ ] Domain detection (software, novel, research, general)
- [ ] Decomposition prompts per domain
- [ ] Parse milestone output into Goal objects
- [ ] Tests for decomposition

### Phase 3: Milestone Tracking (1 day)
- [ ] Create `MilestoneTracker` class
- [ ] Context building for next milestone
- [ ] Learning extraction at milestone boundaries
- [ ] Tests for milestone transitions

### Phase 4: Signal Integration (0.5 day)
- [ ] Add `is_epic` to AdaptiveSignals
- [ ] Add "HIERARCHICAL" route to planning_route
- [ ] Update Agent.run() to handle hierarchical route
- [ ] Tests for routing

### Phase 5: Events & UI (1 day)
- [ ] Add epic/milestone events to event schema
- [ ] Add EpicProgress component to Studio
- [ ] Wire events to UI updates
- [ ] Manual testing

### Phase 6: CLI (0.5 day)
- [ ] Add `sunwell epic` command group
- [ ] Status, milestones, skip, replan subcommands
- [ ] Integration with existing `sunwell run`

---

## Success Criteria

1. **"Build an RTS game" works**: Decomposes into ~8 milestones, plans each when reached
2. **"Write a mystery novel" works**: Artifacts (world, characters) before chapters
3. **Sliding window**: Milestone N+1 plan uses Milestone N learnings
4. **Progress visible**: UI shows milestone progress, not just task progress
5. **Adapts to reality**: Can re-plan milestone if scope changes

---

## Future Work

- **Parallel milestones**: Some milestones may be independent (M5 and M6 both need M4)
- **Milestone estimation**: Predict milestone duration based on complexity
- **Smart re-decomposition**: If milestone proves too large, split it
- **Template milestones**: Common patterns (3-act structure, MVC architecture)

---

## Appendix: Decomposition Prompts

### Software Domain

```
Decompose this goal into milestones. Each milestone should:
- Build a coherent subsystem or component
- Produce artifacts other milestones can depend on
- Be completable in 1-4 hours of focused work

GOAL: {goal}

Output format:
MILESTONE 1: [Title]
PRODUCES: [comma-separated artifacts]
REQUIRES: [comma-separated milestone numbers, or "none"]
DESCRIPTION: [1-2 sentences]

MILESTONE 2: ...
```

### Novel Domain

```
Decompose this writing goal into milestones. 

IMPORTANT: World-building, characters, and plot architecture are ARTIFACTS 
that chapters CONSUME. Build foundations before writing chapters.

GOAL: {goal}

Structure as:
1. World/Setting milestone
2. Character development milestone  
3. Plot architecture milestone
4. Act milestones (chapters grouped by narrative arc)
5. Revision milestone

Output format:
MILESTONE 1: [Title]
PRODUCES: [artifacts - e.g., "Detective character", "Crime scene location"]
REQUIRES: [milestone numbers, or "none"]
DESCRIPTION: [1-2 sentences]
```
