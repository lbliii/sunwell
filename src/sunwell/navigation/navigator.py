"""LLM-powered ToC navigation engine (RFC-124).

Provides reasoning-based codebase navigation using hierarchical
Table of Contents in the LLM context window.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.navigation.toc import ProjectToc

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

logger = logging.getLogger(__name__)


# Navigation prompt template
NAVIGATION_PROMPT = """You are navigating a codebase to find relevant code.

## Project Structure (Table of Contents)

{toc_context}

## Query

{query}

## Previous Steps

{history}

## Instructions

Based on the project structure, decide which path to explore.
Consider:
1. Directory/module names that match the query intent
2. Class/function names that suggest relevant functionality
3. Cross-references that might lead to the answer
4. What you've already explored (don't repeat)

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "selected_path": "path/to/explore",
  "reasoning": "Why this path is likely to contain what we need",
  "confidence": 0.0-1.0,
  "follow_up": ["other/paths", "to/consider"]
}}
"""

# Sufficiency check prompt
SUFFICIENCY_PROMPT = """Based on the content retrieved so far, determine if we have enough \
information to answer the query.

## Query
{query}

## Retrieved Content
{content}

Respond ONLY with valid JSON:
{{"sufficient": true/false, "reason": "brief explanation"}}
"""


@dataclass(frozen=True, slots=True)
class NavigationResult:
    """Result of a navigation query.

    Attributes:
        path: Selected path to read.
        reasoning: Why this path was selected.
        confidence: Navigation confidence (0.0-1.0).
        content: Content if already read.
        follow_up: Suggested paths to explore next.
    """

    path: str
    reasoning: str
    confidence: float
    content: str | None = None
    follow_up: tuple[str, ...] = ()


@dataclass
class NavigatorConfig:
    """Configuration for ToC navigation."""

    max_depth: int = 3
    """Maximum ToC depth to include in context."""

    max_iterations: int = 3
    """Maximum navigation iterations."""

    cache_size: int = 100
    """LRU cache size for query→path mappings."""

    max_content_lines: int = 200
    """Maximum lines to read from a file."""

    subtree_budget: int = 500
    """Token budget for subtree expansion."""


@dataclass
class TocNavigator:
    """LLM-powered navigation using ToC reasoning.

    The navigator puts the ToC in context and asks the LLM
    to reason about where to look, rather than using embeddings.

    This approach excels at structural queries:
    - "Where is authentication implemented?"
    - "How does the routing work?"
    - "Find the model validation code"
    """

    toc: ProjectToc
    """Project Table of Contents."""

    model: ModelProtocol
    """LLM model for navigation reasoning."""

    workspace_root: Path
    """Project root directory for reading files."""

    config: NavigatorConfig = field(default_factory=NavigatorConfig)
    """Navigator configuration."""

    _cache: dict[str, NavigationResult] = field(default_factory=dict, init=False)
    """Query cache for repeated lookups."""

    async def navigate(
        self,
        query: str,
        history: list[str] | None = None,
    ) -> NavigationResult:
        """Navigate to relevant code section.

        Single-step navigation: read ToC, reason, select path.

        Args:
            query: What the user is looking for.
            history: Previous navigation steps (for context).

        Returns:
            NavigationResult with selected path and reasoning.
        """
        # Check cache first
        cache_key = self._cache_key(query, history)
        if cache_key in self._cache:
            logger.debug("Navigation cache hit: %s", query[:50])
            return self._cache[cache_key]

        # Build navigation prompt
        toc_context = self.toc.to_context_json(max_depth=self.config.max_depth)

        prompt = NAVIGATION_PROMPT.format(
            toc_context=toc_context,
            query=query,
            history=(
                self._format_history(history) if history else "None - first navigation."
            ),
        )

        # Get LLM response
        try:
            response = await self.model.generate(prompt)
            result = self._parse_navigation_response(response.text)
        except Exception as e:
            logger.warning("Navigation failed: %s", e)
            # Fallback to best-guess based on query keywords
            result = self._fallback_navigate(query)

        # Cache result
        if len(self._cache) >= self.config.cache_size:
            # Simple eviction: remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cache_key] = result

        return result

    async def iterative_search(
        self,
        query: str,
        max_iterations: int | None = None,
    ) -> list[NavigationResult]:
        """Iteratively navigate until sufficient content found.

        Implements the PageIndex loop:
        1. Read ToC
        2. Select section
        3. Extract content
        4. Is it enough? → Yes: stop, No: repeat

        Args:
            query: What the user is looking for.
            max_iterations: Override default max iterations.

        Returns:
            List of NavigationResults with content.
        """
        iterations = max_iterations or self.config.max_iterations
        results: list[NavigationResult] = []
        history: list[str] = []
        visited_paths: set[str] = set()

        for i in range(iterations):
            logger.debug("Navigation iteration %d/%d", i + 1, iterations)

            # Navigate to next location
            result = await self.navigate(query, history)

            # Skip if already visited
            if result.path in visited_paths:
                logger.debug("Already visited: %s", result.path)
                # Try follow-up paths
                for follow_up in result.follow_up:
                    if follow_up not in visited_paths:
                        result = NavigationResult(
                            path=follow_up,
                            reasoning=f"Follow-up from {result.path}",
                            confidence=result.confidence * 0.8,
                            follow_up=(),
                        )
                        break
                else:
                    # No unvisited paths, stop
                    break

            visited_paths.add(result.path)

            # Read the selected content
            content = await self._read_path(result.path)
            result_with_content = NavigationResult(
                path=result.path,
                reasoning=result.reasoning,
                confidence=result.confidence,
                content=content,
                follow_up=result.follow_up,
            )
            results.append(result_with_content)

            # Check if we have enough
            if await self._is_sufficient(query, results):
                logger.debug("Sufficient content found after %d iterations", i + 1)
                break

            # Update history for next iteration
            history.append(f"Explored {result.path}: {result.reasoning}")

        return results

    async def navigate_to_concept(self, concept: str) -> list[NavigationResult]:
        """Navigate directly to nodes tagged with a concept.

        Faster than iterative search when looking for known concepts
        like 'auth', 'api', 'config', etc.

        Args:
            concept: Concept name (e.g., 'auth', 'api').

        Returns:
            NavigationResults for concept-tagged nodes.
        """
        nodes = self.toc.get_nodes_by_concept(concept)
        if not nodes:
            return []

        results: list[NavigationResult] = []
        for node in nodes[:5]:  # Limit to top 5
            content = await self._read_path(node.path)
            results.append(NavigationResult(
                path=node.path,
                reasoning=f"Tagged with concept: {concept}",
                confidence=0.9,
                content=content,
                follow_up=tuple(node.children[:3]),
            ))

        return results

    async def expand_subtree(self, node_id: str, depth: int = 2) -> str:
        """Expand a subtree for deeper navigation.

        Used when initial navigation finds a relevant module
        but needs more detail.

        Args:
            node_id: Node ID to expand.
            depth: Depth to expand.

        Returns:
            JSON string of subtree.
        """
        return self.toc.get_subtree(node_id, depth=depth)

    async def _read_path(self, path: str) -> str | None:
        """Read file content for a path.

        Args:
            path: Relative path to read.

        Returns:
            File content or None if not readable.
        """
        file_path = self.workspace_root / path

        # If it's a directory, read __init__.py
        if file_path.is_dir():
            init_file = file_path / "__init__.py"
            if init_file.exists():
                file_path = init_file
            else:
                logger.debug("Directory has no __init__.py: %s", path)
                return None

        # Handle node ID format (dotted) vs path format
        if not file_path.exists() and "." in path and "/" not in path:
            # Try converting node ID to path
            possible_path = path.replace(".", "/") + ".py"
            file_path = self.workspace_root / possible_path
            if not file_path.exists():
                # Try as directory with __init__.py
                possible_path = path.replace(".", "/")
                dir_path = self.workspace_root / possible_path
                if dir_path.is_dir():
                    init_file = dir_path / "__init__.py"
                    if init_file.exists():
                        file_path = init_file

        if not file_path.exists():
            logger.debug("File not found: %s", path)
            return None

        try:
            content = file_path.read_text(errors="ignore")
            lines = content.splitlines()

            # Truncate if too long
            if len(lines) > self.config.max_content_lines:
                lines = lines[: self.config.max_content_lines]
                lines.append(f"\n... (truncated, {len(content.splitlines())} total lines)")

            return "\n".join(lines)
        except OSError as e:
            logger.warning("Failed to read %s: %s", path, e)
            return None

    async def _is_sufficient(
        self,
        query: str,
        results: list[NavigationResult],
    ) -> bool:
        """Check if retrieved content is sufficient.

        Uses a quick LLM call to assess sufficiency.

        Args:
            query: Original query.
            results: Results collected so far.

        Returns:
            True if content appears sufficient.
        """
        if not results:
            return False

        # Build content summary
        content_parts = []
        for r in results:
            if r.content:
                # Truncate each result for the check
                preview = r.content[:500] if len(r.content) > 500 else r.content
                content_parts.append(f"## {r.path}\n{preview}")

        if not content_parts:
            return False

        content = "\n\n".join(content_parts)

        prompt = SUFFICIENCY_PROMPT.format(query=query, content=content)

        try:
            response = await self.model.generate(prompt)
            data = self._parse_json_response(response.text)
            return data.get("sufficient", False)
        except Exception as e:
            logger.warning("Sufficiency check failed: %s", e)
            # Default to stopping after 2 results with content
            return len([r for r in results if r.content]) >= 2

    def _parse_navigation_response(self, response: str) -> NavigationResult:
        """Parse LLM navigation response.

        Args:
            response: Raw LLM response.

        Returns:
            NavigationResult parsed from response.
        """
        data = self._parse_json_response(response)

        path = data.get("selected_path", "")
        reasoning = data.get("reasoning", "No reasoning provided")
        confidence = float(data.get("confidence", 0.5))
        follow_up = tuple(data.get("follow_up", []))

        # Normalize path
        path = self._normalize_path(path)

        return NavigationResult(
            path=path,
            reasoning=reasoning,
            confidence=min(max(confidence, 0.0), 1.0),  # Clamp 0-1
            follow_up=follow_up,
        )

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response.

        Handles common issues like markdown code blocks.

        Args:
            response: Raw response text.

        Returns:
            Parsed dictionary.
        """
        text = response.strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines if they're code fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Try to find JSON object
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON: %s", text[:100])
            return {}

    def _normalize_path(self, path: str) -> str:
        """Normalize a path from LLM response.

        Args:
            path: Raw path from LLM.

        Returns:
            Normalized path.
        """
        # Remove leading/trailing whitespace and quotes
        path = path.strip().strip("\"'")

        # Remove leading ./ or /
        path = path.lstrip("./")

        # Convert backslashes to forward slashes
        path = path.replace("\\", "/")

        return path

    def _fallback_navigate(self, query: str) -> NavigationResult:
        """Fallback navigation using keyword matching.

        Used when LLM call fails.

        Args:
            query: Query to match.

        Returns:
            Best-guess NavigationResult.
        """
        # Extract keywords from query
        keywords = set(re.findall(r"[a-z]+", query.lower()))
        keywords -= {"the", "a", "an", "is", "are", "how", "does", "what", "where", "find"}

        # Score nodes by keyword overlap
        best_score = 0
        best_node = None

        for node in self.toc.nodes.values():
            text = f"{node.title} {node.path} {node.summary}".lower()
            node_words = set(re.findall(r"[a-z]+", text))
            score = len(keywords & node_words)

            if score > best_score:
                best_score = score
                best_node = node

        if best_node:
            return NavigationResult(
                path=best_node.path,
                reasoning=f"Keyword match (fallback): {best_score} matching terms",
                confidence=0.3,
                follow_up=tuple(best_node.children[:3]),
            )

        # Ultimate fallback: root
        return NavigationResult(
            path=".",
            reasoning="No matching nodes found (fallback to root)",
            confidence=0.1,
            follow_up=(),
        )

    def _format_history(self, history: list[str]) -> str:
        """Format navigation history for prompt.

        Args:
            history: List of previous steps.

        Returns:
            Formatted history string.
        """
        if not history:
            return "None"

        return "\n".join(f"- {step}" for step in history)

    def _cache_key(self, query: str, history: list[str] | None) -> str:
        """Generate cache key for a query.

        Args:
            query: Query string.
            history: Navigation history.

        Returns:
            Cache key string.
        """
        history_str = "|".join(history) if history else ""
        return f"{query}::{history_str}"

    def clear_cache(self) -> None:
        """Clear the navigation cache."""
        self._cache.clear()


@lru_cache(maxsize=100)
def _cached_concept_lookup(toc_id: int, concept: str) -> tuple[str, ...]:
    """Cached concept lookup helper.

    Args:
        toc_id: ID of the ToC (for cache key).
        concept: Concept to look up.

    Returns:
        Tuple of node IDs.
    """
    # This is a placeholder - actual implementation uses toc.get_nodes_by_concept
    # The cache is keyed by toc_id to invalidate on ToC changes
    return ()
