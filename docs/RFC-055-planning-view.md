# RFC-055: Planning View — Visual Task Management for Humans

**Status**: Draft  
**Created**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 85% 🟢  
**Depends on**: 
- RFC-032 (Task types) — `Task`, `TaskStatus`, `TaskMode`
- RFC-034 (Contract-aware planning) — DAG dependencies, parallel groups
- RFC-040 (Plan persistence) — `SavedExecution`, `PlanStore`
- RFC-046 (Autonomous Backlog) — `Goal`, `Backlog`, `BacklogManager`
- RFC-043 (Studio) — GUI shell

---

## Summary

Sunwell already has sophisticated DAG-based task planning powering agent execution. This RFC surfaces that infrastructure through a visual Kanban/Linear-style view, enabling:

1. **View agent plans** as human-readable task boards
2. **Add human goals** alongside AI-discovered work
3. **Track progress** across projects for individuals or tiny teams
4. **Prioritize and reorder** work visually

**The key insight**: We're not building planning from scratch—we're creating a human-friendly window into what already exists.

---

## Motivation

### What We Already Have

```python
# Task with rich metadata (naaru/types.py)
Task(
    id="add-auth",
    description="Implement user authentication",
    mode=TaskMode.GENERATE,
    depends_on=("user-model",),
    produces=frozenset(["AuthService"]),
    requires=frozenset(["UserModel"]),
    parallel_group="features",
    priority=0.8,
    estimated_effort="medium",
    status=TaskStatus.PENDING,
)

# Backlog with goal DAG (backlog/manager.py)
Backlog(
    goals={"auth": auth_goal, "tests": test_goal},
    completed={"user-model"},
    in_progress="add-auth",
    blocked={"deploy": "needs CI"},
)

# Already exports to Mermaid!
backlog.to_mermaid()  # → "graph TD\n  auth[✓ Add auth]..."
```

### What's Missing

**A visual interface.** Users can only see this through:
- Terminal output during execution
- JSON files in `.sunwell/plans/`

Linear, Monday, Trello, and Notion succeed because they make task management **visual and tactile**. We have the data model—we need the view.

---

## Design

### The Planning Mode

Planning mode is a new view in Sunwell Studio, alongside Home and Project.

