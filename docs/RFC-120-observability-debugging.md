# RFC-120: Observability & Debugging

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-119 (Unified Event Bus)

## Summary

Add debugging and observability features that help humans understand what Sunwell is doing: debug dumps for troubleshooting, plan versioning for transparency, and session summaries for context.

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

#### Sanitization

Remove sensitive data before export:

```python
SANITIZE_PATTERNS = [
    r'ANTHROPIC_API_KEY=.*',
    r'OPENAI_API_KEY=.*',
    r'Bearer .*',
    r'token=.*',
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
        collect_events(root / 'events.jsonl')
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
```

#### Server Endpoint (for Studio)

```
GET /api/debug/dump
→ Returns tar.gz as file download
```

---

### Part 2: Plan Versioning

#### Data Model

```python
# sunwell/planning/versioning.py

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
    added_artifacts: list[str]
    removed_artifacts: list[str]
    modified_artifacts: list[str]


class PlanVersionStore:
    """Tracks plan versions for a project."""
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'plans'
        self.store_path.mkdir(parents=True, exist_ok=True)
    
    def save_version(self, plan: Plan, reason: str) -> PlanVersion:
        """Save a new version of a plan."""
        plan_id = self._compute_plan_id(plan.goal)
        versions = self.get_versions(plan_id)
        version_num = len(versions) + 1
        
        # Compute diff from previous
        prev = versions[-1] if versions else None
        diff = self._compute_diff(prev, plan) if prev else {}
        
        version = PlanVersion(
            version=version_num,
            plan_id=plan_id,
            goal=plan.goal,
            artifacts=[a.id for a in plan.artifacts],
            tasks=[t.description for t in plan.tasks],
            score=getattr(plan, 'score', None),
            created_at=datetime.utcnow(),
            reason=reason,
            **diff,
        )
        
        self._write_version(version)
        return version
    
    def get_versions(self, plan_id: str) -> list[PlanVersion]:
        """Get all versions of a plan."""
        ...
    
    def diff(self, plan_id: str, v1: int, v2: int) -> PlanDiff:
        """Compute diff between two versions."""
        ...
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

#### Data Model

```python
# sunwell/session/summary.py

@dataclass
class SessionSummary:
    """Summary of a coding session."""
    session_id: str
    started_at: datetime
    ended_at: datetime | None
    
    # Activity counts
    goals_started: int
    goals_completed: int
    goals_failed: int
    
    # Artifact stats
    files_created: int
    files_modified: int
    files_deleted: int
    lines_added: int
    lines_removed: int
    
    # Learning stats
    learnings_added: int
    dead_ends_recorded: int
    
    # Timing
    total_duration_seconds: float
    planning_seconds: float
    execution_seconds: float
    waiting_seconds: float  # Time waiting for user input
    
    # Top files touched
    top_files: list[tuple[str, int]]  # (path, edit_count)
    
    # Goals list
    goals: list[GoalSummary]


@dataclass
class GoalSummary:
    """Summary of a single goal."""
    goal_id: str
    goal: str
    status: str  # completed, failed, cancelled
    duration_seconds: float
    tasks_completed: int
    tasks_failed: int
    files_touched: list[str]
```

#### Session Tracking

```python
# sunwell/session/tracker.py

class SessionTracker:
    """Tracks activity within a session."""
    
    def __init__(self):
        self.session_id = str(uuid4())
        self.started_at = datetime.utcnow()
        self._goals: list[GoalSummary] = []
        self._file_edits: dict[str, int] = {}
        self._lines_added = 0
        self._lines_removed = 0
        # ... etc
    
    def record_goal_complete(self, goal_id: str, goal: str, ...):
        """Record a completed goal."""
        ...
    
    def record_file_edit(self, path: str, lines_added: int, lines_removed: int):
        """Record a file edit."""
        ...
    
    def get_summary(self) -> SessionSummary:
        """Generate current session summary."""
        ...
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

## Storage

### File Locations

```
.sunwell/
├── events.jsonl          # Event history (RFC-119)
├── plans/                # Plan versions
│   ├── abc123/
│   │   ├── v1.json
│   │   ├── v2.json
│   │   └── v3.json
│   └── def456/
│       └── v1.json
├── sessions/             # Session summaries
│   ├── 2026-01-24-session-1.json
│   └── 2026-01-24-session-2.json
└── simulacrum.json       # Memory (existing)
```

### Retention Policy

- Events: Keep last 10,000 or 7 days
- Plans: Keep last 50 plan versions per goal
- Sessions: Keep last 30 days

---

## Implementation Plan

### Phase 1: Debug Dump (2-3 hours)

1. Create `sunwell/cli/debug_cmd.py`
2. Implement collectors for each component
3. Add sanitization
4. Add to CLI group
5. Add `/api/debug/dump` endpoint

### Phase 2: Plan Versioning (1 day)

1. Create `sunwell/planning/versioning.py`
2. Integrate with HarmonicPlanner
3. Add CLI commands (`plan history`, `plan diff`, `plan show`)
4. Add server endpoints
5. Add Studio component (PlanHistory.svelte)

### Phase 3: Session Summary (1 day)

1. Create `sunwell/session/tracker.py`
2. Integrate with event handling
3. Add CLI command (`session summary`)
4. Add server endpoint
5. Add Studio integration

---

## Testing

```python
# test_debug_dump.py
async def test_dump_creates_valid_tarball():
    result = await run_cli_command("sunwell debug dump -o test.tar.gz")
    assert result.exit_code == 0
    
    with tarfile.open("test.tar.gz") as tar:
        names = tar.getnames()
        assert "sunwell-debug/meta.json" in names
        assert "sunwell-debug/config.yaml" in names

async def test_dump_sanitizes_secrets():
    # Set env with secret
    os.environ["ANTHROPIC_API_KEY"] = "sk-secret-key"
    
    result = await run_cli_command("sunwell debug dump -o test.tar.gz")
    
    # Extract and check config doesn't contain secret
    with tarfile.open("test.tar.gz") as tar:
        config = tar.extractfile("sunwell-debug/config.yaml").read()
        assert b"sk-secret-key" not in config


# test_plan_versioning.py
async def test_plan_versions_saved():
    store = PlanVersionStore(project_root)
    
    plan1 = Plan(goal="Add auth", artifacts=[...])
    v1 = store.save_version(plan1, "Initial")
    assert v1.version == 1
    
    plan2 = Plan(goal="Add auth", artifacts=[...])  # Modified
    v2 = store.save_version(plan2, "Resonance")
    assert v2.version == 2
    assert v2.added_artifacts or v2.removed_artifacts  # Has diff


# test_session_summary.py
async def test_session_tracks_goals():
    tracker = SessionTracker()
    
    tracker.record_goal_complete("g1", "Add OAuth", ...)
    tracker.record_goal_complete("g2", "Add tests", ...)
    
    summary = tracker.get_summary()
    assert summary.goals_completed == 2
```

---

## Success Metrics

- Debug dump < 5MB for typical project
- Plan history loads in < 100ms
- Session summary accurate within 5% of actual activity

---

## References

- Pachyderm `pachctl debug dump`
- RFC-119: Unified Event Bus (prerequisite for event history)
- RFC-112: Observatory (UI integration point)
