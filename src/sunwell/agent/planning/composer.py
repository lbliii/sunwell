"""Skill composition for dynamic capability expansion (RFC-111 Phase 4).

This module implements the SkillComposer — Sunwell's ability to CREATE
its own capability graphs, not just execute predefined ones.

The key innovation: Given a complex goal, the composer can:
1. Analyze the goal to identify needed capabilities
2. Match capabilities to existing skills
3. Generate inline skills for gaps
4. Build an optimized DAG
5. Self-heal if validation fails

This creates a self-improving system where Sunwell becomes more capable
over time by composing and generating new skills.

Example:
    >>> composer = SkillComposer(skills=library.skills, model=model)
    >>> graph = await composer.compose_for_goal("Build a REST API with auth")
    >>> # Returns DAG with skills for: scaffold → auth → routes → tests
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sunwell.planning.skills.graph import SkillGraph
from sunwell.planning.skills.types import Skill, SkillDependency, SkillMetadata, SkillType

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

# Pre-compiled regex for skill name extraction
_RE_SKILL_NAME = re.compile(r"'([a-z-]+)'")


# =============================================================================
# COMPOSITION TYPES
# =============================================================================


class CompositionType(Enum):
    """How skills should be composed together."""

    SEQUENCE = "sequence"
    """Execute in order with data flow between skills."""

    PARALLEL = "parallel"
    """Execute independently and merge results."""

    CONDITIONAL = "conditional"
    """Execute based on context values."""

    FALLBACK = "fallback"
    """Try skills in order, stop on first success."""


# =============================================================================
# COMPOSITION RESULTS
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompositionResult:
    """Result of a skill composition operation."""

    skill: Skill
    """The composed skill."""

    source_skills: tuple[str, ...]
    """Names of skills that were composed."""

    composition_type: CompositionType
    """How skills were composed."""

    generated: bool = False
    """Whether any skills were generated (not just composed)."""


@dataclass(frozen=True, slots=True)
class CapabilityAnalysis:
    """Analysis of capabilities needed for a goal."""

    capabilities: tuple[str, ...]
    """Identified capability descriptions."""

    matched_skills: tuple[str, ...]
    """Skills that match needed capabilities."""

    gaps: tuple[str, ...]
    """Capability gaps with no matching skill."""

    suggested_flow: str | None = None
    """Suggested data flow between capabilities."""


# =============================================================================
# SKILL COMPOSER
# =============================================================================


@dataclass(slots=True)
class SkillComposer:
    """Dynamically compose and generate skills (RFC-111 Phase 4).

    This is Sunwell's secret weapon: the agent can CREATE
    its own capability graphs, not just execute predefined ones.

    The composer supports three operations:
    1. compose_for_goal: Analyze goal → generate complete skill graph
    2. compose_skills: Combine existing skills into a workflow
    3. generate_skill: Create a single skill for a capability gap

    Attributes:
        skills: Available skills to compose from
        model: Model for capability extraction and skill generation
    """

    skills: list[Skill] | tuple[Skill, ...] = field(default_factory=list)
    """Available skills to compose from."""

    model: ModelProtocol | None = None
    """Model for natural language understanding and generation."""

    max_generated_skills: int = 5
    """Maximum skills to generate for a single goal."""

    # Internal indexes (init=False means they're set in __post_init__)
    _skill_by_name: dict[str, Skill] = field(default_factory=dict, init=False)
    """Index for fast skill lookup by name."""

    _metadata: list[SkillMetadata] = field(default_factory=list, init=False)
    """Precomputed metadata for all skills."""

    _producers: dict[str, str] = field(default_factory=dict, init=False)
    """Mapping of produced keys to skill names."""

    def __post_init__(self) -> None:
        """Build skill index for fast lookup."""
        self._skill_by_name = {s.name: s for s in self.skills}
        self._metadata = [SkillMetadata.from_skill(s) for s in self.skills]
        self._producers = {}
        for skill in self.skills:
            for key in skill.produces:
                self._producers[key] = skill.name

    async def compose_for_goal(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> SkillGraph:
        """Generate a skill graph to accomplish a complex goal.

        This is the main entry point for dynamic composition.
        Given a goal, it:
        1. Analyzes the goal to identify needed capabilities
        2. Matches capabilities to existing skills
        3. Generates inline skills for gaps
        4. Builds an optimized DAG with inferred dependencies
        5. Self-heals if validation fails

        Args:
            goal: Natural language description of what to accomplish
            context: Optional context with known values

        Returns:
            SkillGraph ready for compilation

        Example:
            >>> graph = await composer.compose_for_goal("Build REST API with auth")
            >>> print(graph.execution_waves())
            [['scaffold-project'], ['add-auth', 'add-routes'], ['add-tests']]
        """
        context = context or {}

        # Step 1: Analyze goal for capabilities
        analysis = await self._analyze_goal(goal)

        # Step 2: Collect matched skills
        matched_skills = [
            self._skill_by_name[name]
            for name in analysis.matched_skills
            if name in self._skill_by_name
        ]

        # Step 3: Generate skills for gaps
        generated_skills: list[Skill] = []
        if analysis.gaps and self.model:
            for gap in analysis.gaps[: self.max_generated_skills]:
                skill = await self._generate_skill_for_gap(gap, context)
                if skill:
                    generated_skills.append(skill)

        # Step 4: Build DAG
        all_skills = matched_skills + generated_skills
        if not all_skills:
            # No skills found - generate a single task skill
            fallback = await self._generate_fallback_skill(goal, context)
            if fallback:
                all_skills = [fallback]

        graph = self._build_dag_from_contracts(all_skills)

        # Step 5: Validate and self-heal
        errors = graph.validate()
        if errors and self.model:
            graph = await self._self_heal_graph(graph, errors, goal)

        return graph

    def compose_skills(
        self,
        skill_names: list[str],
        composition_type: CompositionType = CompositionType.SEQUENCE,
        name: str | None = None,
        description: str | None = None,
    ) -> CompositionResult:
        """Compose multiple skills into a new reusable skill.

        This creates a meta-skill that orchestrates other skills
        according to the composition type.

        Args:
            skill_names: Names of skills to compose
            composition_type: How to compose (sequence, parallel, etc.)
            name: Name for composed skill (auto-generated if None)
            description: Description (auto-generated if None)

        Returns:
            CompositionResult with the new skill

        Example:
            >>> result = composer.compose_skills(
            ...     ["read-file", "analyze-code", "generate-report"],
            ...     CompositionType.SEQUENCE,
            ... )
            >>> print(result.skill.name)
            'read-file-analyze-code-generate-report-sequence'
        """
        # Get the skills
        skills_to_compose = [
            self._skill_by_name[n]
            for n in skill_names
            if n in self._skill_by_name
        ]

        if not skills_to_compose:
            raise ValueError(f"No valid skills found: {skill_names}")

        # Generate name if not provided
        if not name:
            name = "-".join(s.name for s in skills_to_compose[:3])
            if len(skills_to_compose) > 3:
                name += f"-and-{len(skills_to_compose) - 3}-more"
            name += f"-{composition_type.value}"

        # Generate description
        if not description:
            skill_descs = ", ".join(s.name for s in skills_to_compose)
            description = f"Composed skill: {composition_type.value} of [{skill_descs}]"

        # Build depends_on, requires, produces based on composition type
        if composition_type == CompositionType.SEQUENCE:
            composed = self._compose_sequence(skills_to_compose, name, description)
        elif composition_type == CompositionType.PARALLEL:
            composed = self._compose_parallel(skills_to_compose, name, description)
        elif composition_type == CompositionType.CONDITIONAL:
            composed = self._compose_conditional(skills_to_compose, name, description)
        else:
            composed = self._compose_fallback(skills_to_compose, name, description)

        return CompositionResult(
            skill=composed,
            source_skills=tuple(skill_names),
            composition_type=composition_type,
            generated=False,
        )

    async def generate_skill(
        self,
        capability: str,
        requires: tuple[str, ...] = (),
        produces: tuple[str, ...] = (),
    ) -> Skill | None:
        """Generate a single skill for a capability.

        Args:
            capability: What the skill should accomplish
            requires: Context keys needed as input
            produces: Context keys to output

        Returns:
            Generated Skill or None if generation fails
        """
        if not self.model:
            return None

        return await self._generate_skill_for_gap(
            capability,
            context={"requires": requires, "produces": produces},
        )

    # =========================================================================
    # INTERNAL: Goal Analysis
    # =========================================================================

    async def _analyze_goal(self, goal: str) -> CapabilityAnalysis:
        """Analyze a goal to identify needed capabilities."""
        if not self.model:
            # Heuristic analysis without model
            return self._analyze_goal_heuristic(goal)

        prompt = f"""
