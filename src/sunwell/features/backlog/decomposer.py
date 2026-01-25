"""Epic Decomposition for Hierarchical Goals (RFC-115).

Decomposes ambitious goals (epics) into milestones before detailed planning.

The key insight: You can't plan 200 tasks upfront. But you can plan 8 milestones,
then plan 25 tasks when you reach each one.

Example:
    decomposer = EpicDecomposer(model=model)

    # Detect if goal is an epic
    if await decomposer.is_epic("Build an RTS game"):
        domain = await decomposer.detect_domain("Build an RTS game")
        milestones = await decomposer.decompose("Build an RTS game", domain=domain)
        # Returns ~8 milestones, each with produces/requires
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from sunwell.features.backlog.goals import Goal, GoalScope

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

# Pre-compiled regex patterns for milestone parsing
_MILESTONE_SPLIT_PATTERN = re.compile(r"MILESTONE\s+(\d+)\s*:", re.IGNORECASE)
_PRODUCES_PATTERN = re.compile(r"PRODUCES:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_REQUIRES_PATTERN = re.compile(r"REQUIRES:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_DESCRIPTION_PATTERN = re.compile(
    r"DESCRIPTION:\s*(.+?)(?:\n\n|$)", re.IGNORECASE | re.DOTALL
)
_NUMBER_PATTERN = re.compile(r"\d+")


# =============================================================================
# Domain Detection
# =============================================================================

DOMAIN_DETECTION_PROMPT = """Classify this goal into one domain:

GOAL: {goal}

Output ONLY one of:
- software: Building an app, game, API, CLI tool, library
- novel: Writing fiction, narrative, story, screenplay
- research: Academic paper, analysis, investigation, report
- general: Other multi-phase projects

DOMAIN:"""


async def detect_domain(goal: str, model: "ModelProtocol") -> str:
    """Detect domain for appropriate decomposition strategy.

    Args:
        goal: The epic goal to classify
        model: Model for classification

    Returns:
        One of: "software", "novel", "research", "general"
    """
    from sunwell.models.protocol import GenerateOptions

    prompt = DOMAIN_DETECTION_PROMPT.format(goal=goal)

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.0, max_tokens=20),
    )

    text = result.text.lower().strip()

    if "software" in text:
        return "software"
    if "novel" in text:
        return "novel"
    if "research" in text:
        return "research"
    return "general"


# =============================================================================
# Epic Detection
# =============================================================================

EPIC_DETECTION_PROMPT = """Is this goal ambitious enough to need hierarchical decomposition?

GOAL: {goal}

An epic needs decomposition if:
- It has multiple distinct systems/components
- It would require 50+ tasks to complete
- It spans multiple domains (UI + backend + data)
- Words like "full", "complete", "entire", "build a"
- Examples: "build an RTS game", "write a novel", "create a SaaS platform"

NOT an epic if:
- Single feature or fix
- Clear, bounded scope
- Can be done in <10 tasks
- Examples: "add dark mode", "fix login bug", "refactor auth"

Output ONLY: YES or NO

IS_EPIC:"""


async def is_epic(goal: str, model: "ModelProtocol") -> bool:
    """Detect if goal is an epic requiring hierarchical decomposition.

    Args:
        goal: The goal to check
        model: Model for classification

    Returns:
        True if goal should be treated as an epic
    """
    from sunwell.models.protocol import GenerateOptions

    prompt = EPIC_DETECTION_PROMPT.format(goal=goal)

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.0, max_tokens=10),
    )

    return "YES" in result.text.upper()


# =============================================================================
# Decomposition Prompts
# =============================================================================

SOFTWARE_DECOMPOSITION_PROMPT = """Decompose this software goal into milestones.

Each milestone should:
- Build a coherent subsystem or component
- Produce artifacts other milestones can depend on
- Be completable in 1-4 hours of focused work
- Follow natural architectural boundaries

GOAL: {goal}
{context}

Output format (one milestone per block):
MILESTONE 1: [Title - 3-5 words]
PRODUCES: [comma-separated artifacts this creates]
REQUIRES: [milestone numbers it depends on, or "none"]
DESCRIPTION: [1-2 sentences describing what gets built]

MILESTONE 2: [Title]
...

Generate 5-12 milestones. Start with foundational systems, end with integration/polish."""


NOVEL_DECOMPOSITION_PROMPT = """Decompose this writing goal into milestones.

IMPORTANT: World-building, characters, and plot architecture are ARTIFACTS
that chapters CONSUME. Build foundations before writing chapters.

