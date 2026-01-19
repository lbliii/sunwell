# RFC-040: Plan Persistence and Incremental Execution

| Field | Value |
|-------|-------|
| **RFC** | 040 |
| **Title** | Plan Persistence and Incremental Execution |
| **Status** | Draft |
| **Created** | 2026-01-19 |
| **Author** | llane |
| **Builds on** | RFC-036 (Artifact-First Planning), RFC-032 (Agent Mode) |
| **Prerequisites** | RFC-036 merged (provides ArtifactGraph), `get_dependents()` API added |

---

## Abstract

Sunwell's artifact-first planning (RFC-036) creates sophisticated DAGs representing work to be done, but these plans are **ephemeral** — lost after execution, unresumable on interruption, and rebuilt from scratch on re-runs.

This RFC proposes **plan persistence**: saving the artifact graph, execution state, and content hashes to disk. This enables:

1. **Resume** — Pick up interrupted builds mid-wave
2. **Audit** — See what was planned vs. executed
3. **Incremental** — Skip unchanged artifacts, re-run only what's affected
4. **Preview** — Show the plan before committing tokens/time

**The key insight**: Build systems have done this for decades. Make, Bazel, and Nix persist dependency graphs and only rebuild what changed. Sunwell should do the same.

```
CURRENT:    Goal → Plan → Execute → (plan lost)
                          ↓ (interrupted)
                          Start over

PROPOSED:   Goal → Plan → Save → Execute → Save progress
                          ↓ (interrupted)
                          Resume from checkpoint
```

---

## Goals and Non-Goals

### Goals

1. **Plan persistence** — Save `ArtifactGraph` to disk after discovery
2. **Execution trace** — Log which artifacts completed, failed, or were skipped
3. **Resume protocol** — Load saved plan, skip completed work, continue
4. **Content hashing** — Detect when artifact outputs changed
5. **Invalidation cascade** — Re-run dependents when a source artifact changes
6. **Plan preview** — Show cost/complexity estimate before executing

### Non-Goals

1. **Version control integration** — Not managing git branches/commits (separate concern)
2. **Distributed execution** — Plans are local; remote execution is future work
3. **Full build system** — This is persistence, not a Make replacement
4. **Schema evolution** — Migrating old plans to new schemas is out of scope

---

## Motivation

### The Ephemeral Problem

Currently, Sunwell's planning is ephemeral:

```python
# RFC-036: Artifact discovery
graph = await planner.discover_graph(goal)  # ← Created in memory

# Execute
result = await executor.execute(graph, create_fn)  # ← Graph is used

# After execution: graph is gone
# - Can't see what was planned
# - Can't resume if interrupted
# - Must re-plan from scratch on re-run
```

**Concrete problems:**

| Scenario | Current Behavior | Desired Behavior |
|----------|-----------------|------------------|
| Interrupted mid-build | Start over | Resume from last completed wave |
| Re-run same goal | Full re-plan, full re-execute | Skip unchanged artifacts |
| Debug failed artifact | Re-run entire graph | Re-run just the failed branch |
| Cost estimation | Unknown until done | Preview before committing |
| Audit trail | None | Full history of plans |

### The Build System Model

Build systems solved this decades ago:

```makefile
# Make persists:
# 1. Dependency graph (in the Makefile itself)
# 2. File modification times (filesystem metadata)
# 3. Implicit state (which targets exist)

# Result: `make` only rebuilds what changed
app: main.o utils.o
	$(CC) -o $@ $^  # Only runs if deps are newer
```

Sunwell has the graph (RFC-036), but lacks:
- **Persistence** — Graph not saved
- **Content tracking** — No hash of artifact outputs
- **Incremental logic** — No "what changed?" detection

### Evidence: Infrastructure Exists

The persistence infrastructure is **already there** but unused:

```python
# ArtifactGraph has serialization (artifacts.py:644-657)
def to_dict(self) -> dict[str, Any]:
    return {
        "artifacts": {aid: spec.to_dict() for aid, spec in self._artifacts.items()},
        "waves": self.execution_waves() if self._artifacts else [],
    }

@classmethod
def from_dict(cls, data: dict[str, Any]) -> ArtifactGraph:
    graph = cls()
    for spec_data in data.get("artifacts", {}).values():
        graph.add(ArtifactSpec.from_dict(spec_data))
    return graph
```

