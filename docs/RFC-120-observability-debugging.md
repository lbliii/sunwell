# RFC-120: Observability & Debugging

**Status**: Revised  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Revised**: 2026-01-24  
**Depends on**: RFC-119 (Unified Event Bus) — soft dependency with fallback  
**Confidence**: 88% 🟡 (evaluated, revised)

## Summary

Add debugging and observability features that help humans understand what Sunwell is doing: debug dumps for troubleshooting, plan versioning for transparency, and session summaries for context.

**Key insight**: These features build on existing infrastructure (`TraceLogger`, `ScopeTracker`, `PlanStore`) and can ship incrementally before RFC-119 is fully implemented.

## Motivation

### Problem

When things go wrong or users want to understand Sunwell's behavior:

1. **"Sunwell is stuck"** → No easy way to collect diagnostics
2. **"Why did the plan change?"** → No history of plan evolution
3. **"What did I do today?"** → No session-level view of activity

### User Stories

**Debug dump:**
> "Sunwell keeps failing on my project. I want to share diagnostics with the community without manually copying logs."

**Plan versioning:**
> "The resonance loop changed my plan 3 times. I want to see what changed and why."

**Session summary:**
> "I've been coding all day with Sunwell. Show me what we accomplished."

## Goals

1. **Debug dump**: One command collects all diagnostics for bug reports
2. **Plan versioning**: Track plan evolution, show diffs between versions
3. **Session summary**: Aggregate activity into human-readable summaries

## Non-Goals

- Real-time alerting or monitoring dashboards
- Automatic error reporting to cloud services
- Plan rollback/restore (separate RFC if needed)

---

## Existing Infrastructure

This RFC builds on existing code to minimize new abstractions:

| Feature | Existing Code | Gap Filled by This RFC |
|---------|---------------|------------------------|
| Event logging | `TraceLogger` at `naaru/persistence.py:563` | Unified collection in debug dump |
| Plan persistence | `PlanStore` at `naaru/persistence.py:370` | Version history, diffs |
| Session stats | `ScopeTracker.get_session_stats()` at `guardrails/scope.py:171` | Timeline, aggregation |
| Simulacrum state | `Simulacrum.save()` at `simulacrum/core/core.py:277` | Already ready |
| Run tracking | `RunState` at `server/runs.py:18` | Collection in dump |

---

## Design

### Part 1: Debug Dump

#### CLI Command

```bash
sunwell debug dump [--output FILE]
```

Creates a tarball with:

```
sunwell-debug-2026-01-24-103045.tar.gz
├── meta.json              # Sunwell version, OS, Python version
├── config.yaml            # User configuration (sanitized)
├── events.jsonl           # Recent event history (last 1000 events)
├── runs/                  # Recent run summaries
│   ├── run-abc123.json    # Goal, plan, status, timing
│   └── run-def456.json
├── plans/                 # Plan snapshots
│   └── plan-abc123-v1.json
├── simulacrum.json        # Memory state (learnings, dead ends)
├── agent.log              # Recent log output (last 1000 lines)
└── system/
    ├── disk.txt           # Disk space
    ├── memory.txt         # Memory usage
    └── processes.txt      # Running processes (if relevant)
```

#### Size Limits

Debug dumps are capped to ensure reasonable file sizes:

```python
# sunwell/cli/debug_cmd.py

DUMP_LIMITS = {
    'events': 1000,           # Last N events
    'log_lines': 1000,        # Last N log lines
    'runs': 20,               # Most recent runs
    'plan_versions': 10,      # Per plan
    'max_total_mb': 5,        # Hard cap on tarball size
}
```

If a component exceeds limits, it's truncated with a marker:

```json
{"_truncated": true, "_total": 5432, "_included": 1000}
```

#### Sanitization

Remove sensitive data before export:

```python
SANITIZE_PATTERNS = [
    r'ANTHROPIC_API_KEY=.*',
    r'OPENAI_API_KEY=.*',
    r'Bearer .*',
    r'token=.*',
    r'password["\']?\s*[:=]\s*["\']?[^"\']*',
    r'secret["\']?\s*[:=]\s*["\']?[^"\']*',
]
```

