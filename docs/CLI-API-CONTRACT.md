# CLI-as-API Contract System

**Status**: ✅ Implemented  
**Created**: 2026-01-20

---

## Problem

Your architecture uses **CLI-as-API** pattern:

```
Python CLI (sunwell agent run --json)
    ↓ NDJSON stdout
Rust Bridge (spawns subprocess, reads stdout)
    ↓ Tauri IPC
TypeScript Frontend (Svelte)
```

**Challenge**: How do you ensure all three layers stay aligned?

---

## Solution: Schema Contract System

### Single Source of Truth

**Python** (`src/sunwell/adaptive/event_schema.py`) defines the contract:
- `TypedDict` schemas for each event type
- Required fields validation
- Type-safe event factories

**Generated Artifacts** (auto-generated from Python):
- `schemas/agent-events.schema.json` - JSON Schema for validation
- `studio/src/lib/agent-events.ts` - TypeScript types

**Contract Tests** (`tests/test_event_schema_contract.py`):
- Validates Python events match schema
- Ensures required fields are present
- Tests JSON round-trip compatibility

---

## How It Works

### 1. Python Defines Schema

```python
# src/sunwell/adaptive/event_schema.py

class TaskStartData(TypedDict, total=False):
    task_id: str  # Required
    description: str  # Required
    artifact_id: str  # Optional (alias)

REQUIRED_FIELDS = {
    EventType.TASK_START: {"task_id", "description"},
    # ...
}
```

### 2. Generate Schemas

```bash
python scripts/generate_event_schema.py
```

**Outputs**:
- `schemas/agent-events.schema.json` - JSON Schema
- `studio/src/lib/agent-events.ts` - TypeScript types

### 3. Use in Code

**Python** (validates before emitting):
```python
from sunwell.adaptive.event_schema import validate_event_data, create_validated_event

# Validate before emitting
validated_data = validate_event_data(EventType.TASK_START, {
    "task_id": "UserModel",
    "description": "Create user model"
})
event = AgentEvent(EventType.TASK_START, validated_data)
print(json.dumps(event.to_dict()))
```

**TypeScript** (type-safe):
```typescript
import type { AgentEvent, TaskStartData } from '$lib/agent-events';

function handleEvent(event: AgentEvent) {
  if (event.type === 'task_start') {
    const data = event.data as TaskStartData;
    console.log(data.task_id);  // TypeScript knows this exists
  }
}
```

**Rust** (optional validation):
```rust
// Could add JSON Schema validation here if needed
// Currently just forwards JSON (flexible by design)
```

---

## Testing

### Run Contract Tests

```bash
pytest tests/test_event_schema_contract.py -v
```

**Tests verify**:
- ✅ All event types serialize to JSON
- ✅ Required fields are present
- ✅ Events match JSON Schema structure
- ✅ Events can be round-tripped through JSON
- ✅ Incremental execution events are compatible

### Add to CI

```yaml
# .github/workflows/test.yml
- name: Test event schema contract
  run: pytest tests/test_event_schema_contract.py
```

---

## Best Practices

### 1. **Always Validate Before Emitting**

```python
# ✅ Good
validated_data = validate_event_data(event_type, data)
event = AgentEvent(event_type, validated_data)
emit(event)

# ❌ Bad
event = AgentEvent(event_type, data)  # No validation
emit(event)
```

### 2. **Use Type-Safe Factories**

```python
# ✅ Good
from sunwell.adaptive.event_schema import validated_task_start_event
event = validated_task_start_event("UserModel", "Create user model")

# ❌ Bad
event = AgentEvent(EventType.TASK_START, {"task_id": "UserModel"})  # Missing description
```

### 3. **Regenerate After Schema Changes**

When you modify `event_schema.py`:
1. Run `python scripts/generate_event_schema.py`
2. Review generated files
3. Update TypeScript imports if needed
4. Run tests: `pytest tests/test_event_schema_contract.py`
5. Commit generated files

### 4. **Backward Compatibility**

- **Additive changes only** - New fields should be optional
- **Deprecation period** - Mark fields deprecated before removal
- **Version field** - Consider adding `version` to events for future compatibility

---

## Current Status

### ✅ Implemented
- [x] JSON Schema generation script
- [x] TypeScript type generation
- [x] Contract tests
- [x] Required fields validation

### 🔄 Optional (Future)
- [ ] Rust JSON Schema validation (currently just forwards)
- [ ] CI check for schema changes
- [ ] Schema versioning
- [ ] API documentation generation

---

## Example: Adding a New Event Type

### Step 1: Define Schema in Python

```python
# src/sunwell/adaptive/event_schema.py

class MyNewEventData(TypedDict, total=False):
    field1: str  # Required
    field2: int  # Optional

EVENT_SCHEMAS[EventType.MY_NEW_EVENT] = MyNewEventData
REQUIRED_FIELDS[EventType.MY_NEW_EVENT] = {"field1"}
```

### Step 2: Add Event Type

```python
# src/sunwell/adaptive/events.py

class EventType(Enum):
    # ... existing events ...
    MY_NEW_EVENT = "my_new_event"
```

### Step 3: Regenerate Schemas

```bash
python scripts/generate_event_schema.py
```

### Step 4: Use in Code

```python
from sunwell.adaptive.event_schema import create_validated_event

event = create_validated_event(
    EventType.MY_NEW_EVENT,
    {"field1": "value", "field2": 42}
)
```

### Step 5: Test

```bash
pytest tests/test_event_schema_contract.py -k my_new_event
```

---

## FAQ

### Q: Why not use Protocol Buffers or gRPC?

**A**: CLI-as-API is simpler - just JSON over stdout. No need for complex RPC frameworks.

### Q: What if I need to change the schema?

**A**: 
1. Make additive changes (new fields optional)
2. Regenerate schemas
3. Update TypeScript if needed
4. Test thoroughly
5. Consider versioning for breaking changes

### Q: Do I need to validate in Rust?

**A**: Optional. Currently Rust just forwards JSON (flexible). You can add JSON Schema validation if you want stricter checking.

### Q: How do I test the full pipeline?

**A**: 
```bash
# Test CLI output
sunwell agent run --json --plan "test goal" | jq .

# Test in Studio (dev mode)
cd studio && npm run tauri dev
```

---

## References

- `docs/CLI-SCHEMA-CONTRACT.md` - Detailed implementation plan
- `docs/EVENT-STANDARD.md` - Event standardization doc
- `src/sunwell/adaptive/event_schema.py` - Python schemas (source of truth)
- `schemas/agent-events.schema.json` - Generated JSON Schema
- `studio/src/lib/agent-events.ts` - Generated TypeScript types
- `tests/test_event_schema_contract.py` - Contract tests