```python
# AgentCheckpoint exists for task-based checkpointing (checkpoint.py:89-203)
@dataclass
class AgentCheckpoint:
    goal: str
    tasks: list[Task]
    completed_ids: set[str]
    artifacts: list[Path]
    # ... can save/load from disk
```

**Gap**: No equivalent `ArtifactCheckpoint` that saves the **graph** and **per-artifact state**.

### Prerequisite: ArtifactGraph.get_dependents()

The invalidation cascade requires traversing from an artifact to its dependents. The `_dependents` dict exists internally (`artifacts.py:276`) but has no public API. **This RFC requires adding:**

```python
# Addition to ArtifactGraph (artifacts.py)
def get_dependents(self, artifact_id: str) -> set[str]:
    """Get artifacts that depend on this artifact.
    
    Args:
        artifact_id: The artifact to find dependents for
        
    Returns:
        Set of artifact IDs that have this artifact in their requires
    """
    self._ensure_dependents_initialized()
    return self._dependents.get(artifact_id, set()).copy()
```

**Implementation note**: Add this method to `ArtifactGraph` in Phase 1 before building the invalidation cascade.

### Relationship to AgentCheckpoint

The existing `AgentCheckpoint` (`checkpoint.py:89-203`) provides **task-based** checkpointing for RFC-032. This RFC introduces **artifact-based** persistence via `SavedExecution`:

| Aspect | AgentCheckpoint | SavedExecution (new) |
|--------|-----------------|---------------------|
| **Unit** | Task | Artifact |
| **Graph** | Task list (flat) | ArtifactGraph (DAG) |
| **Resume** | Resume tasks | Resume waves |
| **Incremental** | No | Yes (content hashing) |
| **Use case** | Long-running agent | Build-like workflows |

**Coexistence strategy**: Both will exist. `AgentCheckpoint` for general agent sessions; `SavedExecution` for artifact-first planning (RFC-036). Future work may unify them.

---

## Core Concepts

### Plan vs Checkpoint

| Concept | Purpose | Contents |
|---------|---------|----------|
| **Plan** | What to do | ArtifactGraph (specs, dependencies) |
| **Checkpoint** | Progress so far | Completed IDs, outputs, hashes |
| **Execution Trace** | What happened | Per-artifact timing, errors, model tier |

A **saved execution** combines all three:

```python
@dataclass
class SavedExecution:
    """Complete state for a goal's execution."""
    
    # Identity
    goal: str
    goal_hash: str  # Deterministic hash for lookup
    
    # Plan (RFC-036)
    graph: ArtifactGraph
    
    # Progress
    completed: dict[str, ArtifactResult]
    failed: dict[str, str]  # artifact_id → error
    
    # Content tracking
    content_hashes: dict[str, str]  # artifact_id → sha256 of output
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    model_distribution: dict[str, int]  # small/medium/large counts
```

### Content Hashing

To know if an artifact needs re-execution, we hash its output:

```python
def hash_artifact_output(artifact_id: str, output: str | Path) -> str:
    """Hash artifact output for change detection."""
    import hashlib
    
    if isinstance(output, Path):
        content = output.read_bytes()
    else:
        content = output.encode()
    
    return hashlib.sha256(content).hexdigest()[:16]
```

**Hash storage:**
```json
{
  "UserProtocol": "a1b2c3d4e5f6g7h8",
  "AuthService": "9i0j1k2l3m4n5o6p",
  ...
}
```

### Invalidation Cascade

When an artifact changes, its dependents must re-run:

```
UserProtocol (changed) ──→ UserModel (must re-run)
                       ├─→ AuthService (must re-run)
                       │         ↓
                       └──→ UserRoutes (must re-run)
```

```python
def find_invalidated(
    graph: ArtifactGraph,
    changed_ids: set[str],
) -> set[str]:
    """Find all artifacts invalidated by changes."""
    
    invalidated = set(changed_ids)
    
    # BFS from changed artifacts to their dependents
    queue = list(changed_ids)
    while queue:
        artifact_id = queue.pop(0)
        for dependent_id in graph.get_dependents(artifact_id):
            if dependent_id not in invalidated:
                invalidated.add(dependent_id)
                queue.append(dependent_id)
    
    return invalidated
```

