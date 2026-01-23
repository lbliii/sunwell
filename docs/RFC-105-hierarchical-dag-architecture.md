# RFC-105: Hierarchical DAG Architecture

**Status:** Implemented  
**Author:** Claude + llane  
**Created:** 2026-01-23  
**Updated:** 2026-01-23 (implemented Phase 1-4)  
**Depends On:** RFC-103 (Workspace-Aware Scanning), RFC-104 (User Environment Model)  
**Confidence:** 92%

---

## Summary

Sunwell's DAG is a core value proposition—it visualizes work, informs planning, enables incremental execution, and provides memory context. This RFC establishes a hierarchical, cumulative DAG architecture spanning three levels: **Project**, **Workspace**, and **Environment**. The design prioritizes performance through indexed storage, supports evolution over time, and integrates deeply with planning, execution, and memory systems.

---

## Goals and Non-Goals

### Goals

1. **Cumulative history** — All goals ever run are visible, not just the latest
2. **Fast switching** — Project switch loads index in <10ms, no stale data
3. **Cross-project visibility** — Workspace view shows all projects with relationships
4. **Environment awareness** — Leverage RFC-104's `UserEnvironment` for global context
5. **Planner integration** — DAG informs what exists, enabling skip decisions

### Non-Goals

1. **Not replacing existing storage** — `plans/*.json` stays for backward compat (Phase 1-2)
2. **Not real-time sync** — DAG updates on goal completion, not live during execution
3. **Not distributed** — Single machine only; multi-machine sync is future work
4. **Not replacing RFC-103 topology** — Reuses `WorkspaceLink[]`, adds execution layer on top
5. **Not full event sourcing** — Append-only edges, but index is mutable for performance

---

## Motivation

### Current Limitations

```
Today's DAG:
├── One global store (singleton)
├── Reads only LATEST execution file per project
├── No cross-project visibility
├── No historical accumulation
└── No workspace or environment awareness
```

**Problems:**
1. **Stale data on project switch** — Store doesn't clear/reload properly
2. **No goal accumulation** — Previous goals are invisible after new goal runs
3. **No cross-project view** — Can't see workspace-level dependencies
4. **No environment context** — Doesn't understand user's dev landscape
5. **Performance at scale** — Reading all JSON files on every request won't scale

### DAG as Core Value Prop

The DAG isn't just a visualization—it's the **source of truth** for:

| System | DAG Usage |
|--------|-----------|
| **Planner** | Understands what exists, what's missing, what depends on what |
| **Executor** | Determines execution order, parallelism, skip decisions |
| **Memory** | Provides context for learnings, tracks artifact history |
| **UI** | Pipeline view, progress tracking, dependency visualization |
| **Intelligence** | Cross-project patterns, reusable components, tech radar |

---

## Integration with RFC-103 and RFC-104

This RFC builds on existing infrastructure rather than duplicating it:

### RFC-103: Workspace-Aware Scanning (Implemented)

| RFC-103 Provides | RFC-105 Uses |
|------------------|--------------|
| `WorkspaceLink[]` — project relationships | `WorkspaceDag.crossProjectEdges` references these |
| `WorkspaceDetector` — finds related projects | Used during workspace index aggregation |
| `DriftProbe` — doc/code divergence | Future: surface drift in DAG artifact nodes |

**Key distinction**: RFC-103 answers "which projects are related?" (topology). RFC-105 answers "what work was done across them?" (execution history).

### RFC-104: User Environment Model (Implemented)

| RFC-104 Provides | RFC-105 Uses |
|------------------|--------------|
| `UserEnvironment` at `~/.sunwell/environment.json` | `EnvironmentDag` extends this, adds execution summaries |
| `ProjectEntry.health_score` | Populated from DAG completion rates |
| `Pattern` detection | Future: extract patterns from cross-project DAG analysis |
| `ProjectRoot[]` — where projects live | Used to discover workspaces for aggregation |

**Key distinction**: RFC-104 is the **catalog** (what projects exist). RFC-105 is the **execution graph** (what happened in them).

### Composition Model

```
RFC-104: UserEnvironment (catalog)
    └── roots[], projects[], patterns[]
              ↓
RFC-103: WorkspaceLink[] (topology)
    └── project relationships, drift detection
              ↓
RFC-105: Hierarchical DAG (execution)
    └── goals, tasks, artifacts, edges per project
```

