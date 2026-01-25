#!/usr/bin/env python3
"""Demonstrate the schema contract system in action.

Shows:
1. Python event creation with validation
2. JSON serialization
3. Schema validation
4. Round-trip through JSON
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunwell.agent.events.schemas import (
    REQUIRED_FIELDS,
    create_validated_event,
    validate_event_data,
)
from sunwell.agent.events import AgentEvent, EventType


def main() -> None:
    """Demonstrate schema contract."""
    print("🔍 Schema Contract System Demo\n")
    print("=" * 60)

    # 1. Create validated event
    print("\n1️⃣ Creating validated event (Python):")
    print("-" * 60)
    event = create_validated_event(
        EventType.TASK_START,
        {"task_id": "UserModel", "description": "Create user model"},
    )
    print(f"✅ Event created: {event.type.value}")
    print(f"   Data: {event.data}")

    # 2. Serialize to JSON
    print("\n2️⃣ Serializing to JSON:")
    print("-" * 60)
    event_dict = event.to_dict()
    json_str = json.dumps(event_dict, indent=2)
    print(json_str)

    # 3. Validate against schema
    print("\n3️⃣ Validating required fields:")
    print("-" * 60)
    required = REQUIRED_FIELDS.get(EventType.TASK_START, set())
    print(f"Required fields for {EventType.TASK_START.value}: {required}")
    for field in required:
        if field in event.data:
            print(f"  ✅ {field}: {event.data[field]}")
        else:
            print(f"  ❌ {field}: MISSING")

    # 4. Round-trip test
    print("\n4️⃣ Round-trip through JSON:")
    print("-" * 60)
    parsed = json.loads(json_str)
    reconstructed = AgentEvent.from_dict(parsed)
    print(f"✅ Original type: {event.type.value}")
    print(f"✅ Reconstructed type: {reconstructed.type.value}")
    print(f"✅ Types match: {event.type == reconstructed.type}")
    print(f"✅ Data matches: {event.data == reconstructed.data}")

    # 5. Show all event types
    print("\n5️⃣ All event types in schema:")
    print("-" * 60)
    print(f"Total event types: {len(EventType)}")
    print("\nEvent types with required fields:")
    for event_type, required in sorted(REQUIRED_FIELDS.items(), key=lambda x: x[0].value):
        print(f"  • {event_type.value:25} → {required}")

    # 6. Show schema files
    print("\n6️⃣ Generated schema files:")
    print("-" * 60)
    root = Path(__file__).parent.parent
    schema_path = root / "schemas" / "agent-events.schema.json"
    ts_path = root / "studio" / "src" / "lib" / "agent-events.ts"

    if schema_path.exists():
        schema_size = len(schema_path.read_text())
        print(f"✅ JSON Schema: {schema_path} ({schema_size:,} bytes)")
    else:
        print(f"❌ JSON Schema: {schema_path} (not found)")

    if ts_path.exists():
        ts_size = len(ts_path.read_text())
        print(f"✅ TypeScript types: {ts_path} ({ts_size:,} bytes)")
    else:
        print(f"❌ TypeScript types: {ts_path} (not found)")

    # 7. Validation error example
    print("\n7️⃣ Validation error example:")
    print("-" * 60)
    try:
        # Missing required field
        validate_event_data(EventType.TASK_START, {"task_id": "test"})
        print("❌ Should have failed (missing 'description')")
    except ValueError as e:
        print(f"✅ Validation correctly caught error: {e}")

    print("\n" + "=" * 60)
    print("✅ Schema contract system working correctly!")
    print("\nNext steps:")
    print("  1. Run: python scripts/generate_event_schema.py")
    print("  2. Use generated types in TypeScript")
    print("  3. Add Rust validation (optional)")
    print("  4. Run tests: pytest tests/test_event_schema_contract.py")


if __name__ == "__main__":
    main()