---

## Storage Model

### Directory Structure

```
.sunwell/
├── plans/
│   ├── <goal_hash>.json          # Saved plan + execution state
│   └── <goal_hash>.trace.jsonl   # Execution events (append-only)
├── hashes/
│   └── <goal_hash>.json          # Content hashes for incremental
└── checkpoints/
    └── agent-*.json              # Existing RFC-032 checkpoints
```

### Plan File Format

```json
{
  "version": "1.0",
  "goal": "Build a REST API with authentication",
  "goal_hash": "a1b2c3d4",
  "created_at": "2026-01-19T10:30:00Z",
  "updated_at": "2026-01-19T10:45:00Z",
  
  "graph": {
    "artifacts": {
      "UserProtocol": {
        "id": "UserProtocol",
        "description": "Protocol defining User entity",
        "contract": "Protocol with fields: id, email, password_hash",
        "requires": [],
        "produces_file": "src/protocols/user.py",
        "domain_type": "protocol"
      },
      "UserModel": {
        "id": "UserModel",
        "description": "SQLAlchemy model implementing UserProtocol",
        "contract": "Class User(Base) implementing UserProtocol",
        "requires": ["UserProtocol"],
        "produces_file": "src/models/user.py",
        "domain_type": "model"
      }
    },
    "waves": [
      ["UserProtocol", "AuthInterface"],
      ["UserModel", "AuthService"],
      ["App"]
    ]
  },
  
  "execution": {
    "status": "completed",
    "completed": {
      "UserProtocol": {
        "content_hash": "a1b2c3d4",
        "model_tier": "small",
        "duration_ms": 1234,
        "verified": true
      },
      "UserModel": {
        "content_hash": "e5f6g7h8",
        "model_tier": "medium",
        "duration_ms": 2345,
        "verified": true
      }
    },
    "failed": {},
    "skipped": []
  },
  
  "metrics": {
    "total_duration_ms": 15000,
    "model_distribution": {"small": 3, "medium": 2, "large": 1},
    "parallelization_factor": 2.5,
    "estimated_sequential_ms": 37500
  }
}
```

### Trace File Format (JSONL)

Append-only event log for debugging:

```jsonl
{"ts": "2026-01-19T10:30:00Z", "event": "plan_created", "artifact_count": 6}
{"ts": "2026-01-19T10:30:01Z", "event": "wave_start", "wave": 0, "artifacts": ["UserProtocol", "AuthInterface"]}
{"ts": "2026-01-19T10:30:02Z", "event": "artifact_complete", "id": "UserProtocol", "duration_ms": 1200}
{"ts": "2026-01-19T10:30:03Z", "event": "artifact_complete", "id": "AuthInterface", "duration_ms": 1100}
{"ts": "2026-01-19T10:30:03Z", "event": "wave_complete", "wave": 0}
{"ts": "2026-01-19T10:30:04Z", "event": "wave_start", "wave": 1, "artifacts": ["UserModel", "AuthService"]}
...
```

---

## API Design

### PlanStore

```python
@dataclass
class PlanStore:
    """Manages plan persistence with file locking."""
    
    base_path: Path = field(default_factory=lambda: Path(".sunwell/plans"))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def save(self, execution: SavedExecution) -> Path:
        """Save execution state to disk (thread-safe)."""
        path = self.base_path / f"{execution.goal_hash}.json"
        lock_path = path.with_suffix(".lock")
        
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file, then atomic rename
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(execution.to_dict(), f, indent=2)
            temp_path.rename(path)
        
        return path
    
    def load(self, goal_hash: str) -> SavedExecution | None:
        """Load execution state from disk."""
        path = self.base_path / f"{goal_hash}.json"
        if not path.exists():
            return None
        
        with open(path) as f:
            return SavedExecution.from_dict(json.load(f))
    
    def find_by_goal(self, goal: str) -> SavedExecution | None:
        """Find execution by goal text (computes hash)."""
        goal_hash = hash_goal(goal)
        return self.load(goal_hash)
    
    def list_recent(self, limit: int = 10) -> list[SavedExecution]:
        """List recent executions."""
        plans = sorted(
            self.base_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [self.load(p.stem) for p in plans[:limit] if p.stem != "hashes"]
```

