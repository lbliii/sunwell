"""Vortex primitives — atomic reasoning operations.

Each primitive is a specific reasoning pattern:
- Interference: Multiple perspectives, agreement as signal
- Dialectic: Thesis/antithesis/synthesis
- Resonance: Iterative refinement with feedback
- Gradient: Decomposition with difficulty estimation
"""


import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import GenerateOptions, ModelProtocol


# Pre-compiled regex patterns for gradient parsing
_SUBTASK_RE = re.compile(r"SUBTASK:\s*(.+?)(?:\||$)", re.IGNORECASE)
_DIFFICULTY_RE = re.compile(r"DIFFICULTY:\s*([\d.]+)", re.IGNORECASE)
_DEPENDS_RE = re.compile(r"DEPENDS:\s*(.+?)(?:\||$)", re.IGNORECASE)



# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True)
class InterferenceResult:
    """Result from interference primitive."""

    perspectives: tuple[str, ...]
    """Raw perspective responses."""

    consensus: str | None
    """Consensus answer if agreement is high."""

    agreement: float
    """Agreement score (0.0-1.0)."""

    pattern: str
    """'constructive' (high agreement) or 'destructive' (disagreement)."""


@dataclass(frozen=True, slots=True)
class DialecticResult:
    """Result from dialectic primitive."""

    thesis: str
    """Argument for."""

    antithesis: str
    """Argument against."""

    synthesis: str
    """Reconciled conclusion."""


@dataclass(frozen=True, slots=True)
class ResonanceResult:
    """Result from resonance primitive."""

    iterations: tuple[str, ...]
    """Response at each iteration."""

    peak_iteration: int
    """Which iteration had best quality."""

    final: str
    """Final refined response."""

    improvement: float
    """Quality improvement from first to peak."""


@dataclass(frozen=True, slots=True)
class Subtask:
    """A decomposed subtask with difficulty estimate."""

    id: str
    description: str
    difficulty: float  # 0.0 = easy, 1.0 = hard
    dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GradientResult:
    """Result from gradient decomposition."""

    subtasks: tuple[Subtask, ...]
    """Decomposed subtasks."""

    easy_count: int
    """Number of easy subtasks (difficulty < 0.4)."""

    hard_count: int
    """Number of hard subtasks (difficulty >= 0.4)."""


# =============================================================================
# Interference
# =============================================================================


PERSPECTIVE_PROMPTS = [
    ("analyst", "As a methodical analyst examining all details"),
    ("skeptic", "As a skeptic looking for flaws"),
    ("pragmatist", "As a pragmatist focused on simplicity"),
    ("expert", "As a domain expert with deep knowledge"),
    ("user", "As an end-user thinking about practicality"),
]


async def interference(
    task: str,
    model: ModelProtocol,
    options: GenerateOptions,
    n_perspectives: int = 3,
) -> InterferenceResult:
    """Run interference primitive — multiple perspectives measure agreement.

    High agreement = constructive interference (amplified confidence).
    Low agreement = destructive interference (signals uncertainty).
    """
    perspectives = []

    for _name, description in PERSPECTIVE_PROMPTS[:n_perspectives]:
        prompt = f"""{description}:

{task}

Your perspective (be concise):"""

        result = await model.generate(prompt, options=options)
        perspectives.append(result.text.strip())

    # Measure agreement via semantic similarity
    if len(perspectives) < 2:
        agreement = 1.0
    else:
        sims = []
        for i in range(len(perspectives)):
            for j in range(i + 1, len(perspectives)):
                sim = SequenceMatcher(
                    None,
                    perspectives[i].lower(),
                    perspectives[j].lower(),
                ).ratio()
                sims.append(sim)
        agreement = sum(sims) / len(sims)

    # Determine consensus (use first perspective if agreement is high)
    consensus = perspectives[0] if agreement >= 0.6 else None
    pattern = "constructive" if agreement >= 0.5 else "destructive"

    return InterferenceResult(
        perspectives=tuple(perspectives),
        consensus=consensus,
        agreement=agreement,
        pattern=pattern,
    )


# =============================================================================
# Dialectic
# =============================================================================


THESIS_PROMPT = """Task: {task}

Argue FOR the most straightforward approach. Be specific.

Thesis:"""


ANTITHESIS_PROMPT = """Task: {task}

Thesis argument: {thesis}

Now argue AGAINST it. Find flaws, edge cases, alternatives.

Antithesis:"""


SYNTHESIS_PROMPT_DIALECTIC = """Task: {task}

Thesis: {thesis}

Antithesis: {antithesis}

Synthesize both perspectives into a balanced conclusion:"""