#### Implementation

```python
# sunwell/cli/debug_cmd.py

@click.command()
@click.option('--output', '-o', default=None, help='Output file path')
def dump(output: str | None):
    """Collect diagnostics for bug reports."""
    timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    output = output or f'sunwell-debug-{timestamp}.tar.gz'
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Collect each component
        collect_meta(root / 'meta.json')
        collect_config(root / 'config.yaml')
        collect_events(root / 'events.jsonl')  # Uses fallback strategy
        collect_runs(root / 'runs')
        collect_plans(root / 'plans')
        collect_simulacrum(root / 'simulacrum.json')
        collect_logs(root / 'agent.log')
        collect_system(root / 'system')
        
        # Create tarball
        with tarfile.open(output, 'w:gz') as tar:
            tar.add(root, arcname='sunwell-debug')
    
    console.print(f'[green]✓[/green] Debug dump saved to {output}')
    console.print(f'  Size: {Path(output).stat().st_size / 1024:.1f} KB')
    console.print(f'  [dim]Attach to bug reports or share in Discord[/dim]')


def collect_events(dest: Path) -> None:
    """Collect events with fallback strategy.
    
    Priority order (use first available):
    1. RFC-119 EventBus storage (.sunwell/events.jsonl) — if implemented
    2. TraceLogger files (.sunwell/plans/*.trace.jsonl) — existing
    3. ExternalEventStore (.sunwell/external/events.jsonl) — existing
    """
    events: list[dict] = []
    
    # Try RFC-119 event storage first
    event_bus_path = Path.cwd() / '.sunwell' / 'events.jsonl'
    if event_bus_path.exists():
        events.extend(_read_jsonl(event_bus_path, limit=DUMP_LIMITS['events']))
    
    # Fallback: collect from TraceLogger files (existing infrastructure)
    if not events:
        trace_dir = Path.cwd() / '.sunwell' / 'plans'
        if trace_dir.exists():
            for trace_file in trace_dir.glob('*.trace.jsonl'):
                events.extend(_read_jsonl(trace_file, limit=100))
    
    # Also include external events if available
    external_path = Path.cwd() / '.sunwell' / 'external' / 'events.jsonl'
    if external_path.exists():
        events.extend(_read_jsonl(external_path, limit=200))
    
    # Sort by timestamp, keep most recent
    events.sort(key=lambda e: e.get('ts', e.get('timestamp', '')), reverse=True)
    events = events[:DUMP_LIMITS['events']]
    
    # Write output
    with open(dest, 'w') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')
```

#### Server Endpoint (for Studio)

```
GET /api/debug/dump
→ Returns tar.gz as file download
```

---

### Part 2: Plan Versioning

#### Design Options

**Option A: Extend existing `PlanStore`** (Recommended)

Leverage `PlanStore` at `naaru/persistence.py:370` by adding version tracking:

```python
# Modify existing PlanStore
class PlanStore:
    def save(self, execution: SavedExecution, reason: str = "Update") -> Path:
        """Save with versioning."""
        # Existing: saves to {goal_hash}.json
        # New: also saves to {goal_hash}/v{N}.json
        ...
```

✅ Pros: Reuses existing code, single source of truth  
❌ Cons: Modifies existing API, migration needed

**Option B: New `PlanVersionStore`**

Separate store that tracks versions independently.

✅ Pros: No impact to existing code, cleaner separation  
❌ Cons: Two stores for plans, potential drift

**Decision**: Option A — extend `PlanStore` to minimize code duplication.

#### Data Model