### IncrementalExecutor

```python
@dataclass
class IncrementalExecutor:
    """Executes artifact graphs with incremental rebuild support."""
    
    store: PlanStore
    hasher: ContentHasher
    
    async def execute(
        self,
        graph: ArtifactGraph,
        create_fn: CreateArtifactFn,
        goal: str,
        force_rebuild: bool = False,
    ) -> ExecutionResult:
        """Execute with incremental rebuild support."""
        
        goal_hash = hash_goal(goal)
        
        # Load previous execution if exists
        previous = self.store.load(goal_hash) if not force_rebuild else None
        
        # Determine what needs to run
        if previous:
            changed = self._detect_changes(graph, previous)
            invalidated = find_invalidated(graph, changed)
            to_execute = invalidated | self._find_incomplete(previous)
        else:
            to_execute = set(graph)
        
        # Create subgraph of work to do
        work_graph = graph.subgraph(to_execute) if to_execute != set(graph) else graph
        
        # Execute
        result = await self._execute_graph(work_graph, create_fn, previous)
        
        # Merge with previous results
        if previous:
            result = self._merge_results(previous, result)
        
        # Save
        execution = SavedExecution(
            goal=goal,
            goal_hash=goal_hash,
            graph=graph,
            completed=result.completed,
            failed=result.failed,
            content_hashes=self._compute_hashes(result),
            created_at=previous.created_at if previous else datetime.now(),
            updated_at=datetime.now(),
        )
        self.store.save(execution)
        
        return result
    
    def _detect_changes(
        self,
        graph: ArtifactGraph,
        previous: SavedExecution,
    ) -> set[str]:
        """Detect which artifacts changed since last execution."""
        changed = set()
        
        for artifact_id in graph:
            # New artifact?
            if artifact_id not in previous.content_hashes:
                changed.add(artifact_id)
                continue
            
            # Output file exists and matches hash?
            artifact = graph[artifact_id]
            if artifact.produces_file:
                current_hash = self.hasher.hash_file(artifact.produces_file)
                if current_hash != previous.content_hashes.get(artifact_id):
                    changed.add(artifact_id)
        
        return changed
```

### CLI Integration

**Existing infrastructure** (`agent_cmd.py`):
- `sunwell agent run "goal" --dry-run` — Plan only (will become `--show-plan`)
- `sunwell agent resume` — Resume from checkpoint (task-based, RFC-032)

**New options for `sunwell agent run`**:

```python
# Extend existing run command (agent_cmd.py:44-99)
@agent.command()
@click.argument("goal")
# ... existing options (--time, --trust, --strategy, --dry-run, --verbose, --model) ...
# New persistence options:
@click.option("--incremental", "-i", is_flag=True, help="Only rebuild changed artifacts")
@click.option("--force", is_flag=True, help="Force full rebuild (ignore saved state)")
@click.option("--show-plan", is_flag=True, help="Show plan with cost estimate (alias for --dry-run)")
@click.option("--diff-plan", is_flag=True, help="Show changes vs previous plan")
@click.option("--plan-id", help="Explicit plan identifier (default: hash of goal)")
async def run(
    goal: str,
    incremental: bool,
    force: bool,
    show_plan: bool,
    diff_plan: bool,
    plan_id: str | None,
    # ... existing params ...
):
    """Execute a goal with plan persistence."""
    
    store = PlanStore()
    goal_hash = plan_id or hash_goal(goal)
    
    if show_plan or diff_plan:
        # Plan-only mode (extends existing --dry-run)
        planner = ArtifactPlanner(model=model)
        graph = await planner.discover_graph(goal)
        _display_plan(graph)
        
        if diff_plan:
            previous = store.load(goal_hash)
            if previous:
                _display_diff(previous.graph, graph)
            else:
                console.print("[dim]No previous plan to compare[/dim]")
        
        return
    
    # Normal execution with incremental support
    executor = IncrementalExecutor(store=store)
    result = await executor.execute(
        graph=await planner.discover_graph(goal),
        create_fn=create_artifact,
        goal=goal,
        goal_hash=goal_hash,
        force_rebuild=force,
        incremental=incremental,  # Default: True when previous plan exists
    )
```

