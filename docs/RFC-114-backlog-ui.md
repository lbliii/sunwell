# RFC-114: Backlog UI — Visual Goal Queue Management

**Status**: Draft  
**Created**: 2026-01-23  
**Author**: @llane  
**Depends on**: RFC-100 (Workers/ATC), RFC-046 (Autonomous Backlog)  
**Priority**: P1 — Completes the parallel execution story

---

## Summary

Add a **Backlog panel** to Studio that visualizes and manages the goal queue. Currently, the Workers tab exists but users cannot see or manage what workers will work on—forcing a CLI detour that breaks flow.

**The thesis**: Workers without a visible backlog is like a kitchen without orders. The feature exists but is unusable.

---

## Problem Statement

### The Disconnect

```
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT STATE                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CLI-only                         UI exists                     │
│  ──────────────────────────────────────────────────────────────│
│                                                                 │
│  sunwell backlog add "..."  ─────►  ???                         │
│  sunwell backlog show       ◄─────  Workers tab (empty)         │
│                                                                 │
│  User: "Start Workers"                                          │
│  System: "No goals in backlog"                                  │
│  User: "Where's the backlog?"                                   │
│  System: "CLI only"                                             │
│  User: 😤                                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### User Journey (Current — Broken)

1. User opens Studio → Project view
2. Sees "Workers" tab, clicks it
3. Clicks "Start Workers"
4. Nothing happens (backlog is empty)
5. User confused: "What do workers work on?"
6. Has to leave Studio, open terminal, run `sunwell backlog show`
7. Realizes they need to add goals via CLI
8. Context switch, flow broken

### What's Missing

| Feature | CLI | Studio UI |
|---------|-----|-----------|
| View backlog | `sunwell backlog show` | ❌ |
| Add goal | `sunwell backlog add "..."` | ❌ |
| Remove/skip goal | `sunwell backlog skip <id>` | ❌ |
| Reorder priorities | `sunwell backlog prioritize` | ❌ |
| View dependencies | `sunwell backlog show --mermaid` | ❌ |
| Run specific goal | `sunwell backlog run <id>` | ❌ |
| Start workers | `sunwell workers start` | ✅ |
| View worker status | `sunwell workers status` | ✅ |

The Workers UI is orphaned.

---

## Goals

1. **Unified surface**: See backlog + workers in one view
2. **Full CRUD**: Add, edit, remove, reorder goals without CLI
3. **Dependency visualization**: Show which goals block others
4. **Seamless flow**: Add goals → Start workers → Watch progress
5. **Maintain CLI parity**: Everything in UI is also in CLI

## Non-Goals

1. **Replace CLI entirely** — CLI remains primary for power users
2. **Complex project management** — Not a Jira/Linear replacement
3. **Historical analytics** — Focus on current queue, not past metrics
4. **Goal generation UI** — `backlog refresh` stays CLI-only (complex)

---

## User Journeys

### Persona 1: The Visual User

**Who**: Developer who prefers GUI over CLI  
**Trigger**: "I want to queue up work for Sunwell"

```
JOURNEY: Adding Goals via UI
────────────────────────────────────────────────────────────────

1. User opens Studio → Project → "Backlog" tab
2. Sees empty state: "No goals yet. Add your first goal."
3. Clicks [+ Add Goal]
4. Types: "Implement user authentication"
5. Goal appears in list with priority slider
6. Adds 3 more goals
7. Drags to reorder by priority
8. Clicks "Start 4 Workers"
9. Watches workers claim and execute goals in real-time

OUTCOME: Full parallel execution without touching terminal
```

### Persona 2: The Debugger

**Who**: Developer whose worker got stuck  
**Trigger**: "Why is Worker 2 blocked?"

```
JOURNEY: Understanding Dependencies
────────────────────────────────────────────────────────────────

1. User sees Worker 2 status: "Blocked"
2. Clicks on the blocked goal
3. Sees dependency view:
   - "Create API routes" (this goal)
   - └── Requires: "Set up database schema" (in progress by Worker 1)
4. Understands: must wait for Worker 1 to finish
5. Optionally: removes dependency to unblock