```python
# sunwell/naaru/persistence.py (additions)

@dataclass(frozen=True)
class PlanVersion:
    """A single version of a plan."""
    version: int                    # 1, 2, 3, ...
    plan_id: str                    # Hash of goal + context
    goal: str
    artifacts: list[str]           # Artifact IDs in this version
    tasks: list[str]               # Task descriptions
    score: float | None            # Harmonic score if available
    created_at: datetime
    reason: str                    # Why this version exists
    
    # Diff from previous version
    added_artifacts: list[str] = field(default_factory=list)
    removed_artifacts: list[str] = field(default_factory=list)
    modified_artifacts: list[str] = field(default_factory=list)


class PlanStore:
    """Manages plan persistence with file locking and versioning.
    
    Extended from existing implementation to support version history.
    """
    
    # ... existing methods ...
    
    def save_version(self, execution: SavedExecution, reason: str) -> PlanVersion:
        """Save a new version of a plan."""
        plan_id = execution.goal_hash
        versions = self.get_versions(plan_id)
        version_num = len(versions) + 1
        
        # Compute diff from previous
        prev = versions[-1] if versions else None
        diff = self._compute_diff(prev, execution) if prev else {}
        
        version = PlanVersion(
            version=version_num,
            plan_id=plan_id,
            goal=execution.goal,
            artifacts=[a.id for a in execution.artifacts],
            tasks=[t.description for t in execution.tasks],
            score=getattr(execution, 'score', None),
            created_at=datetime.now(UTC),
            reason=reason,
            **diff,
        )
        
        self._write_version(version)
        return version
    
    def get_versions(self, plan_id: str) -> list[PlanVersion]:
        """Get all versions of a plan."""
        version_dir = self.base_path / plan_id
        if not version_dir.exists():
            return []
        
        versions = []
        for vfile in sorted(version_dir.glob('v*.json')):
            with open(vfile) as f:
                versions.append(PlanVersion(**json.load(f)))
        return versions
    
    def diff(self, plan_id: str, v1: int, v2: int) -> PlanDiff:
        """Compute diff between two versions."""
        ...
```

#### Retention Policy Integration

Versioning integrates with existing `PlanStore.clean_old()`:

```python
def clean_old(self, max_age_hours: float = 168.0, max_versions: int = 50) -> int:
    """Clean old plans and version history.
    
    Args:
        max_age_hours: Delete plans older than this
        max_versions: Keep at most N versions per plan (NEW)
    """
    deleted = 0
    
    # Existing age-based cleanup
    for plan_file in self.base_path.glob('*.json'):
        # ... existing logic ...
    
    # NEW: Version cleanup
    for plan_dir in self.base_path.iterdir():
        if plan_dir.is_dir():
            versions = sorted(plan_dir.glob('v*.json'))
            if len(versions) > max_versions:
                for old_version in versions[:-max_versions]:
                    old_version.unlink()
                    deleted += 1
    
    return deleted
```

#### Integration Points

**During planning:**
```python
# In HarmonicPlanner
plan = await self._generate_plan(goal)
version_store.save_version(plan, reason="Initial plan")

# After resonance refinement
refined_plan = await self._refine(plan)
version_store.save_version(refined_plan, reason=f"Resonance round {round}")
```

**During user edits:**
```python
# In Studio when user modifies plan
version_store.save_version(edited_plan, reason="User edit")
```

#### CLI Commands

```bash
# List plan versions
sunwell plan history [PLAN_ID]
  v3  2026-01-24 10:45  User edit: removed auth task
  v2  2026-01-24 10:30  Resonance round 2: +15% score
  v1  2026-01-24 10:28  Initial plan

# Show diff between versions
sunwell plan diff v1 v2
  + artifact: tests/test_auth.py
  - artifact: auth/legacy.py
  ~ task: "Create auth module" → "Create OAuth module"

# Show specific version
sunwell plan show v2
```

#### Server Endpoints

```
GET /api/plans/{plan_id}/versions
GET /api/plans/{plan_id}/versions/{version}
GET /api/plans/{plan_id}/diff?v1=1&v2=2
```

#### Studio Integration

