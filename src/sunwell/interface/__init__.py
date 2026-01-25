"""Interface domain - CLI, Server, UI primitives, Generative Interface.

RFC-138: Module Architecture Consolidation

This domain consolidates all user-facing modules:
- CLI: Command-line interface  
- Server: HTTP API for Studio
- Surface: UI primitives
- Generative: LLM-driven interaction routing (RFC-075)
"""

# Re-exports from submodules
from sunwell.interface.cli import *  # noqa: F403, F401
from sunwell.interface.server import *  # noqa: F403, F401
from sunwell.interface.surface import *  # noqa: F403, F401
from sunwell.interface.generative import *  # noqa: F403, F401
