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


def generate_api_types() -> str:
    """Generate TypeScript types from CamelModel response classes."""
    import types
    from typing import Literal, Union, get_args, get_origin

    from pydantic import BaseModel

    from sunwell.interface.server.routes.models import CamelModel

    # Import all response models
    import sunwell.interface.server.routes.models as models_module

    # Build set of known CamelModel class names for reference
    known_models = {
        name for name in dir(models_module)
        if isinstance(getattr(models_module, name), type)
        and issubclass(getattr(models_module, name), CamelModel)
        and name != "CamelModel"
    }

    def to_camel(name: str) -> str:
        """Convert snake_case to camelCase."""
        parts = name.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    def python_type_to_ts(python_type: type | str) -> str:
        """Convert Python type annotation to TypeScript type."""
        # Handle None
        if python_type is type(None):
            return "null"

        # Get origin and args for generic types
        origin = get_origin(python_type)
        args = get_args(python_type)

        # Handle Literal types
        if origin is Literal:
            return " | ".join(f"'{a}'" if isinstance(a, str) else str(a) for a in args)

        # Handle Union types (X | Y or Optional[X])
        if origin is Union or origin is types.UnionType:
            ts_parts = [python_type_to_ts(arg) for arg in args]
            return " | ".join(ts_parts)

        # Handle list types
        if origin is list:
            if args:
                inner_type = python_type_to_ts(args[0])
                return f"{inner_type}[]"
            return "unknown[]"

        # Handle dict types
        if origin is dict:
            if len(args) >= 2:
                key_type = python_type_to_ts(args[0])
                val_type = python_type_to_ts(args[1])
                return f"Record<{key_type}, {val_type}>"
            return "Record<string, unknown>"

        # Handle basic types
        if python_type is str:
            return "string"
        if python_type is int:
            return "number"
        if python_type is float:
            return "number"
        if python_type is bool:
            return "boolean"

        # Handle our own CamelModel classes by name
        if hasattr(python_type, "__name__"):
            name = python_type.__name__
            if name in known_models:
                return name

        # Fallback for string representations
        type_str = str(python_type)
        if "str" in type_str and "list" not in type_str:
            return "string"
        if "int" in type_str and "list" not in type_str:
            return "number"
        if "float" in type_str and "list" not in type_str:
            return "number"
        if "bool" in type_str and "list" not in type_str:
            return "boolean"

        return "unknown"

    lines = [
        "// Auto-generated from Python CamelModel response classes",
        "// DO NOT EDIT MANUALLY - Run: python scripts/generate_event_schema.py",
        "//",
        "// These types match the API response shapes with automatic camelCase conversion.",
        "",
        "// ═══════════════════════════════════════════════════════════════",
        "// API RESPONSE TYPES",
        "// ═══════════════════════════════════════════════════════════════",
        "",
    ]

    # Find all CamelModel subclasses
    camel_models: list[tuple[str, type[BaseModel]]] = []
    for name in dir(models_module):
        obj = getattr(models_module, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, CamelModel)
            and obj is not CamelModel
        ):
            camel_models.append((name, obj))

    # Sort by name for consistent output
    camel_models.sort(key=lambda x: x[0])

    for class_name, model_class in camel_models:
        lines.append(f"export interface {class_name} {{")

        # Get field definitions from Pydantic model
        for field_name, field_info in model_class.model_fields.items():
            camel_name = to_camel(field_name)
            annotation = field_info.annotation

            ts_type = python_type_to_ts(annotation)

            # Check if field is optional (has default or is None-able)
            is_optional = field_info.default is not None or "None" in str(annotation) or "null" in ts_type

            if is_optional and "null" not in ts_type:
                lines.append(f"  {camel_name}?: {ts_type};")
            else:
                lines.append(f"  {camel_name}: {ts_type};")

        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Generate JSON Schema, TypeScript types, and API types."""
    root = Path(__file__).parent.parent

    # Generate JSON Schema
    schema = generate_json_schema()
    schema_path = root / "schemas" / "agent-events.schema.json"
    schema_path.parent.mkdir(exist_ok=True)
    schema_path.write_text(json.dumps(schema, indent=2))
    print(f"✅ Generated JSON Schema: {schema_path}")

    # Generate TypeScript event types
    ts_code = generate_typescript_types()
    ts_path = root / "studio" / "src" / "lib" / "agent-events.ts"
    ts_path.parent.mkdir(exist_ok=True)
    ts_path.write_text(ts_code)
    print(f"✅ Generated TypeScript event types: {ts_path}")

    # Generate TypeScript API response types
    api_types = generate_api_types()
    api_types_path = root / "studio" / "src" / "lib" / "api-types.ts"
    api_types_path.write_text(api_types)
    print(f"✅ Generated TypeScript API types: {api_types_path}")

    print("\n📝 Next steps:")
    print("  1. Review generated files")
    print("  2. Update imports in studio/src/lib/types.ts to use generated types")
    print("  3. Run TypeScript compiler to verify type compatibility")


if __name__ == "__main__":
    main()