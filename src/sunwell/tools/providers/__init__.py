"""External tool providers."""

from sunwell.tools.providers.expertise import ExpertiseToolHandler, get_self_directed_prompt
from sunwell.tools.providers.web_search import (
    BraveWebSearch,
    OllamaWebSearch,
    TavilyWebSearch,
    WebFetchResult,
    WebSearchHandler,
    WebSearchProvider,
    WebSearchResult,
    create_web_search_provider,
    get_available_providers,
)

__all__ = [
    # Protocol
    "WebSearchProvider",
    # Data types
    "WebSearchResult",
    "WebFetchResult",
    # Handler
    "WebSearchHandler",
    # Providers
    "OllamaWebSearch",
    "TavilyWebSearch",
    "BraveWebSearch",
    # Factory
    "create_web_search_provider",
    "get_available_providers",
    # Expertise
    "ExpertiseToolHandler",
    "get_self_directed_prompt",
]
