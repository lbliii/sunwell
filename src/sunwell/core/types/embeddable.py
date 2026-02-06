"""Embeddable protocol for objects convertible to embedding text.

Canonical definitions moved to sunwell.foundation.schema.models.embeddable;
re-exported here for backward compatibility.
"""

from sunwell.foundation.schema.models.embeddable import Embeddable, to_embedding_text

__all__ = ["Embeddable", "to_embedding_text"]
