# RFC-034: Contract-Aware Parallel Task Planning

| Field | Value |
|-------|-------|
| **RFC** | 034 |
| **Title** | Contract-Aware Parallel Task Planning |
| **Status** | Implemented |
| **Created** | 2026-01-18 |
| **Implemented** | 2026-01-18 |
| **Author** | llane |
| **Builds on** | Agent Mode (`naaru/planners/agent.py`, `naaru/types.py`) |

---

## Abstract

Current task planning decomposes goals into tasks with sequential dependencies but doesn't reason about **parallelization** or **interface contracts**. This RFC proposes enhancing task decomposition to:

1. **Identify parallel groups** — Tasks that can safely execute concurrently
2. **Extract contracts first** — Define interfaces before implementations
3. **Detect resource conflicts** — Prevent parallel tasks from colliding

**The key insight**: When building systems with multiple components (dataclasses, protocols, modules), defining interfaces is inherently parallelizable. Once interfaces exist, implementations that don't share state can also parallelize.

```
CURRENT:       1 → 2 → 3 → 4 → 5 → 6  (sequential)
PROPOSED:      [1a, 1b, 1c] → [2a, 2b] → 3  (parallel phases)
```

---

## Goals and Non-Goals

### Goals

1. **Enable parallel task execution** — Execute independent tasks concurrently when safe
2. **Contract-first planning** — Identify interface definitions that can parallelize
3. **Conflict detection** — Prevent parallel tasks from writing the same files
4. **Backward compatibility** — Existing task definitions continue to work unchanged

### Non-Goals

1. **Distributed execution** — Tasks run on a single machine (no cross-process or network coordination)
2. **Automatic contract extraction** — The LLM identifies contracts; no static analysis of existing code
3. **Function-level conflict detection** — Conflicts are file-level, not AST-level
4. **Cross-task memory sharing** — Tasks communicate via files, not shared memory
5. **Dynamic re-planning** — Task graph is fixed after planning; no runtime adjustments

---

## Problem Statement

### The Sequential Bottleneck

The current `AgentPlanner` produces task lists with `depends_on` relationships, and `_execute_task_graph` respects these dependencies. However:

1. **Execution is sequential** — Even when multiple tasks are "ready" (all dependencies satisfied), they execute one at a time
2. **Planning doesn't consider parallelization** — The planner asks "what comes before?" but not "what can run simultaneously?"
3. **No resource conflict detection** — Two tasks might both try to write the same file

**Current prompt** (from `agent.py:116-142`):
```
Output a JSON array of tasks. Each task has:
- id: unique identifier
- description: what to do
- depends_on: array of task IDs that must complete first
```

This captures **ordering** but not **parallelism** or **contracts**.

### The Contract Opportunity

When a user asks to "Build a REST API with user auth", the naive decomposition is:

```
1. Create project structure
2. Define User model
3. Define Auth service
4. Implement User model
5. Implement Auth service
6. Create routes
```

But a smarter decomposition recognizes that **contracts can be defined in parallel**:

```
Phase 1 - Contracts (parallel):
  1a. Define User protocol      [produces: UserProtocol]
  1b. Define Auth interface     [produces: AuthInterface]
  1c. Define Route types        [produces: RouteTypes]

Phase 2 - Implementations (parallel where safe):
  2a. Implement UserModel       [requires: UserProtocol]
  2b. Implement AuthService     [requires: AuthInterface, UserProtocol]
  2c. Implement routes          [requires: RouteTypes, AuthInterface]
```

**Why this matters**:
- **Contracts are inherently parallel** — They don't modify shared state
- **Implementations can parallelize** — If they don't write the same files
- **Frontloading contracts** — Makes dependencies explicit, enables better verification

### Current Code Evidence

**`naaru/types.py:166-168`** — Task already has `depends_on` but nothing for parallelization:
```python
# Dependencies
depends_on: tuple[str, ...] = ()     # Task IDs that must complete first
subtasks: tuple["Task", ...] = ()    # For composite tasks
```