**Separate resume command** (enhance existing `agent_cmd.py:482-579`):

```python
# Enhance existing resume to support artifact-based resume
@agent.command()
@click.option("--checkpoint", "-c", type=click.Path(exists=True))
@click.option("--plan-id", help="Resume specific plan by ID")
def resume(checkpoint: str | None, plan_id: str | None) -> None:
    """Resume an interrupted execution.
    
    Examples:
        sunwell agent resume                    # Resume latest
        sunwell agent resume --plan-id my-api   # Resume specific plan
    """
    # If plan_id provided, use SavedExecution (artifact-based)
    # Otherwise, fall back to AgentCheckpoint (task-based)
```

---

## Resume Protocol

### State Machine

```
┌──────────────┐
│   PLANNED    │ ← Graph created, not started
└──────┬───────┘
       │ start
       ▼
┌──────────────┐
│  IN_PROGRESS │ ← Executing waves
└──────┬───────┘
       │
  ┌────┴────┐
  │         │
  ▼         ▼
┌──────┐ ┌──────────┐
│PAUSED│ │COMPLETED │ ← All artifacts done
└──┬───┘ └──────────┘
   │
   │ resume
   ▼
┌──────────────┐
│  IN_PROGRESS │
└──────────────┘
```

### Resume Logic

```python
async def resume_execution(
    execution: SavedExecution,
    create_fn: CreateArtifactFn,
) -> ExecutionResult:
    """Resume a paused or incomplete execution."""
    
    # Find completed wave
    completed_ids = set(execution.completed.keys())
    waves = execution.graph.execution_waves()
    
    resume_from_wave = 0
    for i, wave in enumerate(waves):
        if all(aid in completed_ids for aid in wave):
            resume_from_wave = i + 1
        else:
            break
    
    console.print(f"Resuming from wave {resume_from_wave + 1}")
    
    # Execute remaining waves
    result = ExecutionResult(
        completed=dict(execution.completed),  # Preserve previous
        failed=dict(execution.failed),
    )
    
    for wave_num in range(resume_from_wave, len(waves)):
        wave = waves[wave_num]
        
        # Filter to incomplete artifacts in this wave
        to_execute = [aid for aid in wave if aid not in completed_ids]
        
        if not to_execute:
            continue
        
        # Execute wave
        wave_results = await asyncio.gather(
            *[create_fn(execution.graph[aid]) for aid in to_execute],
            return_exceptions=True,
        )
        
        # Process results
        for artifact_id, wave_result in zip(to_execute, wave_results, strict=True):
            if isinstance(wave_result, Exception):
                result.failed[artifact_id] = str(wave_result)
            else:
                result.completed[artifact_id] = wave_result
    
    return result
```

---

## Incremental Rebuild

### Change Detection Strategy

```python
class ChangeDetector:
    """Detects what changed since last execution."""
    
    def detect(
        self,
        graph: ArtifactGraph,
        previous: SavedExecution,
    ) -> ChangeReport:
        """Detect all changes."""
        
        changes = ChangeReport()
        
        for artifact_id, artifact in graph.artifacts.items():
            # New artifact (not in previous plan)
            if artifact_id not in previous.graph:
                changes.added.add(artifact_id)
                continue
            
            prev_artifact = previous.graph[artifact_id]
            
            # Contract changed (spec modified)
            if artifact.contract != prev_artifact.contract:
                changes.contract_changed.add(artifact_id)
                continue
            
            # Dependencies changed
            if artifact.requires != prev_artifact.requires:
                changes.deps_changed.add(artifact_id)
                continue
            
            # Output file modified externally
            if artifact.produces_file:
                current_hash = hash_file(artifact.produces_file)
                prev_hash = previous.content_hashes.get(artifact_id)
                
                if current_hash != prev_hash:
                    changes.output_modified.add(artifact_id)
        
        # Removed artifacts
        for artifact_id in previous.graph:
            if artifact_id not in graph:
                changes.removed.add(artifact_id)
        
        return changes


@dataclass
class ChangeReport:
    """Report of what changed between executions."""
    
    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    contract_changed: set[str] = field(default_factory=set)
    deps_changed: set[str] = field(default_factory=set)
    output_modified: set[str] = field(default_factory=set)
    
    @property
    def all_changed(self) -> set[str]:
        """All artifacts that need re-execution."""
        return (
            self.added | 
            self.contract_changed | 
            self.deps_changed | 
            self.output_modified
        )
```

