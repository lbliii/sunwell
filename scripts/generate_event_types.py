#!/usr/bin/env python3
"""Generate TypeScript type definitions from Python event schemas.

DEPRECATED: Use scripts/generate_event_schema.py instead, which provides:
- Full TypeScript type generation from TypedDict schemas
- JSON Schema generation for validation
- Synchronization across Python, TypeScript, and Rust

Usage:
    python scripts/generate_event_schema.py --typescript > studio/src/lib/types/events.ts
"""

import sys


def main() -> None:
    """Print deprecation notice and exit."""
    print(
        "⚠️  DEPRECATED: This script has been superseded by generate_event_schema.py",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print("Use instead:", file=sys.stderr)
    print("    python scripts/generate_event_schema.py --typescript", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "The generate_event_schema.py script provides more complete type generation",
        file=sys.stderr,
    )
    print("from the TypedDict schemas in event_schema.py.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
