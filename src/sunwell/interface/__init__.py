"""Interface domain - CLI, Chirp UI, UI primitives, Generative Interface.

RFC-138: Module Architecture Consolidation

Subpackages:
- cli/: Command-line interface (sunwell.interface.cli)
- chirp/: HTTP UI for Studio (sunwell.interface.chirp) - Chirp SSR + Pounce
- server/: Legacy FastAPI routes (deprecated, being phased out)
- surface/: UI primitives (sunwell.interface.surface)
- generative/: LLM-driven interaction routing (sunwell.interface.generative)

Example:
    from sunwell.interface import main, create_app, IntentPipeline
"""

# CLI entry points
from sunwell.interface.cli import cli_entrypoint, main

# Generative interface
from sunwell.interface.generative import IntentPipeline, analyze_with_pipeline

# Chirp UI (primary web interface)
from sunwell.interface.chirp import create_app

# Surface composition
from sunwell.interface.surface import SurfaceComposer, compose_surface

__all__ = [
    # CLI
    "cli_entrypoint",
    "main",
    # Server
    "create_app",
    # Generative
    "IntentPipeline",
    "analyze_with_pipeline",
    # Surface
    "SurfaceComposer",
    "compose_surface",
]
