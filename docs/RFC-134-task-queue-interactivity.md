# RFC-134: Task Queue Interactivity in Main Workflow

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-25  
**Related**: RFC-114 (Backlog UI), RFC-115 (Hierarchical Goals), RFC-086 (Workflow Engine), RFC-106 (Unified Project Surface)

---

## Executive Summary

Users can see tasks being generated during goal execution but **cannot interact with them**. The interactive `BacklogPanel` (with drag-to-reorder, skip, add goals) exists but is buried in the **Workers tab** — a view designed for multi-agent orchestration, not single-user workflows.

This RFC proposes surfacing task queue interactivity in the **main Project tab** during execution, enabling users to:
- **Expand tasks** to see details and context
- **Skip tasks** they don't need
- **Reorder pending tasks** to prioritize what matters
- **Add tasks** mid-execution for emerging requirements
- **Pause and resume** with clear feedback

**Current state**: `WorkingState` shows a read-only `Progress` component. Users watch passively.

**Proposed state**: `WorkingState` includes an interactive task queue that responds to user intent without disrupting the agent.

---

## 🎯 Goals

| Goal | Benefit |
|------|---------|
| **See task details** | Understand what each task will do before/during execution |
| **Skip tasks** | Avoid wasted time on unwanted work |
| **Reorder queue** | Prioritize urgent tasks without restarting |
| **Add tasks** | Capture emerging requirements without losing context |
| **Pause/resume** | Take control when needed, resume seamlessly |
| **Progressive disclosure** | Don't overwhelm; show detail on demand |

---

## 🚫 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Replace Workers tab | Workers is for multi-agent; this is for single-user |
| Full DAG editing | Complex dependency editing belongs in Pipeline view |
| Cancel individual running tasks | Mid-tool interruption is a separate concern (RFC-TBD) |
| Persistent queue across sessions | Session checkpoints (RFC-128) handles this |

---

## 📍 User Journey Analysis

### Journey 1: "I see the tasks but what ARE they?"

**Current Experience**:
```
User kicks off: "add user authentication"
    ↓
Progress shows:
  ├─ [1] Set up auth models        ████████░░ 80%
  ├─ [2] Create login endpoint     ░░░░░░░░░░ 0%
  └─ [3] Add JWT middleware        ░░░░░░░░░░ 0%

User thinks: "What files? What approach? Can I see more?"
    ↓
No interaction possible. User waits passively.
```

**Proposed Experience**:
```
Progress shows with expandable tasks:
  ▸ [1] Set up auth models        ████████░░ 80%   [⏸ Pause]
    └─ Click to expand details
  ▸ [2] Create login endpoint     ░░░░░░░░░░ queued  [Skip]
  ▸ [3] Add JWT middleware        ░░░░░░░░░░ queued  [Skip]
                                              [+ Add Task]

User clicks [2]:
  ▾ [2] Create login endpoint     ░░░░░░░░░░ queued  [Skip]
    │
    │  📝 Description: Implement POST /login with email/password
    │  📁 Files: src/routes/auth.py, src/schemas/auth.py
    │  🔗 Depends on: [1] Set up auth models
    │  ⚡ Complexity: simple (~2 min)
    │
    └─ [Run Now] [Edit] [Skip]
```

### Journey 2: "Wait, I don't need that task"

**Current Experience**:
```
Tasks generated:
  [1] Create user model           ████████████ complete
  [2] Add admin dashboard         ░░░░░░░░░░░░ queued  ← DON'T NEED THIS
  [3] Write user tests            ░░░░░░░░░░░░ queued

User: "I don't want an admin dashboard!"
    ↓
Options: Stop everything and restart, OR wait for unwanted work.
```

**Proposed Experience**:
```
Tasks generated:
  [1] Create user model           ████████████ complete
  [2] Add admin dashboard         ░░░░░░░░░░░░ queued   [Skip]  ← CLICK
  [3] Write user tests            ░░░░░░░░░░░░ queued

User clicks [Skip] on task 2:
  [2] Add admin dashboard         ⏭ skipped (user choice)

Agent continues with [3] without interruption.
```

### Journey 3: "Actually, can you also..."

