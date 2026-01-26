"""Tool calling support for Sunwell (RFC-012, RFC-024, RFC-027).

This package provides:
- ToolTrust: Trust levels for tool execution
- CORE_TOOLS: Built-in tool definitions
- GIT_TOOLS: Git operation tools (RFC-024)
- ENV_TOOLS: Environment variable tools (RFC-024)
- EXPERTISE_TOOLS: Self-directed expertise retrieval tools (RFC-027)
- CoreToolHandlers: Handlers for built-in tools
- ToolExecutor: Tool dispatch and execution
- ExpertiseToolHandler: Handler for expertise tools (RFC-027)
- WebSearchProvider: Protocol for web search providers
- OllamaWebSearch: Web search via Ollama API

RFC-024 additions:
- 12 git tools (status, diff, log, blame, show, add, restore, commit, etc.)
- 2 environment tools (get_env, list_env) with security allowlist
- Updated trust level mappings for all tools

RFC-027 additions:
- 3 expertise tools (get_expertise, verify_against_expertise, list_expertise_areas)
- ExpertiseToolHandler for self-directed expertise retrieval
- System prompt for ReAct-style tool usage
"""

# Core types
from sunwell.tools.core.constants import TRUST_LEVEL_TOOLS
from sunwell.tools.core.types import (
    ToolAuditEntry,
    ToolPolicy,
    ToolRateLimits,
    ToolResult,
    ToolTrust,
)

# Tool definitions
from sunwell.tools.definitions import (
    CORE_TOOLS,
    ENV_ALLOWLIST,
    ENV_BLOCKLIST_PATTERNS,
    ENV_TOOLS,
    EXPERTISE_TOOLS,
    GIT_TOOLS,
    get_all_tools,
    get_tools_for_trust_level,
)

# Errors
from sunwell.tools.errors import (
    ToolError,
    ToolErrorCode,
    format_error_for_model,
    get_retry_strategy,
    should_retry,
)

# Execution
from sunwell.tools.execution import ToolExecutor

# Handlers
from sunwell.tools.handlers import CoreToolHandlers, PathSecurityError

# Providers
from sunwell.tools.providers import (
    ExpertiseToolHandler,
    OllamaWebSearch,
    WebFetchResult,
    WebSearchHandler,
    WebSearchProvider,
    WebSearchResult,
    create_web_search_provider,
    get_self_directed_prompt,
)

# Sunwell handlers
from sunwell.tools.sunwell import SunwellToolHandlers

__all__ = [
    # Trust levels
    "ToolTrust",
    "ToolResult",
    "ToolRateLimits",
    "ToolAuditEntry",
    "ToolPolicy",
    "TRUST_LEVEL_TOOLS",
    # Tool definitions
    "CORE_TOOLS",
    "GIT_TOOLS",
    "ENV_TOOLS",
    "EXPERTISE_TOOLS",
    "ENV_ALLOWLIST",
    "ENV_BLOCKLIST_PATTERNS",
    "get_tools_for_trust_level",
    "get_all_tools",
    # Handlers and execution
    "CoreToolHandlers",
    "PathSecurityError",
    "ToolExecutor",
    # Expertise tools (RFC-027)
    "ExpertiseToolHandler",
    "get_self_directed_prompt",
    # Web search
    "WebSearchProvider",
    "WebSearchResult",
    "WebFetchResult",
    "WebSearchHandler",
    "OllamaWebSearch",
    "create_web_search_provider",
    # Sunwell handlers
    "SunwellToolHandlers",
    # Errors
    "ToolError",
    "ToolErrorCode",
    "should_retry",
    "get_retry_strategy",
    "format_error_for_model",
]