### Invalidation Algorithm

```python
def compute_rebuild_set(
    graph: ArtifactGraph,
    changes: ChangeReport,
) -> set[str]:
    """Compute minimal set of artifacts to rebuild."""
    
    # Start with directly changed artifacts
    to_rebuild = changes.all_changed.copy()
    
    # Cascade to dependents
    to_process = list(to_rebuild)
    while to_process:
        artifact_id = to_process.pop()
        
        for dependent_id in graph.get_dependents(artifact_id):
            if dependent_id not in to_rebuild:
                to_rebuild.add(dependent_id)
                to_process.append(dependent_id)
    
    return to_rebuild
```

### Visualization

```
$ sunwell run "Build REST API" --incremental --verbose

📊 Change Analysis:
   ✓ UserProtocol      unchanged (hash: a1b2c3d4)
   ✓ AuthInterface     unchanged (hash: e5f6g7h8)
   ⚡ UserModel        contract changed
   ⚡ AuthService      dependency (UserModel) changed
   ⚡ App              dependency (AuthService) changed
   
🎯 Rebuild Plan:
   Skip: UserProtocol, AuthInterface (2 artifacts)
   Build: UserModel → AuthService → App (3 artifacts)
   
   Estimated savings: 40% (2/5 artifacts skipped)
   
Proceed? [Y/n]
```

---

## Plan Preview

### Cost Estimation

Before executing, show what will happen:

```python
@dataclass
class PlanPreview:
    """Preview of execution plan with cost estimates."""
    
    graph: ArtifactGraph
    waves: list[list[str]]
    model_distribution: dict[str, int]
    
    # Estimates
    estimated_tokens: int
    estimated_cost_usd: float
    estimated_duration_seconds: float
    
    # Comparison (if previous exists)
    previous: SavedExecution | None = None
    changes: ChangeReport | None = None
    
    def display(self) -> None:
        """Display the preview."""
        console.print("\n📋 Execution Plan")
        console.print("=" * 40)
        
        for i, wave in enumerate(self.waves):
            parallel = "⚡" if len(wave) > 1 else "→"
            console.print(f"\nWave {i + 1} {parallel}")
            for artifact_id in wave:
                artifact = self.graph[artifact_id]
                tier = self._estimate_tier(artifact)
                console.print(f"  [{tier}] {artifact_id}")
                console.print(f"      {artifact.description[:50]}...")
        
        console.print("\n📊 Estimates")
        console.print(f"  Artifacts: {len(self.graph)}")
        console.print(f"  Waves: {len(self.waves)}")
        console.print(f"  Parallelization: {self._parallelization_factor():.1f}x")
        console.print(f"  Model mix: {self.model_distribution}")
        console.print(f"  Est. tokens: ~{self.estimated_tokens:,}")
        console.print(f"  Est. cost: ~${self.estimated_cost_usd:.3f}")
        console.print(f"  Est. time: ~{self.estimated_duration_seconds:.0f}s")
        
        if self.changes:
            console.print("\n🔄 Changes vs Previous")
            console.print(f"  New: {len(self.changes.added)}")
            console.print(f"  Modified: {len(self.changes.contract_changed)}")
            console.print(f"  Unchanged: {len(self.graph) - len(self.changes.all_changed)}")
```

### CLI Usage

```bash
# Show plan without executing
$ sunwell run "Build REST API" --show-plan

📋 Execution Plan
========================================

Wave 1 ⚡
  [small] UserProtocol
      Protocol defining User entity...
  [small] AuthInterface
      Interface for authentication...

Wave 2 ⚡
  [medium] UserModel
      SQLAlchemy model implementing...
  [medium] AuthService
      JWT-based authentication...

Wave 3 →
  [large] App
      Flask application factory...

📊 Estimates
  Artifacts: 5
  Waves: 3
  Parallelization: 2.0x
  Model mix: {'small': 2, 'medium': 2, 'large': 1}
  Est. tokens: ~8,500
  Est. cost: ~$0.012
  Est. time: ~45s

Execute? [Y/n]
```

