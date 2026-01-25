"""Tests for web search tools (RFC-012 extension)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from sunwell.tools.web_search import (
    WebSearchResult,
    WebFetchResult,
    WebSearchHandler,
    OllamaWebSearch,
    create_web_search_provider,
)
from sunwell.tools.executor import ToolExecutor
from sunwell.tools.types import ToolPolicy, ToolTrust
from sunwell.tools.builtins import CORE_TOOLS
from sunwell.models.core.protocol import ToolCall


# =============================================================================
# Test WebSearchResult and WebFetchResult
# =============================================================================


def test_web_search_result_frozen():
    """WebSearchResult should be immutable."""
    result = WebSearchResult(
        title="Test",
        url="https://example.com",
        content="Test content",
    )
    assert result.title == "Test"
    assert result.url == "https://example.com"
    assert result.content == "Test content"
    
    with pytest.raises(AttributeError):
        result.title = "Changed"


def test_web_fetch_result_frozen():
    """WebFetchResult should be immutable."""
    result = WebFetchResult(
        title="Test Page",
        content="Page content",
        links=("https://a.com", "https://b.com"),
    )
    assert result.title == "Test Page"
    assert len(result.links) == 2


# =============================================================================
# Test WebSearchHandler
# =============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock web search provider."""
    provider = MagicMock()
    provider.search = AsyncMock(return_value=[
        WebSearchResult(
            title="Result 1",
            url="https://example.com/1",
            content="First result content",
        ),
        WebSearchResult(
            title="Result 2",
            url="https://example.com/2",
            content="Second result content",
        ),
    ])
    provider.fetch = AsyncMock(return_value=WebFetchResult(
        title="Fetched Page",
        content="This is the page content.",
        links=("https://link1.com", "https://link2.com"),
    ))
    return provider


@pytest.fixture
def handler(mock_provider):
    """Create a WebSearchHandler with mock provider."""
    return WebSearchHandler(provider=mock_provider)


@pytest.mark.asyncio
async def test_web_search_handler_search(handler, mock_provider):
    """web_search should return formatted results."""
    result = await handler.web_search({"query": "test query", "max_results": 5})
    
    assert "Found 2 results" in result
    assert "Result 1" in result
    assert "https://example.com/1" in result
    mock_provider.search.assert_called_once_with("test query", max_results=5)


@pytest.mark.asyncio
async def test_web_search_handler_search_empty(handler, mock_provider):
    """web_search should handle no results."""
    mock_provider.search.return_value = []
    
    result = await handler.web_search({"query": "no results"})
    
    assert "No results found" in result


@pytest.mark.asyncio
async def test_web_search_handler_search_error(handler, mock_provider):
    """web_search should handle errors gracefully."""
    mock_provider.search.side_effect = Exception("API error")
    
    result = await handler.web_search({"query": "error query"})
    
    assert "Web search failed" in result


@pytest.mark.asyncio
async def test_web_fetch_handler(handler, mock_provider):
    """web_fetch should return formatted page content."""
    result = await handler.web_fetch({"url": "https://example.com"})
    
    assert "Fetched Page" in result
    assert "This is the page content" in result
    assert "Links found" in result
    mock_provider.fetch.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_web_fetch_handler_error(handler, mock_provider):
    """web_fetch should handle errors gracefully."""
    mock_provider.fetch.side_effect = Exception("Fetch failed")
    
    result = await handler.web_fetch({"url": "https://example.com"})
    
    assert "Web fetch failed" in result


# =============================================================================
# Test OllamaWebSearch
# =============================================================================


def test_ollama_web_search_requires_api_key():
    """OllamaWebSearch should require an API key."""
    provider = OllamaWebSearch()
    
    with pytest.raises(ValueError, match="API key required"):
        provider._get_api_key()


def test_ollama_web_search_uses_env_var():
    """OllamaWebSearch should read OLLAMA_API_KEY from environment."""
    with patch.dict("os.environ", {"OLLAMA_API_KEY": "test-key"}):
        provider = OllamaWebSearch()
        assert provider._get_api_key() == "test-key"


def test_ollama_web_search_uses_param_over_env():
    """OllamaWebSearch should prefer api_key parameter over env var."""
    with patch.dict("os.environ", {"OLLAMA_API_KEY": "env-key"}):
        provider = OllamaWebSearch(api_key="param-key")
        assert provider._get_api_key() == "param-key"


@pytest.mark.asyncio
async def test_ollama_web_search_integration():
    """OllamaWebSearch should make correct API calls."""
    # Mock httpx
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"title": "Title", "url": "https://example.com", "content": "Content"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    
    provider = OllamaWebSearch(api_key="test-key")
    provider._client = mock_client
    
    results = await provider.search("test query", max_results=3)
    
    assert len(results) == 1
    assert results[0].title == "Title"
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "web_search" in call_args[0][0]
    assert call_args[1]["json"]["query"] == "test query"
    assert call_args[1]["json"]["max_results"] == 3


# =============================================================================
# Test ToolExecutor Integration
# =============================================================================


@pytest.mark.asyncio
async def test_tool_executor_with_web_search(tmp_path, mock_provider):
    """ToolExecutor should route web_search to handler."""
    handler = WebSearchHandler(provider=mock_provider)
    
    executor = ToolExecutor(
        workspace=tmp_path,
        web_search_handler=handler,
        policy=ToolPolicy(trust_level=ToolTrust.FULL),
    )
    
    # Verify web_search is registered
    assert "web_search" in executor.get_available_tools()
    assert "web_fetch" in executor.get_available_tools()
    
    # Execute web_search
    result = await executor.execute(ToolCall(
        id="call-1",
        name="web_search",
        arguments={"query": "test", "max_results": 3},
    ))
    
    assert result.success
    assert "Found 2 results" in result.output


@pytest.mark.asyncio
async def test_tool_executor_web_search_requires_full_trust(tmp_path, mock_provider):
    """web_search should not be available below FULL trust level."""
    handler = WebSearchHandler(provider=mock_provider)
    
    # SHELL trust level - should NOT include web search
    executor = ToolExecutor(
        workspace=tmp_path,
        web_search_handler=handler,
        policy=ToolPolicy(trust_level=ToolTrust.SHELL),
    )
    
    assert "web_search" not in executor.get_available_tools()
    assert "web_fetch" not in executor.get_available_tools()


# =============================================================================
# Test Factory
# =============================================================================


def test_create_web_search_provider_ollama():
    """Factory should create OllamaWebSearch."""
    provider = create_web_search_provider("ollama", api_key="test")
    assert isinstance(provider, OllamaWebSearch)


def test_create_web_search_provider_unknown():
    """Factory should raise for unknown providers."""
    with pytest.raises(ValueError, match="Unknown provider"):
        create_web_search_provider("unknown")


# =============================================================================
# Test Tool Definitions
# =============================================================================


def test_web_search_tool_in_builtins():
    """web_search and web_fetch should be in CORE_TOOLS."""
    assert "web_search" in CORE_TOOLS
    assert "web_fetch" in CORE_TOOLS
    
    web_search = CORE_TOOLS["web_search"]
    assert web_search.name == "web_search"
    assert "query" in web_search.parameters["properties"]
    
    web_fetch = CORE_TOOLS["web_fetch"]
    assert web_fetch.name == "web_fetch"
    assert "url" in web_fetch.parameters["properties"]
