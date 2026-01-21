# CLI Schema Contract System

**Goal**: Ensure Python CLI ↔ Rust Bridge ↔ TypeScript Frontend stay aligned

**Architecture**: CLI-as-API pattern where JSON output is the contract

---

## Current State

### ✅ What Works
- Python has `AgentEvent` class with `to_dict()` serialization
- Python has `event_schema.py` with TypedDict validation
- TypeScript has manually-maintained types in `types.ts`
- Rust uses flexible `serde_json::Value` (forwards everything)

### ⚠️ What's Missing
- **No single source of truth** - Types defined in 3 places
- **No schema validation** in Rust (just forwards JSON)
- **No contract testing** - Changes can break silently
- **No CI checks** - Schema drift goes undetected

---

## Solution: JSON Schema as Single Source of Truth

### Architecture

```
┌─────────────────────────────────────────┐
│   Python (Source of Truth)              │
│   - event_schema.py (TypedDict)         │
│   - Generates JSON Schema               │
└──────────────┬──────────────────────────┘
               │ JSON Schema
               ▼
┌─────────────────────────────────────────┐
│   Generated Artifacts                   │
│   - agent-events.schema.json            │
│   - studio/src/lib/agent-events.ts      │
│   - studio/src-tauri/src/events.rs      │
└─────────────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌─────────────┐
│ TypeScript  │  │    Rust     │
│ (validated) │  │ (validated) │
└─────────────┘  └─────────────┘
```

---

## Implementation Plan

### Phase 1: JSON Schema Generation

**Create**: `scripts/generate-event-schema.py`

```python
"""Generate JSON Schema from Python event schemas."""

import json
from pathlib import Path
from sunwell.adaptive.event_schema import EVENT_SCHEMAS, REQUIRED_FIELDS, EventType

def generate_json_schema() -> dict:
    """Generate JSON Schema for all event types."""
    schema = {
        "$schema": "http://json-schema.org/draft-2020-12/schema",
        "title": "Sunwell Agent Events",
        "type": "object",
        "oneOf": []
    }
    
    for event_type, typed_dict in EVENT_SCHEMAS.items():
        # Convert TypedDict to JSON Schema
        event_schema = {
            "type": "object",
            "properties": {
                "type": {
                    "const": event_type.value,
                    "description": f"Event type: {event_type.value}"
                },
                "data": {
                    "type": "object",
                    "properties": {},
                    "required": list(REQUIRED_FIELDS.get(event_type, set()))
                },
                "timestamp": {
                    "type": "number",
                    "description": "Unix timestamp"
                }
            },
            "required": ["type", "data", "timestamp"]
        }
        
        # Add data properties from TypedDict annotations
        # (This would introspect TypedDict __annotations__)
        
        schema["oneOf"].append(event_schema)
    
    return schema

if __name__ == "__main__":
    schema = generate_json_schema()
    output_path = Path(__file__).parent.parent / "schemas" / "agent-events.schema.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"✅ Generated JSON Schema: {output_path}")
```

**Output**: `schemas/agent-events.schema.json`

---

### Phase 2: TypeScript Type Generation

**Create**: `scripts/generate-typescript-types.py`

```python
"""Generate TypeScript types from JSON Schema."""

import json
from pathlib import Path
from sunwell.adaptive.event_schema import EVENT_SCHEMAS, REQUIRED_FIELDS, EventType

def generate_typescript() -> str:
    """Generate TypeScript type definitions."""
    lines = [
        "// Auto-generated from Python event schemas",
        "// DO NOT EDIT MANUALLY - Run: python scripts/generate-typescript-types.py",
        "",
        "export type AgentEventType =",
    ]
    
    # Event type union
    event_types = [f"  | '{et.value}'" for et in EventType]
    lines.extend(event_types)
    lines.append(";")
    lines.append("")
    
    # Base event interface
    lines.extend([
        "export interface AgentEvent {",
        "  type: AgentEventType;",
        "  data: Record<string, unknown>;",
        "  timestamp: number;",
        "}",
        "",
    ])
    
    # Event-specific data types
    for event_type, typed_dict in EVENT_SCHEMAS.items():
        type_name = f"{event_type.name.title().replace('_', '')}Data"
        lines.append(f"export interface {type_name} {{")
        
        # Add required fields
        required = REQUIRED_FIELDS.get(event_type, set())
        for field in required:
            lines.append(f"  {field}: {infer_ts_type(field, event_type)};")
        
        # Add optional fields (would need TypedDict introspection)
        lines.append("}")
        lines.append("")
    
    return "\n".join(lines)

if __name__ == "__main__":
    ts_code = generate_typescript()
    output_path = Path(__file__).parent.parent / "studio" / "src" / "lib" / "agent-events.ts"
    output_path.write_text(ts_code)
    print(f"✅ Generated TypeScript types: {output_path}")
```

