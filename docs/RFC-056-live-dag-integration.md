# RFC-056: Live DAG Integration — Wiring the Pipeline View to Real Data

**Status**: Evaluated  
**Created**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 87% 🟢  
**Depends on**: 
- RFC-055 (Planning View) — DAG visualization components ✅ Implemented
- RFC-053 (Studio Agent Bridge) — Event streaming ✅ Implemented
- RFC-046 (Autonomous Backlog) — Goal/task persistence ✅ Implemented
- RFC-040 (Plan Persistence) — Execution state storage ✅ Implemented

---

## Summary

The DAG visualization prototype (RFC-055) is working with demo data. This RFC wires it to **real execution state** so users see their actual project's task pipeline with live progress updates.

**Deliverables:**
1. Move DAG view from landing page to **per-project**
2. Rust commands to read from `.sunwell/backlog/` and `.sunwell/plans/`
3. Live updates via existing agent event stream
4. Bidirectional: execute tasks from the DAG view

---

## Current State

### What Works ✅

| Component | Status | Location |
|-----------|--------|----------|
| DAG layout (dagre) | ✅ Working | `stores/dag.ts` |
| Node rendering | ✅ Working | `components/dag/DagNode.svelte` |
| Edge rendering | ✅ Working | `components/dag/DagEdge.svelte` |
| Zoom/pan controls | ✅ Working | `components/dag/DagControls.svelte` |
| Detail panel | ✅ Working | `components/dag/DagDetail.svelte` |
| Critical path highlighting | ✅ Working | `stores/dag.ts` derived |
| "Would unblock" preview | ✅ Working | `stores/dag.ts` derived |

### What's Missing ❌

| Gap | Impact |
|-----|--------|
| Shows demo data, not real tasks | Users can't see actual work |
| Accessible from landing page | Should be per-project |
| No live updates | Doesn't reflect execution progress |
| Can't execute from DAG | View-only, not interactive |

---

## Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SVELTE FRONTEND                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Project.svelte                                          │  │
│  │  ├── [Progress Tab] ← existing linear view               │  │
│  │  └── [Pipeline Tab] ← NEW: DagCanvas + DagDetail         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↑                                  │
│                    stores/dag.ts                                │
│                              ↑                                  │
│          ┌───────────────────┴───────────────────┐             │
│          │                                       │              │
│    Rust commands                          Agent events          │
│    (initial load)                         (live updates)        │
└──────────┼───────────────────────────────────────┼──────────────┘
           ↓                                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                         RUST BACKEND                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  get_project_dag(path) → DagGraph                        │  │
│  │  - Reads .sunwell/backlog/current.json                   │  │
│  │  - Reads .sunwell/plans/<goal_hash>.json                 │  │
│  │  - Merges into unified DagGraph                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  execute_dag_node(path, node_id) → starts agent          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
           ↑                                       ↑
           │                                       │
┌──────────┴───────────────────────────────────────┴──────────────┐
│                       FILE SYSTEM                               │
│  .sunwell/                                                      │
│  ├── backlog/                                                   │
│  │   └── current.json      ← Goals with dependencies           │
│  └── plans/                                                     │
│      └── <hash>.json       ← Execution state (tasks, progress) │
└─────────────────────────────────────────────────────────────────┘
```

### Design Alternatives Considered

#### Option A: Event Streaming Only (Rejected)

**Approach**: No initial load command; rely entirely on agent events to populate DAG.

**Pros**:
- Simpler Rust backend (no file reading)
- Always synchronized with agent state

**Cons**:
- Empty DAG when no agent running
- Can't show historical state or backlog
- Users can't see planned work before execution

**Decision**: Rejected — users need to see the full pipeline, not just active execution.

---

#### Option B: Polling (Rejected)

**Approach**: Periodically poll `.sunwell/` files for changes instead of event streaming.

**Pros**:
- Simpler implementation
- Works without agent running

**Cons**:
- Higher latency (poll interval)
- Unnecessary I/O when nothing changes
- Battery/CPU impact

**Decision**: Rejected — we already have event streaming from RFC-053, use it.

---

#### Option C: Hybrid Initial Load + Events (Selected) ✅

**Approach**: Load full state on mount, then apply incremental updates via events.

**Pros**:
- Complete state visible immediately
- Low-latency live updates
- Efficient (no polling)
- Works when agent idle (shows backlog)

**Cons**:
- Slight complexity in merging initial + event state
- Potential for drift if events lost

**Mitigations**:
- Refresh button for manual resync
- Auto-refresh on tab focus (see Behaviors below)

---

### Behaviors

#### Auto-Refresh Strategy

| Trigger | Action |
|---------|--------|
| Tab becomes visible | Reload DAG from files |
| Agent starts | Subscribe to events |
| Agent stops | Final reload to sync |
| Manual refresh click | Reload DAG from files |

**Rationale**: Tab focus refresh catches any missed updates without constant polling. Event streaming handles real-time during execution.

```typescript
// In Project.svelte
import { onMount } from 'svelte';