Analyze this goal and identify what capabilities are needed:

Goal: {goal}

Available skills:
{self._format_available_skills()}

For each capability needed:
1. Check if an existing skill can provide it
2. If not, describe what capability is missing

Format your response as:
CAPABILITIES:
- capability 1 description
- capability 2 description

MATCHED_SKILLS:
- skill-name-1
- skill-name-2

GAPS:
- gap description 1
- gap description 2

SUGGESTED_FLOW:
skill-1 -> skill-2 -> skill-3
"""
        response = await self.model.generate(prompt)
        return self._parse_capability_analysis(response.content)

    def _analyze_goal_heuristic(self, goal: str) -> CapabilityAnalysis:
        """Heuristic goal analysis without LLM."""
        goal_lower = goal.lower()
        matched: list[str] = []

        # Match by triggers
        for meta in self._metadata:
            for trigger in meta.triggers:
                if trigger.lower() in goal_lower:
                    if meta.name not in matched:
                        matched.append(meta.name)
                    break

        # Match by name
        for meta in self._metadata:
            name_words = meta.name.replace("-", " ")
            if name_words in goal_lower:
                if meta.name not in matched:
                    matched.append(meta.name)

        return CapabilityAnalysis(
            capabilities=(),
            matched_skills=tuple(matched),
            gaps=(),
        )

    def _format_available_skills(self) -> str:
        """Format available skills for LLM prompt."""
        lines = []
        for meta in self._metadata:
            lines.append(f"- {meta.name}: {meta.description}")
            if meta.produces:
                lines.append(f"  produces: {', '.join(meta.produces)}")
            if meta.requires:
                lines.append(f"  requires: {', '.join(meta.requires)}")
        return "\n".join(lines)

    def _parse_capability_analysis(self, content: str) -> CapabilityAnalysis:
        """Parse LLM response into CapabilityAnalysis."""
        capabilities: list[str] = []
        matched: list[str] = []
        gaps: list[str] = []
        suggested_flow: str | None = None

        section = ""
        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("CAPABILITIES:"):
                section = "cap"
            elif line.startswith("MATCHED_SKILLS:"):
                section = "matched"
            elif line.startswith("GAPS:"):
                section = "gaps"
            elif line.startswith("SUGGESTED_FLOW:"):
                section = "flow"
            elif line.startswith("- "):
                item = line[2:].strip()
                if section == "cap":
                    capabilities.append(item)
                elif section == "matched":
                    matched.append(item)
                elif section == "gaps":
                    gaps.append(item)
            elif section == "flow" and line:
                suggested_flow = line

        return CapabilityAnalysis(
            capabilities=tuple(capabilities),
            matched_skills=tuple(matched),
            gaps=tuple(gaps),
            suggested_flow=suggested_flow,
        )

    # =========================================================================
    # INTERNAL: Skill Generation
    # =========================================================================

    async def _generate_skill_for_gap(
        self,
        gap: str,
        context: dict[str, Any],
    ) -> Skill | None:
        """Generate a skill to fill a capability gap."""
        if not self.model:
            return None

        requires = context.get("requires", ())
        produces = context.get("produces", ())

        prompt = f"""