**`naaru/naaru.py:1765`** — Ready tasks execute sequentially:
```python
# Execute ready tasks (sequentially for now, parallelization in Phase 6)
for task in ready:
```

**`naaru/parallel.py`** — Parallel *execution* exists but doesn't inform *planning*:
```python
class ParallelAutonomousRunner:
    """Parallel runner using multiple worker threads."""
```

---

## Solution: Contract-Aware Task Model

### Enhanced Task Dataclass

Extend `Task` with parallelization and contract fields:

```python
@dataclass
class Task:
    """A unit of work for Naaru to execute (RFC-032, RFC-034).
    
    RFC-034 additions:
    - produces: Artifacts this task creates (interfaces, types, files)
    - requires: Artifacts that must exist before this runs
    - modifies: Resources this task touches (for conflict detection)
    - parallel_group: Tasks in the same group can run concurrently
    - contract: Interface signature this task should conform to
    - is_contract: Whether this task defines an interface vs implements one
    """
    
    id: str
    description: str
    mode: TaskMode
    
    # Existing fields (RFC-032)
    tools: frozenset[str] = field(default_factory=frozenset)
    target_path: str | None = None
    working_directory: str = "."
    depends_on: tuple[str, ...] = ()
    subtasks: tuple["Task", ...] = ()
    
    # === RFC-034: Contract-Aware Planning ===
    
    # Artifact flow (what this task produces/consumes)
    produces: frozenset[str] = field(default_factory=frozenset)
    """Artifacts this task creates: types, interfaces, files, modules.
    
    Example: frozenset(["UserProtocol", "user_types.py"])
    """
    
    requires: frozenset[str] = field(default_factory=frozenset)
    """Artifacts that must exist before this task can run.
    
    Unlike depends_on (task IDs), this is semantic: what artifacts are needed.
    Example: frozenset(["UserProtocol", "AuthInterface"])
    """
    
    modifies: frozenset[str] = field(default_factory=frozenset)
    """Resources this task may modify (for conflict detection).
    
    Two tasks with overlapping `modifies` sets cannot run in parallel.
    Example: frozenset(["src/models/user.py", "pyproject.toml"])
    """
    
    # Parallelization hints
    parallel_group: str | None = None
    """Tasks in the same parallel group can execute concurrently.
    
    Groups are typically phases: "contracts", "implementations", "tests".
    Tasks in the same group MUST have non-overlapping `modifies` sets.
    """
    
    # Contract information
    is_contract: bool = False
    """True if this task defines an interface/protocol, not an implementation.
    
    Contract tasks are inherently parallelizable (no shared mutable state).
    """
    
    contract: str | None = None
    """The interface signature this implementation should conform to.
    
    Example: "UserProtocol" - the implementation must satisfy this protocol.
    """
```

### Enhanced Planning Prompt

Update `AgentPlanner._build_planning_prompt()` to extract parallelization info:

```python
def _build_planning_prompt(self, goals: list[str], context: dict[str, Any] | None) -> str:
    return f"""You are a task planner with parallel execution awareness.

GOAL: {goal}

CONTEXT:
{context_str}

AVAILABLE TOOLS:
{tools_docs}

=== PLANNING STRATEGY ===

1. IDENTIFY CONTRACTS FIRST
   When building systems with multiple components, identify the INTERFACES first:
   - Protocols/ABCs that define behavior
   - Type definitions shared between components
   - API schemas that components must conform to
   
   Contracts can be defined IN PARALLEL because they don't modify shared state.

2. GROUP BY PHASE
   Organize tasks into phases where tasks within a phase can run concurrently:
   - Phase 1: Define contracts/interfaces (all parallel)
   - Phase 2: Implement against contracts (parallel if no file conflicts)
   - Phase 3: Integration/testing (may require sequential)

3. TRACK ARTIFACTS
   For each task, identify:
   - PRODUCES: What artifacts does this create? (types, files, modules)
   - REQUIRES: What artifacts must exist first?
   - MODIFIES: What files does this touch? (tasks with overlapping modifies cannot parallelize)

=== OUTPUT FORMAT ===

Output a JSON array of tasks. Each task has:
- id: unique identifier (e.g., "1a", "1b", "2a")
- description: what to do
- mode: "generate" | "modify" | "execute" | "research"
- tools: array of tools needed (from AVAILABLE TOOLS)
- depends_on: task IDs that must complete first
- target_path: file or directory affected

RFC-034 ADDITIONS:
- parallel_group: phase name (e.g., "contracts", "implementations", "tests")
- is_contract: true if this defines an interface, false for implementations
- produces: array of artifacts this creates (e.g., ["UserProtocol", "user_types.py"])
- requires: array of artifacts needed (e.g., ["UserProtocol"])
- modifies: array of files this task may write to
- contract: interface this implementation must satisfy (for implementations only)

=== EXAMPLE ===

Goal: "Build a REST API with user authentication"

```json
[
  {{
    "id": "1a",
    "description": "Define User protocol with required fields and methods",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": [],
    "target_path": "src/protocols/user.py",
    "parallel_group": "contracts",
    "is_contract": true,
    "produces": ["UserProtocol"],
    "requires": [],
    "modifies": ["src/protocols/user.py"]
  }},
  {{
    "id": "1b", 
    "description": "Define Auth interface with authenticate/authorize methods",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": [],
    "target_path": "src/protocols/auth.py",
    "parallel_group": "contracts",
    "is_contract": true,
    "produces": ["AuthInterface"],
    "requires": [],
    "modifies": ["src/protocols/auth.py"]
  }},
  {{
    "id": "2a",
    "description": "Implement User model conforming to UserProtocol",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": ["1a"],
    "target_path": "src/models/user.py",
    "parallel_group": "implementations",
    "is_contract": false,
    "produces": ["UserModel"],
    "requires": ["UserProtocol"],
    "modifies": ["src/models/user.py"],
    "contract": "UserProtocol"
  }},
  {{
    "id": "2b",
    "description": "Implement Auth service using UserProtocol",
    "mode": "generate",
    "tools": ["write_file"],
    "depends_on": ["1a", "1b"],
    "target_path": "src/services/auth.py",
    "parallel_group": "implementations",
    "is_contract": false,
    "produces": ["AuthService"],
    "requires": ["UserProtocol", "AuthInterface"],
    "modifies": ["src/services/auth.py"],
    "contract": "AuthInterface"
  }}
]
```

Note how:
- Tasks 1a and 1b are in "contracts" group → can run in parallel
- Tasks 2a and 2b are in "implementations" group → can run in parallel (different files)
- Task 2b depends on both 1a and 1b (needs both protocols)

Decompose the goal into {self.max_subtasks} or fewer tasks. Output ONLY valid JSON:"""
```

### Parallel Execution with Conflict Detection

Update `_execute_task_graph` to execute ready tasks in parallel, with conflict detection:

```python
async def _execute_task_graph(
    self,
    tasks: list[Task],
    output: Callable[[str], None],
    max_time: float,
) -> list[Task]:
    """Execute tasks respecting dependencies AND parallelization (RFC-034)."""
    from sunwell.naaru.types import Task, TaskStatus
    
    completed_ids: set[str] = set()
    completed_artifacts: set[str] = set()  # RFC-034: Track produced artifacts
    start_time = datetime.now()
    
    while True:
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > max_time:
            output("⏰ Timeout reached")
            break
        
        # Find ready tasks (dependencies AND required artifacts satisfied)
        ready = [
            t for t in tasks
            if t.status == TaskStatus.PENDING
            and t.is_ready(completed_ids)
            and t.requires <= completed_artifacts  # RFC-034: artifact check
        ]
        
        if not ready:
            pending = [t for t in tasks if t.status == TaskStatus.PENDING]
            if not pending:
                break
            # Check for deadlock
            blocked = self._detect_deadlock(tasks, completed_ids, completed_artifacts)
            if blocked:
                output(f"⚠️ {len(blocked)} tasks blocked")
            break
        
        # RFC-034: Group ready tasks by parallel_group and check for conflicts
        parallel_batches = self._group_for_parallel_execution(ready)
        
        for batch in parallel_batches:
            if len(batch) == 1:
                # Single task - execute directly
                task = batch[0]
                task.status = TaskStatus.IN_PROGRESS
                output(f"   → {task.description}")
                await self._execute_single_task(task)
                task.status = TaskStatus.COMPLETED
                completed_ids.add(task.id)
                completed_artifacts.update(task.produces)
                output(f"   ✅ {task.id}")
            else:
                # Multiple tasks - execute in parallel
                output(f"   ⚡ Executing {len(batch)} tasks in parallel")
                for task in batch:
                    task.status = TaskStatus.IN_PROGRESS
                    output(f"      → {task.description}")
                
                # Execute all tasks concurrently
                results = await asyncio.gather(
                    *[self._execute_single_task(t) for t in batch],
                    return_exceptions=True,
                )
                
                for task, result in zip(batch, results, strict=True):
                    if isinstance(result, Exception):
                        task.status = TaskStatus.FAILED
                        task.error = str(result)
                        output(f"      ❌ {task.id}: {result}")
                    else:
                        task.status = TaskStatus.COMPLETED
                        completed_ids.add(task.id)
                        completed_artifacts.update(task.produces)
                        output(f"      ✅ {task.id}")
    
    return tasks

def _group_for_parallel_execution(self, ready: list[Task]) -> list[list[Task]]:
    """Group ready tasks into parallel-safe batches (RFC-034).
    
    Tasks can run in parallel if:
    1. They're in the same parallel_group (or both have None)
    2. Their `modifies` sets don't overlap
    """
    batches: list[list[Task]] = []
    remaining = list(ready)
    
    while remaining:
        batch: list[Task] = [remaining.pop(0)]
        batch_modifies: set[str] = set(batch[0].modifies)
        
        i = 0
        while i < len(remaining):
            task = remaining[i]
            # Check for conflicts
            if not (task.modifies & batch_modifies):
                # No conflict - can parallelize
                batch.append(task)
                batch_modifies.update(task.modifies)
                remaining.pop(i)
            else:
                i += 1
        
        batches.append(batch)
    
    return batches
```

---

## Task Analysis Utilities

### Dependency Graph Visualization

Add utilities to visualize the task graph:

```python
def visualize_task_graph(tasks: list[Task]) -> str:
    """Generate a Mermaid diagram of the task graph (RFC-034)."""
    lines = ["graph TD"]
    
    # Group by parallel_group
    groups: dict[str, list[Task]] = {}
    for task in tasks:
        group = task.parallel_group or "ungrouped"
        groups.setdefault(group, []).append(task)
    
    # Create subgraphs for each group
    for group_name, group_tasks in groups.items():
        lines.append(f"    subgraph {group_name}")
        for task in group_tasks:
            icon = "📜" if task.is_contract else "🔧"
            lines.append(f"        {task.id}[{icon} {task.description[:30]}]")
        lines.append("    end")
    
    # Add edges for dependencies
    for task in tasks:
        for dep in task.depends_on:
            lines.append(f"    {dep} --> {task.id}")
    
    return "\n".join(lines)


def analyze_parallelism(tasks: list[Task]) -> dict[str, Any]:
    """Analyze parallelization potential of a task graph (RFC-034).
    
    Returns:
        {
            "total_tasks": int,
            "contract_tasks": int,
            "implementation_tasks": int,
            "max_parallel_width": int,  # Max tasks that can run simultaneously
            "critical_path_length": int,  # Minimum sequential steps
            "parallelization_ratio": float,  # total / critical_path
            "phases": [{"name": str, "tasks": int, "parallel": bool}],
            "potential_conflicts": [(task_id, task_id, overlapping_files)],
        }
    """
    ...
```