```
┌─────────────────────────────────────────────────────────────────┐
│  forum-app › Planning                            🔄  ⚙️  ─ □ x │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📋 Goals                                           [+ Add Goal]│
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │  Backlog    │ │  Ready      │ │  In Progress│ │  Done     │ │
│  │             │ │             │ │             │ │           │ │
│  │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌───────┐ │ │
│  │ │ Rate    │ │ │ │ Auth    │ │ │ │ Post    │ │ │ │ User  │ │ │
│  │ │ limiting│ │ │ │ system  │ │ │ │ CRUD    │ │ │ │ model │ │ │
│  │ │         │ │ │ │ ▸▸▸     │ │ │ │ █████░░ │ │ │ │   ✓   │ │ │
│  │ │ 🤖 auto │ │ │ │ 🤖 auto │ │ │ │ 🤖 auto │ │ │ │ 🤖    │ │ │
│  │ └─────────┘ │ │ └─────────┘ │ │ └─────────┘ │ │ └───────┘ │ │
│  │             │ │             │ │             │ │           │ │
│  │ ┌─────────┐ │ │ ┌─────────┐ │ │             │ │ ┌───────┐ │ │
│  │ │ Mobile  │ │ │ │ Test    │ │ │             │ │ │Comment│ │ │
│  │ │ support │ │ │ │ coverage│ │ │             │ │ │ model │ │ │
│  │ │         │ │ │ │         │ │ │             │ │ │   ✓   │ │ │
│  │ │ 👤 human│ │ │ │ 🤖 auto │ │ │             │ │ │ 🤖    │ │ │
│  │ └─────────┘ │ │ └─────────┘ │ │             │ │ └───────┘ │ │
│  │             │ │             │ │             │ │           │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  💡 Sunwell suggested 3 goals from codebase analysis           │
│     [Review Suggestions]                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Two Types of Goals

| Type | Source | Badge | Execution |
|------|--------|-------|-----------|
| **AI-discovered** | Codebase signals (TODOs, low coverage, issues) | 🤖 auto | Sunwell can auto-execute |
| **Human-created** | User adds manually | 👤 human | User triggers execution |

Both flow through the same `Goal` → `Task` → execution pipeline.

### Views

#### 1. Kanban View (Default)

Classic columns: **Backlog → Ready → In Progress → Done**

- Drag to reorder within Backlog
- Cards show: title, source (🤖/👤), priority, estimate
- Click to expand: description, dependencies, subtasks

#### 2. List View

Linear/GitHub Issues style—sortable table:

```
┌──────────────────────────────────────────────────────────────────┐
│  Status  │  Title              │  Priority │  Effort  │  Source  │
├──────────────────────────────────────────────────────────────────┤
│  ⏳      │  Post CRUD routes   │  ████░    │  Medium  │  🤖 auto │
│  □       │  Auth system        │  █████    │  Large   │  🤖 auto │
│  □       │  Rate limiting      │  ███░░    │  Small   │  🤖 auto │
│  □       │  Mobile support     │  ██░░░    │  Large   │  👤 human│
│  ✓       │  User model         │  █████    │  Small   │  🤖 auto │
└──────────────────────────────────────────────────────────────────┘
```

#### 3. DAG View

Visual dependency graph (uses existing `to_mermaid()` or custom renderer):

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│           ┌─────────┐                                           │
│           │  User   │                                           │
│           │  Model  │ ✓                                         │
│           └────┬────┘                                           │
│                │                                                │
│       ┌────────┼────────┐                                       │
│       ▼        ▼        ▼                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                           │
│  │  Post   │ │  Auth   │ │ Comment │                           │
│  │  Model  │ │ System  │ │  Model  │ ✓                         │
│  └────┬────┘ └────┬────┘ └─────────┘                           │
│       │           │                                             │
│       ▼           ▼                                             │
│  ┌─────────┐ ┌─────────┐                                       │
│  │  Post   │ │  Rate   │                                       │
│  │  CRUD   │ │ Limiting│                                       │
│  │ ████░░░ │ └─────────┘                                       │
│  └─────────┘                                                    │
│                                                                 │
│  Legend: ✓ Complete  ███ In Progress  □ Pending                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 4. Timeline View (Future)

Gantt-style view showing estimated completion:

```
Jan 20  │  Jan 21  │  Jan 22  │  Jan 23  │
────────┼──────────┼──────────┼──────────┼
████████│          │          │          │  User Model ✓
        │██████████│██████████│          │  Post CRUD
        │          │██████████│██████████│  Auth System
        │          │          │██████████│  Rate Limiting
```

---

## User Workflows

### Workflow 1: View Agent's Plan

User runs a goal, then wants to see the plan:

```
1. User: "Build a forum app"
2. Sunwell: Plans 8 tasks, starts executing
3. User: Clicks "📋 Planning" tab
4. → Sees Kanban with all 8 tasks in appropriate columns
5. → Can see dependencies, progress, what's blocked
```

### Workflow 2: Add Human Goal

User wants to add something the AI didn't suggest:

```
1. User: Clicks [+ Add Goal]
2. → Modal: "What would you like to do?"
3. User: "Add mobile responsive design"
4. Sunwell: Analyzes, creates Goal with:
   - Estimated effort: Large
   - Dependencies: (none detected)
   - Suggested breakdown into tasks
5. → Goal appears in Backlog with 👤 badge
6. User: Drags to Ready when they want to work on it
7. User: Clicks "▶ Execute" to start
```

### Workflow 3: Prioritize Work

User wants to reorder the backlog:

```
1. User: Views Kanban in Planning mode
2. → Sees AI suggested "Rate limiting" is low priority
3. User: Drags "Rate limiting" above "Mobile support"
4. → Priority updates, affects execution order
5. → Backlog persists to .sunwell/backlog/current.json
```

### Workflow 4: Review AI Suggestions

Sunwell proactively finds work from codebase signals:

```
1. User: Opens project in Studio
2. → Banner: "💡 Sunwell found 3 potential goals"
3. User: Clicks [Review Suggestions]
4. → Modal shows:
   - "Add tests for auth.py" (coverage: 23%)
   - "Fix TODO in routes.py:89" (rate limiting)
   - "Update deprecated bcrypt rounds" (security)
