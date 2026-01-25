#!/usr/bin/env python3
"""Generate JSON Schema and TypeScript types from Python event schemas.

This script ensures the CLI JSON output contract is maintained across:
- Python (source of truth)
- TypeScript (frontend)
- Rust (bridge)

Run this script whenever event_schema.py changes.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunwell.agent.events.schemas import EVENT_SCHEMAS, REQUIRED_FIELDS
from sunwell.agent.events import EventType


def infer_json_schema_type(python_type: type | str) -> dict[str, Any]:
    """Infer JSON Schema type from Python type annotation."""
    # Handle string representation of types
    type_str = str(python_type)
    
    # Handle union types (e.g., str | None, int | None)
    if "|" in type_str or "Union" in type_str:
        # Extract non-None types
        if "None" in type_str:
            # Optional field - extract the actual type
            parts = type_str.split("|")
            non_none_parts = [p.strip() for p in parts if "None" not in p]
            if non_none_parts:
                # Recursively infer from the non-None type
                return infer_json_schema_type(non_none_parts[0])
        else:
            # Multiple types - use first non-None
            parts = type_str.split("|")
            return infer_json_schema_type(parts[0].strip())
    
    # Handle generic types (e.g., dict[str, Any], list[str])
    if "dict" in type_str.lower() or "Dict" in type_str:
        return {"type": "object", "additionalProperties": True}
    if "list" in type_str.lower() or "List" in type_str:
        return {"type": "array", "items": {}}
    
    # Handle basic types
    if python_type == str or type_str == "str" or "<class 'str'>" in type_str:
        return {"type": "string"}
    elif python_type == int or type_str == "int" or "<class 'int'>" in type_str:
        return {"type": "integer"}
    elif python_type == float or type_str == "float" or "<class 'float'>" in type_str:
        return {"type": "number"}
    elif python_type == bool or type_str == "bool" or "<class 'bool'>" in type_str:
        return {"type": "boolean"}
    elif python_type == dict or type_str == "dict":
        return {"type": "object", "additionalProperties": True}
    elif python_type == list or type_str == "list":
        return {"type": "array", "items": {}}
    else:
        # Default to any (empty schema allows anything)
        return {}


def infer_typescript_type(python_type: type | str) -> str:
    """Infer TypeScript type from Python type annotation."""
    # Handle string representation of types
    type_str = str(python_type)
    
    # Handle union types (e.g., str | None, int | None)
    if "|" in type_str or "Union" in type_str:
        # Extract non-None types
        if "None" in type_str:
            # Optional field - extract the actual type and make it optional
            parts = type_str.split("|")
            non_none_parts = [p.strip() for p in parts if "None" not in p]
            if non_none_parts:
                # Recursively infer from the non-None type
                return infer_typescript_type(non_none_parts[0])
        else:
            # Multiple types - create union
            parts = type_str.split("|")
            ts_parts = [infer_typescript_type(p.strip()) for p in parts]
            return " | ".join(ts_parts)
    
    # Handle generic types (e.g., dict[str, Any], list[str])
    if "dict" in type_str.lower() or "Dict" in type_str:
        return "Record<string, unknown>"
    if "list" in type_str.lower() or "List" in type_str:
        return "unknown[]"
    
    # Handle basic types
    if python_type == str or type_str == "str" or "<class 'str'>" in type_str:
        return "string"
    elif python_type == int or type_str == "int" or "<class 'int'>" in type_str:
        return "number"
    elif python_type == float or type_str == "float" or "<class 'float'>" in type_str:
        return "number"
    elif python_type == bool or type_str == "bool" or "<class 'bool'>" in type_str:
        return "boolean"
    elif python_type == dict or type_str == "dict":
        return "Record<string, unknown>"
    elif python_type == list or type_str == "list":
        return "unknown[]"
    else:
        return "unknown"


def generate_json_schema() -> dict[str, Any]:
    """Generate JSON Schema for all event types."""
    schema = {
        "$schema": "http://json-schema.org/draft-2020-12/schema",
        "$id": "https://sunwell.ai/schemas/agent-events.json",
        "title": "Sunwell Agent Events",
        "description": "Schema for NDJSON events emitted by Sunwell CLI",
        "type": "object",
        "oneOf": [],
    }

    for event_type in EventType:
        # Get schema for this event type if it exists
        typed_dict = EVENT_SCHEMAS.get(event_type)
        required_fields = REQUIRED_FIELDS.get(event_type, set())

        # Build data schema
        data_properties: dict[str, Any] = {}
        data_required: list[str] = list(required_fields)

        # Try to introspect TypedDict if available
        if typed_dict and hasattr(typed_dict, "__annotations__"):
            annotations = typed_dict.__annotations__
            for field_name, field_type in annotations.items():
                # Handle ForwardRef (from __future__ import annotations)
                # Check both typing.ForwardRef and annotationlib.ForwardRef
                if hasattr(field_type, "__forward_arg__"):
                    # Extract the string representation
                    type_str = field_type.__forward_arg__
                    data_properties[field_name] = infer_json_schema_type(type_str)
                elif hasattr(field_type, "__forward_value__"):
                    # Alternative ForwardRef interface
                    type_str = str(field_type.__forward_value__)
                    data_properties[field_name] = infer_json_schema_type(type_str)
                elif str(type(field_type).__name__) == "ForwardRef":
                    # Fallback: convert to string and parse
                    type_str = str(field_type)
                    # Extract the argument from ForwardRef('str | None')
                    if "ForwardRef(" in type_str:
                        import re
                        match = re.search(r"ForwardRef\('([^']+)'", type_str)
                        if match:
                            type_str = match.group(1)
                    data_properties[field_name] = infer_json_schema_type(type_str)
                else:
                    data_properties[field_name] = infer_json_schema_type(field_type)

        # If no TypedDict, infer from required fields (fallback)
        if not data_properties and required_fields:
            for field in required_fields:
                # Default to string for unknown types
                data_properties[field] = {"type": "string"}

        event_schema = {
            "type": "object",
            "properties": {
                "type": {
                    "const": event_type.value,
                    "description": f"Event type: {event_type.value}",
                },
                "data": {
                    "type": "object",
                    "properties": data_properties,
                    "required": data_required if data_required else None,
                    "additionalProperties": True,  # Allow extra fields for flexibility
                },
                "timestamp": {
                    "type": "number",
                    "description": "Unix timestamp (seconds since epoch)",
                },
            },
            "required": ["type", "data", "timestamp"],
        }

        # Remove None values
        if event_schema["properties"]["data"]["required"] is None:
            del event_schema["properties"]["data"]["required"]

        schema["oneOf"].append(event_schema)

    return schema


def generate_typescript_types() -> str:
    """Generate TypeScript type definitions."""
    lines = [
        "// Auto-generated from Python event schemas",
        "// DO NOT EDIT MANUALLY - Run: python scripts/generate_event_schema.py",
        "",
        "// ═══════════════════════════════════════════════════════════════",
        "// EVENT TYPE UNION",
        "// ═══════════════════════════════════════════════════════════════",
        "",
        "export type AgentEventType =",
    ]

    # Event type union
    event_types = [f"  | '{et.value}'" for et in EventType]
    lines.extend(event_types)
    lines.append(";")
    lines.append("")
    lines.append("// ═══════════════════════════════════════════════════════════════")
    lines.append("// BASE EVENT INTERFACE")
    lines.append("// ═══════════════════════════════════════════════════════════════")
    lines.append("")
    lines.extend(
        [
            "export interface AgentEvent {",
            "  type: AgentEventType;",
            "  data: Record<string, unknown>;",
            "  timestamp: number;",
            "}",
            "",
        ]
    )

    # Event-specific data types
    lines.append("// ═══════════════════════════════════════════════════════════════")
    lines.append("// EVENT DATA TYPES")
    lines.append("// ═══════════════════════════════════════════════════════════════")
    lines.append("")

    for event_type, typed_dict in EVENT_SCHEMAS.items():
        type_name = f"{event_type.name.title().replace('_', '')}Data"
        required_fields = REQUIRED_FIELDS.get(event_type, set())

        lines.append(f"export interface {type_name} {{")

        # Try to get annotations from TypedDict
        if typed_dict and hasattr(typed_dict, "__annotations__"):
            annotations = typed_dict.__annotations__
            for field_name, field_type in annotations.items():
                is_required = field_name in required_fields
                # Handle ForwardRef (from __future__ import annotations)
                if hasattr(field_type, "__forward_arg__"):
                    type_str = field_type.__forward_arg__
                    ts_type = infer_typescript_type(type_str)
                else:
                    ts_type = infer_typescript_type(field_type)
                if is_required:
                    lines.append(f"  {field_name}: {ts_type};")
                else:
                    lines.append(f"  {field_name}?: {ts_type};")
        else:
            # Fallback: just list required fields
            for field in required_fields:
                lines.append(f"  {field}: string;  // Type inferred from required field")

        lines.append("}")
        lines.append("")

    # Union type for all event data
    lines.append("// ═══════════════════════════════════════════════════════════════")
    lines.append("// EVENT DATA UNION")
    lines.append("// ═══════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("export type EventData =")

    data_types = [
        f"{et.name.title().replace('_', '')}Data"
        for et in EVENT_SCHEMAS.keys()
    ]
    for dt in data_types:
        lines.append(f"  | {dt}")

    lines.append("  | Record<string, unknown>;  // Fallback for unknown events")

    return "\n".join(lines)


def main() -> None:
    """Generate both JSON Schema and TypeScript types."""
    root = Path(__file__).parent.parent

    # Generate JSON Schema
    schema = generate_json_schema()
    schema_path = root / "schemas" / "agent-events.schema.json"
    schema_path.parent.mkdir(exist_ok=True)
    schema_path.write_text(json.dumps(schema, indent=2))
    print(f"✅ Generated JSON Schema: {schema_path}")

    # Generate TypeScript types
    ts_code = generate_typescript_types()
    ts_path = root / "studio" / "src" / "lib" / "agent-events.ts"
    ts_path.parent.mkdir(exist_ok=True)
    ts_path.write_text(ts_code)
    print(f"✅ Generated TypeScript types: {ts_path}")

    print("\n📝 Next steps:")
    print("  1. Review generated files")
    print("  2. Update imports in studio/src/stores/agent.ts")
    print("  3. Add schema validation to Rust bridge (optional)")
    print("  4. Commit generated files to git")


if __name__ == "__main__":
    main()