### Contract Validation

Verify that implementations satisfy their contracts:

```python
async def validate_contracts(tasks: list[Task], completed: set[str]) -> list[str]:
    """Validate that completed implementations satisfy their contracts (RFC-034).
    
    This runs after task execution to verify the produced artifacts
    actually conform to the declared interfaces.
    
    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []
    
    for task in tasks:
        if task.status != TaskStatus.COMPLETED:
            continue
        if not task.contract:
            continue
        
        # Find the contract task
        contract_task = next(
            (t for t in tasks if task.contract in t.produces),
            None
        )
        if not contract_task:
            errors.append(f"Task {task.id} references unknown contract: {task.contract}")
            continue
        
        # TODO: Actually verify the implementation satisfies the protocol
        # This could use mypy, runtime checks, or LLM-based verification
        
    return errors
```

---

## Integration with Existing Architecture

### Backward Compatibility

All new fields have defaults, so existing code continues to work:

```python
# Old code (RFC-032) still works
task = Task(
    id="1",
    description="Do something",
    mode=TaskMode.GENERATE,
    depends_on=("0",),
)
# New fields default to empty/None/False

# New code (RFC-034) can use parallelization
task = Task(
    id="1a",
    description="Define protocol",
    mode=TaskMode.GENERATE,
    parallel_group="contracts",
    is_contract=True,
    produces=frozenset(["MyProtocol"]),
)
```

### Planning Strategy Selection

Add a planning strategy enum to control decomposition style:

```python
class PlanningStrategy(Enum):
    """How to decompose tasks (RFC-034)."""
    
    SEQUENTIAL = "sequential"      # RFC-032 behavior: linear dependencies
    CONTRACT_FIRST = "contract_first"  # RFC-034: identify contracts, then implementations
    RESOURCE_AWARE = "resource_aware"  # RFC-034: minimize file conflicts for max parallelism


@dataclass
class AgentPlanner:
    strategy: PlanningStrategy = PlanningStrategy.CONTRACT_FIRST  # RFC-034 default
```

### Naaru Configuration

Add to `NaaruConfig`:

```python
@dataclass  
class NaaruConfig:
    # ... existing fields ...
    
    # RFC-034: Parallel task execution
    enable_parallel_execution: bool = True
    """Execute independent tasks in parallel when possible."""
    
    max_parallel_tasks: int = 4
    """Maximum tasks to execute concurrently."""
    
    planning_strategy: PlanningStrategy = PlanningStrategy.CONTRACT_FIRST
    """How to decompose goals into tasks."""
```

---

## Example: Full Decomposition

### Input

```
Goal: "Build a Flask REST API with SQLAlchemy models for users, posts, and comments. Include JWT authentication."
```

### Output (Contract-Aware Decomposition)

