"""Dialectic Reasoning — Split task into complementary perspectives.

The hypothesis: LLMs don't have unique experiences like humans, so voting
is just sampling the same distribution. Instead, SPLIT the task into
complementary lenses, then recombine.

Like a prism splitting white light into spectra.

Patterns:
    1. Thesis/Antithesis/Synthesis - What's good? What's bad? Reconcile.
    2. Expand/Contract - Generate many, prune ruthlessly.
    3. Structure/Content - Design skeleton, fill details.
    4. Positive/Negative - What TO do vs what NOT to do.

Example:
    >>> from sunwell.archive.naaru_experiments.dialectic import dialectic_decide
    >>>
    >>> result = await dialectic_decide(
    ...     question="How should I structure this REST API?",
    ...     context="Building a user management system",
    ...     model=OllamaModel("gemma3:1b"),
    ... )
    >>> print(result.synthesis)
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


@dataclass(frozen=True, slots=True)
class DialecticResult:
    """Result from dialectic reasoning."""

    thesis: str
    """The 'good' perspective — what ideal looks like."""

    antithesis: str
    """The 'bad' perspective — what to avoid."""

    synthesis: str
    """The reconciled judgment incorporating both."""

    question: str
    """The original question."""


@dataclass(frozen=True, slots=True)
class ExpandContractResult:
    """Result from expand/contract pattern."""

    expansions: tuple[str, ...]
    """Generated options (many)."""

    contractions: tuple[str, ...]
    """Surviving options after critique."""

    selection: str
    """Final selected option."""

    pruning_rationale: str
    """Why options were pruned."""


@dataclass(frozen=True, slots=True)
class StructureContentResult:
    """Result from structure/content split."""

    structure: str
    """The skeleton/architecture."""

    content: str
    """The filled-in details."""

    integrated: str
    """The combined result."""


# =============================================================================
# Thesis / Antithesis / Synthesis
# =============================================================================


async def dialectic_decide(
    question: str,
    context: str | None = None,
    model: ModelProtocol | None = None,
) -> DialecticResult:
    """Split decision into thesis (good) and antithesis (bad), then synthesize.

    Like a debate:
    - Advocate argues FOR the best approach
    - Critic argues what could go WRONG
    - Judge reconciles both into wisdom

    Args:
        question: The question to decide
        context: Optional context
        model: The model to use (same model, different prompts)

    Returns:
        DialecticResult with thesis, antithesis, and synthesis
    """
    from sunwell.models import GenerateOptions

    if model is None:
        from sunwell.models import OllamaModel
        model = OllamaModel(model="gemma3:1b")

    ctx = f"\nContext: {context}" if context else ""

    # Thesis: What does GOOD look like?
    thesis_prompt = f"""You are an ADVOCATE. Your job is to describe the IDEAL outcome.

Question: {question}{ctx}

Describe what an EXCELLENT solution looks like. Focus on:
- What makes it good
- Key qualities of success
- The ideal outcome

Be specific and concrete. 2-3 paragraphs max."""

    # Antithesis: What does BAD look like?
    antithesis_prompt = f"""You are a CRITIC. Your job is to identify DANGERS and PITFALLS.

Question: {question}{ctx}

Describe what could go WRONG. Focus on:
- Common mistakes
- Hidden dangers
- What to AVOID

Be specific and concrete. 2-3 paragraphs max."""

    # Get thesis and antithesis (sequential for local Ollama)
    thesis_response = await model.generate(
        thesis_prompt,
        options=GenerateOptions(temperature=0.7, max_tokens=500),
    )
    thesis = thesis_response.text.strip()

    antithesis_response = await model.generate(
        antithesis_prompt,
        options=GenerateOptions(temperature=0.7, max_tokens=500),
    )
    antithesis = antithesis_response.text.strip()

    # Synthesis: Reconcile both perspectives
    synthesis_prompt = f"""You are a JUDGE. You've heard two perspectives on a question.

Question: {question}{ctx}