```svelte
<!-- PlanHistory.svelte -->
<div class="plan-history">
  <h3>Plan Evolution</h3>
  
  <div class="version-timeline">
    {#each versions as version}
      <div class="version" class:selected={version.version === selectedVersion}>
        <span class="version-num">v{version.version}</span>
        <span class="reason">{version.reason}</span>
        <span class="score">{version.score?.toFixed(1)}</span>
        <span class="time">{formatTime(version.created_at)}</span>
      </div>
    {/each}
  </div>
  
  {#if comparing}
    <PlanDiff {diff} />
  {/if}
</div>
```

---

### Part 3: Session Summary

#### Building on Existing Infrastructure

Session summary aggregates data from existing tracking:

| Source | Data | Location |
|--------|------|----------|
| `ScopeTracker` | files_touched, lines_changed, goals_completed | `guardrails/scope.py:171` |
| `RunState` | goal, status, started_at, events | `server/runs.py:18` |
| `LearningStore` | learnings count, dead_ends | `agent/learning.py:322` |

#### Data Model

```python
# sunwell/session/summary.py

@dataclass
class SessionSummary:
    """Summary of a coding session."""
    session_id: str
    started_at: datetime
    ended_at: datetime | None
    source: str  # "cli" | "studio" | "mixed" — tracks origin (RFC-119)
    
    # Activity counts
    goals_started: int
    goals_completed: int
    goals_failed: int
    
    # Artifact stats (from ScopeTracker)
    files_created: int
    files_modified: int
    files_deleted: int
    lines_added: int
    lines_removed: int
    
    # Learning stats (from LearningStore)
    learnings_added: int
    dead_ends_recorded: int
    
    # Timing
    total_duration_seconds: float
    planning_seconds: float
    execution_seconds: float
    waiting_seconds: float  # Time waiting for user input
    
    # Top files touched
    top_files: list[tuple[str, int]]  # (path, edit_count)
    
    # Goals list with timeline
    goals: list[GoalSummary]


@dataclass
class GoalSummary:
    """Summary of a single goal."""
    goal_id: str
    goal: str
    status: str  # completed, failed, cancelled
    source: str  # "cli" | "studio"
    started_at: datetime
    duration_seconds: float
    tasks_completed: int
    tasks_failed: int
    files_touched: list[str]
```

#### Session Tracking

```python
# sunwell/session/tracker.py

class SessionTracker:
    """Tracks activity within a session.
    
    Wraps ScopeTracker for compatibility while adding timeline tracking.
    """
    
    def __init__(self, scope_tracker: ScopeTracker | None = None):
        self.session_id = str(uuid4())
        self.started_at = datetime.now(UTC)
        self._scope_tracker = scope_tracker or ScopeTracker()
        self._goals: list[GoalSummary] = []
        self._learning_count = 0
        self._dead_end_count = 0
    
    def record_goal_complete(
        self,
        goal_id: str,
        goal: str,
        status: str,
        source: str,
        duration_seconds: float,
        tasks_completed: int,
        tasks_failed: int,
        files: list[str],
    ) -> None:
        """Record a completed goal."""
        self._goals.append(GoalSummary(
            goal_id=goal_id,
            goal=goal,
            status=status,
            source=source,
            started_at=datetime.now(UTC) - timedelta(seconds=duration_seconds),
            duration_seconds=duration_seconds,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            files_touched=files,
        ))
    
    def get_summary(self) -> SessionSummary:
        """Generate current session summary.
        
        Combines data from ScopeTracker with timeline data.
        """
        scope_stats = self._scope_tracker.get_session_stats()
        
        # Determine source based on goals
        sources = set(g.source for g in self._goals)
        source = "mixed" if len(sources) > 1 else (sources.pop() if sources else "cli")
        
        return SessionSummary(
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=None,  # Set when session ends
            source=source,
            goals_started=len(self._goals),
            goals_completed=len([g for g in self._goals if g.status == "completed"]),
            goals_failed=len([g for g in self._goals if g.status == "failed"]),
            files_created=0,  # TODO: track creation vs modification
            files_modified=scope_stats["files_touched"],
            files_deleted=0,  # TODO: track deletions
            lines_added=scope_stats["lines_changed"] // 2,  # Approximate
            lines_removed=scope_stats["lines_changed"] // 2,
            learnings_added=self._learning_count,
            dead_ends_recorded=self._dead_end_count,
            total_duration_seconds=(datetime.now(UTC) - self.started_at).total_seconds(),
            planning_seconds=0.0,  # TODO: track planning time
            execution_seconds=0.0,  # TODO: track execution time
            waiting_seconds=0.0,
            top_files=self._compute_top_files(),
            goals=self._goals,
        )
    
    def _compute_top_files(self) -> list[tuple[str, int]]:
        """Compute most frequently edited files."""
        file_counts: dict[str, int] = {}
        for goal in self._goals:
            for f in goal.files_touched:
                file_counts[f] = file_counts.get(f, 0) + 1
        return sorted(file_counts.items(), key=lambda x: -x[1])[:10]
```

