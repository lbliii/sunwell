# RFC-067: Integration-Aware DAG

**Status:** Draft  
**Author:** AI Assistant  
**Created:** 2026-01-20  
**Extends:** RFC-034 (Contract-Aware Planning)

## Executive Summary

AI coding assistants consistently fail to **wire artifacts together**—they create files but don't import them, write functions that are never called, and produce stub implementations. Sunwell already has foundational infrastructure for artifact tracking (`Task.produces`/`requires`), orphan detection (`ArtifactGraph.find_orphans()`), and stub detection (`content_validation.py`). This RFC proposes **three innovations** to close the gap:

1. **Explicit `[Wire]` tasks** — First-class integration tasks that can't be skipped
2. **Integration edges in DAG visualization** — Visual verification of cross-artifact connections  
3. **Unified `IntegrationVerifier`** — Consolidates existing detection into active verification

The key insight: **current infrastructure detects problems after they occur; this RFC makes integration a first-class concern during planning**.

---

## Problem

AI coding assistants (Cursor, Copilot, etc.) consistently exhibit these failure modes:

1. **Building without wiring** — Creates `UserService` but never imports it anywhere
2. **Lazy/stub implementations** — `pass`, `TODO`, `raise NotImplementedError`
3. **Skipping integration steps** — Backend API exists, frontend never calls it
4. **Missing registrations** — Route handler created but not added to router
5. **Orphaned artifacts** — Files exist but aren't connected to the system

### Current Sunwell Capabilities

Sunwell already has partial infrastructure addressing this:

| Capability | Location | Limitation |
|------------|----------|------------|
| Artifact tracking | `Task.produces`/`requires` (`naaru/types.py:186-198`) | String-based, no verification |
| Orphan detection | `ArtifactGraph.find_orphans()` (`naaru/artifacts.py:569-595`) | Graph-level only, not cross-file |
| Stub detection | `fast_validate()` (`naaru/experiments/content_validation.py:153-173`) | Per-content, not systematic |
| AST analysis | `CodebaseAnalyzer` (`intelligence/codebase.py:102-159`) | Read-only, not integrated with execution |
| Contract validation | `validate_contracts()` (`naaru/analysis.py:297-357`) | Placeholder, incomplete |

**The gap**: These capabilities exist in isolation. There's no unified system that:
- Makes integration tasks explicit in the DAG
- Verifies wiring **during** execution (not just after)
- Surfaces integration status visually
- Auto-generates wiring tasks during planning

---

## Goals

1. **Elevate integration to first-class** — Wire tasks appear explicitly in DAGs
2. **Verify before completion** — Artifacts aren't "done" until integrations are verified
3. **Build on existing infrastructure** — Extend `Task`, `ArtifactGraph`, `CodebaseAnalyzer`
4. **Visual integration status** — DAG view shows wiring status on edges
5. **Reduce orphan/stub rate** — Measurable improvement in completion quality

## Non-Goals

1. **Replace existing Task/Goal structures** — Extend, don't replace
2. **Full semantic verification** — That's RFC-047's domain
3. **Cross-language universal parser** — Start with Python, expand later
4. **Real-time IDE integration** — Focus on planning/execution phase first

---

## Design Options

### Option A: Extend Task with Integration Metadata (Recommended)

Extend the existing `Task` dataclass with integration-specific fields:

```python
@dataclass
class Task:
    # Existing RFC-034 fields
    produces: frozenset[str]  # Already exists
    requires: frozenset[str]  # Already exists
    
    # NEW: Structured integration requirements
    integrations: tuple[RequiredIntegration, ...] = ()
    """How this task connects to its dependencies (not just what it needs)."""
    
    # NEW: Task type discrimination
    task_type: Literal["create", "wire", "verify", "refactor"] = "create"
    """Explicit task categorization for DAG visualization."""
    
    # NEW: Post-completion verification
    verification_checks: tuple[IntegrationCheck, ...] = ()
    """Checks to run after task completion."""
```

