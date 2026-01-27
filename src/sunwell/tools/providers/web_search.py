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
# Tavily Implementation
# =============================================================================


@dataclass(slots=True)
class TavilyWebSearch:
    """Web search via Tavily Search API.

    Tavily is optimized for AI agents with clean, structured results.
    Requires: TAVILY_API_KEY environment variable or api_key parameter.

    Get an API key at https://tavily.com

    Usage as context manager (recommended):
        async with TavilyWebSearch() as search:
            results = await search.search("query")
    """

    api_key: str | None = None
    base_url: str = "https://api.tavily.com"
    search_depth: str = "basic"  # "basic" or "advanced"
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "TavilyWebSearch":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager, closing the HTTP client."""
        await self.close()

    def _get_api_key(self) -> str:
        """Get API key from parameter or environment."""
        key = self.api_key or os.environ.get("TAVILY_API_KEY")
        if not key:
            raise ValueError(
                "Tavily API key required. Set TAVILY_API_KEY environment variable "
                "or pass api_key parameter. Get an API key at https://tavily.com"
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

            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """Search the web using Tavily's API.

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
            f"{self.base_url}/search",
            json={
                "api_key": self._get_api_key(),
                "query": query,
                "search_depth": self.search_depth,
                "max_results": max_results,
                "include_answer": False,
            },
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
        """Fetch a web page using Tavily's extract API.

        Args:
            url: URL to fetch

        Returns:
            WebFetchResult with title, content, and links
        """
        client = await self._get_client()

        response = await client.post(
            f"{self.base_url}/extract",
            json={
                "api_key": self._get_api_key(),
                "urls": [url],
            },
        )
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            return WebFetchResult(title="", content="No content extracted", links=())

        result = results[0]
        return WebFetchResult(
            title=result.get("title", ""),
            content=result.get("raw_content", result.get("content", "")),
            links=(),  # Tavily extract doesn't return links separately
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# Brave Implementation
# =============================================================================


@dataclass(slots=True)
class BraveWebSearch:
    """Web search via Brave Search API.

    Brave Search is privacy-focused with high-quality results.
    Requires: BRAVE_API_KEY environment variable or api_key parameter.

    Get an API key at https://brave.com/search/api/

    Usage as context manager (recommended):
        async with BraveWebSearch() as search:
            results = await search.search("query")
    """

    api_key: str | None = None
    base_url: str = "https://api.search.brave.com/res/v1"
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "BraveWebSearch":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager, closing the HTTP client."""
        await self.close()

    def _get_api_key(self) -> str:
        """Get API key from parameter or environment."""
        key = self.api_key or os.environ.get("BRAVE_API_KEY")
        if not key:
            raise ValueError(
                "Brave API key required. Set BRAVE_API_KEY environment variable "
                "or pass api_key parameter. Get an API key at https://brave.com/search/api/"
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
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._get_api_key(),
                },
                timeout=30.0,
            )
        return self._client

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """Search the web using Brave's API.

        Args:
            query: Search query string
            max_results: Maximum results (1-10)

        Returns:
            List of WebSearchResult
        """
        client = await self._get_client()

        # Clamp max_results to valid range
        max_results = max(1, min(20, max_results))

        response = await client.get(
            f"{self.base_url}/web/search",
            params={
                "q": query,
                "count": max_results,
            },
        )
        response.raise_for_status()

        data = response.json()
        web_results = data.get("web", {}).get("results", [])

        return [
            WebSearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("description", ""),
            )
            for r in web_results
        ]

    async def fetch(self, url: str) -> WebFetchResult:
        """Fetch a web page.

        Brave doesn't have a dedicated fetch API, so we use a simple HTTP fetch
        with basic HTML extraction.

        Args:
            url: URL to fetch

        Returns:
            WebFetchResult with title, content, and links
        """
        client = await self._get_client()

        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            return WebFetchResult(
                title="",
                content=f"Failed to fetch: {e}",
                links=(),
            )

        # Simple HTML extraction (could be improved with BeautifulSoup)
        import re

        # Extract title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        # Remove scripts, styles, and HTML tags for content
        content = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()

        # Extract links
        link_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        links = tuple(link_pattern.findall(html)[:50])

        return WebFetchResult(
            title=title,
            content=content[:10000],
            links=links,
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

# Provider priority for auto-selection (first available wins)
_PROVIDER_PRIORITY = [
    ("tavily", "TAVILY_API_KEY", TavilyWebSearch),
    ("brave", "BRAVE_API_KEY", BraveWebSearch),
    ("ollama", "OLLAMA_API_KEY", OllamaWebSearch),
]


def get_available_providers() -> list[str]:
    """Get list of providers with available API keys.

    Returns:
        List of provider names with configured API keys
    """
    available = []
    for name, env_key, _ in _PROVIDER_PRIORITY:
        if os.environ.get(env_key):
            available.append(name)
    return available


def create_web_search_provider(
    provider: str = "auto",
    **kwargs,
) -> WebSearchProvider:
    """Factory to create web search providers.

    Args:
        provider: Provider name or "auto" to select based on available API keys.
                  Options: "auto", "tavily", "brave", "ollama"
        **kwargs: Provider-specific arguments (api_key, etc.)

    Returns:
        Configured WebSearchProvider

    Raises:
        ValueError: If provider is not supported or no API key available

    Example:
        # Auto-select based on available API keys
        provider = create_web_search_provider("auto")

        # Explicit provider
        provider = create_web_search_provider("tavily", api_key="...")
    """
    providers = {
        "ollama": OllamaWebSearch,
        "tavily": TavilyWebSearch,
        "brave": BraveWebSearch,
    }

    if provider == "auto":
        # Auto-select based on available API keys
        for name, env_key, provider_class in _PROVIDER_PRIORITY:
            if os.environ.get(env_key):
                return provider_class(**kwargs)

        # No API key found - list what's needed
        raise ValueError(
            "No web search API key found. Set one of:\n"
            "  - TAVILY_API_KEY (https://tavily.com)\n"
            "  - BRAVE_API_KEY (https://brave.com/search/api/)\n"
            "  - OLLAMA_API_KEY (https://ollama.com)"
        )

    if provider not in providers:
        available = ", ".join(["auto", *providers.keys()])
        raise ValueError(f"Unknown provider '{provider}'. Available: {available}")

    return providers[provider](**kwargs)