onMount(() => {
  const handleVisibilityChange = () => {
    if (!document.hidden && activeTab === 'pipeline') {
      loadDag();
    }
  };
  document.addEventListener('visibilitychange', handleVisibilityChange);
  return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
});
```

---

### Data Flow

#### 1. Initial Load

When user opens a project:

```
User opens project
      ↓
Project.svelte mounts
      ↓
invoke('get_project_dag', { path })
      ↓
Rust reads .sunwell/backlog/current.json
Rust reads .sunwell/plans/*.json
      ↓
Returns DagGraph { nodes, edges, goal, totalProgress }
      ↓
dagGraph.set(data)
      ↓
Dagre computes layout
      ↓
SVG renders
```

#### 2. Live Updates

When agent is executing:

```
Agent emits task_start { task_id, description }
      ↓
agent-event listener in agent.ts
      ↓
Also update dagGraph store:
  - Find node by task_id
  - Set status = 'running'
      ↓
SVG re-renders with pulsing node
      ↓
Agent emits task_progress { task_id, progress: 65 }
      ↓
Update node.progress = 65
      ↓
Progress bar updates
      ↓
Agent emits task_complete { task_id }
      ↓
Update node.status = 'complete'
Update dependent nodes to 'ready' if all deps met
      ↓
SVG re-renders, edges turn green
```

#### 3. Execute from DAG

When user clicks "Execute" on a node:

```
User clicks node → detail panel opens
      ↓
User clicks "▶ Execute"
      ↓
invoke('execute_dag_node', { path, nodeId })
      ↓
Rust: sunwell agent run --goal-id <nodeId> --json
      ↓
Events stream back (existing RFC-053 flow)
      ↓
DAG updates live
```

---

## Implementation

### Phase 1: Rust Commands (Day 1)

#### `get_project_dag`

```rust
// studio/src-tauri/src/dag.rs

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;

#[derive(Debug, Serialize, Deserialize)]
pub struct DagNode {
    pub id: String,
    pub title: String,
    pub description: String,
    pub status: String,  // pending, ready, running, complete, failed, blocked
    pub source: String,  // ai, human, external
    pub progress: u8,
    pub priority: f32,
    pub effort: String,
    pub depends_on: Vec<String>,
    pub category: Option<String>,
    pub current_action: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DagEdge {
    pub id: String,
    pub source: String,
    pub target: String,
    pub artifact: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DagGraph {
    pub nodes: Vec<DagNode>,
    pub edges: Vec<DagEdge>,
    pub goal: Option<String>,
    pub total_progress: u8,
}

#[tauri::command]
pub async fn get_project_dag(path: String) -> Result<DagGraph, String> {
    let project_path = Path::new(&path);
    
    // 1. Read backlog (goals)
    let backlog_path = project_path.join(".sunwell/backlog/current.json");
    let backlog = read_backlog(&backlog_path)?;
    
    // 2. Read latest execution state (tasks within goals)
    let plans_dir = project_path.join(".sunwell/plans");
    let execution = read_latest_execution(&plans_dir)?;
    
    // 3. Merge into DagGraph
    let graph = merge_to_dag(backlog, execution)?;
    
    Ok(graph)
}

fn read_backlog(path: &Path) -> Result<Backlog, String> {
    if !path.exists() {
        return Ok(Backlog::default());
    }
    
    let content = std::fs::read_to_string(path)
        .map_err(|e| format!("Failed to read backlog: {}", e))?;
    
    serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse backlog: {}", e))
}

fn read_latest_execution(plans_dir: &Path) -> Result<Option<SavedExecution>, String> {
    if !plans_dir.exists() {
        return Ok(None);
    }
    
    // Find most recent .json file
    let mut entries: Vec<_> = std::fs::read_dir(plans_dir)
        .map_err(|e| format!("Failed to read plans dir: {}", e))?
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map_or(false, |ext| ext == "json"))
        .filter(|e| !e.path().to_string_lossy().contains(".trace"))
        .collect();
    
    entries.sort_by_key(|e| {
        e.metadata().ok().and_then(|m| m.modified().ok())
    });
    
    if let Some(latest) = entries.last() {
        let content = std::fs::read_to_string(latest.path())
            .map_err(|e| format!("Failed to read plan: {}", e))?;
        
        let execution: SavedExecution = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse plan: {}", e))?;
        
        return Ok(Some(execution));
    }
    
    Ok(None)
}

fn merge_to_dag(backlog: Backlog, execution: Option<SavedExecution>) -> Result<DagGraph, String> {
    let mut nodes = Vec::new();
    let mut edges = Vec::new();
    let mut completed_count = 0;
    
    // If we have execution state, use tasks from there
    if let Some(exec) = &execution {
        for artifact in &exec.graph.artifacts {
            let status = if exec.completed.contains_key(&artifact.id) {
                completed_count += 1;
                "complete"
            } else if exec.failed.contains_key(&artifact.id) {
                "failed"
            } else if artifact.id == exec.current_artifact.as_deref().unwrap_or("") {
                "running"
            } else if is_ready(&artifact.id, &artifact.depends_on, &exec.completed) {
                "ready"
            } else {
                "blocked"
            };
            
            nodes.push(DagNode {
                id: artifact.id.clone(),
                title: artifact.description.clone(),
                description: artifact.description.clone(),
                status: status.to_string(),
                source: "ai".to_string(),
                progress: exec.completed.get(&artifact.id)
                    .map(|c| 100)
                    .unwrap_or(0),
                priority: artifact.priority.unwrap_or(0.5),
                effort: "medium".to_string(),
                depends_on: artifact.depends_on.clone(),
                category: artifact.category.clone(),
                current_action: None,
            });
            
            // Create edges for dependencies
            for dep in &artifact.depends_on {
                edges.push(DagEdge {
                    id: format!("{}->{}", dep, artifact.id),
                    source: dep.clone(),
                    target: artifact.id.clone(),
                    artifact: None,
                });
            }
        }
    }
    
    // Also include goals from backlog that aren't in current execution
    for (goal_id, goal) in &backlog.goals {
        if !nodes.iter().any(|n| n.id == *goal_id) {
            let status = if backlog.completed.contains(goal_id) {
                "complete"
            } else if backlog.blocked.contains_key(goal_id) {
                "blocked"
            } else {
                "pending"
            };
            
            nodes.push(DagNode {
                id: goal_id.clone(),
                title: goal.title.clone(),
                description: goal.description.clone(),
                status: status.to_string(),
                source: if goal.source_signals.is_empty() { "human" } else { "ai" }.to_string(),
                progress: if status == "complete" { 100 } else { 0 },
                priority: goal.priority,
                effort: goal.estimated_complexity.clone(),
                depends_on: goal.requires.iter().cloned().collect(),
                category: Some(goal.category.clone()),
                current_action: None,
            });
        }
    }
    
    let total = nodes.len();
    let progress = if total > 0 {
        ((completed_count as f32 / total as f32) * 100.0) as u8
    } else {
        0
    };
    
    Ok(DagGraph {
        nodes,
        edges,
        goal: execution.map(|e| e.goal),
        total_progress: progress,
    })
}

fn is_ready(id: &str, deps: &[String], completed: &HashMap<String, ArtifactCompletion>) -> bool {
    deps.iter().all(|d| completed.contains_key(d))
}
```

#### `execute_dag_node`

```rust
#[tauri::command]
pub async fn execute_dag_node(
    app: tauri::AppHandle,
    path: String,
    node_id: String,
) -> Result<(), String> {
    // Get the node's description as the goal
    let dag = get_project_dag(path.clone()).await?;
    let node = dag.nodes.iter()
        .find(|n| n.id == node_id)
        .ok_or_else(|| format!("Node {} not found", node_id))?;
    
    // Start agent with this specific task
    // Uses existing run_goal infrastructure from RFC-053
    crate::agent::run_goal(app, node.description.clone(), Some(path)).await
}
```

### Phase 2: Move to Project View (Day 1)

Update `Project.svelte` to include the DAG view as a tab:

```svelte
<!-- Project.svelte additions -->
<script>
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { dagGraph, setGraph, selectedNode } from '../stores/dag';
  
  let activeTab: 'progress' | 'pipeline' = 'progress';
  
  async function loadDag() {
    if (!$currentProject?.path) return;
    
    try {
      const graph = await invoke<DagGraph>('get_project_dag', { 
        path: $currentProject.path 
      });
      setGraph(graph);
    } catch (e) {
      console.error('Failed to load DAG:', e);
    }
  }
  
  // Load DAG when switching to pipeline tab
  $: if (activeTab === 'pipeline' && $currentProject?.path) {
    loadDag();
  }
</script>

<!-- Tab switcher -->
<div class="view-tabs">
  <button 
    class="tab" 
    class:active={activeTab === 'progress'}
    on:click={() => activeTab = 'progress'}
  >
    Progress
  </button>
  <button 
    class="tab" 
    class:active={activeTab === 'pipeline'}
    on:click={() => activeTab = 'pipeline'}
  >
    Pipeline
  </button>
</div>

<!-- Content -->
{#if activeTab === 'progress'}
  <!-- Existing progress view -->
{:else if activeTab === 'pipeline'}
  <div class="pipeline-view">
    <DagControls onFitView={...} onRefresh={loadDag} />
    <div class="pipeline-content">
      <DagCanvas />
      {#if $selectedNode}
        <DagDetail />
      {/if}
    </div>
  </div>
{/if}
```

### Phase 3: Live Updates (Day 2)

Update `agent.ts` to also update the DAG store:

```typescript
// In handleAgentEvent():

import { dagGraph, updateNode, completeNode } from './dag';

case 'task_start': {
  const taskId = data.task_id as string;
  const description = data.description as string;
  
  // Update existing agent state (unchanged)
  agentState.update(s => { ... });
  
  // ALSO update DAG
  updateNode(taskId, { 
    status: 'running',
    currentAction: description,
  });
  break;
}

case 'task_progress': {
  const taskId = data.task_id as string;
  const progress = data.progress as number;
  
  // Update DAG progress
  updateNode(taskId, { progress });
  break;
}

case 'task_complete': {
  const taskId = data.task_id as string;
  
  // Update DAG - this also updates dependent node statuses
  completeNode(taskId);
  break;
}
```

### Phase 4: Execute from DAG (Day 2)

Update `DagDetail.svelte`:

```svelte
<script>
  import { invoke } from '@tauri-apps/api/core';
  import { currentProject } from '../stores/project';
  
  async function handleExecute() {
    if (!node || !$currentProject?.path) return;
    
    try {
      await invoke('execute_dag_node', {
        path: $currentProject.path,
        nodeId: node.id,
      });
    } catch (e) {
      console.error('Failed to execute:', e);
    }
  }
</script>

{#if node.status === 'ready'}
  <Button variant="primary" on:click={handleExecute}>
    ▶ Execute
  </Button>
{/if}
```

---

## Data Model Mapping

### From `.sunwell/backlog/current.json`

```json
{
  "goals": {
    "add-auth": {
      "id": "add-auth",
      "title": "Add authentication",
      "description": "Implement JWT auth",
      "priority": 0.9,
      "requires": ["user-model"],
      "category": "auth",
      "source_signals": ["TODO:routes.py:45"]
    }
  },
  "completed": ["user-model"],
  "in_progress": "add-auth",
  "blocked": {}
}
```

Maps to:

```typescript
DagNode {
  id: "add-auth",
  title: "Add authentication",
  description: "Implement JWT auth",
  status: "running",  // because it's in_progress
  source: "ai",       // because source_signals not empty
  priority: 0.9,
  dependsOn: ["user-model"],
  category: "auth",
}
```

### From `.sunwell/plans/<hash>.json`

```json
{
  "goal": "Build forum app",
  "graph": {
    "artifacts": [
      {
        "id": "user-model",
        "description": "Create User model",
        "depends_on": [],
        "priority": 1.0
      }
    ]
  },
  "execution": {
    "completed": {
      "user-model": { "content_hash": "abc123", "verified": true }
    },
    "failed": {}
  }
}
```

Maps to task-level nodes with execution status.

---

## Edge Cases

### No Backlog Yet

Project opened but no `.sunwell/` directory:

```typescript
if (nodes.length === 0) {
  // Show empty state with "Run a goal to see your pipeline"
}
```

### Backlog Without Execution

Goals exist but agent never ran:

- Show goals as nodes
- All marked as "pending" or "ready" based on dependencies

### Multiple Executions

Multiple plan files in `.sunwell/plans/`:

- Load the most recent one (by mtime)
- Future: Could show history dropdown

### Stale Execution State

Execution state is old, backlog has new goals:

- Merge both: execution tasks + backlog goals
- Mark backlog-only goals as "pending"

---

## Testing Plan

### Unit Tests (Rust)

```rust
// studio/src-tauri/src/dag_test.rs

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    
    #[test]
    fn test_empty_project_returns_empty_dag() {
        let tmp = TempDir::new().unwrap();
        let result = get_project_dag(tmp.path().to_string_lossy().to_string());
        assert!(result.is_ok());
        assert_eq!(result.unwrap().nodes.len(), 0);
    }
    
    #[test]
    fn test_backlog_creates_goal_nodes() {
        let tmp = TempDir::new().unwrap();
        let backlog_dir = tmp.path().join(".sunwell/backlog");
        std::fs::create_dir_all(&backlog_dir).unwrap();
        std::fs::write(
            backlog_dir.join("current.json"),
            r#"{"goals":{"test-goal":{"title":"Test","description":"Test goal"}}}"#
        ).unwrap();
        
        let result = get_project_dag(tmp.path().to_string_lossy().to_string()).unwrap();
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].title, "Test");
    }
    
    #[test]
    fn test_execution_state_marks_completed() {
        // Create backlog + execution with completed task
        // Verify node.status == "complete"
    }
}
```

### Unit Tests (TypeScript)

```typescript
// studio/src/stores/dag.test.ts

import { get } from 'svelte/store';
import { dagGraph, updateNode, completeNode, setGraph } from './dag';

describe('DAG store', () => {
  beforeEach(() => {
    setGraph({ nodes: [], edges: [], goal: undefined, totalProgress: 0 });
  });

  test('updateNode changes node status', () => {
    setGraph({
      nodes: [{ id: 'task-1', status: 'pending', /* ... */ }],
      edges: [],
    });
    
    updateNode('task-1', { status: 'running' });
    
    const graph = get(dagGraph);
    expect(graph.nodes[0].status).toBe('running');
  });

  test('completeNode updates dependents to ready', () => {
    setGraph({
      nodes: [
        { id: 'task-1', status: 'running', dependsOn: [] },
        { id: 'task-2', status: 'blocked', dependsOn: ['task-1'] },
      ],
      edges: [{ id: 'e1', source: 'task-1', target: 'task-2' }],
    });
    
    completeNode('task-1');
    
    const graph = get(dagGraph);
    expect(graph.nodes[0].status).toBe('complete');
    expect(graph.nodes[1].status).toBe('ready');  // Unblocked!
  });
});
```

### Integration Tests

```typescript
// tests/integration/dag-e2e.spec.ts