**Current Experience**:
```
Execution in progress (3/5 tasks done):
  [✓] Task 1
  [✓] Task 2  
  [✓] Task 3
  [▸] Task 4  ← running
  [ ] Task 5

User realizes: "I also need input validation!"
    ↓
Options: Wait until done, then start new goal. Context lost.
```

**Proposed Experience**:
```
Execution in progress:
  [✓] Task 1-3
  [▸] Task 4  ← running
  [ ] Task 5
  [+ Add Task]  ← CLICK

Modal:
  "Add task to queue"
  ┌─────────────────────────────────────┐
  │ Add input validation for user forms │
  │                                     │
  │ Priority: ◉ High (run next)         │
  │           ○ Normal (after current)  │
  │           ○ Low (at end)            │
  └─────────────────────────────────────┘
  [Add to Queue] [Cancel]

Result:
  [✓] Task 1-3
  [▸] Task 4
  [★] Add input validation  ← NEW, high priority
  [ ] Task 5
```

### Journey 4: "This is taking too long, let me reprioritize"

**Current Experience**:
```
Tasks:
  [▸] Task 1: Generate full test suite (10 min)  ← running
  [ ] Task 2: Fix critical bug                   ← URGENT
  [ ] Task 3: Add documentation

User: "I need the bug fix NOW, not after 10 min of tests!"
    ↓
No option. Wait or restart.
```

**Proposed Experience**:
```
Drag-and-drop reordering of pending tasks:

  [▸] Task 1: Generate test suite (running - can't reorder)
  
  Pending (drag to reorder):
  ┌─────────────────────────────────────────┐
  │ ≡ [ ] Task 2: Fix critical bug          │  ↑ DRAG UP
  │ ≡ [ ] Task 3: Add documentation         │
  └─────────────────────────────────────────┘

After drag:
  [▸] Task 1: Generate test suite
  [ ] Task 2: Fix critical bug      ← NEXT
  [ ] Task 3: Add documentation
  
  "Queue updated. Bug fix will run next."
```

### Journey 5: "Let me pause and think"

**Current Experience**:
```
User clicks [Stop]:
  - Execution stops immediately
  - Partial state may be lost
  - To continue, must re-run from scratch
```

**Proposed Experience**:
```
User clicks [Pause]:
  - Current task completes (graceful)
  - Queue preserved
  - UI shows "Paused at task 3/7"
  
Later, user clicks [Resume]:
  - Picks up from task 4
  - Completed work preserved
  - No re-generation needed
```

---

## 🏗️ Technical Design

### Component Hierarchy

```
WorkingState.svelte (updated)
  ├── StatusHeader (unchanged)
  ├── PlanningPanel (unchanged - during planning phase)
  ├── TaskQueuePanel (NEW - replaces Progress during execution)
  │   ├── RunningTask (currently executing)
  │   ├── PendingQueue (interactive list)
  │   │   ├── TaskRow (expandable, draggable)
  │   │   └── AddTaskButton
  │   └── CompletedCollapsible
  ├── QueueControls (pause/resume)
  └── LearningsPanel (unchanged)
```

### TaskQueuePanel Component

