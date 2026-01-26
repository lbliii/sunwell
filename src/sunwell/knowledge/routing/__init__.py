"""Query routing for multi-project workspaces.

Determines which projects a query relates to before performing retrieval.
Enables efficient cross-project search without loading all indexes.
"""

from sunwell.knowledge.routing.query_router import (
    QueryRouter,
    RouteResult,
    route_query,
)
from sunwell.knowledge.routing.workspace_search import (
    SearchResult,
    WorkspaceSearch,
)

__all__ = [
    "QueryRouter",
    "RouteResult",
    "route_query",
    "SearchResult",
    "WorkspaceSearch",
]