---

## Implementation Plan

### Phase 0: Prerequisites

| Task | File | Deliverable |
|------|------|-------------|
| Add `get_dependents()` | `sunwell/naaru/artifacts.py` | Public API for dependent lookup |
| Add serialization tests | `tests/test_artifacts.py` | Round-trip tests for `to_dict`/`from_dict` |

**Exit criteria**: `ArtifactGraph.get_dependents()` exists with tests; serialization verified

### Phase 1: Plan Persistence (Week 1)

| Task | File | Deliverable |
|------|------|-------------|
| SavedExecution dataclass | `sunwell/naaru/persistence.py` | Core persistence model |
| PlanStore (with locking) | `sunwell/naaru/persistence.py` | Thread-safe save/load |
| Content hashing | `sunwell/naaru/persistence.py` | Output hash computation |
| CLI --show-plan | `sunwell/cli/agent_cmd.py` | Plan preview (extends existing `--dry-run`) |

**Exit criteria**: Can save plan to disk, load it back, display preview

### Phase 2: Resume Support (Week 2)

| Task | File | Deliverable |
|------|------|-------------|
| Resume protocol | `sunwell/naaru/persistence.py` | Resume from checkpoint |
| Wave-level state | `sunwell/naaru/executor.py` | Track completed waves |
| CLI --resume | `sunwell/cli/agent_cmd.py` | Resume command |
| Trace logging | `sunwell/naaru/persistence.py` | JSONL event log |

**Exit criteria**: Can resume interrupted execution from last complete wave

### Phase 3: Incremental Rebuild (Week 3)

| Task | File | Deliverable |
|------|------|-------------|
| ChangeDetector | `sunwell/naaru/incremental.py` | Detect what changed |
| Invalidation cascade | `sunwell/naaru/incremental.py` | Find affected artifacts |
| IncrementalExecutor | `sunwell/naaru/incremental.py` | Execute only what's needed |
| CLI --incremental | `sunwell/cli/agent_cmd.py` | Incremental flag |

**Exit criteria**: Re-runs only rebuild changed artifacts and dependents

### Phase 4: Polish & Integration (Week 4)

| Task | File | Deliverable |
|------|------|-------------|
| Plan diff display | `sunwell/naaru/persistence.py` | Show old vs new plan |
| Cost estimation | `sunwell/naaru/persistence.py` | Token/cost preview |
| Documentation | `docs/` | User guide |
| Integration tests | `tests/` | Full workflow tests |

**Exit criteria**: Feature complete, documented, tested

---

## Design Decisions

### Decision 1: Storage Format

| Option | Pros | Cons |
|--------|------|------|
| **A: JSON** | Human-readable, easy debug | Larger files |
| **B: MessagePack** | Compact, fast | Binary, harder to inspect |
| **C: SQLite** | Queryable, ACID | Heavier dependency |

**Recommendation**: **JSON** for plans (readable), **JSONL** for traces (append-only).

### Decision 2: Hash Algorithm

| Option | Speed | Collision Resistance |
|--------|-------|---------------------|
| **A: SHA-256 (16 chars)** | Fast enough | Excellent |
| **B: xxHash** | Very fast | Good |
| **C: MD5** | Fast | Weak (but okay for change detection) |

**Recommendation**: **SHA-256 truncated to 16 chars**. Security isn't the concern; uniqueness is.

### Decision 3: Incremental Granularity

| Option | Granularity | Complexity |
|--------|-------------|------------|
| **A: Artifact-level** | Re-run whole artifact | Simple |
| **B: Chunk-level** | Re-run parts of artifact | Complex |
| **C: Line-level** | Diff-based patching | Very complex |

**Recommendation**: **Artifact-level (A)**. An artifact is the atomic unit. Sub-artifact incrementality adds complexity without clear benefit.

### Decision 4: Goal Identity