```svelte
<!-- studio/src/components/project/TaskQueuePanel.svelte -->
<script lang="ts">
  import { agent, pauseAgent, resumeAgent } from '../../stores/agent.svelte';
  import { 
    skipTask, 
    reorderTasks, 
    addTask 
  } from '../../stores/taskQueue.svelte';
  
  let expandedTaskId = $state<string | null>(null);
  let showAddModal = $state(false);
  
  // Separate running, pending, completed
  let runningTask = $derived(agent.tasks.find(t => t.status === 'running'));
  let pendingTasks = $derived(agent.tasks.filter(t => t.status === 'pending'));
  let completedTasks = $derived(agent.tasks.filter(t => 
    t.status === 'complete' || t.status === 'skipped'
  ));
</script>

<div class="task-queue">
  <!-- Running Task (not interactive) -->
  {#if runningTask}
    <div class="running-section">
      <TaskRow 
        task={runningTask} 
        expanded={expandedTaskId === runningTask.id}
        onToggle={() => expandedTaskId = expandedTaskId === runningTask.id ? null : runningTask.id}
        interactive={false}
      />
    </div>
  {/if}
  
  <!-- Pending Queue (interactive) -->
  <div class="pending-section">
    <h4>Up Next ({pendingTasks.length})</h4>
    <DraggableList 
      items={pendingTasks}
      onReorder={reorderTasks}
    >
      {#snippet item(task)}
        <TaskRow 
          {task}
          expanded={expandedTaskId === task.id}
          onToggle={() => expandedTaskId = expandedTaskId === task.id ? null : task.id}
          onSkip={() => skipTask(task.id)}
          interactive={true}
          draggable={true}
        />
      {/snippet}
    </DraggableList>
    
    <button class="add-task-btn" onclick={() => showAddModal = true}>
      + Add Task
    </button>
  </div>
  
  <!-- Completed (collapsed by default) -->
  {#if completedTasks.length > 0}
    <details class="completed-section">
      <summary>Completed ({completedTasks.length})</summary>
      {#each completedTasks as task (task.id)}
        <TaskRow {task} interactive={false} compact={true} />
      {/each}
    </details>
  {/if}
</div>

{#if showAddModal}
  <AddTaskModal onClose={() => showAddModal = false} onAdd={addTask} />
{/if}
```

### TaskRow Component (Expandable)

```svelte
<!-- studio/src/components/project/TaskRow.svelte -->
<script lang="ts">
  import type { Task } from '$lib/types';
  
  interface Props {
    task: Task;
    expanded?: boolean;
    interactive?: boolean;
    draggable?: boolean;
    compact?: boolean;
    onToggle?: () => void;
    onSkip?: () => void;
  }
  
  let { task, expanded = false, interactive = true, draggable = false, compact = false, onToggle, onSkip }: Props = $props();
</script>

<div 
  class="task-row" 
  class:expanded 
  class:running={task.status === 'running'}
  class:compact
  draggable={draggable}
>
  {#if draggable}
    <span class="drag-handle">≡</span>
  {/if}
  
  <button class="task-header" onclick={onToggle}>
    <span class="expand-icon">{expanded ? '▾' : '▸'}</span>
    <span class="task-number">[{task.index + 1}]</span>
    <span class="task-description">{task.description}</span>
    
    {#if task.status === 'running'}
      <div class="progress-bar" style="width: {task.progress}%"></div>
    {:else if task.status === 'complete'}
      <span class="status-icon complete">◆</span>
    {:else if task.status === 'skipped'}
      <span class="status-icon skipped">⏭</span>
    {:else}
      <span class="status-icon pending">○</span>
    {/if}
  </button>
  
  {#if interactive && task.status === 'pending'}
    <button class="skip-btn" onclick={onSkip} title="Skip this task">
      Skip
    </button>
  {/if}
  
  {#if expanded}
    <div class="task-details">
      {#if task.files?.length}
        <div class="detail-row">
          <span class="detail-label">📁 Files:</span>
          <span class="detail-value">{task.files.join(', ')}</span>
        </div>
      {/if}
      {#if task.dependencies?.length}
        <div class="detail-row">
          <span class="detail-label">🔗 Depends on:</span>
          <span class="detail-value">{task.dependencies.join(', ')}</span>
        </div>
      {/if}
      {#if task.estimatedDuration}
        <div class="detail-row">
          <span class="detail-label">⏱ Estimate:</span>
          <span class="detail-value">{task.estimatedDuration}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>
```

### Task Queue Store

```typescript
// studio/src/stores/taskQueue.svelte.ts

import { apiPost } from '$lib/socket';

// Project path (set when WorkingState mounts)
let _projectPath: string | null = null;

export function setTaskQueueProject(path: string): void {
  _projectPath = path;
}

/**
 * Skip a pending task.
 * Backend marks it as blocked with "User skipped" reason.
 */
export async function skipTask(taskId: string): Promise<void> {
  if (!_projectPath) return;
  
  await apiPost('/api/tasks/skip', {
    path: _projectPath,
    task_id: taskId,
  });
  
  // Agent store will receive event and update
}

/**
 * Reorder pending tasks.
 * Takes array of task IDs in new order.
 */
export async function reorderTasks(taskIds: string[]): Promise<void> {
  if (!_projectPath) return;
  
  await apiPost('/api/tasks/reorder', {
    path: _projectPath,
    order: taskIds,
  });
}

/**
 * Add a new task to the queue.
 */
export async function addTask(
  description: string, 
  priority: 'high' | 'normal' | 'low' = 'normal'
): Promise<void> {
  if (!_projectPath) return;
  
  await apiPost('/api/tasks/add', {
    path: _projectPath,
    description,
    priority,
  });
}
```