```json
{
  "phases": [
    {
      "name": "contracts",
      "parallel": true,
      "tasks": [
        {
          "id": "1a",
          "description": "Define User protocol with id, email, password_hash, posts relationship",
          "is_contract": true,
          "produces": ["UserProtocol"],
          "modifies": ["src/protocols/user.py"]
        },
        {
          "id": "1b", 
          "description": "Define Post protocol with id, title, content, author relationship",
          "is_contract": true,
          "produces": ["PostProtocol"],
          "modifies": ["src/protocols/post.py"]
        },
        {
          "id": "1c",
          "description": "Define Comment protocol with id, content, author, post relationships",
          "is_contract": true,
          "produces": ["CommentProtocol"],
          "modifies": ["src/protocols/comment.py"]
        },
        {
          "id": "1d",
          "description": "Define Auth interface with authenticate, generate_token, verify_token",
          "is_contract": true,
          "produces": ["AuthInterface"],
          "modifies": ["src/protocols/auth.py"]
        }
      ]
    },
    {
      "name": "models",
      "parallel": true,
      "tasks": [
        {
          "id": "2a",
          "description": "Implement SQLAlchemy User model",
          "requires": ["UserProtocol"],
          "contract": "UserProtocol",
          "produces": ["UserModel"],
          "modifies": ["src/models/user.py"]
        },
        {
          "id": "2b",
          "description": "Implement SQLAlchemy Post model",
          "requires": ["PostProtocol", "UserProtocol"],
          "contract": "PostProtocol", 
          "produces": ["PostModel"],
          "modifies": ["src/models/post.py"]
        },
        {
          "id": "2c",
          "description": "Implement SQLAlchemy Comment model",
          "requires": ["CommentProtocol", "UserProtocol", "PostProtocol"],
          "contract": "CommentProtocol",
          "produces": ["CommentModel"],
          "modifies": ["src/models/comment.py"]
        }
      ]
    },
    {
      "name": "services",
      "parallel": true,
      "tasks": [
        {
          "id": "3a",
          "description": "Implement JWT AuthService",
          "requires": ["AuthInterface", "UserProtocol"],
          "contract": "AuthInterface",
          "produces": ["AuthService"],
          "modifies": ["src/services/auth.py"]
        }
      ]
    },
    {
      "name": "routes",
      "parallel": true,
      "tasks": [
        {
          "id": "4a",
          "description": "Create user routes (register, login, profile)",
          "requires": ["UserModel", "AuthService"],
          "modifies": ["src/routes/users.py"]
        },
        {
          "id": "4b",
          "description": "Create post routes (CRUD)",
          "requires": ["PostModel", "AuthService"],
          "modifies": ["src/routes/posts.py"]
        },
        {
          "id": "4c",
          "description": "Create comment routes (CRUD)",
          "requires": ["CommentModel", "AuthService"],
          "modifies": ["src/routes/comments.py"]
        }
      ]
    },
    {
      "name": "integration",
      "parallel": false,
      "tasks": [
        {
          "id": "5a",
          "description": "Create Flask app factory with all routes",
          "requires": ["UserModel", "PostModel", "CommentModel", "AuthService"],
          "modifies": ["src/app.py", "src/__init__.py"]
        }
      ]
    }
  ],
  "analysis": {
    "total_tasks": 12,
    "contract_tasks": 4,
    "implementation_tasks": 8,
    "max_parallel_width": 4,
    "critical_path_length": 5,
    "parallelization_ratio": 2.4,
    "theoretical_speedup": "2.4x (assumes equal task duration, actual speedup depends on LLM latency)"
  }
}
```

### Execution Timeline

```
Sequential (current):
  1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12
  Total: 12 sequential LLM calls

Parallel (RFC-034):
  Phase 1: [1a, 1b, 1c, 1d] ─────┐
  Phase 2: [2a, 2b, 2c]     ─────┼──→ Phase 5: [5a]
  Phase 3: [3a]             ─────┤
  Phase 4: [4a, 4b, 4c]     ─────┘
  Total: 5 sequential phases (theoretical 2.4x speedup*)

* Actual speedup depends on:
  - LLM API concurrency limits (rate limiting may serialize)
  - Task duration variance (long tasks dominate)
  - I/O bottlenecks (disk, network)
  Expected real-world speedup: 1.5-2x on parallelizable workloads
```

---

## Implementation Plan

### Phase 1: Task Model Extension (Week 1)

| Task | File | Deliverable |
|------|------|-------------|
| Extend Task dataclass | `naaru/types.py` | New fields with defaults |
| Update task parsing | `naaru/planners/agent.py` | Parse new JSON fields |
| Add is_ready enhancement | `naaru/types.py` | Check `requires` artifacts |