**Output**: `studio/src/lib/agent-events.ts`

---

### Phase 3: Rust Schema Validation

**Update**: `studio/src-tauri/src/agent.rs`

```rust
// Add JSON Schema validation using jsonschema crate

use jsonschema::{JSONSchema, Draft};
use serde_json::Value;

lazy_static! {
    static ref EVENT_SCHEMA: JSONSchema = {
        let schema_str = include_str!("../../schemas/agent-events.schema.json");
        let schema: Value = serde_json::from_str(schema_str).unwrap();
        JSONSchema::options()
            .with_draft(Draft::Draft202012)
            .compile(&schema)
            .unwrap()
    };
}

impl AgentBridge {
    fn validate_event(&self, event: &Value) -> Result<(), String> {
        EVENT_SCHEMA
            .validate(event)
            .map_err(|errors| {
                errors
                    .map(|e| format!("{}: {}", e.instance_path, e))
                    .collect::<Vec<_>>()
                    .join(", ")
            })?;
        Ok(())
    }
    
    pub fn run_goal(...) -> Result<(), String> {
        // ... existing code ...
        
        for line in reader.lines() {
            let line = line?;
            let event: Value = serde_json::from_str(&line)
                .map_err(|e| format!("Invalid JSON: {}", e))?;
            
            // Validate against schema
            self.validate_event(&event)
                .map_err(|e| format!("Schema validation failed: {}", e))?;
            
            // Forward to frontend
            app.emit("agent-event", &event)?;
        }
    }
}
```

**Add to Cargo.toml**:
```toml
[dependencies]
jsonschema = "0.18"
lazy_static = "1.4"
```

---

### Phase 4: Contract Testing

**Create**: `tests/test_event_contract.py`

```python
"""Test that Python events match JSON Schema."""

import json
from pathlib import Path
from sunwell.adaptive.events import AgentEvent, EventType
from sunwell.adaptive.event_schema import validate_event_data

def test_all_event_types_match_schema():
    """Test that all event types can be validated."""
    schema_path = Path(__file__).parent.parent / "schemas" / "agent-events.schema.json"
    schema = json.loads(schema_path.read_text())
    
    # Test each event type
    for event_type in EventType:
        # Create minimal valid event
        data = {}
        validated_data = validate_event_data(event_type, data)
        event = AgentEvent(event_type, validated_data)
        
        # Serialize to JSON
        event_json = json.dumps(event.to_dict())
        event_dict = json.loads(event_json)
        
        # Validate against schema (would use jsonschema library)
        # assert validate_against_schema(event_dict, schema)
```

**Create**: `tests/test_typescript_compatibility.py`

```python
"""Test that Python events can be parsed by TypeScript types."""

import json
import subprocess
from pathlib import Path

def test_typescript_parsing():
    """Generate sample events and verify TypeScript can parse them."""
    # Generate sample events from Python
    events = [
        {"type": "task_start", "data": {"task_id": "test", "description": "test"}, "timestamp": 1234.5},
        {"type": "task_complete", "data": {"task_id": "test", "duration_ms": 100}, "timestamp": 1234.5},
    ]
    
    # Write to temp file
    events_file = Path("/tmp/test-events.json")
    events_file.write_text(json.dumps(events))
    
    # Run TypeScript validator
    result = subprocess.run(
        ["npx", "tsc", "--noEmit", "--strict", "test-event-parser.ts"],
        cwd=Path(__file__).parent,
        capture_output=True,
    )
    
    assert result.returncode == 0, f"TypeScript validation failed: {result.stderr}"
```

---

### Phase 5: CI Schema Checks

**Create**: `.github/workflows/schema-check.yml`

```yaml
name: Schema Contract Check

on:
  pull_request:
    paths:
      - 'src/sunwell/adaptive/event_schema.py'
      - 'src/sunwell/adaptive/events.py'
      - 'schemas/**'
      - 'studio/src/lib/**'

jobs:
  check-schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      
      - name: Generate schemas
        run: |
          python scripts/generate-event-schema.py
          python scripts/generate-typescript-types.py
      
      - name: Check for changes
        run: |
          git diff --exit-code schemas/ || {
            echo "❌ Schema files changed - commit generated files"
            exit 1
          }
          git diff --exit-code studio/src/lib/agent-events.ts || {
            echo "❌ TypeScript types changed - commit generated files"
            exit 1
          }
      
      - name: Validate Python events
        run: pytest tests/test_event_contract.py
      
      - name: Validate TypeScript types
        run: |
          cd studio
          npm install
          npm run check
```

