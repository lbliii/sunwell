# Event Standardization — UI ↔ Backend Communication

**Status**: Needs Standardization  
**Created**: 2026-01-20  
**Issue**: UI ↔ Backend communication is brittle, events not consistently emitted

---

## Problem

The Studio UI and Python backend communicate via NDJSON events, but:

1. **Inconsistent emission**: Some code paths emit events, others don't
2. **Missing events**: HarmonicPlanner has its own event system that may not be wired
3. **Format drift**: Events might not match what Studio expects
4. **No validation**: No schema validation or type checking

---

## Current Event Flow

```
Python Agent
    ↓
AgentEvent.to_dict() → {"type": "event_type", "data": {...}, "timestamp": ...}
    ↓
stdout (NDJSON)
    ↓
Rust Bridge (agent.rs)
    ↓
Tauri Event System
    ↓
Svelte Store (agent.ts)
```

---

## Event Format Standard

### Python → JSON

```python
# src/sunwell/adaptive/events.py
@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,  # e.g., "plan_start"
            "data": self.data,
            "timestamp": self.timestamp,
        }
```

### Rust → TypeScript

```rust
// studio/src-tauri/src/agent.rs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    pub data: serde_json::Value,
    pub timestamp: f64,
}
```

```typescript
// studio/src/stores/agent.ts
interface AgentEvent {
  type: string;
  data: Record<string, any>;
  timestamp?: number;
}
```

---

## Required Events for Studio

### Planning Phase
- `plan_start` - Planning begins
- `plan_winner` - Best plan selected (must include `tasks` count)
- `plan_candidate_*` - Harmonic planning visibility (RFC-058)

### Execution Phase
- `task_start` - Task begins (must include `task_id` and `description`)
- `task_progress` - Progress update (must include `task_id` and `progress`)
- `task_complete` - Task done (must include `task_id` and `duration_ms`)
- `task_failed` - Task failed (must include `task_id` and `error`)

### Memory/Learning
- `memory_learning` - New learning extracted (must include `fact`)

### Completion
- `complete` - All done
- `error` - Fatal error (must include `message`)

---

## Issues Found

### 1. HarmonicPlanner Events Not Wired

HarmonicPlanner has `_emit_event()` but callback may not be set:

```python
# src/sunwell/naaru/planners/harmonic.py:239
def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
    """Emit event via callback if configured."""
    if self.event_callback:
        # ... emits events
```

**Fix**: Pass event callback from Naaru config to HarmonicPlanner.

### 2. Incremental Execution Events Missing

`_incremental_run()` emits custom events that may not match standard format:

```python
# src/sunwell/cli/agent/run.py:608
def emit(event_type: str, data: dict | None = None) -> None:
    """Emit event as console or JSON."""
    if json_output:
        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": time.time(),
        }
        print(json.dumps(event), file=sys.stdout, flush=True)
```

**Fix**: Use `AgentEvent` instead of custom dict.

### 3. Naaru Events May Not Flow Through

`Naaru._emit_event()` requires `config.event_callback`:

```python
# src/sunwell/naaru/naaru.py:191
def _emit_event(self, event_type: str, **data: Any) -> None:
    if self.config.event_callback is None:
        return  # ← Silent failure!
```

**Fix**: Ensure callback is always set in JSON mode.

---

## Standardization Plan

### Phase 1: Event Schema Validation

1. Create `EventSchema` class to validate events
2. Add runtime checks in `emit_json()`
3. Add TypeScript types for all events

### Phase 2: Unified Event Emission

1. All code paths use `AgentEvent` class
2. Remove custom `emit()` functions
3. Wire HarmonicPlanner events through Naaru callback

### Phase 3: Event Testing

1. Test that all required events are emitted
2. Test event format matches schema
3. Test Studio can parse all events

---

## Quick Fixes Needed

1. ✅ **Wire HarmonicPlanner events**: Pass `event_callback` from Naaru config
2. ✅ **Standardize incremental events**: Use `AgentEvent` in `_incremental_run()`
3. ✅ **Ensure callback always set**: Fail loudly if missing in JSON mode
4. ✅ **Add event validation**: Check required fields before emitting

---

## References

- `src/sunwell/adaptive/events.py` - Event definitions
- `src/sunwell/cli/agent/run.py` - Event emission
- `studio/src-tauri/src/agent.rs` - Rust bridge
- `studio/src/stores/agent.ts` - Svelte handlers
- RFC-053: Studio Agent Bridge
- RFC-058: Planning Visibility
