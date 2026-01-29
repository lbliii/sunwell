"""Tool rationale for post-selection validation.

This module implements a validation step that asks the model to explain
WHY it chose a particular tool before execution. Weak rationales can
trigger retry with a different tool.

Research backing:
- AutoTool: Tool-selection rationales improve accuracy by 5-7%
- Chain-of-thought prompting improves reasoning quality
- Rationales can be recorded for future learning

The rationale step:
1. Model selects a tool
2. Rationale module asks "Why this tool?"
3. If rationale is strong → execute
4. If rationale is weak → retry or flag for review
5. Success/failure feeds back to LearningStore
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.learning.store import LearningStore
    from sunwell.models import Tool
    from sunwell.models.protocol import ModelProtocol

logger = logging.getLogger(__name__)


class RationaleStrength(Enum):
    """Strength of a tool rationale."""

    STRONG = "strong"  # Clear reasoning, proceed with execution
    MODERATE = "moderate"  # Acceptable, proceed but note
    WEAK = "weak"  # Poor reasoning, consider retry
    INVALID = "invalid"  # No valid rationale, should retry


# Prompt for generating rationale
RATIONALE_PROMPT = """You selected the tool "{tool_name}" for this request:

Request: {query}

Explain in 1-2 sentences WHY this tool is the best choice:
- What does this tool do?
- How does it help accomplish the user's request?
- Why is it better than alternatives?

Rationale:"""

# Prompt for validating an existing rationale
VALIDATION_PROMPT = """Tool: {tool_name}
Request: {query}
Rationale: {rationale}

Is this rationale valid? Answer STRONG, MODERATE, WEAK, or INVALID:
- STRONG: Clear logic, correct tool choice
- MODERATE: Acceptable logic, reasonable choice
- WEAK: Unclear logic or questionable choice
- INVALID: Wrong tool for the task