async def dialectic(
    task: str,
    model: ModelProtocol,
    options: GenerateOptions,
) -> DialecticResult:
    """Run dialectic primitive — thesis/antithesis/synthesis."""
    # Thesis
    result = await model.generate(
        THESIS_PROMPT.format(task=task),
        options=options,
    )
    thesis = result.text.strip()

    # Antithesis
    result = await model.generate(
        ANTITHESIS_PROMPT.format(task=task, thesis=thesis[:200]),
        options=options,
    )
    antithesis = result.text.strip()

    # Synthesis
    result = await model.generate(
        SYNTHESIS_PROMPT_DIALECTIC.format(
            task=task,
            thesis=thesis[:150],
            antithesis=antithesis[:150],
        ),
        options=options,
    )
    synthesis = result.text.strip()

    return DialecticResult(
        thesis=thesis,
        antithesis=antithesis,
        synthesis=synthesis,
    )


# =============================================================================
# Resonance
# =============================================================================


INITIAL_PROMPT = """Task: {task}

Provide your response:"""


FEEDBACK_PROMPT = """Evaluate this response:

{response}

What could be improved? Be specific.

Feedback:"""


REFINE_PROMPT = """Original response:
{original}

Feedback:
{feedback}

Improved response:"""


async def resonance(
    task: str,
    model: ModelProtocol,
    options: GenerateOptions,
    iterations: int = 2,
) -> ResonanceResult:
    """Run resonance primitive — iterative refinement with feedback."""
    responses = []

    # Initial response
    result = await model.generate(
        INITIAL_PROMPT.format(task=task),
        options=options,
    )
    current = result.text.strip()
    responses.append(current)

    # Refinement iterations
    for _ in range(iterations):
        # Get feedback
        result = await model.generate(
            FEEDBACK_PROMPT.format(response=current[:300]),
            options=options,
        )
        feedback = result.text.strip()

        # Refine based on feedback
        result = await model.generate(
            REFINE_PROMPT.format(original=current[:200], feedback=feedback[:150]),
            options=options,
        )
        current = result.text.strip()
        responses.append(current)

    # Simple heuristic: later iterations are better (could use actual quality scoring)
    peak = len(responses) - 1

    return ResonanceResult(
        iterations=tuple(responses),
        peak_iteration=peak,
        final=responses[peak],
        improvement=0.0,  # Would need judge to calculate
    )


# =============================================================================
# Gradient (Decomposition)
# =============================================================================


DECOMPOSE_PROMPT = """Task: {task}

Break this into 3-5 subtasks. For each, estimate difficulty (0.0=easy, 1.0=hard).

Format (one per line):
SUBTASK: [description] | DIFFICULTY: [0.0-1.0] | DEPENDS: [comma-separated ids or "none"]

Example:
SUBTASK: Set up database schema | DIFFICULTY: 0.3 | DEPENDS: none
SUBTASK: Implement API endpoints | DIFFICULTY: 0.6 | DEPENDS: 1

Your decomposition:"""


async def gradient(
    task: str,
    model: ModelProtocol,
    options: GenerateOptions,
) -> GradientResult:
    """Run gradient primitive — decompose with difficulty estimation.

    Easy subtasks can be solved directly.
    Hard subtasks get routed to interference/dialectic.
    """
    result = await model.generate(
        DECOMPOSE_PROMPT.format(task=task),
        options=options,
    )

    subtasks = []
    lines = result.text.strip().split("\n")

    for i, line in enumerate(lines):
        # Parse SUBTASK: ... | DIFFICULTY: ... | DEPENDS: ...
        subtask_match = _SUBTASK_RE.search(line)
        diff_match = _DIFFICULTY_RE.search(line)
        deps_match = _DEPENDS_RE.search(line)

        if subtask_match:
            desc = subtask_match.group(1).strip()

            try:
                difficulty = float(diff_match.group(1)) if diff_match else 0.5
            except ValueError:
                difficulty = 0.5

            deps_str = deps_match.group(1).strip() if deps_match else "none"
            if deps_str.lower() == "none":
                deps = ()
            else:
                deps = tuple(d.strip() for d in deps_str.split(",") if d.strip())

            subtasks.append(Subtask(
                id=str(i + 1),
                description=desc[:100],
                difficulty=min(1.0, max(0.0, difficulty)),
                dependencies=deps,
            ))

    easy = sum(1 for s in subtasks if s.difficulty < 0.4)
    hard = sum(1 for s in subtasks if s.difficulty >= 0.4)

    return GradientResult(
        subtasks=tuple(subtasks),
        easy_count=easy,
        hard_count=hard,
    )