5. User: Accepts 2, dismisses 1
6. → Accepted goals appear in Backlog
```

### Workflow 5: Team Sync (Tiny Team)

For 2-3 person teams sharing a project:

```
1. Alice: Adds "Implement OAuth" goal
2. → Goal saved to .sunwell/backlog/current.json
3. Bob: Pulls latest, opens Studio
4. → Sees Alice's goal in Backlog
5. Bob: Claims goal (moves to In Progress)
6. → Claim recorded with worker_id (RFC-051)
7. Alice: Sees Bob is working on OAuth
```

---

## Data Model

### Mapping Existing Types to Views

```
┌─────────────────────────────────────────────────────────────────┐
│                         PLANNING VIEW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Goal (backlog/goals.py)        →    Card in Kanban            │
│   ├── id                         →    Unique identifier          │
│   ├── title                      →    Card title                 │
│   ├── description                →    Card description           │
│   ├── priority (0.0-1.0)         →    Sort order                │
│   ├── estimated_complexity       →    Effort badge              │
│   ├── requires (frozenset)       →    Dependency lines          │
│   ├── source_signals             →    Source indicator (🤖/👤)   │
│   ├── claimed_by                 →    Assignee (RFC-051)        │
│   └── category                   →    Label/tag                  │
│                                                                  │
│   Backlog (backlog/manager.py)   →    Board state               │
│   ├── goals                      →    All cards                 │
│   ├── completed                  →    Done column               │
│   ├── in_progress                →    In Progress column        │
│   └── blocked                    →    Blocked indicator         │
│                                                                  │
│   Task (naaru/types.py)          →    Subtask within card       │
│   ├── id                         →    Subtask ID                │
│   ├── description                →    Subtask title             │
│   ├── depends_on                 →    Dependency in DAG view    │
│   ├── status                     →    Checkbox state            │
│   └── parallel_group             →    Swim lane in DAG          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### New Types

```python
# src/sunwell/planning/types.py

from dataclasses import dataclass
from enum import Enum

class GoalSource(Enum):
    """Where a goal came from."""
    AI_DISCOVERED = "ai_discovered"   # Codebase analysis
    USER_CREATED = "user_created"     # Human added
    EXTERNAL = "external"             # GitHub issue, etc. (RFC-049)


@dataclass(frozen=True, slots=True)
class PlanningViewState:
    """State for the planning view UI."""
    
    view_mode: str = "kanban"  # kanban | list | dag | timeline
    sort_by: str = "priority"  # priority | created | effort
    show_completed: bool = True
    show_ai_suggestions: bool = True
    selected_goal_id: str | None = None
    
    # Filters
    filter_source: GoalSource | None = None
    filter_category: str | None = None


@dataclass(frozen=True, slots=True) 
class GoalCard:
    """A goal formatted for display in the UI."""
    
    id: str
    title: str
    description: str
    source: GoalSource
    status: str  # backlog | ready | in_progress | done | blocked
    priority: float
    effort: str  # trivial | small | medium | large
    category: str
    
    # Dependencies
    depends_on: tuple[str, ...]
    blocks: tuple[str, ...]  # Goals that depend on this
    
    # Progress
    subtask_count: int
    subtasks_completed: int
    
    # Assignment (RFC-051)
    claimed_by: int | None
    claimed_at: str | None
    
    # Metadata
    created_at: str
    source_signals: tuple[str, ...]  # e.g., "TODO:routes.py:89"
    
    @property
    def progress_percent(self) -> float:
        if self.subtask_count == 0:
            return 0.0
        return (self.subtasks_completed / self.subtask_count) * 100
```

---

## Implementation

### Phase 1: Read-Only View (Week 1)

Display existing agent plans as a Kanban board.

**Rust commands:**

