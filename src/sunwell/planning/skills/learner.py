"""SkillLearner - Extract reusable skills from successful executions (RFC-111 Phase 5).

When a user accomplishes something complex, we can:
1. Analyze the execution trace (tool calls, context flow)
2. Identify the pattern of steps
3. Generate a reusable skill definition
4. Save it to the local skill library

This enables self-improving agents that learn from successful patterns.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.planning.skills.types import Skill, SkillDependency, SkillType

# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_RE_TOOL_JSON = re.compile(r'"tool"\s*:\s*"([^"]+)"')
_RE_TOOL_CALL = re.compile(r"^(\w+)(?:\(|:)")
_RE_TOOL_NAME = re.compile(r'"name"\s*:\s*"([^"]+)"')
_RE_JSON_KEY = re.compile(r'"(\w+)":')
_RE_SLUG_INVALID = re.compile(r"[^a-z0-9-]")
_RE_SLUG_SPECIAL = re.compile(r"[^a-z0-9]+")
_RE_SLUG_MULTI_HYPHEN = re.compile(r"-+")
_RE_WORD_BOUNDARY = re.compile(r"\b\w+\b")

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.memory.simulacrum.core.turn import Turn


@dataclass(frozen=True, slots=True)
class ExecutionPattern:
    """A pattern extracted from successful execution.

    Captures the essence of what made an execution successful:
    - What tools were used and in what order
    - What context keys flowed between steps
    - What the goal was
    """

    goal: str
    """The original user goal/request."""

    steps_description: str
    """Human-readable description of steps taken."""

    tools_used: tuple[str, ...]
    """Tools invoked during execution, in order."""

    context_keys: tuple[str, ...]
    """Context keys produced/consumed during execution."""

    turn_ids: tuple[str, ...]
    """Turn IDs that comprise this pattern."""

    success_indicators: tuple[str, ...] = ()
    """Keywords/phrases that indicate success."""


@dataclass(frozen=True, slots=True)
class LearnedSkillMetadata:
    """Metadata for a skill learned from execution."""

    source_session: str
    """Session ID the skill was learned from."""

    learned_at: str
    """ISO timestamp when skill was learned."""

    pattern_hash: str
    """Hash of the execution pattern for deduplication."""

    confidence: float = 0.8
    """Confidence that this skill is reusable."""


@dataclass(slots=True)
class SkillLearner:
    """Extract reusable skills from successful executions.

    Integrates with Simulacrum to analyze session history and
    extract patterns that can become reusable skills.

    Usage:
        learner = SkillLearner(model=model)
        skill = await learner.extract_skill_from_session(
            store=simulacrum_store,
            session_id="20260123_143022",
            success_criteria="Successfully generated API",
        )
        if skill:
            library.save_learned_skill(skill, source="learned")
    """

    model: "ModelProtocol | None" = None
    """Model for LLM-based pattern analysis. Optional."""

    min_turns_for_learning: int = 5
    """Minimum turns needed to extract a pattern."""

    min_tool_calls: int = 2
    """Minimum tool calls needed for a meaningful pattern."""

    async def extract_skill_from_session(
        self,
        store: "SimulacrumStore",
        session_id: str,
        success_criteria: str,
    ) -> Skill | None:
        """Extract a reusable skill from a successful session.

        Args:
            store: SimulacrumStore containing the session
            session_id: ID of the session to analyze
            success_criteria: Description of what made this successful

        Returns:
            A Skill if extraction succeeded, None otherwise
        """
        # Load the session
        try:
            dag = store.load_session(session_id)
        except FileNotFoundError:
            return None

        # Check if session has enough content
        if len(dag.turns) < self.min_turns_for_learning:
            return None

        # Extract the execution pattern
        pattern = self._extract_pattern(dag, success_criteria)
        if not pattern:
            return None

        # Check if pattern has enough tool usage
        if len(pattern.tools_used) < self.min_tool_calls:
            return None

        # Generate skill from pattern
        if self.model:
            skill = await self._generate_skill_with_llm(pattern, success_criteria)
        else:
            skill = self._generate_skill_heuristic(pattern, success_criteria)

        return skill

    def extract_pattern_from_dag(
        self,
        dag: "ConversationDAG",
        goal: str,
    ) -> ExecutionPattern | None:
        """Extract execution pattern from a conversation DAG.

        Public method for cases where you have the DAG directly.

        Args:
            dag: The conversation DAG to analyze
            goal: The user's goal

        Returns:
            ExecutionPattern if extraction succeeded
        """
        return self._extract_pattern(dag, goal)

    def _extract_pattern(
        self,
        dag: "ConversationDAG",
        goal: str,
    ) -> ExecutionPattern | None:
        """Extract pattern from conversation DAG."""
        from sunwell.memory.simulacrum.core.turn import TurnType

        # Collect tool calls in order
        tool_calls: list[str] = []
        turn_ids: list[str] = []
        context_keys: set[str] = set()

        # Walk the DAG from roots to heads
        for turn in self._topological_sort(dag):
            turn_ids.append(turn.id)

            if turn.turn_type == TurnType.TOOL_CALL:
                # Extract tool name from content
                tool_name = self._extract_tool_name(turn.content)
                if tool_name:
                    tool_calls.append(tool_name)

            elif turn.turn_type == TurnType.TOOL_RESULT:
                # Extract context keys from result
                keys = self._extract_context_keys(turn.content)
                context_keys.update(keys)

        if not tool_calls:
            return None

        # Build steps description from user/assistant exchanges
        steps = self._summarize_steps(dag)

        return ExecutionPattern(
            goal=goal,
            steps_description=steps,
            tools_used=tuple(tool_calls),
            context_keys=tuple(sorted(context_keys)),
            turn_ids=tuple(turn_ids),
        )

    def _topological_sort(
        self,
        dag: "ConversationDAG",
    ) -> list["Turn"]:
        """Return turns in topological order."""
        visited: set[str] = set()
        result: list["Turn"] = []

        def dfs(turn_id: str) -> None:
            if turn_id in visited or turn_id not in dag.turns:
                return
            visited.add(turn_id)

            turn = dag.turns[turn_id]
            for parent_id in turn.parent_ids:
                dfs(parent_id)

            result.append(turn)

        # Start from all heads
        for head_id in dag.heads:
            dfs(head_id)

        return result

    def _extract_tool_name(self, content: str) -> str | None:
        """Extract tool name from tool call content."""
        # Try common patterns
        # Pattern 1: {"tool": "tool_name", ...}
        match = _RE_TOOL_JSON.search(content)
        if match:
            return match.group(1)

        # Pattern 2: tool_name(...) or tool_name:
        match = _RE_TOOL_CALL.search(content.strip())
        if match:
            return match.group(1)

        # Pattern 3: "name": "tool_name" for function calls
        match = _RE_TOOL_NAME.search(content)
        if match:
            return match.group(1)

        return None

    def _extract_context_keys(self, content: str) -> set[str]:
        """Extract likely context keys from tool result."""
        keys: set[str] = set()

        # Look for JSON-like key patterns
        for match in _RE_JSON_KEY.finditer(content):
            key = match.group(1)
            # Filter out common noise
            if key not in ("type", "content", "role", "id", "status"):
                keys.add(key)

        return keys

    def _summarize_steps(self, dag: "ConversationDAG") -> str:
        """Summarize the steps taken in the conversation."""
        from sunwell.memory.simulacrum.core.turn import TurnType

        steps: list[str] = []
        for turn in self._topological_sort(dag):
            if turn.turn_type == TurnType.USER:
                # Truncate long user messages
                content = turn.content[:100] + "..." if len(turn.content) > 100 else turn.content
                steps.append(f"User: {content}")
            elif turn.turn_type == TurnType.TOOL_CALL:
                tool = self._extract_tool_name(turn.content) or "unknown"
                steps.append(f"Called: {tool}")

        return "\n".join(steps[:20])  # Limit to 20 steps

    def _generate_skill_heuristic(
        self,
        pattern: ExecutionPattern,
        success_criteria: str,
    ) -> Skill:
        """Generate skill using heuristic rules (no LLM).

        Creates a reasonable skill definition based on the pattern.
        """
        import hashlib

        # Generate skill name from goal
        name = self._slugify(pattern.goal)[:50]

        # Deduplicate tools while preserving order
        seen: set[str] = set()
        unique_tools: list[str] = []
        for tool in pattern.tools_used:
            if tool not in seen:
                seen.add(tool)
                unique_tools.append(tool)

        # Build instructions
        instructions = f"""## Goal
{pattern.goal}