ADVOCATE (what's ideal):
{thesis}

CRITIC (what to avoid):
{antithesis}

Now synthesize both into practical wisdom. What should actually be done?
Balance the ideal with the warnings. Be concrete and actionable.
2-3 paragraphs max."""

    synthesis_response = await model.generate(
        synthesis_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=500),
    )
    synthesis = synthesis_response.text.strip()

    return DialecticResult(
        thesis=thesis,
        antithesis=antithesis,
        synthesis=synthesis,
        question=question,
    )


# =============================================================================
# Expand / Contract
# =============================================================================


async def expand_contract(
    question: str,
    n_expansions: int = 5,
    model: ModelProtocol | None = None,
) -> ExpandContractResult:
    """Generate many options, then ruthlessly prune.

    Like brainstorming followed by critical evaluation:
    - Expansion: Generate diverse options without judgment
    - Contraction: Critique and eliminate weak options
    - Selection: Pick the survivor

    Args:
        question: The question/task
        n_expansions: How many options to generate
        model: The model to use

    Returns:
        ExpandContractResult with options, survivors, and selection
    """
    from sunwell.models import GenerateOptions

    if model is None:
        from sunwell.models import OllamaModel
        model = OllamaModel(model="gemma3:1b")

    # Expansion: Generate options
    expand_prompt = f"""Generate {n_expansions} DIFFERENT approaches to this:

{question}

List them numbered 1-{n_expansions}. Each should be meaningfully different.
Be creative — include conventional AND unconventional approaches.
One line each, be concise."""

    expand_response = await model.generate(
        expand_prompt,
        options=GenerateOptions(temperature=0.9, max_tokens=400),
    )

    # Parse expansions
    lines = expand_response.text.strip().split("\n")
    expansions = tuple(
        line.lstrip("0123456789.-) ").strip()
        for line in lines
        if line.strip() and any(c.isalpha() for c in line)
    )[:n_expansions]

    # Contraction: Critique and prune
    options_str = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(expansions))

    contract_prompt = f"""Critically evaluate these options:

{options_str}

ELIMINATE the weakest options. Keep only the 2-3 BEST.
For each eliminated option, briefly say why.

Format:
KEEP: [numbers]
ELIMINATE: [number] - [reason]
..."""

    contract_response = await model.generate(
        contract_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=400),
    )

    # Parse contractions (simplified — just find KEEP line)
    contract_text = contract_response.text
    contractions: list[str] = []
    pruning_rationale = contract_text

    for line in contract_text.split("\n"):
        if "KEEP" in line.upper():
            # Extract numbers
            import re
            numbers = re.findall(r"\d+", line)
            for num in numbers:
                idx = int(num) - 1
                if 0 <= idx < len(expansions):
                    contractions.append(expansions[idx])
            break

    # If parsing failed, keep first 2
    if not contractions:
        contractions = list(expansions[:2])

    # Selection: Pick the best
    survivors_str = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(contractions))

    select_prompt = f"""From these finalists, pick the SINGLE BEST option:

{survivors_str}

Just state which one and why in one sentence."""

    await model.generate(
        select_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=100),
    )

    selection = contractions[0] if contractions else expansions[0] if expansions else ""

    return ExpandContractResult(
        expansions=expansions,
        contractions=tuple(contractions),
        selection=selection,
        pruning_rationale=pruning_rationale,
    )


# =============================================================================
# Structure / Content
# =============================================================================


async def structure_then_content(
    task: str,
    model: ModelProtocol | None = None,
) -> StructureContentResult:
    """Design structure first, then fill content.

    Like an architect and interior designer:
    - Structure: Design the skeleton/architecture
    - Content: Fill in the details
    - Integration: Combine into coherent whole

    Args:
        task: The task to accomplish
        model: The model to use

    Returns:
        StructureContentResult with structure, content, and integrated result
    """
    from sunwell.models import GenerateOptions

    if model is None:
        from sunwell.models import OllamaModel
        model = OllamaModel(model="gemma3:1b")

    # Structure: Design skeleton
    structure_prompt = f"""Design the STRUCTURE for this task (skeleton only, no details):

{task}

Describe:
- What are the main components/sections?
- How do they relate to each other?
- What's the organization?

Just the architecture — NO implementation details yet."""

    structure_response = await model.generate(
        structure_prompt,
        options=GenerateOptions(temperature=0.5, max_tokens=400),
    )
    structure = structure_response.text.strip()

    # Content: Fill details
    content_prompt = f"""Given this structure, now fill in the CONTENT/DETAILS:

TASK: {task}

STRUCTURE:
{structure}

For each component in the structure, provide the specific details,
implementation notes, or content that belongs there."""

    content_response = await model.generate(
        content_prompt,
        options=GenerateOptions(temperature=0.7, max_tokens=600),
    )
    content = content_response.text.strip()

    # Integration: Combine
    integrate_prompt = f"""Combine this structure and content into a coherent final result:

TASK: {task}

STRUCTURE:
{structure}

CONTENT:
{content}

Now integrate these into a complete, coherent output.
Make it flow naturally — not just concatenated."""

    integrate_response = await model.generate(
        integrate_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=600),
    )
    integrated = integrate_response.text.strip()

    return StructureContentResult(
        structure=structure,
        content=content,
        integrated=integrated,
    )


# =============================================================================
# Positive / Negative Split
# =============================================================================


async def positive_negative_split(
    task: str,
    model: ModelProtocol | None = None,
) -> dict[str, str]:
    """Split into what TO do and what NOT to do.

    Args:
        task: The task
        model: The model to use

    Returns:
        Dict with 'do', 'dont', and 'balanced' keys
    """
    from sunwell.models import GenerateOptions

    if model is None:
        from sunwell.models import OllamaModel
        model = OllamaModel(model="gemma3:1b")

    # What TO do
    do_prompt = f"""For this task, list what you SHOULD DO:

{task}

Focus only on positive actions. What are the best practices?
Bullet points, be specific."""

    do_response = await model.generate(
        do_prompt,
        options=GenerateOptions(temperature=0.5, max_tokens=300),
    )

    # What NOT to do
    dont_prompt = f"""For this task, list what you should NOT DO:

{task}

Focus only on things to AVOID. What are common mistakes?
Bullet points, be specific."""

    dont_response = await model.generate(
        dont_prompt,
        options=GenerateOptions(temperature=0.5, max_tokens=300),
    )

    # Balance
    balance_prompt = f"""Given these guidelines for a task, create a balanced summary:

TASK: {task}

DO:
{do_response.text}

DON'T:
{dont_response.text}

Create a balanced, practical guide that incorporates both."""

    balance_response = await model.generate(
        balance_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=400),
    )

    return {
        "do": do_response.text.strip(),
        "dont": dont_response.text.strip(),
        "balanced": balance_response.text.strip(),
    }