```rust
// studio/src-tauri/src/planning.rs

#[tauri::command]
pub async fn get_backlog(path: String) -> Result<Backlog, String> {
    // Read .sunwell/backlog/current.json
    let backlog_path = Path::new(&path).join(".sunwell/backlog/current.json");
    // ... parse and return
}

#[tauri::command]
pub async fn get_execution_state(path: String, goal_id: String) -> Result<ExecutionState, String> {
    // Read .sunwell/plans/<goal_hash>.json
    // ... return task graph with status
}

#[tauri::command]
pub async fn get_pending_suggestions(path: String) -> Result<Vec<GoalSuggestion>, String> {
    // Run signal extraction, return potential goals
    // Calls: sunwell backlog discover --json
}
```

**Svelte components:**

```
studio/src/
├── routes/
│   └── Planning.svelte          # Main planning view
├── components/
│   ├── planning/
│   │   ├── KanbanBoard.svelte   # Kanban view
│   │   ├── KanbanColumn.svelte  # Single column
│   │   ├── GoalCard.svelte      # Card component
│   │   ├── ListView.svelte      # Table view
│   │   ├── DagView.svelte       # Graph view (Mermaid or custom)
│   │   └── GoalDetail.svelte    # Expanded goal modal
│   └── ...
├── stores/
│   └── planning.ts              # Planning state store
```

### Phase 2: Human Goal Creation (Week 2)

Allow users to add and prioritize goals.

**New commands:**

```rust
#[tauri::command]
pub async fn add_goal(path: String, title: String, description: String) -> Result<Goal, String> {
    // Create Goal, add to backlog
    // Calls: sunwell backlog add --title "..." --description "..."
}

#[tauri::command]
pub async fn update_goal_priority(path: String, goal_id: String, priority: f32) -> Result<(), String> {
    // Update priority in backlog
}

#[tauri::command]
pub async fn accept_suggestion(path: String, suggestion_id: String) -> Result<Goal, String> {
    // Convert suggestion to goal
}
```

### Phase 3: Goal Execution Integration (Week 3)

Connect planning view to agent execution.

```rust
#[tauri::command]
pub async fn execute_goal(
    app: AppHandle,
    path: String,
    goal_id: String,
) -> Result<(), String> {
    // Start agent for specific goal
    // Calls: sunwell agent run --goal-id <id> --json
    // Stream events back to UI
}
```

**UI flow:**
1. User clicks "▶ Execute" on a goal card
2. Card moves to "In Progress"
3. Progress bar updates as tasks complete
4. On completion, card moves to "Done"

### Phase 4: DAG Visualization (Week 4)

Rich dependency visualization.

**Options:**
1. **Mermaid.js** — Use existing `to_mermaid()`, render with Mermaid
2. **D3.js** — Custom interactive graph
3. **Cytoscape.js** — Graph visualization library

```svelte
<!-- DagView.svelte -->
<script lang="ts">
  import mermaid from 'mermaid';
  import { backlog } from '../stores/planning';
  
  $: mermaidCode = $backlog?.to_mermaid ?? '';
  
  $: if (mermaidCode) {
    mermaid.render('dag', mermaidCode).then(({ svg }) => {
      dagContainer.innerHTML = svg;
    });
  }
</script>

<div bind:this={dagContainer} class="dag-container"></div>
```

---

## UI Design

### Card Design

```
┌─────────────────────────────────┐
│ 🤖  Add authentication          │  ← Source + Title
│                                 │
│ Set up JWT-based user auth      │  ← Description (truncated)
│                                 │
│ ████████░░  3/4 tasks           │  ← Progress
│                                 │
│ ⏱ Medium  ·  🔗 2 deps  ·  P1   │  ← Metadata
└─────────────────────────────────┘
```

**States:**
- Default: `--bg-secondary`
- Hover: `--bg-tertiary` + slight lift
- Dragging: Elevated shadow, reduced opacity
- In Progress: Pulsing left border
- Blocked: Red left border + ⚠️ indicator

### Column Design

```
┌─────────────────────┐
│     Backlog (5)     │  ← Title + count
├─────────────────────┤
│                     │
│  ┌───────────────┐  │
│  │    Card 1     │  │
│  └───────────────┘  │
│                     │
│  ┌───────────────┐  │
│  │    Card 2     │  │
│  └───────────────┘  │
│                     │
│       · · ·         │  ← More indicator if scrolled
│                     │
└─────────────────────┘
```