#### CLI Command

```bash
sunwell session summary

╭─────────────────────────────────────────────╮
│  📊 Session Summary                         │
│  Started: 2 hours ago                       │
╰─────────────────────────────────────────────╯

Goals: 4 completed, 0 failed
Files: 8 created, 12 modified
Code:  +342 lines, -89 lines

Top files:
  auth/oauth.py        (5 edits)
  tests/test_auth.py   (3 edits)
  api/routes.py        (2 edits)

Learnings: 3 new patterns recorded
Dead ends: 1 avoided

Timeline:
  10:30  ✓ Add OAuth configuration
  10:45  ✓ Create auth callback route
  11:15  ✓ Add session middleware
  11:30  ✓ Write auth tests
```

#### Server Endpoint

```
GET /api/session/summary
→ SessionSummary JSON
```

#### Studio Integration

Session summary could appear:
- In sidebar as collapsible panel
- In Observatory as new tab
- As end-of-session modal

---

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Debug dump contains secrets | High — credential leak | Pattern-based sanitization + manual review reminder |
| Plan versions consume disk | Medium — storage bloat | 50 version cap + `clean_old()` integration |
| Session tracking adds overhead | Low — performance | Lazy aggregation, only compute on request |
| RFC-119 not implemented | Medium — incomplete events | Fallback to TraceLogger (existing) |
| Large projects exceed 5MB | Low — unusable dump | Truncation with markers, user warning |

### Security Considerations

Debug dumps are designed for sharing. Sanitization patterns catch common secrets, but users should review before posting publicly:

```bash
sunwell debug dump -o debug.tar.gz
# ⚠️  Review contents before sharing publicly
```

The CLI warns if sanitization found patterns:

```
[yellow]⚠[/yellow] Sanitized 3 potential secrets (ANTHROPIC_API_KEY, Bearer tokens)
```

---

## Storage

### File Locations

```
.sunwell/
├── events.jsonl          # Event history (RFC-119, or fallback)
├── plans/                # Existing plan files (PlanStore)
│   ├── abc123.json       # Latest execution state
│   ├── abc123/           # NEW: Version history
│   │   ├── v1.json
│   │   ├── v2.json
│   │   └── v3.json
│   └── def456.json
├── sessions/             # Session summaries
│   ├── 2026-01-24-session-1.json
│   └── 2026-01-24-session-2.json
├── external/             # Existing external events
│   └── events.jsonl
└── simulacrum.json       # Memory (existing)
```

### Retention Policy

| Data | Retention | Cleanup Trigger |
|------|-----------|-----------------|
| Events | 10,000 events OR 7 days | `clean_old()` |
| Plan versions | 50 per goal | `clean_old()` |
| Plan files | 168 hours (existing) | `clean_old()` |
| Sessions | 30 days | On session start |

**Interaction with existing cleanup**:

```python
# Existing: PlanStore.clean_old() runs on startup
# Enhanced to also clean version history
plan_store.clean_old(max_age_hours=168.0, max_versions=50)
```

