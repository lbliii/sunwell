# RFC-127: Observatory Session Loading

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-120 (Observability), RFC-119 (Unified Event Bus)  
**Confidence**: 85% 🟡

## Summary

Define how the Observatory loads and displays session data on startup: prioritize active runs when present, fall back to the most recent historical session, and clearly indicate the viewing mode to users.

**Key insight**: The Observatory currently always loads the most recent session file without checking for active runs, causing confusion about whether displayed data is live or stale.

## Motivation

### Problem

When users open the Observatory:

1. **"Is this live?"** → No indication whether data is from an active run or historical
2. **"Why is it showing old data?"** → Confusing when no active work is happening
3. **"It didn't update"** → Historical sessions don't refresh, but this isn't obvious

### User Stories

**Developer returning to work:**
> "I opened Studio and see session stats from yesterday. I want to know this is historical data before I start thinking something is wrong."

**Developer mid-task:**
> "I triggered a run from CLI and switched to Observatory. I expect to see my active run, not yesterday's session."

**Developer reviewing past work:**
> "I want to see what I accomplished in my last session, even though I'm not actively running anything."

## Goals

1. **Active-first loading**: Detect active runs and show live session data when present
2. **Clear mode indication**: Users always know if they're viewing live vs. historical data
3. **Seamless transitions**: Auto-switch from historical to live when a run starts
4. **Historical fallback**: Show most recent session when no active runs exist

## Non-Goals

- Session persistence across browser refreshes (handled by backend)
- Multi-session comparison views
- Session replay/scrubbing (future feature)

---

## Current Behavior

```
Observatory opens
    → GET /api/session/summary (no params)
    → Server returns most recent session file
    → No distinction between active/historical
```

**Problems**:
1. No check for in-memory active runs (`RunManager`)
2. No `mode` indicator in API response
3. Frontend can't distinguish stale from live data

---

## Design

### Part 1: Session Mode Detection

Define three session modes:

| Mode | Condition | Behavior |
|------|-----------|----------|
| `live` | Active run exists (`status='running'`) | Real-time updates, pulsing indicator |
| `historical` | No active run, recent session exists | Static display, "Last session" label |
| `empty` | No sessions at all | Empty state with guidance |

### Part 2: API Enhancement

Enhance `/api/session/summary` to return mode information:

```python
# sunwell/server/routes/memory.py

@router.get("/session/summary")
async def get_session_summary(session_id: str | None = None) -> dict[str, Any]:
    """Get session summary with mode detection.
    
    Returns:
        - mode: "live" | "historical" | "empty"
        - active_run_id: Present when mode="live"
        - session data...
    """
    from sunwell.server.routes.agent import get_run_manager
    
    run_manager = get_run_manager()
    
    # 1. Check for specific session request
    if session_id:
        return _load_historical_session(session_id)
    
    # 2. Check for active runs
    active_runs = [r for r in run_manager.list_runs() if r.status == "running"]
    
    if active_runs:
        # Return live session context
        run = active_runs[0]  # Primary active run
        return {
            "mode": "live",
            "active_run_id": run.run_id,
            "session_id": f"live-{run.run_id[:8]}",
            "started_at": run.started_at.isoformat(),
            "ended_at": None,
            "source": run.source,
            "goals_started": 1,
            "goals_completed": 0,
            "goals_failed": 0,
            "files_created": 0,
            "files_modified": 0,
            "files_deleted": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "learnings_added": 0,
            "dead_ends_recorded": 0,
            "total_duration_seconds": _elapsed_seconds(run.started_at),
            "top_files": [],
            "goals": [],
        }
    
    # 3. Fall back to historical session
    recent = SessionTracker.list_recent(limit=1)
    if recent:
        tracker = SessionTracker.load(recent[0])
        summary = tracker.get_summary().to_dict()
        summary["mode"] = "historical"
        return summary
    
    # 4. No sessions at all
    return {
        "mode": "empty",
        "error": "No sessions found",
    }


def _elapsed_seconds(start: datetime) -> float:
    """Calculate elapsed seconds from start time."""
    return (datetime.now(UTC) - start).total_seconds()


def _load_historical_session(session_id: str) -> dict[str, Any]:
    """Load a specific historical session by ID."""
    recent = SessionTracker.list_recent(limit=100)
    for path in recent:
        if session_id in path.stem:
            tracker = SessionTracker.load(path)
            summary = tracker.get_summary().to_dict()
            summary["mode"] = "historical"
            return summary
    
    return {"mode": "empty", "error": f"Session {session_id} not found"}
```

### Part 3: Frontend Mode Display

Update `SessionSummary.svelte` to handle modes:

```svelte
<script lang="ts">
  // ... existing code ...
  
  interface SessionData {
    mode: 'live' | 'historical' | 'empty';
    active_run_id?: string;
    session_id: string;
    // ... existing fields ...
  }
  
  // Derived state for UI
  let isLive = $derived(session?.mode === 'live');
  let isHistorical = $derived(session?.mode === 'historical');
  let isEmpty = $derived(session?.mode === 'empty');
  
  // Adjust refresh interval based on mode
  $effect(() => {
    if (isLive) {
      const interval = setInterval(loadSession, 5000);  // 5s for live
      return () => clearInterval(interval);
    } else if (isHistorical && !sessionId) {
      // Check for mode changes (new run might start)
      const interval = setInterval(loadSession, 30000);  // 30s for historical
      return () => clearInterval(interval);
    }
  });
</script>

<div class="session-summary" class:compact class:live={isLive}>
  {#if isLive}
    <div class="mode-badge live">
      <span class="pulse"></span>
      Live Session
    </div>
  {:else if isHistorical}
    <div class="mode-badge historical">
      📊 Last Session
    </div>
  {/if}
  
  <!-- ... existing content ... -->
</div>

<style>
  .mode-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-family: var(--font-mono);
  }
  
  .mode-badge.live {
    background: rgba(34, 197, 94, 0.15);
    color: var(--success);
    border: 1px solid rgba(34, 197, 94, 0.3);
  }
  
  .mode-badge.historical {
    background: var(--bg-tertiary);
    color: var(--text-tertiary);
    border: 1px solid var(--border-subtle);
  }
  
  .pulse {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success);
    animation: pulse 2s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 4px var(--success); }
    50% { opacity: 0.5; box-shadow: 0 0 8px var(--success); }
  }
</style>
```

### Part 4: Live Session Aggregation

When in live mode, aggregate real-time data from the event stream:

```typescript
// studio/src/lib/socket.ts - add session aggregation

export interface LiveSessionStats {
  filesModified: Set<string>;
  linesAdded: number;
  linesRemoved: number;
  tasksCompleted: number;
  tasksFailed: number;
}

let liveStats = $state<LiveSessionStats>({
  filesModified: new Set(),
  linesAdded: 0,
  linesRemoved: 0,
  tasksCompleted: 0,
  tasksFailed: 0,
});

// Update on relevant events
onGlobalEvent((event) => {
  if (event.type === 'file_edit') {
    liveStats.filesModified.add(event.data.path);
    liveStats.linesAdded += event.data.lines_added ?? 0;
    liveStats.linesRemoved += event.data.lines_removed ?? 0;
  }
  if (event.type === 'task_complete') {
    liveStats.tasksCompleted += 1;
  }
  if (event.type === 'task_failed') {
    liveStats.tasksFailed += 1;
  }
});

export function resetLiveStats() {
  liveStats = {
    filesModified: new Set(),
    linesAdded: 0,
    linesRemoved: 0,
    tasksCompleted: 0,
    tasksFailed: 0,
  };
}
```

---

## State Transitions

```
┌─────────────┐
│   empty     │  No sessions, no runs
└──────┬──────┘
       │ run starts
       ▼
┌─────────────┐
│    live     │  Active run in progress
└──────┬──────┘
       │ run completes
       ▼
┌─────────────┐
│ historical  │  Session saved, no active runs
└──────┬──────┘
       │ new run starts
       ▼
┌─────────────┐
│    live     │
└─────────────┘
```

**Transition triggers**:
- `empty → live`: Run created
- `live → historical`: Run completes/fails, session saved
- `historical → live`: New run starts

---

## API Contract

### GET /api/session/summary

**Request**:
```
GET /api/session/summary
GET /api/session/summary?session_id=abc123
```

**Response (live mode)**:
```json
{
  "mode": "live",
  "active_run_id": "run-abc123",
  "session_id": "live-abc123",
  "started_at": "2026-01-24T10:30:00Z",
  "ended_at": null,
  "source": "cli",
  "goals_started": 1,
  "goals_completed": 0,
  "total_duration_seconds": 45.2,
  "top_files": [],
  "goals": []
}
```

**Response (historical mode)**:
```json
{
  "mode": "historical",
  "session_id": "2026-01-24-abc12345",
  "started_at": "2026-01-24T09:00:00Z",
  "ended_at": "2026-01-24T10:00:00Z",
  "source": "studio",
  "goals_started": 5,
  "goals_completed": 4,
  "goals_failed": 1,
  "total_duration_seconds": 3600,
  "top_files": [["auth.py", 3], ["tests.py", 2]],
  "goals": [...]
}
```

**Response (empty mode)**:
```json
{
  "mode": "empty",
  "error": "No sessions found"
}
```

---

## Implementation Plan

