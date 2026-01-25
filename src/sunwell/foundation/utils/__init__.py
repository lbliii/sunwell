"""Foundation utilities - Generic helpers with zero dependencies.

RFC-138: Module Architecture Consolidation
"""

from sunwell.foundation.utils.strings import slugify
from sunwell.foundation.utils.validation import validate_slug

__all__ = [
    "slugify",
    "validate_slug",
]
