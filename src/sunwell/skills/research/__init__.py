"""Research skill: web search + memory store + structured summary."""

import logging
from typing import TYPE_CHECKING

from sunwell.skills.protocol import Skill, skill_action

if TYPE_CHECKING:
    from sunwell.memory import PersistentMemory  # noqa: F401
    from sunwell.tools.providers.web_search import WebSearchHandler  # noqa: F401

logger = logging.getLogger(__name__)


class ResearchSkill(Skill):
    """Deep research on any topic using web search and memory."""

    name = "research"
    description = "Deep research on any topic"
    tools_required = ("web_search", "web_fetch", "memory_recall")

    @skill_action
    async def research(self, topic: str, depth: str = "moderate") -> str:
        """Research a topic: search web, fetch key pages, summarize, store in memory.

        Args:
            topic: The topic to research
            depth: shallow (3 results), moderate (5), deep (8)

        Returns:
            Structured summary of findings
        """
        web = self._tools
        memory = self._memory

        if not web:
            return "Web search not configured. Set web_search_handler on SkillExecutor."

        max_results = 5
        if depth == "shallow":
            max_results = 3
        elif depth == "deep":
            max_results = 8

        try:
            results = await web.web_search({"query": topic, "max_results": max_results})
        except Exception as e:
            return f"Web search failed: {e}"

        if not results or "No results" in results:
            return f"No results found for: {topic}"

        summary_parts = [f"# Research: {topic}\n", f"Depth: {depth}\n", "", results]

        if memory and hasattr(memory, "simulacrum") and memory.simulacrum:
            try:
                summary_text = "\n".join(summary_parts)[:2000]
                memory.simulacrum.add_learning(summary_text, category="fact")
            except Exception as e:
                logger.debug("Could not store in memory: %s", e)

        return "\n".join(summary_parts)