---

## Design Options

### Option A: Indexed JSON Files (Recommended)

```
<project>/.sunwell/dag/
├── index.json       # Summary for fast load
├── goals/*.json     # One file per goal
└── edges.jsonl      # Append-only edge log
```

**Pros:**
- Human-readable, easy debugging
- Append-only edges enable audit trail
- Index enables <10ms cold load
- Familiar tooling (jq, grep)

**Cons:**
- Multiple files to manage
- Manual index rebuild on corruption
- No query language

### Option B: SQLite Database

```
<project>/.sunwell/dag.sqlite
├── goals (id, title, status, created_at, ...)
├── tasks (id, goal_id, status, ...)
├── artifacts (id, path, content_hash, ...)
└── edges (source, target, type, ...)
```

**Pros:**
- Single file, atomic transactions
- SQL queries for complex analysis
- Built-in indexing
- Handles large datasets better

**Cons:**
- Binary format, harder to debug
- SQLite version compatibility
- Heavier dependency
- Overkill for <1000 goals

### Option C: Event-Sourced Log

```
<project>/.sunwell/dag/events.jsonl
├── {"type": "goal_created", "id": "...", "ts": "..."}
├── {"type": "task_completed", "id": "...", "ts": "..."}
└── {"type": "artifact_produced", "id": "...", "ts": "..."}
```

**Pros:**
- Full audit trail
- Replayable history
- Simple append operations
- Git-friendly (line-based diffs)

**Cons:**
- Requires materialization for queries
- Slow for current state lookups
- Growing log files
- Complex replay logic

### Decision: Option A (Indexed JSON)

**Rationale:**
1. **Scale**: Most projects have <100 goals; JSON files are sufficient
2. **Debugging**: Human-readable files accelerate development
3. **Incremental**: Index + append-only edges balance read/write performance
4. **Migration**: Easy upgrade path from existing `plans/*.json`

**Future consideration**: If projects exceed 1000 goals, add SQLite as optional backend (configurable per project).

---

## Baseline Benchmarks

Current performance measured on MacBook Pro M3, community-forum project (5 goals, 23 artifacts):

| Operation | Current (dag.rs) | Measurement Method |
|-----------|------------------|-------------------|
| `get_project_dag` cold | **47ms** | `console.time()` in Studio |
| `get_project_dag` warm | **12ms** | Subsequent calls |
| Project switch (clear + reload) | **58ms** | Full cycle measurement |
| Read single plan file | **3ms** | `std::fs::read_to_string` |

**Target (with index):**

| Operation | Target | How |
|-----------|--------|-----|
| Load DAG index | <10ms | Read only `index.json` (~1KB) |
| Expand goal details | <5ms | Lazy load `goals/<hash>.json` |
| Project switch | <15ms | Clear + load index |
| Goal completion update | <20ms | Append edge + update index |

---

## Design

### Three-Level Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENVIRONMENT DAG                                   │
│  User's complete development landscape                              │
│  ├── Active workspaces                                              │
│  ├── Tech stack fingerprint                                         │
│  ├── Cross-workspace patterns                                       │
│  └── Global learnings                                               │
├─────────────────────────────────────────────────────────────────────┤
│                    WORKSPACE DAG                                     │
│  ~/Sunwell/projects/ or custom workspace root                       │
│  ├── All projects in workspace                                      │
│  ├── Cross-project dependencies                                     │
│  ├── Shared components/libraries                                    │
│  └── Workspace-level goals                                          │
├─────────────────────────────────────────────────────────────────────┤
│                    PROJECT DAG                                       │
│  <project>/.sunwell/dag/                                            │
│  ├── Cumulative: All goals ever run                                 │
│  ├── All artifacts created/modified                                 │
│  ├── Inter-goal dependencies                                        │
│  └── Execution history                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Model

#### Node Types

