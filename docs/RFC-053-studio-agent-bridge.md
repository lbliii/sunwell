# RFC-053: Studio Agent Bridge — Python Event Streaming

**Status**: Implemented  
**Created**: 2026-01-20  
**Updated**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 85% 🟢  
**Depends on**: 
- RFC-043 (Sunwell Studio) — GUI shell
- RFC-042 (Adaptive Agent) — execution engine

---

## Summary

This RFC completes the Studio-Agent communication by adding **real-time event streaming** from the Python agent. The Rust↔Svelte bridge already exists; the gap is that Python's `--json` mode only emits a final completion event rather than streaming progress during execution.

**Core deliverable:**
- Wire existing `AgentEvent` streaming through `--json` mode so events flow: Python → stdout → Rust → Svelte

---

## Motivation

### Current State ✅

The Studio-Agent bridge is **largely implemented**:

| Component | Status | Evidence |
|-----------|--------|----------|
| Rust subprocess spawn | ✅ Done | `agent.rs:96-102` |
| NDJSON parsing | ✅ Done | `agent.rs:125` |
| Event emission to Svelte | ✅ Done | `agent.rs:128` |
| Svelte event handlers | ✅ Done | `agent.ts:289-424` |
| `--json` CLI flag | ✅ Done | `agent_cmd.py:126-129` |
| Demo mode fallback | ✅ Done | `agent.ts:17` `DEMO_MODE = true` |

### The Actual Gap ❌

Python's `--json` mode (`agent_cmd.py:336-368`) **only emits a single completion event** at the end:

```python
# Current behavior (agent_cmd.py:351-356)
result = await naaru.run(goal=goal, ...)
event = complete_event(tasks_completed=result.completed_count, ...)
print(json.dumps(event.to_dict()), file=sys.stdout, flush=True)
# ↑ One event at the end, no streaming
```

The `AdaptiveAgent.run()` already yields `AgentEvent` objects (`agent.py:201-262`), but these events are consumed by the `RichRenderer` for terminal display rather than being forwarded to stdout in JSON mode.

### Success Criteria

```
User types goal → Python streams events → Rust forwards → Svelte updates live
                         ↑
                    THIS IS THE GAP
                  (currently batched)
```

---

## Goals and Non-Goals

### Goals

1. **Stream events during execution** — Forward `AgentEvent` objects to stdout as NDJSON in real-time
2. **Use existing infrastructure** — Leverage `events.py` types and existing Rust/Svelte handlers
3. **Zero regression** — Rich terminal output continues to work when `--json` is not passed
4. **Enable real mode** — Allow `DEMO_MODE = false` to work end-to-end

### Non-Goals

- **New event types** — Use existing `EventType` enum from `events.py`
- **Session persistence** — Out of scope for v1 (future RFC)
- **Bidirectional control** — Pause/resume deferred to future RFC
- **Event buffering** — Direct streaming for v1
- **Windows-specific fixes** — Address as discovered

---

## Design

### Architecture (Existing)

```
┌─────────────────────────────────────────────────────────────────┐
│                        SVELTE FRONTEND                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  handleAgentEvent() ← listen('agent-event')              │  │ ✅ EXISTS
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              ↑ IPC
┌─────────────────────────────────────────────────────────────────┐
│                         RUST BACKEND                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AgentBridge::run_goal()                                 │  │ ✅ EXISTS
│  │  - spawns subprocess                                     │  │
│  │  - reads stdout line by line                             │  │
│  │  - parses NDJSON → app.emit("agent-event")               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              ↑ stdout
┌─────────────────────────────────────────────────────────────────┐
│                       PYTHON AGENT                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  sunwell agent run "goal" --json                         │  │
│  │                                                          │  │
│  │  AdaptiveAgent.run() yields AgentEvent objects           │  │ ✅ EXISTS
│  │           ↓                                              │  │
│  │  JSONRenderer.render() → print(json.dumps(event))        │  │ ❌ NOT WIRED
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Event Schema (Existing)

The `EventType` enum in `events.py:23-135` already defines all needed events:

```python
# events.py - ALREADY EXISTS
class EventType(Enum):
    # Memory events
    MEMORY_LOAD = "memory_load"
    MEMORY_LOADED = "memory_loaded"
    MEMORY_LEARNING = "memory_learning"
    # ... etc
    
    # Planning events
    PLAN_START = "plan_start"
    PLAN_CANDIDATE = "plan_candidate"
    PLAN_WINNER = "plan_winner"
    
    # Execution events
    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    
    # Completion events
    COMPLETE = "complete"
    ERROR = "error"
    ESCALATE = "escalate"
