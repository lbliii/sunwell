"""Foundation domain - Zero-dependency base types, config, errors, identity.

This domain contains the foundational building blocks that have no dependencies
on other sunwell modules. Everything else imports from here.

RFC-138: Module Architecture Consolidation
"""

# Re-exports from new locations (Phase 2)
from sunwell.foundation.types import *  # noqa: F403, F401
from sunwell.foundation.config import *  # noqa: F403, F401
from sunwell.foundation.errors import *  # noqa: F403, F401
from sunwell.foundation.identity import *  # noqa: F403, F401
from sunwell.foundation.freethreading import *  # noqa: F403, F401
from sunwell.foundation.schema import *  # noqa: F403, F401
from sunwell.foundation.binding import *  # noqa: F403, F401
from sunwell.foundation.utils import *  # noqa: F403, F401