Structure:
1. World/Setting milestone (produces: setting, era, locations)
2. Character development milestone (produces: protagonist, antagonist, cast)
3. Plot architecture milestone (produces: timeline, structure, themes)
4. Act milestones (chapters grouped by narrative arc)
5. Revision milestone

GOAL: {goal}
{context}

Output format:
MILESTONE 1: [Title]
PRODUCES: [artifacts - e.g., "Detective character", "Crime scene location"]
REQUIRES: [milestone numbers, or "none"]
DESCRIPTION: [1-2 sentences]

MILESTONE 2: ...

Generate 6-10 milestones. Foundation milestones first, then acts, then revision."""


RESEARCH_DECOMPOSITION_PROMPT = """Decompose this research goal into milestones.

Structure:
1. Literature review (produces: sources, prior art, gaps)
2. Methodology (produces: approach, tools, criteria)
3. Data collection/Analysis phases
4. Synthesis/Conclusions
5. Writing/Review

GOAL: {goal}
{context}

Output format:
MILESTONE 1: [Title]
PRODUCES: [artifacts - e.g., "Literature review", "Analysis framework"]
REQUIRES: [milestone numbers, or "none"]
DESCRIPTION: [1-2 sentences]

Generate 5-8 milestones following research methodology."""


GENERAL_DECOMPOSITION_PROMPT = """Decompose this goal into milestones.

Each milestone should:
- Be a coherent phase with clear deliverables
- Produce artifacts other milestones can depend on
- Have reasonable scope (1-4 hours of focused work)

GOAL: {goal}
{context}

Output format:
MILESTONE 1: [Title]
PRODUCES: [artifacts this milestone creates]
REQUIRES: [milestone numbers it depends on, or "none"]
DESCRIPTION: [1-2 sentences]