```

The `AgentEvent` dataclass (`events.py:137-178`) already has `to_dict()`:

```python
@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: EventType
    data: dict[str, Any]
    timestamp: float
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,  # e.g., "task_start"
            "data": self.data,
            "timestamp": self.timestamp,
        }
```

### Design Options

#### Option A: Wire JSONRenderer to agent_cmd (Recommended)

Use the existing `JSONRenderer` class (`renderer.py:339-352`) in `agent_cmd.py`:

```python
# agent_cmd.py - Change from:
if json_output:
    result = await naaru.run(...)
    event = complete_event(...)
    print(json.dumps(event.to_dict()))

# To:
if json_output:
    from sunwell.adaptive.renderer import JSONRenderer
    renderer = JSONRenderer()
    async for event in agent.run(goal, context):
        # JSONRenderer already does: print(json.dumps(event.to_dict()))
        pass  # Renderer handles output
```

**Pros:**
- Uses existing `JSONRenderer` class
- Minimal code changes
- Consistent with `create_renderer()` factory pattern

**Cons:**
- Need to refactor `agent_cmd.py` to use `AdaptiveAgent` directly (currently uses `Naaru`)

#### Option B: Add streaming callback to Naaru

Add an `on_event` callback to `Naaru.run()`:

```python
async def run(
    self,
    goal: str,
    on_progress: Callable[[str], None] | None = None,
    on_event: Callable[[AgentEvent], None] | None = None,  # NEW
    ...
) -> NaaruResult:
```

**Pros:**
- Non-breaking change to existing API
- Works with current `agent_cmd.py` structure

**Cons:**
- Callback pattern less clean than async iteration
- Need to thread callback through Naaru → execution layers

#### Option C: Dual output mode

Have `Naaru.run()` yield events when a flag is set:

```python
result = await naaru.run(
    goal=goal,
    stream_events=True,  # NEW
)
# result.events contains all events
```

**Pros:**
- Simple API change

**Cons:**
- Events buffered, not truly streaming
- Requires result object changes

### Recommended Approach: Option B

Option B (callback) provides the cleanest integration path because:
1. `agent_cmd.py` already uses `Naaru`, not `AdaptiveAgent` directly
2. Callbacks integrate naturally with the existing `on_progress` pattern
3. No need to refactor the CLI architecture

---

## Implementation

### Phase 1: Add Event Callback to Naaru

**File:** `src/sunwell/naaru/executor.py`

```python
# Add to NaaruConfig or run() signature
@dataclass
class NaaruConfig:
    # ... existing fields ...
    event_callback: Callable[[AgentEvent], None] | None = None
```

Then in execution methods, emit events:

```python
def _emit_event(self, event_type: str, **data) -> None:
    """Emit event to callback if configured."""
    if self.config.event_callback:
        from sunwell.adaptive.events import AgentEvent, EventType
        event = AgentEvent(EventType(event_type), data)
        self.config.event_callback(event)
```

### Phase 2: Wire CLI to Use Callback

**File:** `src/sunwell/cli/agent_cmd.py`

```python
# Replace lines 336-368 with:
if json_output:
    import json
    import sys
    from sunwell.adaptive.events import AgentEvent
    
    def emit_json(event: AgentEvent) -> None:
        print(json.dumps(event.to_dict()), file=sys.stdout, flush=True)
    
    naaru_config = NaaruConfig(event_callback=emit_json)
    naaru = Naaru(
        sunwell_root=Path.cwd(),
        synthesis_model=synthesis_model,
        planner=planner,
        tool_executor=tool_executor,
        config=naaru_config,
    )
    
    try:
        result = await naaru.run(
            goal=goal,
            context={"cwd": str(Path.cwd())},
            on_progress=lambda msg: None,  # Suppress console
            max_time_seconds=time,
        )
    except KeyboardInterrupt:
        emit_json(AgentEvent(EventType.ERROR, {"message": "Interrupted"}))
    except Exception as e:
        emit_json(AgentEvent(EventType.ERROR, {"message": str(e)}))
    return
```

### Phase 3: Enable Real Mode in Studio

**File:** `studio/src/stores/agent.ts`

```typescript
// Change line 17 from:
const DEMO_MODE = true;

// To:
const DEMO_MODE = false;
```

**File:** `studio/src/stores/project.ts`

```typescript
// Change line 9 from:
const DEMO_MODE = true;