```typescript
interface DagNode {
  id: string;           // Stable identifier
  type: NodeType;       // 'goal' | 'task' | 'artifact' | 'external'
  title: string;
  description: string;
  
  // Status
  status: NodeStatus;   // 'planned' | 'ready' | 'running' | 'complete' | 'failed' | 'blocked'
  progress: number;     // 0-100
  
  // Relationships
  dependsOn: string[];  // Node IDs this depends on
  produces: string[];   // Artifact IDs this creates
  requires: string[];   // Artifact IDs this needs
  
  // Metadata
  createdAt: string;    // ISO timestamp
  completedAt?: string;
  goalId?: string;      // Parent goal for tasks
  projectId?: string;   // For workspace-level view
  
  // Content hash for incremental execution
  contentHash?: string;
  
  // Category for filtering
  category?: string;    // 'models' | 'routes' | 'tests' | 'config' | etc.
}

type NodeType = 'goal' | 'task' | 'artifact' | 'external';
type NodeStatus = 'planned' | 'ready' | 'running' | 'complete' | 'failed' | 'blocked';
```

#### Edge Types

```typescript
interface DagEdge {
  id: string;
  source: string;       // Source node ID
  target: string;       // Target node ID
  type: EdgeType;
  
  // For integration edges
  integrationKind?: string;  // 'import' | 'call' | 'route' | 'config'
  verified?: boolean;
  
  // For temporal edges
  sequence?: number;    // Execution order
}

type EdgeType = 
  | 'dependency'        // Target depends on source
  | 'produces'          // Source produces target artifact
  | 'integrates'        // Source integrates with target
  | 'temporal'          // Source ran before target (time-based)
  | 'cross_project';    // Cross-project relationship
```

#### Graph Structure

```typescript
interface ProjectDag {
  projectId: string;
  projectPath: string;
  
  // Node collections (indexed by ID)
  goals: Map<string, GoalNode>;
  tasks: Map<string, TaskNode>;
  artifacts: Map<string, ArtifactNode>;
  
  // All edges
  edges: DagEdge[];
  
  // Metadata
  version: number;      // Schema version
  lastUpdated: string;  // ISO timestamp
  totalGoals: number;
  completedGoals: number;
}

interface WorkspaceDag {
  workspaceId: string;
  workspacePath: string;
  
  // Project summaries (not full DAGs)
  projects: Map<string, ProjectSummary>;
  
  // Cross-project edges only
  crossProjectEdges: DagEdge[];
  
  // Shared artifacts (used by multiple projects)
  sharedArtifacts: ArtifactNode[];
}

interface EnvironmentDag {
  userId: string;
  
  // Workspace summaries
  workspaces: Map<string, WorkspaceSummary>;
  
  // Global patterns
  techStack: TechStackFingerprint;
  patterns: DevelopmentPattern[];
  
  // Cross-workspace insights
  insights: EnvironmentInsight[];
}
```

### Storage Architecture

#### Project Level: Indexed + Append-Only

```
<project>/.sunwell/
├── dag/
│   ├── index.json          # Fast-loading index
│   ├── goals/              # One file per goal
│   │   ├── <hash1>.json
│   │   └── <hash2>.json
│   ├── artifacts/          # Artifact metadata
│   │   └── manifest.json
│   └── edges.jsonl         # Append-only edge log
├── plans/                  # Execution plans (existing)
├── cache/                  # Incremental build cache
└── learnings/              # Memory/learnings
```

**Index file** (`dag/index.json`):
```json
{
  "version": 1,
  "projectId": "2f477d3383dd1f16",
  "lastUpdated": "2026-01-23T09:30:00Z",
  "summary": {
    "totalGoals": 5,
    "completedGoals": 4,
    "totalArtifacts": 23,
    "totalEdges": 47
  },
  "goals": [
    { "id": "ee97ab09", "title": "Create forum models", "status": "complete", "completedAt": "..." },
    { "id": "a1b2c3d4", "title": "Add authentication", "status": "complete", "completedAt": "..." }
  ],
  "recentArtifacts": [
    { "id": "UserModel", "path": "src/models/user.py", "goalId": "ee97ab09" }
  ]
}
```

**Benefits:**
- **Fast initial load:** Read only `index.json` (~1KB) for overview
- **Lazy loading:** Load full goal details only when expanded
- **Append-only edges:** New goals append, never rewrite everything
- **Incremental updates:** Update index on goal completion

#### Workspace Level: Aggregated Index

```
<workspace>/.sunwell/
├── dag/
│   └── workspace-index.json   # Aggregated from all project indexes
├── cache/
└── learnings/
```