### Phase 1: API Enhancement (1-2 hours)
1. Update `/api/session/summary` with mode detection
2. Add `_elapsed_seconds` helper
3. Add tests for mode transitions

### Phase 2: Frontend Mode Display (1-2 hours)
1. Add mode badge to `SessionSummary.svelte`
2. Adjust refresh intervals by mode
3. Style live/historical badges

### Phase 3: Live Aggregation (2-3 hours)
1. Add `LiveSessionStats` to socket lib
2. Aggregate from event stream
3. Merge live stats into session display

### Phase 4: Polish (1 hour)
1. Smooth transitions between modes
2. Loading states during mode switches
3. Error handling for edge cases

**Total estimate**: 5-8 hours

---

## Alternatives Considered

### Alternative A: Frontend-Only Detection

Check `agent.isRunning` in frontend without API changes.

**Pros**:
- No backend changes needed
- Faster to implement

**Cons**:
- Frontend might miss CLI runs not tracked in agent store
- Duplicates logic between frontend and backend
- Harder to extend for future features

**Decision**: Rejected. Backend should be source of truth for mode detection.

### Alternative B: Always Show Empty Until Active

Only show session data when there's an active run.

**Pros**:
- Simpler—no historical loading
- No confusion about stale data

**Cons**:
- Loses useful "what did I do yesterday" context
- Observatory feels broken when not actively running

**Decision**: Rejected. Historical context is valuable for continuity.

### Alternative C: Separate Live/History Tabs

Two explicit tabs: "Live" and "History".

**Pros**:
- Clear separation
- User controls what they see

**Cons**:
- More complex UI
- User has to manually switch
- Doesn't solve "what should I see by default"

**Decision**: Deferred. Could add later, but automatic detection is better default.

---

## Testing

### Unit Tests

```python
# tests/test_session_mode.py

def test_mode_live_when_active_run():
    """Mode should be 'live' when RunManager has active runs."""
    run_manager = RunManager()
    run = run_manager.create_run("Test goal", source="cli")
    run.status = "running"
    
    response = get_session_summary()
    
    assert response["mode"] == "live"
    assert response["active_run_id"] == run.run_id


def test_mode_historical_when_no_active_runs():
    """Mode should be 'historical' when only saved sessions exist."""
    # Create and save a session
    tracker = SessionTracker()
    tracker.record_goal_complete(...)
    tracker.save()
    
    response = get_session_summary()
    
    assert response["mode"] == "historical"


def test_mode_empty_when_no_sessions():
    """Mode should be 'empty' when no sessions or runs exist."""
    response = get_session_summary()
    
    assert response["mode"] == "empty"


def test_transition_historical_to_live():
    """Starting a run should transition from historical to live."""
    # Setup: historical session exists
    tracker = SessionTracker()
    tracker.save()
    
    assert get_session_summary()["mode"] == "historical"
    
    # Action: start a run
    run_manager = RunManager()
    run_manager.create_run("New goal")
    
    assert get_session_summary()["mode"] == "live"
```

### Integration Tests

```typescript
// studio/tests/session-mode.spec.ts

test('displays live badge when run is active', async ({ page }) => {
  // Start a run via API
  await fetch('/api/run', { method: 'POST', body: JSON.stringify({ goal: 'Test' }) });
  
  await page.goto('/observatory');
  
  await expect(page.locator('.mode-badge.live')).toBeVisible();
  await expect(page.locator('.mode-badge.live')).toContainText('Live Session');
});

test('displays historical badge when no active run', async ({ page }) => {
  await page.goto('/observatory');
  
  await expect(page.locator('.mode-badge.historical')).toBeVisible();
  await expect(page.locator('.mode-badge.historical')).toContainText('Last Session');
});
```

---

## Success Metrics

1. **Mode accuracy**: 100% of users see correct mode badge
2. **Transition latency**: < 5 seconds to switch from historical to live
3. **User confusion**: Reduce "is this live?" questions in feedback

---

## Open Questions

1. **Multiple active runs**: Should we aggregate all active runs or show primary only?
   - **Proposed**: Show primary (first started), mention count if > 1

2. **Session timeout**: When does a "live" session without events become "stale"?
   - **Proposed**: Keep live while `RunManager` has active run; backend handles cleanup

3. **History depth**: How many historical sessions should be easily accessible?
   - **Proposed**: Last 10 via `/api/session/history`, link to full list

---

## References

- RFC-119: Unified Event Bus (event streaming infrastructure)
- RFC-120: Observability & Debugging (session tracking foundation)
- `src/sunwell/server/routes/memory.py`: Current session API
- `src/sunwell/server/runs.py`: RunManager for active run detection
- `studio/src/components/observatory/SessionSummary.svelte`: Frontend component