import { test, expect } from '@playwright/test';
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

test.describe('DAG Integration', () => {
  let testProjectPath: string;

  test.beforeEach(async () => {
    // Create temp project with .sunwell directory
    testProjectPath = fs.mkdtempSync('/tmp/sunwell-test-');
    fs.mkdirSync(path.join(testProjectPath, '.sunwell', 'backlog'), { recursive: true });
    fs.mkdirSync(path.join(testProjectPath, '.sunwell', 'plans'), { recursive: true });
  });

  test('loads DAG from real .sunwell files', async ({ page }) => {
    // Write test backlog
    fs.writeFileSync(
      path.join(testProjectPath, '.sunwell', 'backlog', 'current.json'),
      JSON.stringify({
        goals: {
          'add-auth': { title: 'Add Auth', description: 'JWT auth', priority: 0.9 }
        }
      })
    );

    // Open project in Studio
    await page.goto(`sunwell://project?path=${testProjectPath}`);
    await page.click('[data-testid="pipeline-tab"]');

    // Verify node rendered
    await expect(page.locator('.dag-node')).toHaveCount(1);
    await expect(page.locator('.dag-node .node-title')).toHaveText('Add Auth');
  });

  test('live updates when agent runs', async ({ page }) => {
    // Start with empty project
    await page.goto(`sunwell://project?path=${testProjectPath}`);
    await page.click('[data-testid="pipeline-tab"]');

    // Run agent in background
    const agent = spawn('sunwell', ['agent', 'run', '--goal', 'Test', '--json'], {
      cwd: testProjectPath,
    });

    // Wait for DAG to populate
    await expect(page.locator('.dag-node')).toHaveCount.toBeGreaterThan(0, { timeout: 10000 });

    // Verify live status updates
    await expect(page.locator('.dag-node.status-running')).toBeVisible();

    agent.kill();
  });

  test('execute from DAG starts agent', async ({ page }) => {
    // Setup project with ready task
    // ...
    
    await page.click('[data-testid="pipeline-tab"]');
    await page.click('.dag-node[data-status="ready"]');
    await page.click('button:has-text("Execute")');

    // Verify agent started
    await expect(page.locator('.dag-node.status-running')).toBeVisible();
  });
});
```

### Manual Testing Checklist

| Scenario | Steps | Expected |
|----------|-------|----------|
| Empty project | Open new project → Pipeline tab | "Run a goal to see your pipeline" |
| Backlog only | Open project with `.sunwell/backlog/` | Goals shown as pending/ready nodes |
| In-progress | Open project while agent running | Running task pulses, progress updates |
| Completed | Open project after successful run | Green checkmarks, 100% progress |
| Execute ready | Click ready node → Execute | Agent starts, node turns to running |
| Large graph | Open project with 50+ goals | Renders < 500ms, zoom/pan works |
| Tab switch | Progress tab → Pipeline tab | DAG loads, data matches |
| Refresh | Click refresh button | UI matches current file state |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| File format mismatch | High | Validate JSON schema, handle missing fields gracefully |
| Race condition (file write + read) | Medium | BacklogManager uses file locking; read retries on parse error |
| Large graphs (100+ nodes) | Medium | See "Large Graph Strategy" below |
| Stale UI after agent crash | Low | Auto-refresh on tab focus + manual refresh button |
| Thread safety (concurrent access) | Medium | Read-only from Rust; Python agent owns writes |

### Large Graph Strategy

For projects with many tasks (100+ nodes), the following optimizations apply:

**Layout Performance**:
- Dagre handles 200+ nodes efficiently (< 100ms layout time)
- Above 200 nodes: warn user, suggest filtering by category

**Rendering Performance**:
```typescript
// In DagCanvas.svelte — only render visible nodes
$: visibleNodes = $layoutedGraph.nodes.filter(node => {
  const nodeX = (node.x ?? 0) * $dagViewState.zoom + $dagViewState.pan.x;
  const nodeY = (node.y ?? 0) * $dagViewState.zoom + $dagViewState.pan.y;
  return nodeX > -200 && nodeX < viewportWidth + 200 
      && nodeY > -200 && nodeY < viewportHeight + 200;
});
```

**Category Filtering** (future enhancement):
- Add dropdown to filter by `node.category`
- "Show: All | Models | Routes | Auth | Tests"
- Reduces cognitive load for complex projects

### Thread Safety

**Read/Write Separation**:
- **Rust (Studio)**: Read-only access to `.sunwell/` files
- **Python (Agent)**: Exclusive write access via `BacklogManager` and `ExecutionStore`

**File Access Pattern**:
```
Agent (Python)          Studio (Rust)
      │                      │
      │  writes to           │  reads from
      ▼                      ▼
  .sunwell/backlog/     .sunwell/backlog/
  .sunwell/plans/       .sunwell/plans/
      │                      │
      │                      │
  [file lock held]      [no lock needed]