OUTCOME: Transparency into why work is waiting
```

### Persona 3: The Planner

**Who**: Tech lead planning sprint work  
**Trigger**: "Let me queue up this week's goals"

```
JOURNEY: Batch Planning
────────────────────────────────────────────────────────────────

1. User opens Backlog tab
2. Clicks [+ Add Multiple]
3. Pastes list:
   - Fix login bug
   - Add password reset
   - Create admin dashboard
   - Write API tests
   - Update documentation
4. Goals parsed and added with auto-priority
5. Reviews, adjusts priorities
6. Saves backlog
7. Starts workers when ready

OUTCOME: Plan first, execute later
```

---

## Design

### Architecture

The Backlog UI integrates with existing patterns:

```
┌─────────────────────────────────────────────────────────────────┐
│                         STUDIO                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Project │ Pipeline │ Memory │ Health │ State │ Workers         │
│                                                ────┬────         │
│                                                    │             │
│                                          ┌────────┴────────┐    │
│                                          │  UNIFIED VIEW   │    │
│                                          │                 │    │
│                                          │ ┌─────────────┐ │    │
│                                          │ │  Backlog    │ │    │
│                                          │ │  (queue)    │ │    │
│                                          │ └──────┬──────┘ │    │
│                                          │        │        │    │
│                                          │        ▼        │    │
│                                          │ ┌─────────────┐ │    │
│                                          │ │  Workers    │ │    │
│                                          │ │  (ATC)      │ │    │
│                                          │ └─────────────┘ │    │
│                                          └─────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Option A (Recommended)**: Merge Backlog into Workers tab as unified "Execution" view  
**Option B**: Separate Backlog tab alongside Workers

### Component Hierarchy

```
src/
├── components/
│   ├── backlog/                      # NEW: Backlog feature
│   │   ├── index.ts
│   │   ├── BacklogPanel.svelte       # Main container
│   │   ├── GoalCard.svelte           # Individual goal display
│   │   ├── GoalForm.svelte           # Add/edit goal modal
│   │   ├── DependencyGraph.svelte    # Mini DAG of goal deps
│   │   └── PrioritySlider.svelte     # Priority adjustment
│   │
│   ├── coordinator/                  # Existing
│   │   ├── ATCView.svelte            # MODIFY: Include BacklogPanel
│   │   └── ...
│
├── stores/
│   └── backlog.svelte.ts             # NEW: Backlog state management
```

### Data Contracts

```typescript
// stores/backlog.svelte.ts

export interface Goal {
  id: string;
  title: string;
  description: string;
  priority: number;           // 1-10, higher = more urgent
  category: string;           // "feature", "bugfix", "refactor", "docs"
  status: GoalStatus;
  estimated_complexity: string; // "trivial", "small", "medium", "large"
  auto_approvable: boolean;
  requires: string[];         // IDs of blocking goals
  created_at: string;
  claimed_by?: number;        // Worker ID if claimed
}

export type GoalStatus = 
  | 'pending'      // Waiting to be claimed
  | 'blocked'      // Has unsatisfied dependencies
  | 'claimed'      // Worker has claimed it
  | 'executing'    // Currently being worked on
  | 'completed'    // Successfully finished
  | 'failed'       // Execution failed
  | 'skipped';     // User skipped

export interface BacklogState {
  goals: Goal[];
  is_loading: boolean;
  error: string | null;
  last_refresh: string | null;
}
```

### API Integration

Following RFC-113 (Native HTTP Bridge) pattern:

```typescript
// stores/backlog.svelte.ts

export async function loadBacklog(): Promise<void> {
  const response = await fetch('/api/backlog');
  const data = await response.json();
  _state.goals = data.goals;
}

export async function addGoal(title: string, description?: string): Promise<void> {
  await fetch('/api/backlog/goals', {
    method: 'POST',
    body: JSON.stringify({ title, description }),
  });
  await loadBacklog();
}

export async function removeGoal(id: string): Promise<void> {
  await fetch(`/api/backlog/goals/${id}`, { method: 'DELETE' });
  await loadBacklog();
}

export async function reorderGoals(ids: string[]): Promise<void> {
  await fetch('/api/backlog/reorder', {
    method: 'POST',
    body: JSON.stringify({ order: ids }),
  });
  await loadBacklog();
}
```