---

## Implementation Plan

**Dependency**: RFC-119 is a soft dependency. Phase 1 includes fallback strategy; full event integration happens when RFC-119 ships.

### Phase 1: Debug Dump (2-3 hours)

| Task | File | Depends On |
|------|------|------------|
| Create debug CLI group | `sunwell/cli/debug_cmd.py` (new) | — |
| Implement `collect_meta()` | `sunwell/cli/debug_cmd.py` | — |
| Implement `collect_config()` with sanitization | `sunwell/cli/debug_cmd.py` | — |
| Implement `collect_events()` with fallback | `sunwell/cli/debug_cmd.py` | TraceLogger (existing) |
| Implement `collect_runs()` | `sunwell/cli/debug_cmd.py` | RunManager (existing) |
| Implement `collect_plans()` | `sunwell/cli/debug_cmd.py` | PlanStore (existing) |
| Implement `collect_simulacrum()` | `sunwell/cli/debug_cmd.py` | Simulacrum.save() (existing) |
| Implement `collect_system()` | `sunwell/cli/debug_cmd.py` | — |
| Add size limit enforcement | `sunwell/cli/debug_cmd.py` | — |
| Add to CLI group | `sunwell/cli/main.py` | — |
| Add `/api/debug/dump` endpoint | `sunwell/server/main.py` | — |

**Verification**: `pytest tests/test_debug_dump.py`

### Phase 2: Plan Versioning (1 day)

| Task | File | Depends On |
|------|------|------------|
| Add `PlanVersion` dataclass | `sunwell/naaru/persistence.py` | — |
| Add `save_version()` to PlanStore | `sunwell/naaru/persistence.py` | — |
| Add `get_versions()` to PlanStore | `sunwell/naaru/persistence.py` | — |
| Update `clean_old()` for versions | `sunwell/naaru/persistence.py` | — |
| Integrate with HarmonicPlanner | `sunwell/naaru/planners/harmonic.py` | PlanStore changes |
| Add `plan history` CLI command | `sunwell/cli/plan_cmd.py` | PlanStore changes |
| Add `plan diff` CLI command | `sunwell/cli/plan_cmd.py` | PlanStore changes |
| Add server endpoints | `sunwell/server/main.py` | PlanStore changes |
| Add Studio component | `studio/src/components/PlanHistory.svelte` (new) | Server endpoints |

**Verification**: `pytest tests/test_plan_versioning.py`

### Phase 3: Session Summary (1 day)

| Task | File | Depends On |
|------|------|------------|
| Create `SessionSummary` dataclass | `sunwell/session/summary.py` (new) | — |
| Create `SessionTracker` class | `sunwell/session/tracker.py` (new) | ScopeTracker (existing) |
| Integrate with Agent | `sunwell/agent/core.py` | SessionTracker |
| Add `session summary` CLI command | `sunwell/cli/session.py` | SessionTracker |
| Add server endpoint | `sunwell/server/main.py` | SessionTracker |
| Add Studio integration | `studio/src/stores/session.svelte.ts` | Server endpoint |

**Verification**: `pytest tests/test_session_summary.py`

### Phase 4: RFC-119 Integration (when available)

| Task | File | Depends On |
|------|------|------------|
| Switch debug dump to RFC-119 events | `sunwell/cli/debug_cmd.py` | RFC-119 implementation |
| Add unified session tracking | `sunwell/session/tracker.py` | RFC-119 EventBus |

**Verification**: Manual — start Studio, run CLI command, verify events appear

---

## Testing