## Success Criteria
{success_criteria}

## Pattern
This skill was learned from a successful execution that used:
- Tools: {", ".join(unique_tools)}
- Context keys: {", ".join(pattern.context_keys) or "none identified"}

## Steps
{pattern.steps_description}

## Usage
Apply this pattern when the user's goal matches: {pattern.goal}
"""

        # Infer dependencies from tool usage patterns
        depends_on: list[SkillDependency] = []
        produces: list[str] = list(pattern.context_keys)
        requires: list[str] = []

        # Common patterns: if read-file is used, the skill likely requires file paths
        if "read_file" in unique_tools or "read-file" in unique_tools:
            requires.append("file_path")
        if "grep" in unique_tools or "search" in unique_tools:
            requires.append("search_query")

        return Skill(
            name=name,
            description=f"Learned skill: {pattern.goal[:100]}",
            skill_type=SkillType.INLINE,
            instructions=instructions,
            depends_on=tuple(depends_on),
            produces=tuple(produces),
            requires=tuple(requires),
            triggers=tuple(self._extract_triggers(pattern.goal)),
            allowed_tools=tuple(unique_tools),
        )

    async def _generate_skill_with_llm(
        self,
        pattern: ExecutionPattern,
        success_criteria: str,
    ) -> Skill:
        """Generate skill using LLM for better quality."""
        if not self.model:
            return self._generate_skill_heuristic(pattern, success_criteria)

        from sunwell.models import GenerateOptions

        prompt = f"""Based on this successful execution pattern, generate a reusable skill definition.