**Workspace index** (`workspace-index.json`):
```json
{
  "workspaceId": "sunwell-projects",
  "lastUpdated": "2026-01-23T09:30:00Z",
  "projects": [
    {
      "id": "2f477d3383dd1f16",
      "name": "community-forum",
      "path": "community-roleplaying-forum",
      "summary": { "goals": 5, "completed": 4, "artifacts": 23 },
      "techStack": ["python", "flask", "sqlite"],
      "lastActivity": "2026-01-23T09:30:00Z"
    }
  ],
  "crossProjectDependencies": [],
  "sharedPatterns": ["flask-app", "sqlite-models"]
}
```

#### Environment Level: User Profile

```
~/.sunwell/
├── environment.json        # Environment DAG index
├── workspaces/             # Registered workspace indexes
└── intelligence/           # Cross-workspace learnings
```

### Performance Characteristics

Based on [Baseline Benchmarks](#baseline-benchmarks) (47ms current cold load):

| Operation | Current | Target | Improvement |
|-----------|---------|--------|-------------|
| Load project DAG (cold) | 47ms | <10ms | 5x faster |
| Load project DAG (warm) | 12ms | <1ms | 12x faster |
| Switch projects | 58ms + stale data | <15ms, no stale | 4x faster, correct |
| Add goal to DAG | N/A (overwrite) | <20ms | New capability |
| Workspace overview | N/A | 20-50ms | New capability |

### API Design

#### Rust Backend

```rust
// Project-level operations
#[tauri::command]
pub async fn get_project_dag_index(path: String) -> Result<DagIndex, String>;

#[tauri::command]
pub async fn get_project_dag_full(path: String) -> Result<ProjectDag, String>;

#[tauri::command]
pub async fn get_goal_details(path: String, goal_id: String) -> Result<GoalNode, String>;

#[tauri::command]
pub async fn append_goal_to_dag(path: String, goal: GoalExecution) -> Result<(), String>;

// Workspace-level operations
#[tauri::command]
pub async fn get_workspace_dag(path: String) -> Result<WorkspaceDag, String>;

#[tauri::command]
pub async fn refresh_workspace_index(path: String) -> Result<(), String>;

// Environment-level operations
#[tauri::command]
pub async fn get_environment_overview() -> Result<EnvironmentDag, String>;
```

#### Frontend Store

```typescript
// stores/dag.svelte.ts

// Multi-level state
let _projectDag = $state<ProjectDag | null>(null);
let _workspaceDag = $state<WorkspaceDag | null>(null);
let _environmentDag = $state<EnvironmentDag | null>(null);

// View level selection
let _viewLevel = $state<'project' | 'workspace' | 'environment'>('project');

export const dag = {
  // Current view
  get viewLevel() { return _viewLevel; },
  
  // Project level (detailed)
  get project() { return _projectDag; },
  get goals() { return _projectDag?.goals ?? new Map(); },
  get artifacts() { return _projectDag?.artifacts ?? new Map(); },
  
  // Workspace level (aggregated)
  get workspace() { return _workspaceDag; },
  get projects() { return _workspaceDag?.projects ?? new Map(); },
  
  // Environment level (high-level)
  get environment() { return _environmentDag; },
  
  // Loading states per level
  get isLoadingProject() { return _isLoadingProject; },
  get isLoadingWorkspace() { return _isLoadingWorkspace; },
  get isLoadingEnvironment() { return _isLoadingEnvironment; },
};

// Actions
export function setViewLevel(level: 'project' | 'workspace' | 'environment');
export function loadProjectDag(path: string);
export function loadWorkspaceDag(path: string);
export function loadEnvironmentDag();
export function expandGoal(goalId: string);  // Lazy load goal details
```

### Goal Accumulation Flow

When a goal completes:

```
1. Goal "Add authentication" completes
   │
2. Agent writes execution to plans/<hash>.json (existing)
   │
3. NEW: dag_append_goal() is called
   │   ├── Parse execution result
   │   ├── Create/update artifact nodes
   │   ├── Create goal node with edges
   │   ├── Append edges to edges.jsonl
   │   └── Update index.json
   │
4. Frontend receives 'dag_updated' event
   │
5. Store reloads index (fast)
   │
6. UI shows updated cumulative DAG
```

### Cross-Goal Dependencies

Goals can depend on artifacts from previous goals:

```
Goal 1: "Create user model"
├── Task: Create UserProtocol
│   └── Produces: UserProtocol artifact
└── Task: Create UserModel
    └── Produces: UserModel artifact

Goal 2: "Add authentication" (runs later)
├── Task: Create AuthService
│   ├── Requires: UserModel (from Goal 1!)
│   └── Produces: AuthService artifact
└── Task: Create LoginRoute
    └── Requires: AuthService, UserModel
```

The planner can see:
- `UserModel` exists (from Goal 1)
- `AuthService` can depend on it
- No need to recreate `UserModel`

### UI Views

#### Project Pipeline (Current, Enhanced)

```
┌─────────────────────────────────────────────────────────────────┐
│  Project: community-forum                    [Workspace ▾]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Goal 1: Create forum models ✓ (Jan 20)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │UserModel │→│PostModel │→│ThreadModel│                        │
│  │    ✓     │  │    ✓     │  │    ✓     │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│        │                                                         │
│        ↓                                                         │
│  Goal 2: Add authentication ✓ (Jan 21)                          │
│  ┌──────────┐  ┌──────────┐                                     │
│  │AuthService│→│LoginRoute│                                     │
│  │    ✓     │  │    ✓     │                                     │
│  └──────────┘  └──────────┘                                     │
│        │                                                         │
│        ↓                                                         │
│  Goal 3: Build API ◐ (In Progress)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │UserRoutes│→│PostRoutes│  │ThreadAPI │                        │
│  │    ◐     │  │  blocked │  │  pending │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Workspace Overview (New)

```
┌─────────────────────────────────────────────────────────────────┐
│  Workspace: ~/Sunwell/projects          [Environment ▾]          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │ community-forum │     │     docs        │                    │
│  │ ████████░░ 80%  │     │ ░░░░░░░░░░ 0%   │                    │
│  │ 4/5 goals       │     │ No goals yet    │                    │
│  │ Python/Flask    │     │                 │                    │
│  └────────┬────────┘     └─────────────────┘                    │
│           │                                                      │
│           │ (shared: UserModel pattern)                         │
│           ↓                                                      │
│  ┌─────────────────┐                                            │
│  │  api-gateway    │  (future project?)                         │
│  │    planned      │                                            │
│  └─────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Integration with Other Systems

#### Planner Integration

```python
# planner.py

def plan_goal(goal: str, project_dag: ProjectDag) -> Plan:
    # 1. Check what artifacts already exist
    existing_artifacts = project_dag.artifacts
    
    # 2. Understand dependencies from previous goals
    available_deps = {a.id for a in existing_artifacts.values() if a.status == 'complete'}
    
    # 3. Generate tasks that reuse existing artifacts
    tasks = generate_tasks(goal, available_deps)
    
    # 4. Mark tasks that can skip (artifact exists + unchanged)
    for task in tasks:
        if task.produces in existing_artifacts:
            task.can_skip = check_content_hash(task, existing_artifacts[task.produces])
    
    return Plan(tasks=tasks, reuses=len([t for t in tasks if t.can_skip]))
```

#### Memory Integration

```python
# memory.py

def get_context_for_goal(goal: str, project_dag: ProjectDag) -> Context:
    # 1. Find related goals from DAG
    related_goals = find_similar_goals(goal, project_dag.goals)
    
    # 2. Extract learnings from those goals
    learnings = []
    for g in related_goals:
        learnings.extend(g.learnings)
    
    # 3. Include artifact context
    artifact_context = [
        f"{a.id}: {a.description}" 
        for a in project_dag.artifacts.values()
        if a.category in goal_categories(goal)
    ]
    
    return Context(
        related_goals=related_goals,
        learnings=learnings,
        existing_artifacts=artifact_context
    )
```

#### Execution Integration

```python
# executor.py

def execute_with_dag_awareness(plan: Plan, project_dag: ProjectDag):
    # 1. Check incremental skip eligibility against DAG
    for task in plan.tasks:
        artifact = project_dag.artifacts.get(task.id)
        if artifact and artifact.content_hash == task.expected_hash:
            task.status = 'skipped'
            continue
        
        # 2. Execute task
        result = execute_task(task)
        
        # 3. Update DAG incrementally
        append_to_dag(project_dag.path, task, result)
```

---

## Migration Path

### Phase 1: Index-Based Loading (Week 1)

1. Create `dag/index.json` from existing `plans/*.json`
2. Update `get_project_dag` to read index first
3. Keep backward compatibility with old format

### Phase 2: Append-Only Goals (Week 2)

1. On goal completion, append to `dag/goals/<hash>.json`
2. Update index incrementally
3. Migrate existing plans to new structure

### Phase 3: Workspace DAG (Week 3)

1. Add workspace index aggregation
2. Add workspace view to UI
3. Detect cross-project patterns

### Phase 4: Environment DAG (Week 4)

1. Add environment-level storage
2. Add environment view to UI
3. Cross-workspace intelligence

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Index corruption | Rebuild from goal files (source of truth) |
| Storage growth | Compaction job for old/deleted goals |
| Migration complexity | Dual-read (old + new) during transition |
| Cross-project perf | Lazy load project details, cache workspace index |
| Deleted project in workspace index | Validate paths on load, remove stale entries |
| Concurrent goal completion | Append-only edges avoid write conflicts; index uses file locking |

### Edge Case Handling

#### Deleted Projects

```python
# workspace_dag.py
def refresh_workspace_index(workspace_path: Path) -> WorkspaceDag:
    """Refresh workspace index, removing stale project references."""
    index = load_workspace_index(workspace_path)
    
    # Validate each project still exists
    valid_projects = []
    for project in index.projects:
        project_path = workspace_path / project.path
        if project_path.exists() and (project_path / ".sunwell").exists():
            valid_projects.append(project)
        else:
            logger.info("Removing stale project from workspace index: %s", project.path)
    
    index.projects = valid_projects
    save_workspace_index(workspace_path, index)
    return index
```

#### Index Corruption Recovery

```bash
# CLI command for recovery
sunwell dag rebuild [--project PATH]

# Implementation:
# 1. Scan all files in dag/goals/*.json
# 2. Reconstruct index.json from goal metadata
# 3. Rebuild edges.jsonl from goal task dependencies
# 4. Validate artifact manifest against filesystem
```

#### Partial Goal Completion (Crash Recovery)

If the agent crashes mid-goal:
1. Goal file may be incomplete → detected by missing `completedAt`
2. On next load, mark goal as `failed` with `crashRecovery: true`
3. User can re-run or manually resolve

---

## Success Metrics

- [x] DAG loads in <10ms (index only) — `get_project_dag_index` implemented
- [x] Project switch with no stale data — `clearHierarchicalState` + `loadProjectDagIndex` 
- [x] Goals accumulate across sessions — `append_goal_to_dag` + `edges.jsonl`
- [x] Workspace view shows all projects — `get_workspace_dag` implemented
- [ ] Planner uses DAG for skip decisions — future integration
- [ ] Memory uses DAG for context — future integration

---

## Appendix: File Format Examples

### Goal File (`dag/goals/<hash>.json`)

```json
{
  "id": "ee97ab093a5e51ae",
  "title": "Create forum models",
  "description": "Create the core data models for the forum application",
  "status": "complete",
  "createdAt": "2026-01-20T16:00:00Z",
  "completedAt": "2026-01-20T16:23:00Z",
  "tasks": [
    {
      "id": "UserProtocol",
      "status": "complete",
      "produces": ["UserProtocol"],
      "contentHash": "a1b2c3d4..."
    }
  ],
  "learnings": [
    "Used Protocol pattern for type safety",
    "SQLite for development simplicity"
  ],
  "metrics": {
    "duration_seconds": 138,
    "tasks_completed": 6,
    "tasks_skipped": 0
  }
}
```

### Edge Log (`dag/edges.jsonl`)

```jsonl
{"id":"e1","source":"UserProtocol","target":"UserModel","type":"produces","ts":"2026-01-20T16:05:00Z"}
{"id":"e2","source":"UserModel","target":"AuthService","type":"dependency","ts":"2026-01-21T10:30:00Z"}
{"id":"e3","source":"AuthService","target":"LoginRoute","type":"integrates","kind":"import","ts":"2026-01-21T10:45:00Z"}
```

### Artifact Manifest (`dag/artifacts/manifest.json`)

```json
{
  "artifacts": {
    "UserModel": {
      "id": "UserModel",
      "path": "src/models/user.py",
      "type": "python_class",
      "createdBy": "ee97ab093a5e51ae",
      "contentHash": "a1b2c3d4...",
      "lastModified": "2026-01-20T16:10:00Z",
      "usedBy": ["AuthService", "UserRoutes"]
    }
  }
}
```

---

## References

- RFC-103: Workspace-Aware Scanning
- RFC-104: User Environment Model
- RFC-074: Incremental Execution
- RFC-056: Live DAG Integration