```python
# tests/test_debug_dump.py
import tarfile
import os
from pathlib import Path

class TestDebugDump:
    """Debug dump tests."""
    
    async def test_dump_creates_valid_tarball(self, tmp_path):
        """Debug dump creates valid tarball with all components."""
        output = tmp_path / "test.tar.gz"
        result = await run_cli_command(f"sunwell debug dump -o {output}")
        
        assert result.exit_code == 0
        assert output.exists()
        
        with tarfile.open(output) as tar:
            names = tar.getnames()
            assert "sunwell-debug/meta.json" in names
            assert "sunwell-debug/config.yaml" in names
            assert "sunwell-debug/events.jsonl" in names
    
    async def test_dump_sanitizes_secrets(self, tmp_path, monkeypatch):
        """Debug dump removes API keys and tokens."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-key")
        output = tmp_path / "test.tar.gz"
        
        result = await run_cli_command(f"sunwell debug dump -o {output}")
        
        with tarfile.open(output) as tar:
            # Check all files for secrets
            for member in tar.getmembers():
                if member.isfile():
                    content = tar.extractfile(member).read()
                    assert b"sk-secret-key" not in content
                    assert b"ANTHROPIC_API_KEY=sk" not in content
    
    async def test_dump_respects_size_limits(self, tmp_path, large_project):
        """Debug dump stays under 5MB even for large projects."""
        output = tmp_path / "test.tar.gz"
        result = await run_cli_command(f"sunwell debug dump -o {output}")
        
        assert result.exit_code == 0
        assert output.stat().st_size < 5 * 1024 * 1024  # 5MB
    
    async def test_dump_fallback_to_trace_logger(self, tmp_path, no_event_bus):
        """Debug dump uses TraceLogger when RFC-119 not available."""
        # Create trace files (existing infrastructure)
        trace_dir = tmp_path / ".sunwell" / "plans"
        trace_dir.mkdir(parents=True)
        (trace_dir / "abc123.trace.jsonl").write_text(
            '{"ts": "2026-01-24T10:00:00", "event": "plan_created"}\n'
        )
        
        output = tmp_path / "test.tar.gz"
        result = await run_cli_command(f"sunwell debug dump -o {output}")
        
        with tarfile.open(output) as tar:
            events = tar.extractfile("sunwell-debug/events.jsonl").read()
            assert b"plan_created" in events


# tests/test_plan_versioning.py
from sunwell.naaru.persistence import PlanStore, PlanVersion

class TestPlanVersioning:
    """Plan versioning tests."""
    
    async def test_plan_versions_saved(self, tmp_path):
        """Plan versions are saved incrementally."""
        store = PlanStore(base_path=tmp_path / "plans")
        
        # Create execution
        execution1 = create_execution(goal="Add auth", artifacts=["auth.py"])
        v1 = store.save_version(execution1, "Initial")
        assert v1.version == 1
        assert v1.reason == "Initial"
        
        # Modify and save again
        execution2 = create_execution(goal="Add auth", artifacts=["auth.py", "tests.py"])
        v2 = store.save_version(execution2, "Added tests")
        assert v2.version == 2
        assert "tests.py" in v2.added_artifacts
    
    async def test_version_cleanup(self, tmp_path):
        """Old versions are cleaned up."""
        store = PlanStore(base_path=tmp_path / "plans")
        
        # Create 60 versions (exceeds 50 limit)
        execution = create_execution(goal="Test cleanup")
        for i in range(60):
            store.save_version(execution, f"Version {i}")
        
        # Clean with 50 version limit
        deleted = store.clean_old(max_versions=50)
        
        assert deleted == 10
        versions = store.get_versions(execution.goal_hash)
        assert len(versions) == 50
    
    async def test_version_diff(self, tmp_path):
        """Version diffs show added/removed artifacts."""
        store = PlanStore(base_path=tmp_path / "plans")
        
        v1 = store.save_version(
            create_execution(goal="API", artifacts=["a.py", "b.py"]),
            "Initial"
        )
        v2 = store.save_version(
            create_execution(goal="API", artifacts=["a.py", "c.py"]),
            "Replaced b with c"
        )
        
        diff = store.diff(v1.plan_id, 1, 2)
        assert "b.py" in diff.removed
        assert "c.py" in diff.added


# tests/test_session_summary.py
from sunwell.session.tracker import SessionTracker
from sunwell.guardrails.scope import ScopeTracker

class TestSessionSummary:
    """Session summary tests."""
    
    async def test_session_tracks_goals(self):
        """Session tracker records goal completions."""
        scope_tracker = ScopeTracker()
        tracker = SessionTracker(scope_tracker)
        
        tracker.record_goal_complete(
            goal_id="g1", goal="Add OAuth", status="completed",
            source="cli", duration_seconds=120.0,
            tasks_completed=3, tasks_failed=0, files=["oauth.py"]
        )
        tracker.record_goal_complete(
            goal_id="g2", goal="Add tests", status="completed",
            source="studio", duration_seconds=60.0,
            tasks_completed=2, tasks_failed=0, files=["test_oauth.py"]
        )
        
        summary = tracker.get_summary()
        assert summary.goals_completed == 2
        assert summary.source == "mixed"  # Both CLI and Studio
    
    async def test_session_integrates_scope_tracker(self):
        """Session summary includes ScopeTracker data."""
        scope_tracker = ScopeTracker()
        scope_tracker.session_files.add(Path("a.py"))
        scope_tracker.session_lines_changed = 100
        
        tracker = SessionTracker(scope_tracker)
        summary = tracker.get_summary()
        
        assert summary.files_modified == 1
        assert summary.lines_added + summary.lines_removed == 100
    
    async def test_top_files_computed(self):
        """Top files are computed from goal file touches."""
        tracker = SessionTracker()
        
        # Touch same file multiple times
        for i in range(5):
            tracker.record_goal_complete(
                goal_id=f"g{i}", goal=f"Goal {i}", status="completed",
                source="cli", duration_seconds=10.0,
                tasks_completed=1, tasks_failed=0,
                files=["common.py", f"unique{i}.py"]
            )
        
        summary = tracker.get_summary()
        assert summary.top_files[0] == ("common.py", 5)
```

