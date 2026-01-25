"""Selection Layer - Choose the best candidate from diversity layer (RFC-033).

This module implements the Selection Layer of Naaru's unified architecture.
It provides four strategies for selecting the best candidate:
- passthrough: Return first/single candidate (free)
- heuristic: Score using rules (free, CPU only)
- voting: Personas vote on candidates (cheap, ~500 tokens)
- judge: Full LLM evaluation (expensive, ~1000 tokens per candidate)
"""


import asyncio
from collections import Counter
from typing import TYPE_CHECKING

from sunwell.naaru.diversity import Candidate

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


def select_passthrough(candidates: list[Candidate]) -> Candidate:
    """Selection Strategy: Passthrough - Return first candidate.

    Used when diversity=none or diversity=rotation (single candidate).

    Args:
        candidates: List of candidates (should have exactly 1)

    Returns:
        The first candidate

    Cost: Free
    Use when: Single candidate, or integrated output (rotation)
    """
    if not candidates:
        raise ValueError("No candidates provided")
    return candidates[0]


def select_heuristic(
    candidates: list[Candidate],
    task_type: str = "general",
) -> Candidate:
    """Selection Strategy: Heuristic - Score candidates using rules.

    Scores candidates based on structural features without using an LLM.
    Works well for code generation where structure is a strong signal.

    Args:
        candidates: List of candidates to score
        task_type: Type of task ("code", "creative", "analysis", "general")

    Returns:
        The highest-scoring candidate

    Cost: Free (CPU only)
    Use when: Cost-constrained, candidates are structurally distinguishable
    """
    if not candidates:
        raise ValueError("No candidates provided")

    def score(c: Candidate) -> float:
        s = 0.0
        text = c.text

        # Length (prefer complete responses, but not rambling)
        words = len(text.split())
        if words < 50:
            s -= 2.0  # Too short
        elif words < 200:
            s += words * 0.01  # Reward completeness
        elif words < 500:
            s += 2.0  # Good length
        else:
            s += 1.5  # Slightly penalize very long

        # Structure
        s += text.count('\n\n') * 0.3  # Paragraph breaks
        s += min(text.count('```'), 3) * 1.0  # Code blocks (cap at 3)
        s += min(text.count('- '), 10) * 0.2  # Bullet points
        s += min(text.count('1.'), 5) * 0.2  # Numbered lists

        # Quality signals
        if '```python' in text or '```' in text:
            s += 1.0  # Has code
        if task_type == "code" and ('def ' in text or 'class ' in text):
            s += 2.0  # Has function/class definition

        # Negative signals
        s -= text.count('TODO') * 0.5
        s -= text.count('...') * 0.3
        s -= text.lower().count('i think') * 0.2  # Hedging
        s -= text.lower().count('maybe') * 0.2

        # Completion signals
        if text.strip().endswith(('.', '```', ')')):
            s += 0.5  # Ends cleanly

        return s

    return max(candidates, key=score)


async def select_voting(
    model: ModelProtocol,
    candidates: list[Candidate],
    prompt: str,
    personas: dict[str, tuple[str, float]] | None = None,
) -> Candidate:
    """Selection Strategy: Voting - Personas vote on candidates.

    Each persona evaluates all candidates and votes for the best one.
    The candidate with the most votes wins.

    Args:
        model: The model to use for voting
        candidates: List of candidates to vote on
        prompt: Original task prompt
        personas: Dict mapping persona names to (prompt, temperature) tuples.
                 Defaults to HARMONIC_PERSONAS

    Returns:
        The candidate with the most votes

    Cost: ~500 tokens (vote prompt + N short responses)
    Use when: Harmonic diversity, need quality signal
    """
    from sunwell.naaru.diversity import HARMONIC_PERSONAS

    if not candidates:
        raise ValueError("No candidates provided")

    if len(candidates) == 1:
        return candidates[0]

    if personas is None:
        personas = HARMONIC_PERSONAS

    # Build vote prompt
    vote_prompt = _build_vote_prompt(prompt, candidates)

    # Collect votes from each persona
    async def get_vote(persona_name: str, persona_prompt: str) -> int:
        from sunwell.models.protocol import GenerateOptions

        vote_request = f"""{persona_prompt}

{vote_prompt}

Respond with ONLY the number (0-{len(candidates)-1}) of the best candidate."""

        result = await model.generate(
            vote_request,
            options=GenerateOptions(temperature=0.3, max_tokens=10),
        )

        # Parse vote (try to extract number)
        text = result.text.strip()
        for i in range(len(candidates)):
            if str(i) in text:
                return i

        # Fallback: return 0 if parsing fails
        return 0

    votes = await asyncio.gather(*[
        get_vote(name, prompt_text)
        for name, (prompt_text, _) in personas.items()
    ])

    # Majority vote
    vote_counts = Counter(votes)
    winner_idx = vote_counts.most_common(1)[0][0]
    return candidates[winner_idx]


async def select_judge(
    judge_model: ModelProtocol,
    candidates: list[Candidate],
    rubric: str = "Quality, correctness, and completeness",
) -> Candidate:
    """Selection Strategy: Judge - Full LLM evaluation of candidates.

    Each candidate is scored by the judge model using a rubric.
    The highest-scoring candidate wins.

    Args:
        judge_model: The model to use for judging
        candidates: List of candidates to evaluate
        rubric: Evaluation rubric/criteria

    Returns:
        The highest-scoring candidate

    Cost: ~1000 tokens per candidate
    Use when: High-stakes, need rigorous quality assessment
    """
    if not candidates:
        raise ValueError("No candidates provided")

    if len(candidates) == 1:
        return candidates[0]

    async def score_candidate(candidate: Candidate) -> tuple[Candidate, float]:
        from sunwell.models.protocol import GenerateOptions

        score_prompt = f"""Score this output 0-10 based on: {rubric}

Output:
{candidate.text[:2000]}

Respond with ONLY a number between 0 and 10."""

        result = await judge_model.generate(
            score_prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=10),
        )

        # Parse score
        text = result.text.strip()
        try:
            # Try to extract number
            import re
            match = re.search(r'\d+\.?\d*', text)
            if match:
                score = float(match.group())
                return candidate, min(max(score, 0.0), 10.0)
        except (ValueError, AttributeError):
            pass

        # Fallback: return 5.0 if parsing fails
        return candidate, 5.0

    scored = await asyncio.gather(*[score_candidate(c) for c in candidates])
    return max(scored, key=lambda x: x[1])[0]


def _build_vote_prompt(prompt: str, candidates: list[Candidate]) -> str:
    """Build a prompt for voting on candidates."""
    candidate_texts = "\n\n".join(
        f"--- Candidate {i} ({c.source}) ---\n{c.text[:1000]}"
        for i, c in enumerate(candidates)
    )

    return f"""Original task: {prompt[:500]}

Here are {len(candidates)} candidate responses:

{candidate_texts}

Which candidate is best? Respond with ONLY the number (0-{len(candidates)-1})."""