Generate a skill definition for this capability:

Capability: {gap}
Required inputs: {requires if requires else "determine from capability"}
Expected outputs: {produces if produces else "determine from capability"}

Generate a skill in this exact format:
NAME: lowercase-with-hyphens
DESCRIPTION: one line description
REQUIRES: comma-separated context keys (or "none")
PRODUCES: comma-separated context keys
INSTRUCTIONS:
Clear step-by-step instructions to accomplish this capability.
"""
        response = await self.model.generate(prompt)
        return self._parse_generated_skill(response.content, gap)

    async def _generate_fallback_skill(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> Skill | None:
        """Generate a fallback skill when no matches found."""
        if not self.model:
            return Skill(
                name="accomplish-goal",
                description=f"Accomplish: {goal[:50]}",
                skill_type=SkillType.INLINE,
                instructions=f"Goal: {goal}\n\nAccomplish this goal using available tools.",
            )

        prompt = f"""
Generate a skill to accomplish this goal:

Goal: {goal}

No existing skills matched. Create a comprehensive skill that can accomplish this.

Format:
NAME: lowercase-with-hyphens
DESCRIPTION: one line
INSTRUCTIONS:
Detailed steps to accomplish the goal.
"""
        response = await self.model.generate(prompt)
        return self._parse_generated_skill(response.content, goal)

    def _parse_generated_skill(self, content: str, fallback_desc: str) -> Skill | None:
        """Parse generated skill content."""
        try:
            name = ""
            description = ""
            requires: list[str] = []
            produces: list[str] = []
            instructions: list[str] = []
            in_instructions = False

            for line in content.strip().split("\n"):
                line_stripped = line.strip()

                if line_stripped.startswith("NAME:"):
                    name = line_stripped[5:].strip().lower().replace(" ", "-")
                elif line_stripped.startswith("DESCRIPTION:"):
                    description = line_stripped[12:].strip()
                elif line_stripped.startswith("REQUIRES:"):
                    req_str = line_stripped[9:].strip()
                    if req_str.lower() != "none":
                        requires = [r.strip() for r in req_str.split(",") if r.strip()]
                elif line_stripped.startswith("PRODUCES:"):
                    prod_str = line_stripped[9:].strip()
                    if prod_str.lower() != "none":
                        produces = [p.strip() for p in prod_str.split(",") if p.strip()]
                elif line_stripped.startswith("INSTRUCTIONS:"):
                    in_instructions = True
                elif in_instructions:
                    instructions.append(line)

            # Validate and create
            if not name:
                # Generate name from description
                words = (description or fallback_desc)[:30].lower().split()[:3]
                name = "-".join(w for w in words if w.isalnum())
                if not name:
                    name = "generated-skill"

            return Skill(
                name=name,
                description=description or fallback_desc[:100],
                skill_type=SkillType.INLINE,
                requires=tuple(requires),
                produces=tuple(produces),
                instructions="\n".join(instructions) or f"Accomplish: {fallback_desc}",
            )
        except Exception:
            return None

    # =========================================================================
    # INTERNAL: DAG Building
    # =========================================================================

    def _build_dag_from_contracts(self, skills: list[Skill]) -> SkillGraph:
        """Build DAG from produces/requires contracts."""
        # Build producer index
        producers: dict[str, str] = {}
        for skill in skills:
            for key in skill.produces:
                producers[key] = skill.name

        # Infer dependencies
        skills_with_deps: list[Skill] = []
        skill_names = {s.name for s in skills}

        for skill in skills:
            # Find dependencies based on requires
            inferred_deps: list[SkillDependency] = []
            for required_key in skill.requires:
                if required_key in producers:
                    producer = producers[required_key]
                    if producer != skill.name and producer in skill_names:
                        inferred_deps.append(SkillDependency(source=producer))

            # Merge with existing
            existing_names = {d.skill_name for d in skill.depends_on}
            for dep in inferred_deps:
                if dep.skill_name not in existing_names:
                    existing_names.add(dep.skill_name)

            all_deps = list(skill.depends_on) + [
                d for d in inferred_deps
                if d.skill_name not in {e.skill_name for e in skill.depends_on}
            ]

            # Filter to skills in our set
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

    async def _self_heal_graph(
        self,
        graph: SkillGraph,
        errors: list[str],
        goal: str,
    ) -> SkillGraph:
        """Attempt to fix graph validation errors."""
        if not self.model:
            return graph

        # Identify missing dependencies
        missing_skills: set[str] = set()
        for error in errors:
            if "non-existent" in error:
                # Extract skill names from error
                matches = _RE_SKILL_NAME.findall(error)
                missing_skills.update(matches)

        if not missing_skills:
            return graph

        # Generate missing skills
        new_skills = list(graph)
        for missing in missing_skills:
            skill = await self._generate_skill_for_gap(
                f"Provide capability: {missing.replace('-', ' ')}",
                context={},
            )
            if skill:
                # Override name to match expected
                skill = Skill(
                    name=missing,
                    description=skill.description,
                    skill_type=skill.skill_type,
                    produces=skill.produces,
                    requires=skill.requires,
                    instructions=skill.instructions,
                )
                new_skills.append(skill)

        return self._build_dag_from_contracts(new_skills)

    # =========================================================================
    # INTERNAL: Composition Strategies
    # =========================================================================

    def _compose_sequence(
        self,
        skills: list[Skill],
        name: str,
        description: str,
    ) -> Skill:
        """Compose skills as a sequence with data flow."""
        # Collect all requires and produces
        all_requires: set[str] = set()
        all_produces: set[str] = set()

        for skill in skills:
            all_requires.update(skill.requires)
            all_produces.update(skill.produces)

        # External requires = requires not satisfied by internal produces
        internal_produces: set[str] = set()
        for skill in skills:
            internal_produces.update(skill.produces)

        external_requires = all_requires - internal_produces

        # Build instructions
        steps = "\n".join(
            f"{i+1}. Execute {s.name}: {s.description}"
            for i, s in enumerate(skills)
        )

        return Skill(
            name=name,
            description=description,
            skill_type=SkillType.INLINE,
            requires=tuple(external_requires),
            produces=tuple(all_produces),
            instructions=f"""