---

## Alternatives Considered

### Debug Dump

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Tarball (chosen) | Single file, easy to share | Requires extraction | ✅ Selected — matches `pachctl debug dump` |
| JSON bundle | No extraction needed | Large for attachments | ❌ |
| Cloud upload | One-click sharing | Privacy concerns | ❌ |

### Plan Versioning

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Extend PlanStore (chosen) | Reuses code, single source | Modifies existing API | ✅ Selected |
| New PlanVersionStore | No existing code impact | Two stores, duplication | ❌ |
| Git-based versioning | Full history, diff tools | Complex, requires git | ❌ |

### Session Tracking

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Wrap ScopeTracker (chosen) | Reuses existing tracking | Limited to guardrail data | ✅ Selected |
| Independent tracker | Full control | Duplicates ScopeTracker | ❌ |
| Event-sourced (RFC-119) | Complete history | Depends on RFC-119 | ⏳ Phase 4 |

---

## Open Questions

All resolved:

| Question | Resolution |
|----------|------------|
| ~~Event source before RFC-119?~~ | Fallback to TraceLogger + ExternalEventStore |
| ~~Plan version storage scope?~~ | Per-goal (hash-based), integrates with existing PlanStore |
| ~~Session tracking: CLI + Studio?~~ | Yes, `source` field tracks origin; unified when RFC-119 ships |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Debug dump size | < 5MB for typical project | Automated test with fixture |
| Debug dump time | < 5 seconds | CLI timing |
| Plan history load | < 100ms | Server response time |
| Session summary accuracy | Within 5% of actual | Comparison with ScopeTracker stats |
| Sanitization coverage | Zero secrets in dumps | Security audit + automated patterns |

---

## References

- Pachyderm `pachctl debug dump` — inspiration for debug dump format
- RFC-119: Unified Event Bus — soft dependency for event history
- RFC-112: Observatory — UI integration point for plan history
- RFC-116: Harmonic Scoring v2 — HarmonicPlanner integration point
- `sunwell/naaru/persistence.py:370` — Existing PlanStore to extend
- `sunwell/guardrails/scope.py:171` — Existing ScopeTracker to wrap