### Backend API Endpoints

```python
# src/sunwell/api/tasks.py

@router.post("/api/tasks/skip")
async def skip_task(request: SkipTaskRequest) -> dict:
    """Skip a pending task (mark as blocked with user reason)."""
    manager = get_backlog_manager(request.path)
    await manager.block_goal(request.task_id, "User skipped")
    return {"status": "skipped", "task_id": request.task_id}

@router.post("/api/tasks/reorder")
async def reorder_tasks(request: ReorderTasksRequest) -> dict:
    """Reorder pending tasks by priority."""
    manager = get_backlog_manager(request.path)
    await manager.reorder_by_ids(request.order)
    return {"status": "reordered"}

@router.post("/api/tasks/add")
async def add_task(request: AddTaskRequest) -> dict:
    """Add a new task to the queue mid-execution."""
    manager = get_backlog_manager(request.path)
    
    # Map priority to numeric value
    priority_map = {"high": 0.95, "normal": 0.7, "low": 0.3}
    
    goal = Goal(
        id=f"user-{uuid4().hex[:8]}",
        title=request.description[:60],
        description=request.description,
        priority=priority_map[request.priority],
        category="add",
        estimated_complexity="moderate",
        auto_approvable=False,
        source_signals=(),
        requires=frozenset(),
        scope=GoalScope(),
    )
    
    manager.backlog.goals[goal.id] = goal
    manager._save()
    
    return {"status": "added", "task_id": goal.id}
```

---

## 🔄 State Synchronization

### Agent → UI Flow

```
Agent executes task
    ↓
Emits task_progress event
    ↓
agent.svelte.ts receives event
    ↓
Updates _state.tasks
    ↓
TaskQueuePanel re-renders (reactive)
```

### UI → Agent Flow

```
User clicks "Skip" on task
    ↓
skipTask(taskId) called
    ↓
POST /api/tasks/skip
    ↓
BacklogManager.block_goal()
    ↓
Emits backlog_goal_skipped event
    ↓
agent.svelte.ts receives event
    ↓
Updates _state.tasks
    ↓
TaskQueuePanel shows task as skipped
```

### Reorder Flow

```
User drags task 3 above task 2
    ↓
reorderTasks(['task-3', 'task-2', ...])
    ↓
POST /api/tasks/reorder
    ↓
BacklogManager recalculates priority values
    ↓
Agent's next_goal() returns newly prioritized task
    ↓
No event needed (agent pulls next task when ready)
```

---

## 🔀 Alternatives Considered

### Alternative A: Keep BacklogPanel in Workers Tab Only (Status Quo)

**Approach**: No changes; tell users to use Workers tab.

**Pros**:
- No development effort
- Workers tab already works

**Cons**:
- Workers tab framing is wrong (multi-agent, not single-user)
- Users don't discover it
- Interaction requires tab switch (context loss)

**Decision**: Rejected — UX is unacceptably poor for primary workflow.

### Alternative B: Embed Full BacklogPanel in WorkingState

**Approach**: Import BacklogPanel directly into WorkingState.

**Pros**:
- Reuses existing component
- Full feature parity

**Cons**:
- BacklogPanel designed for standalone view, not inline
- Too much visual weight during execution
- Goal-level granularity vs task-level needed
- Polling/WebSocket setup duplicated

**Decision**: Rejected — need task-focused component, not goal-focused.

### Alternative C: Make Progress Component Interactive

**Approach**: Add click handlers directly to existing Progress.svelte.

**Pros**:
- Minimal new code
- Familiar component

**Cons**:
- Progress is read-only by design
- Would mix concerns (display vs interaction)
- Hard to add expandable details to current layout

**Decision**: Partially adopted — new TaskQueuePanel replaces Progress but uses similar visual style.