How do we know if a goal is "the same" as a previous one?

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: Exact string match** | hash(goal) | Simple | "Build API" ≠ "build an API" |
| **B: Semantic similarity** | Embedding distance | Fuzzy matching | Slow, may over-match |
| **C: User-provided ID** | Explicit naming | Precise | Burden on user |

**Recommendation**: **Option A (exact match)** with **Option C** as override. Users can provide `--plan-id` for explicit control.

```bash
# Implicit: uses hash of goal text
sunwell run "Build REST API"

# Explicit: uses provided ID
sunwell run "Build REST API" --plan-id my-api-v1
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Stale plans** | Medium | Medium | Warn if plan >24h old; add `--fresh` flag |
| **Hash collisions** | Very Low | High | 16-char SHA-256 has negligible collision risk |
| **Disk space** | Low | Low | Prune old plans; add `sunwell plans clean` |
| **Concurrent access** | Medium | Medium | File locking; one execution per goal |
| **Schema migration** | Medium | Medium | Version field in JSON; migration logic |

---

## Success Criteria

### Quantitative

- [ ] **Resume works** — Can resume at wave N and complete from there
- [ ] **>50% time savings** on incremental rebuild (vs full rebuild)
- [ ] **<100ms** plan load time for typical plans
- [ ] **<1MB** storage per typical plan

### Qualitative

- [ ] Users understand the --show-plan output
- [ ] Resume feels seamless ("it just works")
- [ ] Incremental rebuild correctly identifies what changed
- [ ] Plan history is useful for debugging

---

## Future Extensions

### Not In Scope, But Enabled

1. **Remote plan storage** — Sync plans to cloud for team sharing
2. **Plan versioning** — Git-like history of plan evolution
3. **Distributed execution** — Run different waves on different machines
4. **Plan templates** — Save a plan as a reusable template
5. **CI/CD integration** — Run `sunwell run --incremental` in pipelines

---

## References

### Code References

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| ArtifactGraph.to_dict | `naaru/artifacts.py:644-657` | Existing serialization | ✅ Exists |
| ArtifactGraph.from_dict | `naaru/artifacts.py:651-657` | Existing deserialization | ✅ Exists |
| ArtifactGraph._dependents | `naaru/artifacts.py:276` | Private dependents tracking | ✅ Exists |
| ArtifactGraph.get_dependents | `naaru/artifacts.py` | Public dependents API | ⚠️ **Add in Phase 0** |
| ArtifactGraph.subgraph | `naaru/artifacts.py:588-615` | Subgraph extraction | ✅ Exists |
| ArtifactGraph.execution_waves | `naaru/artifacts.py:511` | Wave computation | ✅ Exists |
| AgentCheckpoint | `naaru/checkpoint.py:89-203` | Task-based checkpointing | ✅ Exists |
| ExecutionResult | `naaru/executor.py:78-135` | Result structure | ✅ Exists |
| CLI run command | `cli/agent_cmd.py:44-99` | Existing run with --dry-run | ✅ Exists |
| CLI resume command | `cli/agent_cmd.py:482-579` | Existing task-based resume | ✅ Exists |
| PlanStore (new) | `naaru/persistence.py` | Plan storage | 🆕 This RFC |
| SavedExecution (new) | `naaru/persistence.py` | Artifact checkpoint | 🆕 This RFC |
| IncrementalExecutor (new) | `naaru/incremental.py` | Incremental rebuild | 🆕 This RFC |

### Related RFCs

- **RFC-036**: Artifact-First Planning (the planning model)
- **RFC-032**: Agent Mode (checkpoint infrastructure)
- **RFC-034**: Contract-Aware Planning (task model)

### External Inspiration

- **Make**: Timestamp-based rebuild
- **Bazel**: Content-addressed caching
- **Nix**: Hermetic, reproducible builds
- **Gradle**: Incremental compilation

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-19 | Initial draft |
| 2026-01-19 | Added Phase 0 prerequisites (`get_dependents()` API) |
| 2026-01-19 | Clarified relationship to AgentCheckpoint |
| 2026-01-19 | Added thread-safe file locking to PlanStore |
| 2026-01-19 | Fixed `zip()` strict=True for Python 3.14 compliance |
| 2026-01-19 | Updated code references with existence status |
| 2026-01-19 | Aligned CLI integration with existing commands |