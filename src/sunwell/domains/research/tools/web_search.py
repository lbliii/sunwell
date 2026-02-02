"""Web search tool for research domain."""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="web_search",
    simple_description="Search the web for information",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance=(
        "Use web_search when you need current information from the internet. "
        "Provide clear, specific search queries for best results."
    ),
)
class WebSearchTool(BaseTool):
    """Search the web for information.

    Returns search results with titles, snippets, and URLs.
    """

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5, max: 10)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, arguments: dict) -> str:
        """Execute web search.

        Args:
            arguments: Must contain 'query', optionally 'num_results'

        Returns:
            Formatted search results
        """
        query = arguments["query"]
        num_results = min(arguments.get("num_results", 5), 10)

        # Try to use existing web search provider
        try:
            from sunwell.tools.providers.web import web_search

            results = await web_search(query, num_results=num_results)

            if not results:
                return f"No results found for: {query}"

            output = [f"Search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                output.append(f"{i}. **{result.get('title', 'Untitled')}**")
                if result.get("snippet"):
                    output.append(f"   {result['snippet']}")
                if result.get("url"):
                    output.append(f"   URL: {result['url']}")
                output.append("")

            return "\n".join(output)

        except ImportError:
            # Fallback: inform user web search is not configured
            return (
                f"Web search requested for: {query}\n\n"
                "Note: Web search provider not configured. "
                "Please set up a search API (e.g., DuckDuckGo, Google) "
                "or use read_file to search local documentation."
            )
        except Exception as e:
            return f"Web search failed: {e}"
