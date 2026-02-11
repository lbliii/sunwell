"""Central state directory resolution.

Canonical definitions moved to sunwell.foundation.state;
re-exported here for backward compatibility.

See sunwell.foundation.state for full documentation.
"""

from sunwell.foundation.state import (
    IN_TREE_ITEMS,
    STATE_SUBDIRS,
    default_state_root,
    ensure_state_dir,
    resolve_state_dir,
    xdg_data_home,
)

__all__ = [
    "STATE_SUBDIRS",
    "IN_TREE_ITEMS",
    "xdg_data_home",
    "default_state_root",
    "resolve_state_dir",
    "ensure_state_dir",
]