---

## UI Design

### Unified Workers + Backlog View

```
┌────────────────────────────────────────────────────────────────┐
│  🛫 Execution Control                    [Idle] [▶ Start 4]    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  BACKLOG (6 goals)                              [+ Add Goal]   │
│  ──────────────────────────────────────────────────────────────│
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ ≡  1. Implement user authentication          ⬤ High      │ │
│  │     "Add OAuth2 login flow with Google/GitHub"           │ │
│  │     📦 feature │ 🔵 medium │ ⚡ auto-approve             │ │
│  │                                              [▶] [✕]     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ ≡  2. Create API endpoints                   ⬤ High      │ │
│  │     └── Blocked by: #1 (user auth)                       │ │
│  │     📦 feature │ 🔵 medium │ ⚡ auto-approve             │ │
│  │                                              [▶] [✕]     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ ≡  3. Write unit tests                       ○ Medium    │ │
│  │     📦 test │ 🟢 small │ ⚡ auto-approve                 │ │
│  │                                              [▶] [✕]     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ... 3 more goals                                    [Show all]│
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  WORKERS (0 active)                                            │
│  ──────────────────────────────────────────────────────────────│
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │           No workers running.                            │ │
│  │                                                          │ │
│  │           [▶ Start Parallel Execution]                   │ │
│  │                                                          │ │
│  │     Workers will claim goals from the backlog above.     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘

LEGEND:
  ≡     = Drag handle (reorder)
  [▶]   = Run this goal immediately (solo)
  [✕]   = Remove from backlog
  ⬤/○   = Priority indicator (filled = high)
```

### Goal Card States

```
PENDING (ready to claim)
┌──────────────────────────────────────────────────────────┐
│ ≡  Implement user authentication              ⬤ High     │
│    📦 feature │ 🔵 medium │ ⚡ auto-approve              │
│                                            [▶] [✕]      │
└──────────────────────────────────────────────────────────┘

BLOCKED (waiting on dependency)
┌──────────────────────────────────────────────────────────┐
│ ≡  Create API endpoints                       ⬤ High     │
│    └── ⏳ Blocked by: #1 (user auth)                     │
│    📦 feature │ 🔵 medium                               │
│                                                 [✕]      │
└──────────────────────────────────────────────────────────┘

EXECUTING (worker is on it)
┌──────────────────────────────────────────────────────────┐
│    Implement user authentication    🔄 Worker 2 (45%)    │
│    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░                       │
│    📦 feature │ 🔵 medium                               │
└──────────────────────────────────────────────────────────┘

COMPLETED (done)
┌──────────────────────────────────────────────────────────┐
│ ✓  Implement user authentication              ✓ Done     │
│    Completed by Worker 2 in 3m 24s                       │
│    📦 feature │ 🔵 medium                               │
└──────────────────────────────────────────────────────────┘
```

### Add Goal Modal

