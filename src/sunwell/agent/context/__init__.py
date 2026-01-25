"""Context reference system for RFC-024.

This package provides:
- ContextReference: Parsed @ reference (e.g., @file, @git:staged)
- ContextResolver: Resolves references to actual content
- ResolvedContext: Result with content and metadata
- IDEContext: Context from IDE extensions
- SessionContext: All session state in one object (RFC-MEMORY)

Example:
    >>> from sunwell.context import ContextReference, ContextResolver
    >>> refs = ContextReference.parse("review @file:auth.py and check @git:staged")
    >>> resolver = ContextResolver(workspace_root=Path("."))
    >>> for ref in refs:
    ...     ctx = await resolver.resolve(ref)
    ...     print(f"{ref.raw}: {len(ctx.content)} chars")

    >>> from sunwell.context import SessionContext
    >>> session = SessionContext.build(Path.cwd(), "add auth", options)
"""

from sunwell.context.constants import (
    MAX_CONTEXT_CHARS,
    MAX_INLINE_CHARS,
    MAX_TOTAL_CONTEXT,
)
from sunwell.context.ide import IDEContext
from sunwell.context.reference import ContextReference, ResolvedContext
from sunwell.context.resolver import ContextResolver
from sunwell.context.session import SessionContext, workspace_id

__all__ = [
    # Reference system
    "ContextReference",
    "ResolvedContext",
    "ContextResolver",
    "IDEContext",
    "MAX_INLINE_CHARS",
    "MAX_CONTEXT_CHARS",
    "MAX_TOTAL_CONTEXT",
    # Session context
    "SessionContext",
    "workspace_id",
]