Generate 5-10 milestones. Order by dependencies (foundations first)."""


DOMAIN_PROMPTS = {
    "software": SOFTWARE_DECOMPOSITION_PROMPT,
    "novel": NOVEL_DECOMPOSITION_PROMPT,
    "research": RESEARCH_DECOMPOSITION_PROMPT,
    "general": GENERAL_DECOMPOSITION_PROMPT,
}


# =============================================================================
# Milestone Parsing
# =============================================================================


@dataclass(frozen=True, slots=True)
class ParsedMilestone:
    """Intermediate representation of a parsed milestone."""

    index: int
    title: str
    produces: tuple[str, ...]
    requires_indices: tuple[int, ...]  # Milestone numbers (1-indexed from prompt)
    description: str


def parse_milestones(text: str) -> list[ParsedMilestone]:
    """Parse milestone decomposition response.

    Args:
        text: Model response containing milestone blocks

    Returns:
        List of ParsedMilestone objects
    """
    milestones: list[ParsedMilestone] = []

    # Split by MILESTONE N: pattern
    blocks = _MILESTONE_SPLIT_PATTERN.split(text)

    # blocks[0] is before first milestone, then pairs of (number, content)
    for i in range(1, len(blocks) - 1, 2):
        index = int(blocks[i])
        content = blocks[i + 1].strip()

        # Parse title (rest of first line)
        lines = content.split("\n")
        title = lines[0].strip()

        # Parse PRODUCES
        produces: list[str] = []
        produces_match = _PRODUCES_PATTERN.search(content)
        if produces_match:
            produces = [p.strip() for p in produces_match.group(1).split(",") if p.strip()]

        # Parse REQUIRES
        requires_indices: list[int] = []
        requires_match = _REQUIRES_PATTERN.search(content)
        if requires_match:
            req_text = requires_match.group(1).strip().lower()
            if req_text != "none":
                # Extract milestone numbers
                numbers = _NUMBER_PATTERN.findall(req_text)
                requires_indices = [int(n) for n in numbers]

        # Parse DESCRIPTION
        description = ""
        desc_match = _DESCRIPTION_PATTERN.search(content)
        if desc_match:
            description = desc_match.group(1).strip()

        milestones.append(
            ParsedMilestone(
                index=index,
                title=title,
                produces=tuple(produces),
                requires_indices=tuple(requires_indices),
                description=description,
            )
        )

    return milestones


def milestones_to_goals(
    parsed: list[ParsedMilestone],
    epic_id: str,
    epic_title: str,
) -> list[Goal]:
    """Convert parsed milestones to Goal objects.

    Args:
        parsed: List of parsed milestones
        epic_id: ID of the parent epic
        epic_title: Title of the parent epic (for ID generation)

    Returns:
        List of Goal objects with proper dependencies
    """
    # Build index→id mapping
    index_to_id: dict[int, str] = {}

    for m in parsed:
        # Generate stable ID
        id_hash = hashlib.blake2b(
            f"{epic_id}:{m.index}:{m.title}".encode(),
            digest_size=4,
        ).hexdigest()
        milestone_id = f"milestone-{id_hash}"
        index_to_id[m.index] = milestone_id

    # Create Goal objects
    goals: list[Goal] = []

    for m in parsed:
        milestone_id = index_to_id[m.index]

        # Convert requires_indices to goal IDs
        requires = frozenset(
            index_to_id[idx]
            for idx in m.requires_indices
            if idx in index_to_id
        )

        goal = Goal(
            id=milestone_id,
            title=m.title,
            description=m.description,
            source_signals=(),
            priority=1.0 - (m.index * 0.01),  # Earlier milestones slightly higher priority
            estimated_complexity="complex",  # Milestones are complex by definition
            requires=requires,
            category="add",
            auto_approvable=False,  # Milestones need human confirmation
            scope=GoalScope(max_files=50, max_lines_changed=5000),
            goal_type="milestone",
            parent_goal_id=epic_id,
            milestone_produces=tuple(m.produces),
            milestone_index=m.index - 1,  # Convert to 0-indexed
        )

        goals.append(goal)

    return goals


# =============================================================================
# EpicDecomposer Class
# =============================================================================


@dataclass(slots=True)
class EpicDecomposer:
    """Decomposes ambitious goals into milestones (RFC-115).

    Example:
        decomposer = EpicDecomposer(model=model)

        # Check if goal needs hierarchical decomposition
        if await decomposer.is_epic("Build an RTS game"):
            epic, milestones = await decomposer.decompose("Build an RTS game")
    """

    model: "ModelProtocol"
    """Model for decomposition (claude/gpt-4 recommended for quality)."""

    domain_hints: dict[str, str] = field(default_factory=dict)
    """Optional domain hints for specific keywords."""

    async def is_epic(self, goal: str) -> bool:
        """Check if goal should be treated as an epic.

        Args:
            goal: The goal to check

        Returns:
            True if goal needs hierarchical decomposition
        """
        return await is_epic(goal, self.model)

    async def detect_domain(self, goal: str) -> Literal["software", "novel", "research", "general"]:
        """Detect domain for appropriate decomposition strategy.

        Args:
            goal: The epic goal

        Returns:
            One of: "software", "novel", "research", "general"
        """
        # Check domain hints first
        goal_lower = goal.lower()
        for keyword, domain in self.domain_hints.items():
            if keyword.lower() in goal_lower:
                return domain  # type: ignore

        return await detect_domain(goal, self.model)  # type: ignore

    async def decompose(
        self,
        goal: str,
        domain: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[Goal, list[Goal]]:
        """Decompose epic into milestones.

        Args:
            goal: The epic goal to decompose
            domain: Optional domain (auto-detected if None)
            context: Optional context (project info, constraints, etc.)

        Returns:
            Tuple of (epic_goal, list_of_milestone_goals)
        """
        from sunwell.models.protocol import GenerateOptions

        # Detect domain if not provided
        if domain is None:
            domain = await self.detect_domain(goal)

        # Get appropriate prompt
        prompt_template = DOMAIN_PROMPTS.get(domain, GENERAL_DECOMPOSITION_PROMPT)

        # Format context
        context_str = ""
        if context:
            context_str = "\nCONTEXT:\n" + "\n".join(
                f"- {k}: {v}" for k, v in context.items()
            )

        prompt = prompt_template.format(goal=goal, context=context_str)

        # Generate decomposition
        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=2000),
        )

        # Parse milestones
        parsed = parse_milestones(result.text)

        if not parsed:
            # Fallback: create single milestone for the whole goal
            parsed = [
                ParsedMilestone(
                    index=1,
                    title=goal[:60],
                    produces=(),
                    requires_indices=(),
                    description=goal,
                )
            ]

        # Generate epic ID
        epic_hash = hashlib.blake2b(goal.encode(), digest_size=6).hexdigest()
        epic_id = f"epic-{epic_hash}"

        # Create epic goal
        epic_goal = Goal(
            id=epic_id,
            title=goal[:100],
            description=goal,
            source_signals=(),
            priority=1.0,
            estimated_complexity="complex",
            requires=frozenset(),
            category="add",
            auto_approvable=False,
            scope=GoalScope(max_files=100, max_lines_changed=20000),
            goal_type="epic",
            parent_goal_id=None,
            milestone_produces=(),
            milestone_index=None,
        )

        # Convert parsed milestones to goals
        milestone_goals = milestones_to_goals(parsed, epic_id, goal)

        return epic_goal, milestone_goals
