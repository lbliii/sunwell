# Event Type Safety — Solution Summary

**Status**: Implemented  
**Created**: 2026-01-20

---

## Problem Solved

The UI ↔ Backend event system was brittle because:
- ❌ No type checking (ty couldn't catch errors)
- ❌ Field name mismatches (`artifact_id` vs `task_id`)
- ❌ No validation (errors only discovered at runtime in Studio)
- ❌ Manual TypeScript types (drift risk)

---

## Solution: Python Type System Integration

### 1. TypedDict Schemas ✅

**File**: `src/sunwell/adaptive/event_schema.py`

```python
class TaskStartData(TypedDict, total=False):
    """Data for task_start event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    description: str  # Required
```

**Benefits:**
- ✅ ty validates field names at development time
- ✅ IDE autocomplete for event data
- ✅ Self-documenting contracts

### 2. Runtime Validation ✅

```python
def validate_event_data(event_type: EventType, data: dict[str, Any]) -> dict[str, Any]:
    """Validate event data against schema."""
    # Normalize artifact_id → task_id
    if "artifact_id" in data and "task_id" not in data:
        data["task_id"] = data["artifact_id"]
    
    # Check required fields
    required = REQUIRED_FIELDS.get(event_type, set())
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    return data
```

**Benefits:**
- ✅ Catches errors before they reach Studio
- ✅ Automatic field name normalization
- ✅ Fail loudly instead of silently

### 3. Type-Safe Factories ✅

```python
def validated_task_start_event(
    task_id: str,
    description: str,
    artifact_id: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validated task_start event."""
    data: TaskStartData = {
        "task_id": task_id,
        "description": description,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    return create_validated_event(EventType.TASK_START, data)
```

**Benefits:**
- ✅ Type-safe at call site
- ✅ Automatic validation
- ✅ Field name normalization built-in

### 4. Event Emitter Protocol ✅

```python
@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for event emitters."""
    
    def emit(self, event: AgentEvent) -> None:
        """Emit an event."""
        ...
```

**Benefits:**
- ✅ Type checking for emitters
- ✅ Can wrap with validation
- ✅ Clear interface contract

### 5. TypeScript Type Generation ✅

**Script**: `scripts/generate_event_types.py`

```bash
python scripts/generate_event_types.py > studio/src/lib/types/events.ts
```

**Benefits:**
- ✅ Single source of truth (Python)
- ✅ No manual type maintenance
- ✅ Automatic sync

---

## Usage Examples

### Before (Brittle)

```python
# No type checking, no validation, wrong field name
emit("task_start", {"artifact_id": spec.id, "description": spec.description})
# ↑ Studio expects task_id, silently fails
```

### After (Type-Safe)

```python
from sunwell.adaptive.event_schema import validated_task_start_event

# Type-checked, validated, normalized
event = validated_task_start_event(
    task_id=spec.id,
    description=spec.description,
    artifact_id=spec.id,  # Optional alias for compatibility
)
emit_json(event)
# ↑ Always has task_id, validated, type-safe
```

### With Validation Wrapper

```python
from sunwell.adaptive.event_schema import EventEmitter, ValidatedEventEmitter

class StdoutEmitter:
    def emit(self, event: AgentEvent) -> None:
        print(json.dumps(event.to_dict()))

# Wrap with validation
emitter = ValidatedEventEmitter(StdoutEmitter(), validate=True)
emitter.emit(event)  # Validates before emitting
```

---

## Migration Guide

### Step 1: Use Validated Factories

Replace:
```python
emit("task_start", {"artifact_id": spec.id, ...})
```

With:
```python
from sunwell.adaptive.event_schema import validated_task_start_event
event = validated_task_start_event(task_id=spec.id, description=spec.description)
emit_json(event)
```

### Step 2: Wrap Event Callbacks

```python
from sunwell.adaptive.event_schema import ValidatedEventEmitter

def emit_json(event: AgentEvent) -> None:
    print(json.dumps(event.to_dict()))

# Wrap with validation
validated_emitter = ValidatedEventEmitter(
    type("Emitter", (), {"emit": emit_json})(),
    validate=True
)
naaru_config.event_callback = validated_emitter.emit
```

### Step 3: Generate TypeScript Types

```bash
# Add to CI/pre-commit
python scripts/generate_event_types.py > studio/src/lib/types/events.ts
```

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Type Checking** | ❌ None | ✅ ty validates |
| **Field Names** | ❌ Inconsistent | ✅ Normalized automatically |
| **Validation** | ❌ Runtime errors | ✅ Caught early |
| **TypeScript** | ❌ Manual | ✅ Generated |
| **IDE Support** | ❌ None | ✅ Autocomplete |
| **Documentation** | ❌ Scattered | ✅ TypedDict schemas |

---

## Next Steps

1. **Migrate incremental run** to use validated factories
2. **Add validation wrapper** to event callbacks
3. **Generate TypeScript types** and update Studio
4. **Add CI check** to regenerate types
5. **Make validation required** in JSON mode

---

## Files Created

- `src/sunwell/adaptive/event_schema.py` - Type-safe event schemas
- `scripts/generate_event_types.py` - TypeScript type generator
- `docs/EVENT-TYPE-SAFETY.md` - Full documentation
- `docs/EVENT-TYPE-SAFETY-SUMMARY.md` - This file

---

## References

- Python TypedDict: https://docs.python.org/3/library/typing.html#typing.TypedDict
- Protocol: https://docs.python.org/3/library/typing.html#typing.Protocol
- `src/sunwell/adaptive/event_schema.py` - Implementation
- `docs/EVENT-ANALYSIS.md` - Problem analysis
