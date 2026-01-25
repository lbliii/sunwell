"""Project management routes (RFC-113, RFC-117, RFC-132).

Re-export router from project package for backwards compatibility.
"""

from sunwell.interface.server.routes.project import router

__all__ = ["router"]
