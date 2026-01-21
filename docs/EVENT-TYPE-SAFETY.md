# Event Type Safety — Python Type System Integration

**Status**: Proposed  
**Created**: 2026-01-20  
**Goal**: Use Python's type system (Protocols, TypedDict, dataclasses) to enforce event contracts

---

## Problem

Current event system is brittle:
- No type checking for event data
- Field name mismatches (`artifact_id` vs `task_id`)
- No validation of required fields
- TypeScript types manually maintained (drift risk)

---

## Solution: Type-Safe Event System

### 1. TypedDict Schemas

Define contracts for each event type's data:

```python
# src/sunwell/adaptive/event_schema.py

class TaskStartData(TypedDict, total=False):
    """Data for task_start event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    description: str  # Required
```

**Benefits:**
- Type checkers (ty) validate field names
- IDE autocomplete for event data
- Self-documenting contracts

### 2. Runtime Validation

Validate events before emission:

```python
def validate_event_data(event_type: EventType, data: dict[str, Any]) -> dict[str, Any]:
    """Validate event data against schema."""
    # Check required fields
    required = REQUIRED_FIELDS.get(event_type, set())
    missing = required - set(data.keys())
    
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    # Normalize field names (artifact_id → task_id)
    if "artifact_id" in data and "task_id" not in data:
        data["task_id"] = data["artifact_id"]
    
    return data
```

**Benefits:**
- Catch errors at runtime
- Normalize field names automatically
- Fail loudly instead of silently

### 3. Type-Safe Factories

Provide validated event factories:

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
- Type-safe at call site
- Automatic validation
- Field name normalization

### 4. Event Emitter Protocol

Define contract for event emitters:

```python
@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for event emitters."""
    
    def emit(self, event: AgentEvent) -> None:
        """Emit an event."""
        ...
```

**Benefits:**
- Type checking for emitters
- Can wrap with validation
- Clear interface contract

### 5. TypeScript Type Generation

Generate TypeScript types from Python:

```python
def generate_typescript_types() -> str:
    """Generate TypeScript type definitions from Python schemas."""
    # ... generates TypeScript interfaces
```

**Benefits:**
- Single source of truth (Python)
- No manual type maintenance
- Automatic sync

---

## Migration Path

### Phase 1: Add Schemas (Non-Breaking)

1. Create `event_schema.py` with TypedDict schemas
2. Add validation functions
3. Keep existing code working

### Phase 2: Migrate to Validated Factories

1. Update `_incremental_run()` to use `validated_task_start_event()`
2. Update `Naaru.run()` to use validated factories
3. Add validation wrapper for event callbacks

### Phase 3: Generate TypeScript Types

1. Add script to generate TypeScript types
2. Update Studio to use generated types
3. Add CI check to regenerate types

### Phase 4: Strict Mode

1. Make validation required in JSON mode
2. Add ty checks for event data
3. Remove unvalidated event creation

---

## Usage Examples

### Before (Brittle)

```python
# No type checking, no validation
emit("task_start", {"artifact_id": spec.id, "description": spec.description})
# ↑ Studio expects task_id, not artifact_id
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

### With Protocol

```python
from sunwell.adaptive.event_schema import EventEmitter, ValidatedEventEmitter

class MyEmitter:
    def emit(self, event: AgentEvent) -> None:
        print(json.dumps(event.to_dict()))

# Wrap with validation
emitter = ValidatedEventEmitter(MyEmitter(), validate=True)
emitter.emit(event)  # Validates before emitting
```

---

## Benefits

1. **Type Safety**: ty catches errors at development time
2. **Runtime Validation**: Catch errors before they reach Studio
3. **Field Normalization**: Automatic `artifact_id` → `task_id` mapping
4. **Self-Documenting**: TypedDict schemas document contracts
5. **TypeScript Sync**: Generated types stay in sync
6. **IDE Support**: Autocomplete for event data fields

---

## Implementation Status

- [x] TypedDict schemas defined
- [x] Validation functions implemented
- [x] Type-safe factories created
- [x] EventEmitter protocol defined
- [x] TypeScript type generator implemented
- [ ] Migrate existing code to use validated factories
- [ ] Add CI check for type generation
- [ ] Update Studio to use generated types
- [ ] Make validation required in JSON mode

---

## References

- `src/sunwell/adaptive/event_schema.py` - Type-safe event schemas
- `src/sunwell/adaptive/events.py` - Event definitions
- `docs/EVENT-ANALYSIS.md` - Current state analysis
- `docs/EVENT-STANDARD.md` - Standardization plan