**Pros**: 
- Minimal migration (adds fields, doesn't break existing code)
- Leverages existing `is_ready()` logic
- Single source of truth for task dependencies

**Cons**:
- Task becomes larger (more fields)
- Mixing creation and wiring in same structure

### Option B: Separate IntegrationTask Type

Create a new type specifically for wiring:

```python
@dataclass(frozen=True, slots=True)
class IntegrationTask:
    """A task that only wires existing artifacts together."""
    
    id: str
    source_artifact: str
    target_artifact: str
    integration_type: Literal["import", "call", "route", "config"]
    verification: IntegrationCheck
```

**Pros**:
- Clean separation of concerns
- Frozen/immutable by default

**Cons**:
- Two parallel task systems
- Duplicated scheduling logic
- Harder to maintain unified DAG

### Option C: Integration as Edges (Graph-First)

Model integrations as edges in `ArtifactGraph`, not as tasks:

```python
@dataclass
class ArtifactGraph:
    _artifacts: dict[str, ArtifactSpec]
    
    # NEW: Integration edges
    _integrations: dict[tuple[str, str], IntegrationEdge]
    """(source, target) → integration metadata."""
```

**Pros**:
- Natural graph representation
- Leverages existing `find_orphans()` infrastructure

**Cons**:
- Integrations aren't "executed" as tasks
- Harder to track wiring progress
- Doesn't appear in DAG visualization naturally

### Recommendation: Option A

Extend `Task` because:
1. Aligns with existing RFC-034 patterns
2. Wire tasks are just Tasks with `task_type="wire"`
3. Unified scheduling through existing `is_ready()` and `TaskGraph`
4. Natural DAG representation

---

## Solution: Three Innovations

### 1. RequiredIntegration: Structured Wiring Contracts

Enhance artifact requirements with explicit integration contracts:

```python
@dataclass(frozen=True, slots=True)
class RequiredIntegration:
    """How a task connects to its dependencies."""
    
    artifact_id: str
    """Which artifact we need (from Task.requires)."""
    
    integration_type: Literal["import", "call", "route", "config", "inherit"]
    """How we connect to it."""
    
    target_file: Path
    """Where the integration should appear."""
    
    verification_pattern: str | None = None
    """Regex or AST pattern to verify integration exists."""
    
    contract: str | None = None
    """Expected interface (e.g., 'function(user_id: str) -> User')."""
```

This makes the difference between:
- **requires**: "I need UserProtocol to exist" (ordering)
- **integrations**: "I must `from models.user import User`" (wiring)

### 2. Explicit Wire Tasks

Instead of hoping AI wires things, make wiring explicit in task decomposition:

**Before (current):**
```yaml
tasks:
  - id: auth-1
    description: "Create User model"
    produces: ["User", "UserCreate"]
  - id: auth-2
    description: "Create JWT helpers"
    requires: ["User"]  # Ordering only!
    produces: ["create_token", "verify_token"]
```

**After (with wire tasks):**
```yaml
tasks:
  - id: auth-1
    task_type: create
    description: "Create User model"
    produces: ["User", "UserCreate"]
    
  - id: auth-2
    task_type: create
    description: "Create JWT helpers"  
    produces: ["create_token", "verify_token"]
    # No requires - created independently
    
  - id: auth-3
    task_type: wire  # <-- EXPLICIT WIRING
    description: "Wire JWT to import User"
    requires: ["User", "create_token"]
    integrations:
      - artifact_id: User
        integration_type: import
        target_file: src/auth/jwt.py
        verification_pattern: "from.*models.*import.*User"
    verification_checks:
      - check_type: import_exists
        target_file: src/auth/jwt.py
        pattern: "from.*models.*import.*User"
```

The `[Wire]` tasks are:
- **Explicit** — Can't be skipped in DAG execution
- **Verifiable** — Have concrete verification checks
- **First-class** — Appear in DAG visualization

### 3. IntegrationVerifier: Unified Verification

Consolidate existing detection into an active verifier:

```python
class IntegrationVerifier:
    """Unified verification of artifact integrations.
    
    Builds on existing infrastructure:
    - CodebaseAnalyzer for AST parsing (intelligence/codebase.py)
    - fast_validate() for stub detection (naaru/experiments/content_validation.py)
    - find_orphans() for graph-level orphans (naaru/artifacts.py)
    """
    
    def __init__(
        self,
        codebase: CodebaseAnalyzer,
        project_root: Path,
    ):
        self.codebase = codebase
        self.root = project_root
    
    async def verify_integration(
        self,
        check: IntegrationCheck,
    ) -> IntegrationResult:
        """Verify a specific integration exists.
        
        Uses AST parsing for reliable detection of:
        - import statements
        - function calls
        - class inheritance
        """
        match check.check_type:
            case "import_exists":
                return await self._verify_import(check)
            case "call_exists":
                return await self._verify_call(check)
            case "route_registered":
                return await self._verify_route(check)
            case "used_not_orphan":
                return await self._verify_usage(check)
            case _:
                # Fallback to regex
                return await self._verify_pattern(check)
    
    async def detect_stubs(self, file_path: Path) -> list[StubDetection]:
        """Find incomplete implementations.
        
        Delegates to existing fast_validate() with enhanced patterns:
        - `pass` statements in functions
        - `raise NotImplementedError`
        - `TODO`, `FIXME` comments
        - Empty function bodies
        - `...` (ellipsis) bodies
        """
        content = file_path.read_text()
        result = fast_validate(content, ContentType.PYTHON)
        return self._extract_stub_locations(result, file_path)
    
    async def verify_task_complete(
        self,
        task: Task,
        produced_files: list[Path],
    ) -> TaskVerificationResult:
        """Full verification that a task is truly complete.
        
        Checks:
        1. All verification_checks pass
        2. No stubs in produced files
        3. Produced artifacts are importable/usable
        """
```

---

## DAG Visualization

Extend the DAG view with integration edges:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│         ┌─────────────────┐                                     │
│         │ [Create]        │                                     │
│         │ User Model      │ ✓                                   │
│         │                 │                                     │
│         │ produces: User  │                                     │
│         └────────┬────────┘                                     │
│                  │                                              │
│                  │ ───────── depends_on (ordering)              │
│                  │                                              │
│         ┌────────▼────────┐                                     │
│         │ [Create]        │                                     │
│         │ JWT Helpers     │ ✓                                   │
│         │                 │                                     │
│         │ produces: JWT   │                                     │
│         └────────┬────────┘                                     │
│                  │                                              │
│         ═════════════════════ integration (wiring) ⚠️ MISSING   │
│                  │                                              │
│         ┌────────▼────────┐                                     │
│         │ [Wire]          │                                     │
│         │ JWT → User      │ blocked                             │
│         │                 │                                     │
│         │ import User     │                                     │
│         └─────────────────┘                                     │
│                                                                 │
│ Legend:                                                         │
│ ─────── depends_on edge (task ordering)                         │
│ ═══════ integration edge (wiring verification)                  │
│ ✓ verified   ⚠️ missing   ○ pending                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task Decomposition Enhancement

Update planning to auto-generate wire tasks:

```python
async def decompose_with_wiring(
    goal: str,
    context: ProjectContext,
    codebase: CodebaseAnalyzer,
) -> list[Task]:
    """Decompose goal into create + wire + verify tasks.
    
    Extends existing decomposition with explicit wiring.
    """
    # 1. Standard decomposition (existing)
    create_tasks = await standard_decompose(goal, context)
    
    # 2. Analyze artifact dependencies
    artifact_deps = analyze_artifact_flow(create_tasks)
    
    # 3. Generate wire tasks for each cross-file dependency
    wire_tasks = []
    for producer_task, consumer_task in artifact_deps:
        for artifact in producer_task.produces & consumer_task.requires:
            wire_tasks.append(Task(
                id=f"wire-{producer_task.id}-to-{consumer_task.id}",
                description=f"Wire {artifact} from {producer_task.id} to {consumer_task.id}",
                task_type="wire",
                requires=frozenset([artifact]),
                integrations=(RequiredIntegration(
                    artifact_id=artifact,
                    integration_type=infer_integration_type(artifact),
                    target_file=infer_target_file(consumer_task),
                    verification_pattern=generate_pattern(artifact),
                ),),
                verification_checks=(IntegrationCheck(
                    check_type="import_exists",
                    target_file=infer_target_file(consumer_task),
                    pattern=generate_pattern(artifact),
                    required=True,
                ),),
            ))
    
    # 4. Final verification task
    verify_task = Task(
        id=f"verify-{goal_hash(goal)}",
        description="Verify complete integration",
        task_type="verify",
        requires=frozenset(t.id for t in create_tasks + wire_tasks),
        verification_checks=generate_e2e_checks(create_tasks),
    )
    
    return create_tasks + wire_tasks + [verify_task]
```

---

## Integration with Existing Systems

### With CodebaseAnalyzer (`intelligence/codebase.py`)

```python
# Use existing AST infrastructure
analyzer = CodebaseAnalyzer(embedder=None)
graph = await analyzer.full_scan(project_root)

# IntegrationVerifier delegates to it
verifier = IntegrationVerifier(codebase=analyzer, project_root=project_root)
```

### With WeaknessAnalyzer (RFC-063)

```python
# Weakness signals can trigger wire tasks
class WeaknessType(str, Enum):
    ORPHAN = "orphan"          # Existing
    STUB = "stub"              # Existing  
    MISSING_IMPORT = "missing_import"  # NEW
    BROKEN_INTEGRATION = "broken_integration"  # NEW
```

### With ArtifactGraph (`naaru/artifacts.py`)

```python
# Extend find_orphans() to consider integration edges
def find_integration_gaps(self) -> list[IntegrationGap]:
    """Find artifacts that exist but aren't integrated.
    
    Unlike find_orphans() which checks graph connectivity,
    this checks actual file-level wiring.
    """
```

---

## Cross-Layer Touchpoints

This feature spans **Python** (core), **Rust** (Tauri bridge), and **Svelte** (Studio UI). All three layers need coordinated changes.

### Python Layer (`src/sunwell/`)

| File | Change | Priority |
|------|--------|----------|
| `naaru/types.py` | Add `task_type`, `integrations`, `verification_checks` to `Task` | P0 |
| `naaru/artifacts.py` | Add `IntegrationEdge` to `ArtifactGraph` | P1 |
| `naaru/verifier.py` | **NEW**: `IntegrationVerifier` class | P0 |
| `events/types.py` | Add integration verification events | P0 |
| `backlog/goals.py` | Add `produces`/`integrations` to `Goal` | P1 |
| `intelligence/codebase.py` | Enhance with integration-aware queries | P2 |

### Rust Layer (`studio/src-tauri/src/`)

**dag.rs** — Extend DAG types to support integration edges:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DagNode {
    // Existing fields...
    
    // NEW: Task type discrimination
    pub task_type: String,  // "create", "wire", "verify", "refactor"
    
    // NEW: What this node produces (for edge labeling)
    pub produces: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DagEdge {
    // Existing fields...
    
    // NEW: Edge type (dependency vs integration)
    pub edge_type: String,  // "dependency", "integration"
    
    // NEW: Verification status for integration edges
    pub verification_status: Option<String>,  // "verified", "missing", "pending"
    
    // NEW: What integration this edge represents
    pub integration_type: Option<String>,  // "import", "call", "route", etc.
}
```

**agent.rs** — Add new event types:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    // Existing events...
    
    // NEW: Integration verification events
    IntegrationCheckStart,
    IntegrationCheckPass,
    IntegrationCheckFail,
    StubDetected,
    OrphanDetected,
    WireTaskGenerated,
}
```

### Svelte Layer (`studio/src/`)

**lib/types.ts** — Update TypeScript types:

```typescript
export type DagNodeTaskType = 'create' | 'wire' | 'verify' | 'refactor';
export type DagEdgeType = 'dependency' | 'integration';
export type IntegrationStatus = 'verified' | 'missing' | 'pending';

export interface DagNode {
  // Existing fields...
  
  // NEW
  taskType: DagNodeTaskType;
  produces: string[];
}

export interface DagEdge {
  // Existing fields...
  
  // NEW
  edgeType: DagEdgeType;
  verificationStatus?: IntegrationStatus;
  integrationType?: 'import' | 'call' | 'route' | 'config';
}
```

**components/dag/DagEdge.svelte** — Render integration edges differently:

```svelte
<script lang="ts">
  let { edge } = $props<{ edge: DagEdge }>();
  
  // Different styles for dependency vs integration edges
  const isIntegration = edge.edgeType === 'integration';
  const strokeDasharray = isIntegration ? '8,4' : 'none';
  const strokeColor = edge.verificationStatus === 'missing' 
    ? 'var(--color-error)' 
    : edge.verificationStatus === 'verified'
    ? 'var(--color-success)'
    : 'var(--color-border)';
</script>

<path 
  d={pathData}
  stroke={strokeColor}
  stroke-dasharray={strokeDasharray}
  stroke-width={isIntegration ? 2 : 1.5}
/>

{#if isIntegration && edge.verificationStatus === 'missing'}
  <text class="edge-warning">⚠️</text>
{/if}
```

**components/dag/DagNode.svelte** — Show task type badge:

```svelte
{#if node.taskType === 'wire'}
  <span class="badge badge-wire">Wire</span>
{:else if node.taskType === 'verify'}
  <span class="badge badge-verify">Verify</span>
{/if}
```

**stores/agent.svelte.ts** — Handle new events:

```typescript
function handleAgentEvent(event: AgentEvent) {
  switch (event.type) {
    // Existing cases...
    
    case 'integration_check_pass':
      updateEdgeStatus(event.data.edge_id, 'verified');
      break;
      
    case 'integration_check_fail':
      updateEdgeStatus(event.data.edge_id, 'missing');
      addNotification(`Missing integration: ${event.data.message}`, 'warning');
      break;
      
    case 'stub_detected':
      markNodeAsIncomplete(event.data.artifact_id, 'stub');
      break;
      
    case 'orphan_detected':
      markNodeAsOrphan(event.data.artifact_id);
      break;
  }
}
```

### Event Schema (`schemas/agent-events.schema.json`)

Add new event definitions:

```json
{
  "IntegrationCheckStart": {
    "type": "object",
    "properties": {
      "edge_id": { "type": "string" },
      "check_type": { "type": "string" },
      "source_artifact": { "type": "string" },
      "target_artifact": { "type": "string" }
    }
  },
  "IntegrationCheckPass": {
    "type": "object", 
    "properties": {
      "edge_id": { "type": "string" },
      "check_type": { "type": "string" },
      "verification_method": { "type": "string" }
    }
  },
  "IntegrationCheckFail": {
    "type": "object",
    "properties": {
      "edge_id": { "type": "string" },
      "check_type": { "type": "string" },
      "expected": { "type": "string" },
      "actual": { "type": "string" },
      "suggested_fix": { "type": "string" }
    }
  },
  "StubDetected": {
    "type": "object",
    "properties": {
      "artifact_id": { "type": "string" },
      "file_path": { "type": "string" },
      "stub_type": { "type": "string" },
      "location": { "type": "string" }
    }
  }
}
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PYTHON LAYER                                 │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │ AgentPlanner │───▶│IntegrationVer│───▶│ EventEmitter │           │
│  │              │    │   ifier      │    │              │           │
│  │ generates    │    │ verifies     │    │ emits NDJSON │           │
│  │ wire tasks   │    │ integrations │    │ events       │           │
│  └──────────────┘    └──────────────┘    └──────┬───────┘           │
│                                                  │                   │
└──────────────────────────────────────────────────│───────────────────┘
                                                   │ stdout (NDJSON)
                                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          RUST LAYER                                  │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │ AgentBridge  │───▶│ EventParser  │───▶│ Tauri Emit   │           │
│  │              │    │              │    │              │           │
│  │ reads stdout │    │ parses JSON  │    │ emits to     │           │
│  │              │    │ validates    │    │ frontend     │           │
│  └──────────────┘    └──────────────┘    └──────┬───────┘           │
│                                                  │                   │
└──────────────────────────────────────────────────│───────────────────┘
                                                   │ Tauri events
                                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         SVELTE LAYER                                 │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │ EventHandler │───▶│ DAG Store    │───▶│ DAG Canvas   │           │
│  │              │    │              │    │              │           │
│  │ routes events│    │ updates      │    │ renders      │           │
│  │ to handlers  │    │ node/edge    │    │ integration  │           │
│  │              │    │ state        │    │ edges        │           │
│  └──────────────┘    └──────────────┘    └──────────────┘           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| AST parsing is slow | Verification delays execution | Batch verification, cache parse results, quick regex pre-filter |
| False positives | User frustration, noise | High-confidence threshold, allow `# sunwell:ignore` annotations |
| Polyglot projects | Incomplete coverage | Start Python-only, add language plugins incrementally |
| Over-generation of wire tasks | DAG bloat, overwhelm | Collapse trivial wires, show summary in UI |
| LLM doesn't understand wire tasks | Poor execution | Clear prompts, examples, few-shot learning |
| Cross-layer schema drift | Events mismatched between Python/Rust/TS | Use `generate_event_types.py` script, add CI validation |
| Svelte/Rust coordination | Type mismatches, breaking changes | TypeScript types auto-generated from Rust, shared schema |
| Event ordering race conditions | UI shows stale state | Sequence numbers on events, optimistic UI with reconciliation |

---

## Implementation Phases

### Phase 1: Python Core — Task Extension (Week 1)
**Python only — no frontend changes**

- [ ] Add `task_type`, `integrations`, `verification_checks` to `Task` (`naaru/types.py`)
- [ ] Update `TaskGraph.get_ready_tasks()` to handle wire tasks
- [ ] Add integration event types to `events/types.py`
- [ ] No breaking changes to existing flows

**Deliverable**: Wire tasks can be created and executed, events emitted

### Phase 2: Python Core — IntegrationVerifier (Week 2)
**Python only — no frontend changes**

- [ ] Create `naaru/verifier.py` with `IntegrationVerifier` class
- [ ] Integrate with existing `CodebaseAnalyzer` for AST parsing
- [ ] Integrate with `content_validation.py` for stub detection
- [ ] Add `verify_task_complete()` method
- [ ] Emit `integration_check_*` events during verification

**Deliverable**: Integration verification works via CLI with `--json` output

### Phase 3: Rust Bridge — Event Handling (Week 3)
**Rust + TypeScript types only**

- [ ] Add new event types to `agent.rs` (`EventType` enum)
- [ ] Update `DagNode` and `DagEdge` in `dag.rs` with new fields
- [ ] Update `lib/types.ts` with TypeScript equivalents
- [ ] Run `generate_event_types.py` to sync schemas
- [ ] Add unit tests for event parsing

**Deliverable**: Rust correctly parses and forwards integration events

### Phase 4: Svelte UI — DAG Visualization (Week 4)
**Svelte only**

- [ ] Update `DagEdge.svelte` to render integration edges (dashed, colored)
- [ ] Update `DagNode.svelte` to show task type badge
- [ ] Update `dag.svelte.ts` store to track integration status
- [ ] Handle new events in `agent.svelte.ts`
- [ ] Add integration status legend to `DagCanvas.svelte`

**Deliverable**: DAG view shows integration edges with verification status

### Phase 5: Python Planner — Wire Task Generation (Week 5)
**Python + integration tests**

- [ ] Update `AgentPlanner` to generate wire tasks automatically
- [ ] Implement `decompose_with_wiring()` in planner
- [ ] Connect to `WeaknessAnalyzer` for orphan/stub signals
- [ ] Add benchmark tasks for wiring completeness
- [ ] Measure success metrics

**Deliverable**: Full flow works end-to-end with verification

### Phase 6: Polish & Documentation (Week 6)
**All layers**

- [ ] Add `# sunwell:ignore-integration` annotation support
- [ ] Add collapsible wire tasks in DAG view
- [ ] Update CLI help text
- [ ] Add user documentation
- [ ] Performance optimization (batch verification)

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Wiring completion rate | ~60% (estimated) | 95%+ | Benchmark: % of created artifacts that are imported somewhere |
| Orphan rate at completion | ~15% (estimated) | <5% | `find_orphans()` count / total artifacts |
| Stub rate at completion | ~10% (estimated) | <2% | Stub detection hits / total functions |
| User "you forgot" feedback | Baseline TBD | -50% | User study feedback categorization |

---

## Related RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-034 | **Extends**: Builds on `Task.produces`/`requires` |
| RFC-046 | **Integrates**: Goal → Task decomposition |
| RFC-047 | **Complements**: Deep verification for semantic correctness (this RFC: structural correctness) |
| RFC-055 | **Enhances**: DAG visualization with integration edges |
| RFC-056 | **Integrates**: Live execution with wiring status |
| RFC-063 | **Feeds**: Weakness signals trigger integration fixes |

---

## Open Questions

1. **How much verification is too much?**
   - Proposal: Quick regex check during execution, full AST verification on completion
   - Configurable via `verification_depth: "quick" | "full"`

2. **How to handle polyglot projects?**
   - Python first (AST + CodebaseAnalyzer exists)
   - Add `LanguageAdapter` protocol for TypeScript, Rust, Go
   - Fallback to regex patterns for unsupported languages

3. **Should wire tasks be auto-generated or explicit?**
   - Default: Auto-generate with LLM-based decomposition
   - Option: `--explicit-wiring` flag to show/edit wire tasks
   - UI: Collapsible wire task section in DAG view

4. **How to handle false positives?**
   - Allow `# sunwell:ignore-integration` annotations
   - Confidence threshold (only fail if >90% confident)
   - "Soft" verification mode for exploration

---

## Appendix: IntegrationCheck Types

```python
class IntegrationCheckType(str, Enum):
    # File-level
    IMPORT_EXISTS = "import_exists"      # Does file A import X from file B?
    CALL_EXISTS = "call_exists"          # Does function A call function B?
    CLASS_INHERITS = "class_inherits"    # Does class A inherit from class B?
    
    # Application-level
    ROUTE_REGISTERED = "route_registered"  # Is route /foo in the app?
    CONFIG_PRESENT = "config_present"      # Is key X in config file?
    ENV_VAR_USED = "env_var_used"          # Is env var X referenced?
    
    # Quality
    TEST_EXISTS = "test_exists"          # Is there a test for function X?
    USED_NOT_ORPHAN = "used_not_orphan"  # Is artifact X used anywhere?
    NO_STUBS = "no_stubs"                # Does file have no stub implementations?
```