---

## Best Practices for CLI-as-API

### 1. **Version Your Schema**

Add version to schema:

```python
# event_schema.py
SCHEMA_VERSION = "1.0.0"

def to_dict(self) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,  # ← Add version
        "type": self.type.value,
        "data": self.data,
        "timestamp": self.timestamp,
    }
```

### 2. **Backward Compatibility**

- **Additive changes only** - New fields optional
- **Deprecation period** - Mark fields deprecated before removal
- **Version negotiation** - Frontend can request specific schema version

### 3. **Error Handling**

```python
# Python: Validate before emitting
try:
    validated_data = validate_event_data(event_type, data)
    event = AgentEvent(event_type, validated_data)
    emit(event)
except ValueError as e:
    # Log error, emit error event instead
    emit(AgentEvent(EventType.ERROR, {"message": f"Invalid event: {e}"}))
```

```rust
// Rust: Validate before forwarding
match validate_event(&event) {
    Ok(_) => app.emit("agent-event", &event)?,
    Err(e) => {
        eprintln!("Schema validation failed: {}", e);
        // Emit error event to frontend
        app.emit("agent-error", json!({"message": e}))?;
    }
}
```

### 4. **Testing Strategy**

```python
# tests/test_cli_output.py

def test_cli_json_output():
    """Test that CLI outputs valid JSON events."""
    result = subprocess.run(
        ["sunwell", "agent", "run", "--json", "--plan", "test goal"],
        capture_output=True,
        text=True,
    )
    
    # Parse NDJSON
    events = []
    for line in result.stdout.strip().split("\n"):
        if line:
            event = json.loads(line)
            events.append(event)
    
    # Validate each event
    for event in events:
        assert "type" in event
        assert "data" in event
        assert "timestamp" in event
        assert event["type"] in [et.value for et in EventType]
```

### 5. **Documentation**

Generate API docs from schema:

```python
def generate_event_docs() -> str:
    """Generate markdown docs from event schemas."""
    docs = ["# Agent Events API", ""]
    
    for event_type in EventType:
        docs.append(f"## {event_type.value}")
        docs.append("")
        docs.append(f"**Type**: `{event_type.value}`")
        docs.append("")
        
        required = REQUIRED_FIELDS.get(event_type, set())
        if required:
            docs.append("**Required fields:**")
            for field in required:
                docs.append(f"- `{field}`")
            docs.append("")
        
        docs.append("**Example:**")
        docs.append("```json")
        # Generate example
        docs.append("```")
        docs.append("")
    
    return "\n".join(docs)
```

---

## Migration Path

### Step 1: Generate Schemas (Week 1)
- ✅ Create `scripts/generate-event-schema.py`
- ✅ Generate `schemas/agent-events.schema.json`
- ✅ Add to git (committed, not generated)

### Step 2: TypeScript Types (Week 1)
- ✅ Create `scripts/generate-typescript-types.py`
- ✅ Generate `studio/src/lib/agent-events.ts`
- ✅ Update imports in `agent.ts`

### Step 3: Rust Validation (Week 2)
- ✅ Add `jsonschema` crate
- ✅ Add validation in `agent.rs`
- ✅ Test with invalid events

### Step 4: Contract Tests (Week 2)
- ✅ Add `tests/test_event_contract.py`
- ✅ Add `tests/test_typescript_compatibility.py`
- ✅ Run in CI

### Step 5: CI Checks (Week 3)
- ✅ Add `.github/workflows/schema-check.yml`
- ✅ Require schema checks on PRs
- ✅ Document in CONTRIBUTING.md

---

## Benefits

1. **Single Source of Truth** - Python defines schema, everything else generated
2. **Type Safety** - TypeScript and Rust validate at runtime
3. **Early Detection** - CI catches schema drift before merge
4. **Documentation** - Schema serves as API docs
5. **Confidence** - Changes are validated automatically

---

## References

- [JSON Schema](https://json-schema.org/)
- [TypeScript JSON Schema](https://github.com/YousefED/typescript-json-schema)
- [Rust jsonschema](https://docs.rs/jsonschema/)
- RFC-053: Studio Agent Bridge
- EVENT-STANDARD.md: Current event standardization doc