```
┌────────────────────────────────────────────────────────────┐
│  Add Goal                                            [✕]   │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Title *                                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Implement user authentication                        │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  Description (optional)                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Add OAuth2 login flow supporting Google and GitHub   │ │
│  │ providers. Include session management and logout.    │ │
│  │                                                      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │ Category        │  │ Complexity      │                 │
│  │ [feature    ▼]  │  │ [medium     ▼]  │                 │
│  └─────────────────┘  └─────────────────┘                 │
│                                                            │
│  Priority                                                  │
│  Low ────────────●──────────── High                        │
│                  7                                         │
│                                                            │
│  ☑ Auto-approve if tests pass                              │
│                                                            │
│  Depends on (optional)                                     │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Select goals this depends on...                  [▼] │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│                            [Cancel]  [Add Goal]            │
└────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Store + Basic Display (Week 1)

- [ ] Create `stores/backlog.svelte.ts` with state management
- [ ] Add backend endpoints: `GET /api/backlog`, `POST /api/backlog/goals`
- [ ] Create `BacklogPanel.svelte` — read-only list view
- [ ] Create `GoalCard.svelte` — individual goal display
- [ ] Integrate into Workers tab (ATCView.svelte)

### Phase 2: CRUD Operations (Week 1-2)

- [ ] Create `GoalForm.svelte` — add/edit modal
- [ ] Add `DELETE /api/backlog/goals/:id` endpoint
- [ ] Add `PUT /api/backlog/goals/:id` endpoint
- [ ] Implement drag-to-reorder with `POST /api/backlog/reorder`
- [ ] Add inline priority adjustment

### Phase 3: Dependencies + Polish (Week 2)

- [ ] Create `DependencyGraph.svelte` — mini DAG visualization
- [ ] Show blocked state with dependency chain
- [ ] Add "Run Single Goal" button (bypasses workers)
- [ ] Add batch add (paste multiple goals)
- [ ] Wire real-time updates via WebSocket events

### Phase 4: Integration (Week 2-3)

- [ ] Connect backlog events to worker status
- [ ] Show which worker claimed which goal
- [ ] Add progress indicators from worker heartbeats
- [ ] Polish empty states and loading states

---

## API Endpoints

Following RFC-113 Native HTTP pattern:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/backlog` | GET | List all goals |
| `/api/backlog/goals` | POST | Add new goal |
| `/api/backlog/goals/:id` | GET | Get single goal |
| `/api/backlog/goals/:id` | PUT | Update goal |
| `/api/backlog/goals/:id` | DELETE | Remove goal |
| `/api/backlog/goals/:id/skip` | POST | Skip goal |
| `/api/backlog/reorder` | POST | Reorder goals |
| `/api/backlog/refresh` | POST | Refresh from signals |

---

## Event Integration

Backlog events already exist (RFC-094). The UI subscribes:

| Event | UI Effect |
|-------|-----------|
| `backlog_goal_added` | Add card to list with animation |
| `backlog_goal_started` | Move to "executing" state |
| `backlog_goal_completed` | Show success, move to history |
| `backlog_goal_failed` | Show error state |
| `backlog_refreshed` | Reload entire list |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Drag-reorder feels janky** | Medium | Medium | Use proven library (dnd-kit pattern). Test on 50+ items. |
| **Real-time sync races** | Medium | High | Optimistic UI with rollback. Server is source of truth. |
| **Overwhelmed with goals** | Low | Medium | Collapse completed. Filter by status. Pagination at 100+. |
| **Dependency cycles** | Low | High | Backend validates on add. UI shows error if cycle detected. |

---

## Success Criteria

| Criterion | Metric | Target |
|-----------|--------|--------|
| **Feature completeness** | CLI parity | 100% of `sunwell backlog` commands have UI equivalent |
| **User flow** | Add goal → Start workers | ≤5 clicks, no CLI needed |
| **Real-time accuracy** | Event-to-UI latency | <500ms for status changes |
| **Usability** | New user can add + run goal | Without reading docs |

---

## Alternatives Considered

### Option A: Unified Execution Tab (Recommended)

Merge Backlog into Workers tab. One "Execution" surface.

**Pros**: Single destination. Clear flow (queue → workers).  
**Cons**: Tab gets busy with many goals.

### Option B: Separate Backlog Tab

Add 7th tab: `Project │ Pipeline │ Memory │ Health │ State │ Backlog │ Workers`

**Pros**: Clean separation. More room.  
**Cons**: Navigation friction. "Where do I go?"

### Option C: Backlog in Pipeline Tab

Show backlog as pending nodes in the existing Pipeline DAG.

**Pros**: Reuses existing visualization.  
**Cons**: Conflates planning (DAG) with execution (backlog). Confusing.

### Decision

**Option A selected.** The Workers tab is useless without seeing the backlog. Combining them creates a coherent "Execution Control Center" — see what's queued, watch it execute.

---

## References

- RFC-046: Autonomous Backlog (CLI implementation)
- RFC-100: Workers/ATC (existing Workers UI)
- RFC-094: Event-driven file refresh (backlog events)
- RFC-113: Native HTTP Bridge (API pattern)
- `src/sunwell/cli/backlog_cmd.py` (CLI reference implementation)