## Goal
{pattern.goal}

## Steps Taken
{pattern.steps_description}

## Tools Used
{', '.join(pattern.tools_used)}

## Context Keys Identified
{', '.join(pattern.context_keys) or 'none'}

## Success Criteria
{success_criteria}

Generate a skill that:
1. Can reproduce this pattern for similar goals
2. Has clear requires/produces contracts
3. Works for variations of the original task

Output in this exact format:
NAME: [skill-name-lowercase-with-hyphens]
DESCRIPTION: [one line description]
TRIGGERS: [comma-separated trigger words]
REQUIRES: [comma-separated context keys needed]
PRODUCES: [comma-separated context keys produced]
INSTRUCTIONS:
[markdown instructions for the agent]
"""

        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=1500),
            )
            return self._parse_skill_from_llm(result.text, pattern)
        except Exception:
            # Fall back to heuristic
            return self._generate_skill_heuristic(pattern, success_criteria)

    def _parse_skill_from_llm(
        self,
        text: str,
        pattern: ExecutionPattern,
    ) -> Skill:
        """Parse skill from LLM output."""
        import re

        lines = text.strip().split("\n")
        name = self._slugify(pattern.goal)[:50]
        description = f"Learned: {pattern.goal[:80]}"
        triggers: list[str] = []
        requires: list[str] = []
        produces: list[str] = []
        instructions_lines: list[str] = []
        in_instructions = False

        for line in lines:
            if line.startswith("NAME:"):
                name = line[5:].strip().lower().replace(" ", "-")[:50]
            elif line.startswith("DESCRIPTION:"):
                description = line[12:].strip()
            elif line.startswith("TRIGGERS:"):
                triggers = [t.strip() for t in line[9:].split(",") if t.strip()]
            elif line.startswith("REQUIRES:"):
                requires = [r.strip() for r in line[9:].split(",") if r.strip()]
            elif line.startswith("PRODUCES:"):
                produces = [p.strip() for p in line[9:].split(",") if p.strip()]
            elif line.startswith("INSTRUCTIONS:"):
                in_instructions = True
            elif in_instructions:
                instructions_lines.append(line)

        instructions = "\n".join(instructions_lines).strip()
        if not instructions:
            instructions = f"## Goal\n{pattern.goal}\n\n## Steps\n{pattern.steps_description}"

        # Validate name
        name = _RE_SLUG_INVALID.sub("", name.lower())
        if not name or name[0].isdigit():
            name = f"learned-{name or 'skill'}"

        return Skill(
            name=name,
            description=description,
            skill_type=SkillType.INLINE,
            instructions=instructions,
            triggers=tuple(triggers),
            requires=tuple(requires),
            produces=tuple(produces),
            allowed_tools=tuple(set(pattern.tools_used)),
        )

    def _slugify(self, text: str) -> str:
        """Convert text to a valid skill name slug."""
        # Lowercase and replace spaces/special chars with hyphens
        slug = _RE_SLUG_SPECIAL.sub("-", text.lower())
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Collapse multiple hyphens
        slug = _RE_SLUG_MULTI_HYPHEN.sub("-", slug)
        # Ensure it starts with a letter
        if slug and slug[0].isdigit():
            slug = f"skill-{slug}"
        return slug or "learned-skill"

    def _extract_triggers(self, goal: str) -> list[str]:
        """Extract trigger keywords from goal text."""
        # Common action words that might trigger this skill
        words = _RE_WORD_BOUNDARY.findall(goal.lower())

        # Filter to meaningful triggers
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "up", "about", "into", "through", "during",
            "before", "after", "above", "below", "between", "under", "this", "that",
            "these", "those", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "i", "you",
            "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
        }

        triggers = [w for w in words if len(w) > 3 and w not in stopwords]
        return triggers[:5]  # Limit to 5 triggers


@dataclass(frozen=True, slots=True)
class SkillLearningResult:
    """Result of skill learning operation."""

    success: bool
    """Whether learning succeeded."""

    skill: Skill | None = None
    """The learned skill, if successful."""

    pattern: ExecutionPattern | None = None
    """The extracted pattern."""

    message: str = ""
    """Status message."""

    metadata: LearnedSkillMetadata | None = None
    """Metadata about the learning."""
