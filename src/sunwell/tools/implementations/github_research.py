"""GitHub Research Tool - Search and analyze GitHub repositories.

Provides an agent-callable tool to research GitHub repositories using
magnetic search techniques to extract patterns and architecture.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry.base import BaseTool, tool_metadata

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@tool_metadata(
    name="github_research",
    simple_description="Research GitHub repos to find patterns for a project",
    trust_level=ToolTrust.FULL,  # Requires network access for GitHub API + git clone
    usage_guidance=(
        "Use github_research to discover patterns and architecture from similar projects on GitHub. "
        "Provide a descriptive query like 'todo app in svelte' or 'auth system in fastapi'. "
        "The tool will search GitHub, clone top repositories, and analyze their structure."
    ),
)
class GitHubResearchTool(BaseTool):
    """Research GitHub repositories for patterns and architecture.

    Searches GitHub for repositories matching a query, clones them,
    and analyzes their structure using magnetic search techniques.

    Useful for:
    - Understanding common patterns for a type of project
    - Discovering recommended directory structures
    - Finding common dependencies and libraries
    - Learning from well-structured existing projects
    """

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research query (e.g., 'todo app in svelte', 'auth system fastapi')",
            },
            "max_repos": {
                "type": "integer",
                "description": "Maximum repositories to analyze",
                "default": 3,
            },
            "min_stars": {
                "type": "integer",
                "description": "Minimum stars filter for search",
                "default": 50,
            },
            "focus": {
                "type": "string",
                "enum": ["architecture", "patterns", "examples"],
                "description": "What to focus on in the analysis",
                "default": "architecture",
            },
        },
        "required": ["query"],
    }

    async def execute(self, arguments: dict) -> str:
        """Execute the GitHub research tool.

        Args:
            arguments: Tool arguments with query and options.

        Returns:
            Markdown-formatted research report.
        """
        query = arguments.get("query", "")
        max_repos = arguments.get("max_repos", 3)
        min_stars = arguments.get("min_stars", 50)
        focus = arguments.get("focus", "architecture")

        if not query:
            return "Error: query is required"

        # Import research components (lazy to avoid import overhead)
        from sunwell.research.analyzer import MagneticAnalyzer
        from sunwell.research.fetcher import RepoFetcher
        from sunwell.research.github import GitHubSearcher
        from sunwell.research.reporter import format_for_tool
        from sunwell.research.synthesizer import PatternSynthesizer
        from sunwell.research.types import ResearchIntent

        # Parse query for language hints
        search_terms, language = self._parse_query(query)

        # Map focus to intent
        intent_map = {
            "architecture": ResearchIntent.ARCHITECTURE,
            "patterns": ResearchIntent.PATTERNS,
            "examples": ResearchIntent.EXAMPLES,
        }
        intent = intent_map.get(focus, ResearchIntent.ARCHITECTURE)

        # Initialize components
        searcher = GitHubSearcher()
        fetcher = RepoFetcher()
        analyzer = MagneticAnalyzer()
        synthesizer = PatternSynthesizer()

        try:
            # Step 1: Search GitHub
            logger.info("Searching GitHub for: %s", search_terms)
            repos = await searcher.search(
                query=search_terms,
                language=language,
                min_stars=min_stars,
                max_results=max_repos,
            )

            if not repos:
                return f"No repositories found matching '{query}'. Try a broader search term."

            # Step 2: Clone repositories
            logger.info("Cloning %d repositories...", len(repos))
            fetched = await fetcher.fetch(repos)

            if not fetched:
                return "Failed to clone any repositories. Check network connectivity."

            # Step 3: Analyze each repository
            logger.info("Analyzing repositories...")
            analyses = []
            for repo in fetched:
                analysis = analyzer.analyze(repo, intent)
                analyses.append(analysis)

            # Step 4: Synthesize patterns
            logger.info("Synthesizing patterns...")
            patterns = synthesizer.synthesize(analyses)

            # Step 5: Format for tool output
            return format_for_tool(query, repos, analyses, patterns)

        except Exception as e:
            logger.exception("Research failed")
            return f"Research failed: {e}"

        finally:
            await searcher.close()
            await fetcher.cleanup()

    def _parse_query(self, query: str) -> tuple[str, str | None]:
        """Parse query to extract search terms and language hint."""
        query = query.lower().strip()

        language_hints = {
            "python": "python",
            "py": "python",
            "fastapi": "python",
            "django": "python",
            "flask": "python",
            "javascript": "javascript",
            "js": "javascript",
            "typescript": "typescript",
            "ts": "typescript",
            "svelte": "svelte",
            "sveltekit": "svelte",
            "react": "javascript",
            "vue": "vue",
            "go": "go",
            "golang": "go",
            "rust": "rust",
        }

        detected_language = None
        search_terms = query

        # Check for "in <language>" pattern
        if " in " in query:
            parts = query.rsplit(" in ", 1)
            search_terms = parts[0]
            lang_hint = parts[1].strip()
            detected_language = language_hints.get(lang_hint, lang_hint)

        # Also check for language keywords
        for keyword, lang in language_hints.items():
            if keyword in query.split():
                detected_language = lang
                break

        return search_terms, detected_language