```

**Edge Case — Partial Write**:
If Rust reads while Python is mid-write:
1. JSON parse fails → return empty/cached state
2. Frontend shows "Loading..." briefly
3. Next event or refresh corrects state

This is acceptable because:
- Writes complete in < 50ms typically
- Events provide authoritative real-time state
- Manual refresh available

---

## Implementation Checklist

### Phase 1: Rust Commands (Day 1 AM)
- [ ] Add `dag.rs` with `DagNode`, `DagEdge`, `DagGraph` structs
- [ ] Implement `read_backlog()` with graceful fallback for missing/malformed JSON
- [ ] Implement `read_latest_execution()` with mtime sorting
- [ ] Implement `merge_to_dag()` to combine backlog + execution
- [ ] Implement `get_project_dag` Tauri command
- [ ] Implement `execute_dag_node` Tauri command (calls existing `run_goal`)
- [ ] Register commands in `main.rs`
- [ ] Add Rust unit tests for edge cases (empty project, parse errors)

### Phase 2: Project Integration (Day 1 PM)
- [ ] Add view tabs to `Project.svelte` (Progress | Pipeline)
- [ ] Implement `loadDag()` function calling `get_project_dag`
- [ ] Load DAG on tab switch to Pipeline
- [ ] Add `visibilitychange` listener for auto-refresh on tab focus
- [ ] Pass project path through to `DagDetail` for execution
- [ ] Add empty state: "Run a goal to see your pipeline"
- [ ] Keep demo on landing page (unchanged)

### Phase 3: Live Updates (Day 2 AM)
- [ ] Import `updateNode`, `completeNode` in `agent.ts`
- [ ] Update `task_start` handler to also call `updateNode()`
- [ ] Update `task_progress` handler to also update DAG progress
- [ ] Update `task_complete` handler to call `completeNode()`
- [ ] Add `task_failed` handler for DAG error state
- [ ] Add TypeScript unit tests for store updates

### Phase 4: Execution (Day 2 PM)
- [ ] Wire "Execute" button in `DagDetail.svelte` to `execute_dag_node`
- [ ] Add loading state while agent starts
- [ ] Handle error: node not ready (show toast)
- [ ] Handle error: agent already running (show toast)
- [ ] Disable Execute button while running

### Phase 5: Testing & Quality (Day 3)
- [ ] Run all Rust unit tests
- [ ] Run all TypeScript unit tests
- [ ] Run integration tests (see Testing Plan)
- [ ] Complete manual testing checklist
- [ ] Measure load time on `forum_app` example
- [ ] Verify no memory leaks (heap snapshot)
- [ ] Update CHANGELOG

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Load time | < 500ms | Time from tab click to DAG rendered |
| Live update latency | < 100ms | Time from agent event to UI update |
| Data accuracy | 100% | All file state reflected in UI |
| Execute flow | ≤ 2 clicks | Node click → Execute button |
| Large graph performance | < 1s | 100+ node layout + render |
| Memory (100 nodes) | < 50MB | Heap snapshot with active DAG |

### Quality Gates

Before shipping:
- [ ] All integration tests pass
- [ ] Manual testing checklist complete
- [ ] Load time measured on real project (forum_app example)
- [ ] No memory leaks after 10 tab switches

---

## Open Questions (Resolved)

### Q: Should DAG auto-refresh on tab focus?

**A: Yes.** Implemented via `visibilitychange` listener. When user switches back to Pipeline tab after being away, we reload from files. This catches any changes made by agent while tab was hidden.

### Q: How to handle 100+ node graphs?

**A: Viewport culling + future category filter.** 
- Dagre handles layout efficiently
- Only render nodes in viewport (see Large Graph Strategy above)
- Future: Add category dropdown filter to reduce visual complexity

### Q: What if agent is already running when user opens Pipeline tab?

**A: Works correctly.**
1. Initial load gets current file state (including `in_progress`)
2. Event listener attaches and receives subsequent updates
3. Running tasks show as "running" immediately

---

## Future Enhancements (Out of Scope)

These are logged for future RFCs:

1. **History dropdown**: Show previous executions, not just latest
2. **Category filter**: Filter nodes by category to reduce complexity
3. **Dependency analysis**: "What blocks this?" and "What does this unblock?" queries
4. **Export**: Export DAG as Mermaid/PNG for documentation
5. **Comparison view**: Diff between planned vs actual execution

---

## References

- `src/sunwell/backlog/manager.py:123-515` — BacklogManager with file locking
- `src/sunwell/naaru/persistence.py:179-431` — SavedExecution model
- `studio/src/stores/dag.ts` — DAG store (459 lines, verified working)
- `studio/src/components/dag/` — All DAG components (verified working)
- `studio/src-tauri/src/commands.rs:137` — Existing `run_goal` command
- RFC-053 (Studio Agent Bridge) — Event streaming ✅
- RFC-046 (Autonomous Backlog) — Goal persistence ✅
- RFC-040 (Plan Persistence) — Execution state ✅
