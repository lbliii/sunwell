"""External tool providers."""

from sunwell.tools.providers.expertise import ExpertiseToolHandler, get_self_directed_prompt
from sunwell.tools.providers.web_search import (
    OllamaWebSearch,
    WebFetchResult,
    WebSearchHandler,
    WebSearchProvider,
    WebSearchResult,
    create_web_search_provider,
)

__all__ = [
    "WebSearchProvider",
    "WebSearchResult",
    "WebFetchResult",
    "WebSearchHandler",
    "OllamaWebSearch",
    "create_web_search_provider",
    "ExpertiseToolHandler",
    "get_self_directed_prompt",
]
