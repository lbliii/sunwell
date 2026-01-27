"""Goal-based planning with skill DAGs (RFC-111).

This module implements the GoalPlanner — the core UX innovation that allows
users to state goals in natural language while Sunwell generates optimal
skill DAGs for execution.

The key insight: Users never write DAGs. They state goals. Sunwell:
1. Analyzes the goal to identify needed capabilities
2. Matches capabilities to existing skills
3. Infers dependencies from produces/requires contracts
4. Fills gaps with generated skills (if needed)
5. Returns a compiled TaskGraph ready for Naaru

Example:
    >>> planner = GoalPlanner(skill_library=library, model=model)
    >>> graph = await planner.plan("Audit the API docs for accuracy")
    >>> # Returns DAG: read-file → extract-api → audit-docs → fix-issues
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.planning.skills.graph import SkillGraph
from sunwell.planning.skills.types import Skill, SkillDependency, SkillMetadata, SkillType

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


# =============================================================================
# CAPABILITY MATCHING
# =============================================================================


@dataclass(frozen=True, slots=True)
class CapabilityMatch:
    """A skill that matches a required capability."""

    skill_name: str
    """Name of the matching skill."""

    capability: str
    """The capability this skill provides."""

    confidence: float
    """Confidence of the match (0.0-1.0)."""


@dataclass(frozen=True, slots=True)
class CapabilityGap:
    """A capability that has no matching skill."""

    description: str
    """What capability is missing."""

    requires: tuple[str, ...]
    """Context keys this capability would need."""

    produces: tuple[str, ...]
    """Context keys this capability would produce."""


# =============================================================================
# GOAL PLANNER
# =============================================================================


@dataclass(slots=True)
class GoalPlanner:
    """Translate natural language goals into skill DAGs (RFC-111).

    This is what makes DAGs fun: you don't write them.

    The planner:
    1. Analyzes the goal to identify required capabilities
    2. Matches capabilities to existing skills
    3. Builds a DAG from produces/requires contracts
    4. Optionally generates skills to fill gaps

    Attributes:
        skills: Available skills to match against
        model: Optional model for capability extraction and gap filling
    """

    skills: list[Skill] | tuple[Skill, ...] = field(default_factory=list)
    """Available skills to plan with."""

    model: ModelProtocol | None = None
    """Model for natural language understanding (optional)."""

    # Internal lookup tables (initialized in __post_init__)
    _skill_by_name: dict[str, Skill] = field(default_factory=dict, init=False, repr=False)
    _metadata: list[SkillMetadata] = field(default_factory=list, init=False, repr=False)
    _producers: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Build skill index for fast lookup."""
        self._skill_by_name = {s.name: s for s in self.skills}
        self._metadata = [SkillMetadata.from_skill(s) for s in self.skills]
        self._producers = {}  # context_key → skill_name
        for skill in self.skills:
            for key in skill.produces:
                self._producers[key] = skill.name

    async def plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> SkillGraph:
        """Convert a goal into an executable skill graph.

        Args:
            goal: Natural language description of what to accomplish
            context: Optional context with known values

        Returns:
            SkillGraph ready for compilation and execution

        Example:
            >>> goal = "Audit the API documentation for accuracy"
            >>> graph = await planner.plan(goal)
            >>> # Returns DAG: read-file → extract-api → audit-docs
        """
        context = context or {}

        # Step 1: Identify what capabilities are needed
        capabilities = await self._identify_capabilities(goal)

        # Step 2: Match capabilities to existing skills
        matched, gaps = self._match_skills(capabilities)

        # Step 3: Build graph from matched skills
        if not matched and not gaps:
            # No matches — try direct skill name matching
            matched = self._match_skills_by_name(goal)

        skills_to_use = [self._skill_by_name[m.skill_name] for m in matched]

        # Step 4: Fill gaps with generated skills (if model available)
        if gaps and self.model:
            generated = await self._generate_skills_for_gaps(gaps)
            skills_to_use.extend(generated)

        # Step 5: Build DAG from produces/requires contracts
        graph = self._build_graph_from_contracts(skills_to_use)

        return graph

    def plan_sync(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> SkillGraph:
        """Synchronous version of plan() for simple cases.

        Uses heuristic matching only (no LLM capability extraction).
        """
        context = context or {}

        # Match skills by name and triggers
        matched = self._match_skills_by_name(goal)

        if not matched:
            # Fall back to trigger matching
            matched = self._match_skills_by_triggers(goal)

        skills_to_use = [self._skill_by_name[m.skill_name] for m in matched]

        return self._build_graph_from_contracts(skills_to_use)

    async def _identify_capabilities(self, goal: str) -> list[str]:
        """Identify capabilities needed to accomplish a goal.

        If model is available, uses LLM to extract capabilities.
        Otherwise, uses keyword extraction.
        """
        if self.model:
            prompt = f"""
Given this goal, identify what capabilities are needed to accomplish it.
Return a list of capability descriptions, one per line.

Goal: {goal}

Capabilities needed (one per line):
"""
            response = await self.model.generate(prompt)
            lines = response.content.strip().split("\n")
            return [line.strip("- ").strip() for line in lines if line.strip()]

        # Fallback: extract keywords
        keywords = goal.lower().split()
        return keywords

    def _match_skills(
        self,
        capabilities: list[str],
    ) -> tuple[list[CapabilityMatch], list[CapabilityGap]]:
        """Match capabilities to skills, identifying gaps."""
        matched: list[CapabilityMatch] = []
        gaps: list[CapabilityGap] = []

        for cap in capabilities:
            best_match: CapabilityMatch | None = None
            best_score = 0.0

            for meta in self._metadata:
                score = meta.matches_intent(cap)
                if score > best_score and score > 0.3:
                    best_score = score
                    best_match = CapabilityMatch(
                        skill_name=meta.name,
                        capability=cap,
                        confidence=score,
                    )

            if best_match:
                # Avoid duplicates
                if not any(m.skill_name == best_match.skill_name for m in matched):
                    matched.append(best_match)
            else:
                gaps.append(CapabilityGap(
                    description=cap,
                    requires=(),
                    produces=(),
                ))

        return matched, gaps

    def _match_skills_by_name(self, goal: str) -> list[CapabilityMatch]:
        """Match skills directly by name in goal."""
        matched: list[CapabilityMatch] = []
        goal_lower = goal.lower()

        for skill in self.skills:
            # Check if skill name appears in goal
            if skill.name.replace("-", " ") in goal_lower or skill.name in goal_lower:
                matched.append(CapabilityMatch(
                    skill_name=skill.name,
                    capability=skill.description,
                    confidence=0.9,
                ))

        return matched

    def _match_skills_by_triggers(self, goal: str) -> list[CapabilityMatch]:
        """Match skills by trigger patterns."""
        matched: list[CapabilityMatch] = []
        goal_lower = goal.lower()

        for meta in self._metadata:
            for trigger in meta.triggers:
                if trigger.lower() in goal_lower:
                    if not any(m.skill_name == meta.name for m in matched):
                        matched.append(CapabilityMatch(
                            skill_name=meta.name,
                            capability=meta.description,
                            confidence=0.7,
                        ))
                    break

        return matched

    def _build_graph_from_contracts(
        self,
        skills: list[Skill],
    ) -> SkillGraph:
        """Build DAG by inferring dependencies from produces/requires.

        This is the magic: users declare contracts, not edges.
        The DAG builds itself from data flow.
        """
        # Build producer index from the selected skills
        producers: dict[str, str] = {}
        for skill in skills:
            for key in skill.produces:
                producers[key] = skill.name

        # Build skills with inferred dependencies
        skills_with_deps: list[Skill] = []

        for skill in skills:
            # Find dependencies based on requires
            inferred_deps: list[SkillDependency] = []
            for required_key in skill.requires:
                if required_key in producers:
                    producer_name = producers[required_key]
                    # Don't add self-dependency
                    if producer_name != skill.name:
                        inferred_deps.append(SkillDependency(source=producer_name))

            # Merge with existing depends_on
            existing_dep_names = {d.skill_name for d in skill.depends_on}
            for dep in inferred_deps:
                if dep.skill_name not in existing_dep_names:
                    existing_dep_names.add(dep.skill_name)

            # Create skill with merged dependencies
            all_deps = tuple(skill.depends_on) + tuple(
                d for d in inferred_deps if d.skill_name not in {
                    e.skill_name for e in skill.depends_on
                }
            )

            # Filter deps to only include skills in our set
            skill_names = {s.name for s in skills}
            filtered_deps = tuple(d for d in all_deps if d.skill_name in skill_names)

            skills_with_deps.append(Skill(
                name=skill.name,
                description=skill.description,
                skill_type=skill.skill_type,
                depends_on=filtered_deps,
                produces=skill.produces,
                requires=skill.requires,
                triggers=skill.triggers,
                instructions=skill.instructions,
                scripts=skill.scripts,
                templates=skill.templates,
                resources=skill.resources,
                preset=skill.preset,
                permissions=skill.permissions,
                security=skill.security,
                trust=skill.trust,
                timeout=skill.timeout,
                validate_with=skill.validate_with,
            ))

        return SkillGraph.from_skills(skills_with_deps)

    async def _generate_skills_for_gaps(
        self,
        gaps: list[CapabilityGap],
    ) -> list[Skill]:
        """Generate inline skills for capability gaps.

        This is where Sunwell creates new skills on-the-fly.
        """
        if not self.model:
            return []

        generated: list[Skill] = []

        for gap in gaps:
            prompt = f"""
Generate a skill definition for this capability:

Capability: {gap.description}
Required inputs: {gap.requires}
Expected outputs: {gap.produces}

Generate a skill with:
- name: lowercase with hyphens (e.g., "analyze-code")
- description: one line
- instructions: clear steps to accomplish the capability

Format as YAML:
name: ...
description: ...
instructions: |
  ...
"""
            response = await self.model.generate(prompt)

            # Parse the response (simple YAML extraction)
            skill = self._parse_generated_skill(response.content, gap)
            if skill:
                generated.append(skill)

        return generated

    def _parse_generated_skill(
        self,
        content: str,
        gap: CapabilityGap,
    ) -> Skill | None:
        """Parse generated skill content into a Skill object."""
        try:
            # Simple YAML parsing for name, description, instructions
            lines = content.strip().split("\n")
            name = ""
            description = ""
            instructions_lines: list[str] = []
            in_instructions = False

            for line in lines:
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("instructions:"):
                    in_instructions = True
                elif in_instructions:
                    instructions_lines.append(line)

            if not name:
                name = f"generated-{gap.description[:20].replace(' ', '-').lower()}"
            if not description:
                description = gap.description

            return Skill(
                name=name,
                description=description,
                skill_type=SkillType.INLINE,
                instructions="\n".join(instructions_lines) or f"Accomplish: {gap.description}",
                requires=gap.requires,
                produces=gap.produces,
            )
        except Exception:
            return None


# =============================================================================
# SHORTCUT MAPPINGS
# =============================================================================

# Map CLI shortcuts to skill names
SHORTCUT_SKILL_MAP: dict[str, set[str]] = {
    # Documentation shortcuts
    "a": {"audit-documentation"},
    "a-2": {"audit-documentation", "fix-documentation-issues"},
    "d": {"create-api-reference"},
    "q": {"create-quickstart"},
    "arch": {"create-architecture-doc"},

    # Analysis shortcuts
    "api": {"extract-api-surface"},
    "deps": {"analyze-dependencies"},
    "map": {"map-codebase-structure"},

    # Validation shortcuts
    "links": {"check-documentation-links"},
    "examples": {"validate-code-examples"},
}


def get_skills_for_shortcut(shortcut: str) -> set[str]:
    """Get skill names for a CLI shortcut.

    Args:
        shortcut: The shortcut identifier (e.g., "a", "a-2")

    Returns:
        Set of skill names to execute
    """
    return SHORTCUT_SKILL_MAP.get(shortcut, set())
