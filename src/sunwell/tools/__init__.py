"""Tool calling support for Sunwell (RFC-012, RFC-024).

This package provides:
- ToolTrust: Trust levels for tool execution
- CORE_TOOLS: Built-in tool definitions
- GIT_TOOLS: Git operation tools (RFC-024)
- ENV_TOOLS: Environment variable tools (RFC-024)
- CoreToolHandlers: Handlers for built-in tools
- ToolExecutor: Tool dispatch and execution
- WebSearchProvider: Protocol for web search providers
- OllamaWebSearch: Web search via Ollama API

RFC-024 additions:
- 12 git tools (status, diff, log, blame, show, add, restore, commit, etc.)
- 2 environment tools (get_env, list_env) with security allowlist
- Updated trust level mappings for all tools
"""

from sunwell.tools.types import ToolTrust, ToolResult, ToolRateLimits, TRUST_LEVEL_TOOLS
from sunwell.tools.builtins import (
    CORE_TOOLS,
    GIT_TOOLS,
    ENV_TOOLS,
    ENV_ALLOWLIST,
    ENV_BLOCKLIST_PATTERNS,
    get_tools_for_trust_level,
    get_all_tools,
)
from sunwell.tools.handlers import CoreToolHandlers, PathSecurityError
from sunwell.tools.executor import ToolExecutor
from sunwell.tools.web_search import (
    WebSearchProvider,
    WebSearchResult,
    WebFetchResult,
    WebSearchHandler,
    OllamaWebSearch,
    create_web_search_provider,
)

__all__ = [
    # Trust levels
    "ToolTrust",
    "ToolResult",
    "ToolRateLimits",
    "TRUST_LEVEL_TOOLS",
    # Tool definitions
    "CORE_TOOLS",
    "GIT_TOOLS",
    "ENV_TOOLS",
    "ENV_ALLOWLIST",
    "ENV_BLOCKLIST_PATTERNS",
    "get_tools_for_trust_level",
    "get_all_tools",
    # Handlers and execution
    "CoreToolHandlers",
    "PathSecurityError",
    "ToolExecutor",
    # Web search
    "WebSearchProvider",
    "WebSearchResult",
    "WebFetchResult",
    "WebSearchHandler",
    "OllamaWebSearch",
    "create_web_search_provider",
]