## Composed Sequence

Execute these skills in order, passing data between them:

{steps}

Each skill's outputs become available to subsequent skills.
""",
        )

    def _compose_parallel(
        self,
        skills: list[Skill],
        name: str,
        description: str,
    ) -> Skill:
        """Compose skills as parallel execution."""
        all_requires: set[str] = set()
        all_produces: set[str] = set()

        for skill in skills:
            all_requires.update(skill.requires)
            all_produces.update(skill.produces)

        skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)

        return Skill(
            name=name,
            description=description,
            skill_type=SkillType.INLINE,
            requires=tuple(all_requires),
            produces=tuple(all_produces),
            instructions=f"""
## Parallel Composition

Execute these skills concurrently:

{skill_list}

Merge all outputs when all skills complete.
""",
        )

    def _compose_conditional(
        self,
        skills: list[Skill],
        name: str,
        description: str,
    ) -> Skill:
        """Compose skills with conditional execution."""
        all_requires: set[str] = set()
        all_produces: set[str] = set()

        for skill in skills:
            all_requires.update(skill.requires)
            all_produces.update(skill.produces)

        conditions = "\n".join(
            f"- If condition_{i}: Execute {s.name}"
            for i, s in enumerate(skills)
        )

        return Skill(
            name=name,
            description=description,
            skill_type=SkillType.INLINE,
            requires=tuple(all_requires),
            produces=tuple(all_produces),
            instructions=f"""
## Conditional Composition

Execute skills based on conditions:

{conditions}

Evaluate conditions and execute matching skills.
""",
        )

    def _compose_fallback(
        self,
        skills: list[Skill],
        name: str,
        description: str,
    ) -> Skill:
        """Compose skills as fallback chain."""
        all_requires: set[str] = set()
        all_produces: set[str] = set()

        for skill in skills:
            all_requires.update(skill.requires)
            all_produces.update(skill.produces)

        chain = "\n".join(
            f"{i+1}. Try {s.name} - if fails, continue"
            for i, s in enumerate(skills)
        )

        return Skill(
            name=name,
            description=description,
            skill_type=SkillType.INLINE,
            requires=tuple(all_requires),
            produces=tuple(all_produces),
            instructions=f"""
## Fallback Composition

Try skills in order until one succeeds:

{chain}

Stop at first successful skill.
""",
        )