// To:
const DEMO_MODE = false;
```

### Phase 4: Verify Event Schema Compatibility

The Rust `EventType` enum (`agent.rs:14-59`) must match Python's `EventType` values. Current alignment:

| Python (`events.py`) | Rust (`agent.rs`) | Svelte Handler | Status |
|---------------------|-------------------|----------------|--------|
| `plan_start` | `PlanStart` | `plan_start` | ✅ |
| `plan_winner` | `PlanWinner` | `plan_winner` | ✅ |
| `task_start` | `TaskStart` | `task_start` | ✅ |
| `task_progress` | `TaskProgress` | `task_progress` | ✅ |
| `task_complete` | `TaskComplete` | `task_complete` | ✅ |
| `task_failed` | `TaskFailed` | `task_failed` | ✅ |
| `complete` | `Complete` | `complete` | ✅ |
| `error` | `Error` | `error` | ✅ |
| `memory_learning` | `MemoryLearning` | `memory_learning` | ✅ |
| `escalate` | `Escalate` | `escalate` | ✅ |

The Rust enum uses `#[serde(rename_all = "snake_case")]` so serialization matches.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Event flood overwhelms UI | High | Throttle high-frequency events (task_progress) |
| Rust JSON parsing fails | Medium | Log unparseable lines, don't crash |
| Process hangs on Windows | Medium | Add timeout to read loop |
| stderr interleaved with stdout | Low | Rust already captures stderr separately |
| Demo mode regression | Low | Keep demo code, use feature flag |

---

## Testing Plan

### Unit Tests

```python
# tests/test_event_streaming.py

def test_json_callback_receives_events():
    """Events flow through callback."""
    received = []
    config = NaaruConfig(event_callback=received.append)
    # Run with simple goal
    assert len(received) > 0
    assert any(e.type == EventType.PLAN_START for e in received)

def test_json_output_format():
    """CLI outputs valid NDJSON."""
    result = subprocess.run(
        ["sunwell", "agent", "run", "echo hello", "--json", "--dry-run"],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().split('\n'):
        parsed = json.loads(line)  # Should not raise
        assert "type" in parsed
        assert "timestamp" in parsed
```

### Integration Tests

```bash
# Verify streaming works
sunwell agent run "create hello.py" --json 2>/dev/null | head -10

# Expected: Multiple events, not just one
# {"type":"plan_start","timestamp":...,"data":{}}
# {"type":"plan_winner","timestamp":...,"data":{"tasks":3}}
# {"type":"task_start","timestamp":...,"data":{"task_id":"1"}}
# ...
```

### E2E Tests

```typescript
// studio/tests/agent-bridge.spec.ts

test('real agent streams events', async () => {
  // Requires DEMO_MODE = false
  await runGoal('create hello.py');
  
  // Should receive multiple state updates
  await waitFor(() => get(agentState).status === 'planning');
  await waitFor(() => get(agentState).status === 'running');
  await waitFor(() => get(agentState).tasks.length > 0);
  await waitFor(() => get(agentState).status === 'done');
});
```

---

## Migration

### Enabling Real Mode

1. Verify `sunwell` CLI is in PATH
2. Set `DEMO_MODE = false` in `agent.ts` and `project.ts`
3. Test with: `sunwell agent run "echo hello" --json`

### Rollback

Set `DEMO_MODE = true` to restore simulated behavior.

### Feature Flag (Recommended)

Add environment variable for gradual rollout:

```typescript
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';
```

---

## Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Event latency | < 100ms | Time from Python print to Svelte update |
| Events per goal | 10-50 | Typical event count for simple goals |
| Error surface rate | 100% | All Python errors appear in UI |
| Memory overhead | < 5MB | Rust bridge memory usage |

---

## Implementation Checklist

### Python (`src/sunwell/`)

- [x] Add `event_callback` to `NaaruConfig`
- [x] Call callback in `_emit_event()` method
- [x] Update `agent_cmd.py` to use callback in `--json` mode
- [x] Ensure all execution paths emit events
- [ ] Add unit tests

### Studio (`studio/`)

- [x] Change `DEMO_MODE = false` in `agent.ts`
- [x] Change `DEMO_MODE = false` in `project.ts`
- [ ] Add E2E test for real agent flow
- [ ] Test error handling (agent not found, crash, etc.)

### Documentation

- [ ] Update Studio README with setup instructions
- [ ] Document event types for Studio developers

---

## References

- `src/sunwell/adaptive/events.py:23-178` — Event types and schema
- `src/sunwell/adaptive/renderer.py:339-352` — Existing JSONRenderer
- `src/sunwell/cli/agent_cmd.py:336-368` — Current JSON output (final event only)
- `studio/src-tauri/src/agent.rs:85-153` — Rust bridge (complete)
- `studio/src/stores/agent.ts:289-424` — Svelte event handlers (complete)
- [NDJSON Specification](http://ndjson.org/)
- [Tauri Event System](https://tauri.app/v1/guides/features/events/)