**Exit criteria**: New fields exist, backward compatible

### Phase 2: Enhanced Planning Prompt (Week 2)

| Task | File | Deliverable |
|------|------|-------------|
| New planning prompt | `naaru/planners/agent.py` | Contract-aware prompt |
| Strategy enum | `naaru/planners/protocol.py` | `PlanningStrategy` |
| Config integration | `types/config.py` | `planning_strategy` field |

**Exit criteria**: Planner produces tasks with parallelization info

### Phase 3: Parallel Execution (Week 3)

| Task | File | Deliverable |
|------|------|-------------|
| Conflict detection | `naaru/naaru.py` | `_group_for_parallel_execution` |
| Parallel task runner | `naaru/naaru.py` | Updated `_execute_task_graph` |
| Artifact tracking | `naaru/naaru.py` | Track `produces` → `requires` |

**Exit criteria**: Tasks execute in parallel when safe

### Phase 4: Analysis & Visualization (Week 4)

| Task | File | Deliverable |
|------|------|-------------|
| Graph visualization | `naaru/analysis.py` | Mermaid diagram generation |
| Parallelism analysis | `naaru/analysis.py` | Metrics and recommendations |
| Contract validation | `naaru/analysis.py` | Post-execution verification |

**Exit criteria**: Full visibility into task graph structure

---

## Success Criteria

### Quantitative

- [ ] **1.5x+ speedup** on parallelizable workloads with ≥4 independent tasks (measured via `benchmark/tasks/`)
- [ ] **0 file conflicts** in parallel execution (conflict detection prevents overwrites)
- [ ] **100% backward compatibility** — existing `Task` definitions work without modification
- [ ] **<5% planning overhead** — contract-aware prompt adds minimal latency vs. sequential planning

### Qualitative

- [ ] Planning output shows clear phase structure with `parallel_group` assignments
- [ ] Contract tasks (`is_contract=True`) correctly identified for interface definitions
- [ ] Resource conflicts detected and logged before execution begins
- [ ] Mermaid visualization renders correctly and shows parallelization structure

---

## Design Decisions

### Decision 1: Contract Verification Strategy

How do we verify implementations satisfy their declared protocols?

| Option | Approach | Pros | Cons | Complexity |
|--------|----------|------|------|------------|
| **A: mypy/pyright** | Run type checker on generated code | Deterministic, catches type errors | Slow (~2-5s), requires valid syntax | Medium |
| **B: LLM verification** | Ask LLM "Does X satisfy protocol Y?" | Fast, works on partial code | Non-deterministic, may miss issues | Low |
| **C: Runtime checks** | Use `isinstance()` or Protocol runtime | Catches runtime violations | Only works after code runs | Low |
| **D: Skip verification** | Trust the planner | Zero overhead | No safety net | Trivial |

**Recommendation**: **Option A (mypy)** for Phase 4. It's deterministic and catches real issues. Run asynchronously after each implementation task completes. If mypy takes >5s, fall back to Option D and log a warning.

**Mitigation**: If mypy is too slow, add `--no-incremental --cache-dir=/tmp` for isolation. Consider pyright as faster alternative.

---

### Decision 2: Conflict Detection Granularity

What level of granularity for the `modifies` field?

| Option | Granularity | Pros | Cons |
|--------|-------------|------|------|
| **A: File-level** | `["src/models/user.py"]` | Simple to implement, clear semantics | May over-serialize (two tasks editing different functions in same file) |
| **B: Function-level** | `["src/models/user.py:User.save"]` | More parallelism possible | Requires AST parsing, complex conflict detection |
| **C: Module-level** | `["src/models/"]` | Coarse but simple | Too conservative, blocks valid parallelism |

**Recommendation**: **Option A (file-level)** for initial implementation. The complexity of function-level tracking doesn't justify the marginal parallelism gains. Most well-structured codebases have one class per file anyway.

