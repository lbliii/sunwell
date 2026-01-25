"""Interface domain - CLI, Server, UI primitives, Generative Interface.

RFC-138: Module Architecture Consolidation

Subpackages:
- cli/: Command-line interface (sunwell.interface.cli)
- server/: HTTP API for Studio (sunwell.interface.server)
- surface/: UI primitives (sunwell.interface.surface)
- generative/: LLM-driven interaction routing (sunwell.interface.generative)

Import from subpackages for most use cases:
    from sunwell.interface.cli import main
    from sunwell.interface.server import create_app
    from sunwell.interface.surface import SurfaceComposer
    from sunwell.interface.generative import IntentPipeline
"""

# Essential entry points only - import from subpackages for detailed APIs
from sunwell.interface.cli import cli_entrypoint, main
from sunwell.interface.server import create_app
from sunwell.interface.generative import IntentPipeline, analyze_with_pipeline
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
