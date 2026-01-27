"""Web search providers for RFC-012 tool calling.

Provides web search and fetch capabilities via pluggable providers.
Default: Ollama's free web search API (https://docs.ollama.com/capabilities/web-search)

Usage:
    provider = OllamaWebSearch(api_key="...")  # or from OLLAMA_API_KEY env
    results = await provider.search("what is sunwell?")
    page = await provider.fetch("https://example.com")
"""


import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import httpx

# =============================================================================
# Data Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    """A single web search result."""

    title: str
    url: str
    content: str  # Snippet/excerpt


@dataclass(frozen=True, slots=True)
class WebFetchResult:
    """Result from fetching a web page."""

    title: str
    content: str
    links: tuple[str, ...] = ()


# =============================================================================
# Provider Protocol
# =============================================================================


@runtime_checkable
class WebSearchProvider(Protocol):
    """Protocol for web search providers.

    Implementations: OllamaWebSearch, TavilyWebSearch, BraveWebSearch, etc.
    """

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """Search the web for a query.

        Args:
            query: Search query string
            max_results: Maximum results to return (1-10)

        Returns:
            List of search results with title, url, and content snippet
        """
        ...

    async def fetch(self, url: str) -> WebFetchResult:
        """Fetch and extract content from a URL.

        Args:
            url: The URL to fetch

        Returns:
            WebFetchResult with title, content, and links
        """
        ...


# =============================================================================
# Ollama Implementation
# =============================================================================


@dataclass(slots=True)
class OllamaWebSearch:
    """Web search via Ollama's free API.

    Requires: OLLAMA_API_KEY environment variable or api_key parameter.
    Free tier available at https://ollama.com

    Docs: https://docs.ollama.com/capabilities/web-search

    Usage as context manager (recommended):
        async with OllamaWebSearch() as search:
            results = await search.search("query")
    """

    api_key: str | None = None
    base_url: str = "https://ollama.com/api"
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "OllamaWebSearch":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager, closing the HTTP client."""
        await self.close()

    def _get_api_key(self) -> str:
        """Get API key from parameter or environment."""
        key = self.api_key or os.environ.get("OLLAMA_API_KEY")
        if not key:
            raise ValueError(
                "Ollama API key required. Set OLLAMA_API_KEY environment variable "
                "or pass api_key parameter. Get a free key at https://ollama.com"
            )
        return key

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            try:
                import httpx
            except ImportError as e:
                raise ImportError(
                    "httpx not installed. Run: pip install httpx"
                ) from e

            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._get_api_key()}"},
                timeout=30.0,
            )
        return self._client

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """Search the web using Ollama's API.

        Args:
            query: Search query string
            max_results: Maximum results (1-10)

        Returns:
            List of WebSearchResult
        """
        client = await self._get_client()

        # Clamp max_results to valid range
        max_results = max(1, min(10, max_results))

        response = await client.post(
            f"{self.base_url}/web_search",
            json={"query": query, "max_results": max_results},
        )
        response.raise_for_status()

        data = response.json()

        return [
            WebSearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
            )
            for r in data.get("results", [])
        ]

    async def fetch(self, url: str) -> WebFetchResult:
        """Fetch a web page using Ollama's API.

        Args:
            url: URL to fetch

        Returns:
            WebFetchResult with title, content, and links
        """
        client = await self._get_client()

        response = await client.post(
            f"{self.base_url}/web_fetch",
            json={"url": url},
        )
        response.raise_for_status()

        data = response.json()

        return WebFetchResult(
            title=data.get("title", ""),
            content=data.get("content", ""),
            links=tuple(data.get("links", [])),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# Web Search Handler
# =============================================================================


@dataclass(frozen=True, slots=True)
class WebSearchHandler:
    """Handler for web search tools. Routes to configured provider.

    Usage:
        handler = WebSearchHandler(provider=OllamaWebSearch())
        result = await handler.web_search({"query": "...", "max_results": 5})
    """

    provider: WebSearchProvider

    async def web_search(self, args: dict) -> str:
        """Execute web_search tool.

        Args:
            args: {"query": str, "max_results": int (optional)}

        Returns:
            Formatted search results
        """
        query = args["query"]
        max_results = args.get("max_results", 5)

        try:
            results = await self.provider.search(query, max_results=max_results)
        except Exception as e:
            return f"Web search failed: {e}"

        if not results:
            return f"No results found for: {query}"

        # Format results for LLM consumption
        output_lines = [f"Found {len(results)} results for: {query}\n"]

        for i, r in enumerate(results, 1):
            output_lines.append(f"[{i}] {r.title}")
            output_lines.append(f"    URL: {r.url}")
            output_lines.append(f"    {r.content[:300]}...")
            output_lines.append("")

        return "\n".join(output_lines)

    async def web_fetch(self, args: dict) -> str:
        """Execute web_fetch tool.

        Args:
            args: {"url": str}

        Returns:
            Formatted page content
        """
        url = args["url"]

        try:
            result = await self.provider.fetch(url)
        except Exception as e:
            return f"Web fetch failed: {e}"

        # Format for LLM consumption
        output_lines = [
            f"# {result.title}",
            f"URL: {url}",
            "",
            result.content[:10_000],  # Limit content size
        ]

        if result.links:
            output_lines.extend([
                "",
                "## Links found:",
                *[f"- {link}" for link in result.links[:20]],
            ])

        return "\n".join(output_lines)


# =============================================================================
# Factory
# =============================================================================


def create_web_search_provider(
    provider: str = "ollama",
    **kwargs,
) -> WebSearchProvider:
    """Factory to create web search providers.

    Args:
        provider: Provider name ("ollama", "tavily", "brave")
        **kwargs: Provider-specific arguments (api_key, etc.)

    Returns:
        Configured WebSearchProvider

    Raises:
        ValueError: If provider is not supported
    """
    providers = {
        "ollama": OllamaWebSearch,
        # Future: "tavily": TavilyWebSearch,
        # Future: "brave": BraveWebSearch,
    }

    if provider not in providers:
        available = ", ".join(providers.keys())
        raise ValueError(f"Unknown provider '{provider}'. Available: {available}")

    return providers[provider](**kwargs)
