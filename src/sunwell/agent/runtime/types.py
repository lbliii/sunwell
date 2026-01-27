"""Runtime type definitions and protocols.

This module contains shared protocols and types for the runtime package.
"""

# Import Saveable from centralized protocol module (RFC-025 Protocol Centralization)
from sunwell.foundation.types.protocol import Saveable

# Re-export for backward compatibility
__all__ = ["Saveable"]