---

## 📊 Feature Matrix

| Feature | Current (Progress) | Proposed (TaskQueuePanel) | Workers Tab |
|---------|-------------------|---------------------------|-------------|
| View task list | ✅ | ✅ | ✅ |
| Progress bars | ✅ | ✅ | ✅ |
| Expand task details | ❌ | ✅ | ❌ (goals, not tasks) |
| Skip task | ❌ | ✅ | ✅ |
| Reorder tasks | ❌ | ✅ | ✅ |
| Add task | ❌ | ✅ | ✅ |
| Drag-and-drop | ❌ | ✅ | ✅ |
| Dependency graph | ❌ | ❌ (link to Pipeline) | ✅ |
| Multi-agent support | N/A | N/A | ✅ |

---

## ✅ Acceptance Criteria

### Must Have
- [ ] Tasks are expandable to show details (files, dependencies, estimate)
- [ ] Pending tasks can be skipped with one click
- [ ] Pending tasks can be reordered via drag-and-drop
- [ ] New tasks can be added mid-execution
- [ ] Skipped/completed tasks collapse out of the way

### Should Have
- [ ] Pause/resume execution with state preservation
- [ ] Visual feedback when queue changes (animation)
- [ ] Keyboard shortcuts (S to skip, Enter to expand)

### Nice to Have
- [ ] "Run this next" quick action (bumps to top)
- [ ] Bulk skip (checkboxes)
- [ ] Undo skip within 5 seconds
- [ ] Link to full Pipeline view for complex dependency editing

---

## 🧪 Testing Strategy

### Manual Testing

| Scenario | Steps | Expected |
|----------|-------|----------|
| Expand task | Click task row | Details panel appears with files, deps |
| Skip task | Click Skip on pending task | Task shows "skipped", removed from queue |
| Reorder | Drag task 3 above task 2 | Order updates, next task changes |
| Add task | Click + Add, enter description | New task appears in queue |
| Add high priority | Add task with "High" priority | Appears at top of pending |

### Integration Tests

```typescript
// studio/src/components/project/TaskQueuePanel.test.ts
import { render, fireEvent } from '@testing-library/svelte';
import TaskQueuePanel from './TaskQueuePanel.svelte';

describe('TaskQueuePanel', () => {
  it('expands task on click', async () => {
    const { getByText, queryByText } = render(TaskQueuePanel, {
      props: { tasks: mockTasks }
    });
    
    expect(queryByText('📁 Files:')).toBeNull();
    await fireEvent.click(getByText('Create user model'));
    expect(getByText('📁 Files:')).toBeInTheDocument();
  });
  
  it('calls skipTask when Skip clicked', async () => {
    const skipMock = vi.fn();
    const { getByText } = render(TaskQueuePanel, {
      props: { tasks: mockTasks, onSkip: skipMock }
    });
    
    await fireEvent.click(getByText('Skip'));
    expect(skipMock).toHaveBeenCalledWith('task-2');
  });
});
```

---

## 🗓️ Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | TaskRow with expand/collapse | 2 hours |
| **2** | TaskQueuePanel layout | 2 hours |
| **3** | Skip task (frontend + API) | 3 hours |
| **4** | Reorder tasks (drag-drop + API) | 4 hours |
| **5** | Add task modal + API | 3 hours |
| **6** | Integrate into WorkingState | 2 hours |
| **7** | Polish + testing | 4 hours |

**Total estimated effort**: 20 hours (3 days)

---

## 🔗 Dependencies

- **RFC-114 (Backlog UI)**: Reuses `skipGoal`, `reorderGoals` backend logic
- **RFC-115 (Hierarchical Goals)**: Task-level operations within milestones
- **RFC-086 (Workflow Engine)**: `pause()` / `resume()` for execution control
- **RFC-128 (Session Checkpoints)**: State preservation across pause/resume

---

## 📚 References

- `studio/src/components/Progress.svelte` — Current read-only task display
- `studio/src/components/backlog/BacklogPanel.svelte` — Full interactive backlog (Workers tab)
- `studio/src/stores/backlog.svelte.ts` — Backlog state management
- `src/sunwell/backlog/manager.py` — Backend backlog operations