### Quick Actions

Right-click or `...` menu on cards:

```
┌────────────────────────┐
│ ▶ Execute              │
│ ✏️ Edit                │
│ ↑ Move to top          │
│ 🔗 View dependencies   │
│ ─────────────────────  │
│ 🗑 Delete               │
└────────────────────────┘
```

---

## Integration with Existing Systems

### Backlog Manager

The planning view is a UI for `BacklogManager`:

```python
# Direct mapping
backlog_manager.refresh()           →  "🔄 Refresh" button
backlog_manager.backlog.next_goal() →  Next card in "Ready" column
backlog_manager.add_external_goal() →  "+ Add Goal" button
backlog_manager.complete_goal()     →  Move to "Done" column
backlog_manager.block_goal()        →  Mark as blocked
```

### Agent Execution

When executing a goal:

```python
# The goal becomes tasks via planning
goal = backlog.goals["add-auth"]
tasks = await agent_planner.plan([goal.description])

# TaskGraph powers the execution
graph = TaskGraph(tasks=tasks)
async for event in agent.execute(graph):
    # Events stream to UI
    emit_to_ui(event)  # task_start, task_complete, etc.
```

### External Integration (RFC-049)

Goals from GitHub issues appear in the backlog:

```
┌─────────────────────────────────┐
│ 🔗  Fix login redirect bug      │  ← External source badge
│                                 │
│ Users redirected to 404 after   │
│ successful login                │
│                                 │
│ □ Not started                   │
│                                 │
│ GitHub #123  ·  P2              │  ← External reference
└─────────────────────────────────┘
```

---

## Future Extensions

### Team Features (Post-MVP)

For small teams (2-5 people):

1. **Assignees**: Claim goals, see who's working on what
2. **Comments**: Discuss goals inline
3. **Mentions**: @user in descriptions
4. **Sync**: Real-time updates via file watching or lightweight sync

### Integrations

1. **GitHub/GitLab**: Two-way sync with issues
2. **Linear**: Import/export
3. **Calendar**: Block time for goals
4. **Slack**: Notifications on completion

### Advanced Views

1. **Sprint planning**: Group goals into time-boxed sprints
2. **Capacity planning**: Based on estimated effort
3. **Velocity tracking**: Historical completion rates

---

## Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| Time to view plan | < 1s | Instant feedback |
| Goals added/week | 5+ | Active usage |
| Goals executed from view | 50% | Integration works |
| View mode usage | Kanban 60%, List 30%, DAG 10% | Feature adoption |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Feature creep (too many views) | High | Start with Kanban only, add others based on demand |
| Drag-and-drop complexity | Medium | Use existing library (dnd-kit, svelte-dnd-action) |
| Sync conflicts (tiny team) | Medium | File locking already in BacklogManager (RFC-051) |
| Performance with many goals | Low | Virtualize lists, lazy load DAG |

---

## Implementation Checklist

### Phase 1: Read-Only
- [ ] `get_backlog` Rust command
- [ ] `Planning.svelte` route
- [ ] `KanbanBoard.svelte` component
- [ ] `GoalCard.svelte` component
- [ ] Wire up to agent events

### Phase 2: Human Goals
- [ ] `add_goal` Rust command
- [ ] Add goal modal
- [ ] Priority reordering (drag-and-drop)
- [ ] Accept/dismiss suggestions

### Phase 3: Execution
- [ ] `execute_goal` Rust command
- [ ] Progress updates on cards
- [ ] Status transitions

### Phase 4: Visualization
- [ ] DAG view with Mermaid
- [ ] List view
- [ ] View switcher

---

## References

- `src/sunwell/backlog/manager.py` — BacklogManager, Backlog
- `src/sunwell/backlog/goals.py` — Goal, GoalScope
- `src/sunwell/naaru/types.py` — Task, TaskStatus, TaskMode
- `src/sunwell/naaru/persistence.py` — SavedExecution, PlanStore
- `src/sunwell/adaptive/agent.py` — TaskGraph
- RFC-046 (Autonomous Backlog)
- RFC-051 (Multi-Instance) — Goal claiming
