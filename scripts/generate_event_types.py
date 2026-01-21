#!/usr/bin/env python3
"""Generate TypeScript type definitions from Python event schemas.

Usage:
    python scripts/generate_event_types.py > studio/src/lib/types/events.ts
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunwell.adaptive.event_schema import generate_typescript_types

if __name__ == "__main__":
    print(generate_typescript_types())