**Mitigation**: If users report over-serialization, add an optional `--fine-grained-conflicts` flag in Phase 5 that enables function-level tracking.

---

### Decision 3: Failure Handling in Parallel Batches

If one task in a parallel batch fails, what happens to siblings?

| Option | Behavior | Pros | Cons |
|--------|----------|------|------|
| **A: Complete siblings** | Let other tasks finish | Maximizes useful work, simpler | May waste time on tasks that depend on failed one |
| **B: Cancel immediately** | Stop all siblings | Fail fast, save resources | May cancel tasks that would have succeeded |
| **C: Configurable** | User chooses per-batch | Flexible | More complexity, decision fatigue |

**Recommendation**: **Option A (complete siblings)** as default. Failed tasks mark their `produces` artifacts as unavailable, so dependent tasks will be blocked anyway. Completed work is never wasted.

**Mitigation**: Add `NaaruConfig.parallel_failure_mode: Literal["complete", "cancel"] = "complete"` for users who want Option B.

---

### Decision 4: Artifact Communication

How do parallel tasks share intermediate results?

| Option | Mechanism | Pros | Cons |
|--------|-----------|------|------|
| **A: File-based** | Tasks write to disk, others read | Simple, debuggable, survives crashes | I/O overhead, requires disk space |
| **B: In-memory registry** | Shared dict of artifacts | Faster for small artifacts | Doesn't survive crashes, memory pressure |
| **C: Hybrid** | Memory for <1KB, disk for larger | Best of both | Implementation complexity |

**Recommendation**: **Option A (file-based)** exclusively. Naaru already uses file-based tools (`write_file`, `read_file`). Adding in-memory artifacts introduces state management complexity and crash recovery issues.

**Mitigation**: None needed. File I/O is fast enough for the task sizes we handle (<100KB typically).

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Planner produces poor parallel groups** | Medium | Low | Add validation that `modifies` sets don't overlap within groups; warn if they do |
| **Race condition in artifact tracking** | Low | High | Use `asyncio.Lock` around `completed_artifacts` set (already thread-safe in Python 3.14t) |
| **Excessive parallelism overwhelms system** | Medium | Medium | Cap via `max_parallel_tasks` config (default: 4) |
| **Contract validation slows execution** | Medium | Low | Run verification async, don't block task completion |
| **Deadlock from circular artifact deps** | Low | High | Add cycle detection in `_detect_deadlock()`, log clear error |
| **LLM doesn't understand parallel planning** | Medium | Medium | Provide detailed examples in prompt; fall back to sequential if no `parallel_group` specified |

---

## References

### Code References

| Component | Location | Purpose |
|-----------|----------|---------|
| Task dataclass | `naaru/types.py:141-188` | Current task model (to be extended) |
| AgentPlanner | `naaru/planners/agent.py:101-161` | Planning prompt (to be enhanced) |
| Task execution | `naaru/naaru.py:1740-1780` | Sequential executor (to add parallelism) |
| Parallel runner | `naaru/parallel.py:78-119` | Existing thread pool infrastructure |

### Related Work

- **Thought Rotation** (`naaru/rotation.py`) — Parallel response generation; this RFC applies similar patterns to task execution
- **asyncio.gather** — Python's native parallel await; used in `_execute_task_graph`

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-18 | Initial draft |
| 2026-01-18 | Added Goals/Non-Goals section |
| 2026-01-18 | Added Design Decisions with comparison tables (contract verification, conflict granularity, failure handling, artifact communication) |
| 2026-01-18 | Added Risks and Mitigations table |
| 2026-01-18 | Updated speedup claims to include realistic expectations (1.5-2x vs theoretical 2.4x) |
| 2026-01-18 | Fixed dependency reference (code locations vs non-existent RFC-032) |
| 2026-01-18 | **Implemented**: All four phases complete - Task model extension, enhanced planning prompt, parallel execution, analysis utilities |