Assessment:"""


@dataclass(frozen=True, slots=True)
class ToolRationale:
    """Result of tool rationale generation/validation.

    Attributes:
        tool_name: Name of the tool being rationalized
        rationale: The explanation for choosing this tool
        strength: Assessed strength of the rationale
        alternatives: Suggested alternative tools if weak
    """

    tool_name: str
    rationale: str
    strength: RationaleStrength
    alternatives: tuple[str, ...] = ()

    @property
    def is_acceptable(self) -> bool:
        """Whether the rationale is acceptable for execution."""
        return self.strength in (RationaleStrength.STRONG, RationaleStrength.MODERATE)

    @property
    def should_retry(self) -> bool:
        """Whether we should retry with a different tool."""
        return self.strength in (RationaleStrength.WEAK, RationaleStrength.INVALID)


@dataclass(slots=True)
class ToolRationaleValidator:
    """Validates tool choices through rationale generation.

    Implements post-selection validation by asking the model to explain
    its tool choice. Can also validate externally provided rationales.

    Attributes:
        require_rationale: If True, always require a rationale
        min_strength: Minimum acceptable strength for execution
        learning_store: Optional store for recording outcomes
        retry_on_weak: Whether to suggest retry for weak rationales
    """

    require_rationale: bool = True
    min_strength: RationaleStrength = RationaleStrength.MODERATE
    learning_store: "LearningStore | None" = None
    retry_on_weak: bool = True

    # Cache for validated rationales
    _cache: dict[str, ToolRationale] = field(default_factory=dict, init=False)

    def _assess_strength(self, rationale: str, tool_name: str, query: str) -> RationaleStrength:
        """Heuristically assess rationale strength.

        Args:
            rationale: The rationale text
            tool_name: Tool being rationalized
            query: Original user query

        Returns:
            Assessed strength
        """
        if not rationale or len(rationale) < 10:
            return RationaleStrength.INVALID

        rationale_lower = rationale.lower()
        tool_lower = tool_name.lower().replace("_", " ")

        # Check if rationale mentions the tool's purpose
        purpose_keywords = {
            "list_files": ["directory", "files", "list", "contents", "folder"],
            "search_files": ["search", "find", "pattern", "grep", "match", "look"],
            "read_file": ["read", "content", "view", "examine", "see", "look at"],
            "edit_file": ["edit", "modify", "change", "update", "fix", "replace"],
            "write_file": ["write", "create", "new file", "save"],
            "git_status": ["status", "changes", "modified", "staged", "working"],
            "git_diff": ["diff", "changes", "compare", "difference"],
            "git_commit": ["commit", "save", "record", "snapshot"],
            "git_add": ["stage", "add", "track"],
            "run_command": ["run", "execute", "command", "shell", "terminal"],
            "web_search": ["search", "google", "find", "look up", "information"],
        }

        keywords = purpose_keywords.get(tool_name, [tool_lower])
        keyword_hits = sum(1 for kw in keywords if kw in rationale_lower)

        # Check if rationale connects to the query
        query_words = set(query.lower().split())
        rationale_words = set(rationale_lower.split())
        overlap = len(query_words & rationale_words)

        # Scoring
        if keyword_hits >= 2 and overlap >= 2:
            return RationaleStrength.STRONG
        elif keyword_hits >= 1 and overlap >= 1:
            return RationaleStrength.MODERATE
        elif keyword_hits >= 1 or overlap >= 2:
            return RationaleStrength.WEAK
        else:
            return RationaleStrength.INVALID

    def _suggest_alternatives(
        self,
        tool_name: str,
        query: str,
        available_tools: "tuple[Tool, ...]",
    ) -> tuple[str, ...]:
        """Suggest alternative tools when rationale is weak.

        Args:
            tool_name: Currently selected tool
            query: User query
            available_tools: All available tools

        Returns:
            Tuple of alternative tool names
        """
        # Simple keyword-based alternatives
        query_lower = query.lower()
        alternatives = []

        # Define tool categories
        file_tools = ["list_files", "search_files", "read_file", "edit_file", "write_file"]
        git_tools = ["git_status", "git_diff", "git_log", "git_add", "git_commit"]
        search_tools = ["search_files", "find_files", "web_search"]

        available_names = {t.name for t in available_tools}

        # Suggest from same category
        if tool_name in file_tools:
            alternatives = [t for t in file_tools if t != tool_name and t in available_names]
        elif tool_name in git_tools:
            alternatives = [t for t in git_tools if t != tool_name and t in available_names]

        # Add search alternatives for "find" queries
        if "find" in query_lower or "search" in query_lower:
            alternatives.extend(t for t in search_tools if t != tool_name and t in available_names)

        return tuple(dict.fromkeys(alternatives))[:3]  # Dedupe, limit to 3

    async def generate_rationale(
        self,
        tool_name: str,
        query: str,
        model: "ModelProtocol",
        available_tools: "tuple[Tool, ...] | None" = None,
    ) -> ToolRationale:
        """Generate a rationale for a tool choice.

        Args:
            tool_name: The selected tool
            query: User's request
            model: Model to generate rationale
            available_tools: All available tools (for alternatives)

        Returns:
            ToolRationale with explanation and strength
        """
        cache_key = f"{tool_name}:{query}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = RATIONALE_PROMPT.format(tool_name=tool_name, query=query)

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await model.generate(messages)

            # Extract text
            if hasattr(response, "content"):
                rationale_text = response.content
            elif hasattr(response, "message"):
                rationale_text = response.message.content
            else:
                rationale_text = str(response)

            # Assess strength
            strength = self._assess_strength(rationale_text, tool_name, query)

            # Suggest alternatives if weak
            alternatives = ()
            if strength in (RationaleStrength.WEAK, RationaleStrength.INVALID) and available_tools:
                alternatives = self._suggest_alternatives(tool_name, query, available_tools)

            result = ToolRationale(
                tool_name=tool_name,
                rationale=rationale_text.strip(),
                strength=strength,
                alternatives=alternatives,
            )

            self._cache[cache_key] = result

            logger.debug(
                "Tool rationale for %s: %s (strength=%s)",
                tool_name,
                rationale_text[:50],
                strength.value,
            )

            return result

        except Exception as e:
            logger.warning("Rationale generation failed: %s", e)
            return ToolRationale(
                tool_name=tool_name,
                rationale=f"Generation failed: {e}",
                strength=RationaleStrength.INVALID,
            )

    def validate_rationale(
        self,
        tool_name: str,
        rationale: str,
        query: str,
        available_tools: "tuple[Tool, ...] | None" = None,
    ) -> ToolRationale:
        """Validate an existing rationale (no model required).

        Args:
            tool_name: The selected tool
            rationale: Provided rationale
            query: User's request
            available_tools: All available tools (for alternatives)

        Returns:
            ToolRationale with assessed strength
        """
        strength = self._assess_strength(rationale, tool_name, query)

        alternatives = ()
        if strength in (RationaleStrength.WEAK, RationaleStrength.INVALID) and available_tools:
            alternatives = self._suggest_alternatives(tool_name, query, available_tools)

        return ToolRationale(
            tool_name=tool_name,
            rationale=rationale,
            strength=strength,
            alternatives=alternatives,
        )

    def record_outcome(
        self,
        rationale: ToolRationale,
        success: bool,
        task_type: str = "general",
    ) -> None:
        """Record the outcome of a tool execution for learning.

        Args:
            rationale: The rationale that was used
            success: Whether the tool execution succeeded
            task_type: Type of task being performed
        """
        if self.learning_store is None:
            return

        if success and rationale.strength == RationaleStrength.STRONG:
            # Record as successful pattern
            try:
                self.learning_store.record_tool_use(
                    tool_name=rationale.tool_name,
                    task_type=task_type,
                    success=True,
                )
                logger.debug(
                    "Recorded successful tool pattern: %s for %s",
                    rationale.tool_name,
                    task_type,
                )
            except Exception as e:
                logger.warning("Failed to record tool pattern: %s", e)

        elif not success and rationale.strength in (RationaleStrength.WEAK, RationaleStrength.INVALID):
            # This confirms the weak rationale was indeed wrong
            # Could record as dead end
            logger.debug(
                "Weak rationale confirmed wrong: %s (strength=%s)",
                rationale.tool_name,
                rationale.strength.value,
            )

    def clear_cache(self) -> None:
        """Clear the rationale cache."""
        self._cache.clear()


# =============================================================================
# HEURISTIC RATIONALE (NO MODEL REQUIRED)
# =============================================================================


def generate_heuristic_rationale(
    tool_name: str,
    query: str,
    available_tools: "tuple[Tool, ...] | None" = None,
) -> ToolRationale:
    """Generate a heuristic rationale without a model.

    Uses keyword matching and tool descriptions to assess fit.

    Args:
        tool_name: The selected tool
        query: User's request
        available_tools: All available tools

    Returns:
        ToolRationale with heuristic assessment
    """
    # Get tool description if available
    tool_desc = ""
    if available_tools:
        for t in available_tools:
            if t.name == tool_name:
                tool_desc = getattr(t, "description", "") or ""
                break

    query_lower = query.lower()
    tool_lower = tool_name.lower().replace("_", " ")

    # Simple relevance check
    relevance_score = 0

    # Check if tool name words appear in query
    tool_words = tool_lower.split()
    for word in tool_words:
        if word in query_lower:
            relevance_score += 2

    # Check if query words appear in description
    if tool_desc:
        desc_lower = tool_desc.lower()
        query_words = query_lower.split()
        for word in query_words:
            if len(word) > 3 and word in desc_lower:
                relevance_score += 1

    # Build rationale
    if relevance_score >= 3:
        strength = RationaleStrength.STRONG
        rationale = f"{tool_name} is appropriate because it can {tool_desc[:50]}... which matches the request."
    elif relevance_score >= 1:
        strength = RationaleStrength.MODERATE
        rationale = f"{tool_name} may help with this request."
    else:
        strength = RationaleStrength.WEAK
        rationale = f"Unclear fit between {tool_name} and the request."

    # Suggest alternatives if weak
    alternatives = ()
    if strength == RationaleStrength.WEAK and available_tools:
        validator = ToolRationaleValidator()
        alternatives = validator._suggest_alternatives(tool_name, query, available_tools)

    return ToolRationale(
        tool_name=tool_name,
        rationale=rationale,
        strength=strength,
        alternatives=alternatives,
    )
