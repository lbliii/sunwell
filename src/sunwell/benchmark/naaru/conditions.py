"""Naaru Condition Implementations (RFC-027).

Implements the 7 benchmark conditions (A-G):
- A: BASELINE - Raw model capability
- B: BASELINE_LENS - Lens context alone
- C: HARMONIC - Multi-persona voting (hardcoded personas)
- D: HARMONIC_LENS - Multi-persona from lens heuristics
- E: RESONANCE - Feedback loop refinement
- F: NAARU_FULL - All techniques combined
- G: NAARU_FULL_LENS - Full Naaru + lens context
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.types import (
    HarmonicMetrics,
    NaaruCondition,
    NaaruConditionOutput,
    ResonanceMetrics,
    RotationMetrics,
)
from sunwell.models.protocol import GenerateOptions

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Hardcoded Personas for HARMONIC condition
# =============================================================================

# Original personas (similar thinking, similar temperatures)
HARDCODED_PERSONAS: dict[str, str] = {
    "security": (
        "You are a security expert. Focus on attack vectors, "
        "defensive coding, and input validation."
    ),
    "quality": (
        "You are a code quality expert. Focus on clean, "
        "maintainable, idiomatic code."
    ),
    "testing": (
        "You are a QA engineer. Focus on testability, "
        "edge cases, and failure modes."
    ),
}

# Divergent personas (conceptually different perspectives)
DIVERGENT_PERSONAS: dict[str, tuple[str, float]] = {
    "adversary": (
        "You MUST find ways to break this. Assume the worst case. "
        "Look for security holes, edge cases that crash, race conditions. "
        "Be paranoid and adversarial.",
        0.4,  # Low temp: methodical, focused attack
    ),
    "advocate": (
        "You MUST defend this solution. Find its strengths. "
        "Explain why this approach is good. Be optimistic and supportive. "
        "Show how it solves the problem elegantly.",
        0.7,  # Medium temp: balanced defense
    ),
    "naive": (
        "You know NOTHING about this domain. Ask obvious questions. "
        "What would a complete beginner wonder? What's confusing? "
        "Point out things that seem weird or unexplained.",
        1.0,  # High temp: wild, unexpected questions
    ),
}

# Temperature strategies for persona generation
class TemperatureStrategy:
    """Temperature sampling strategies for Harmonic Synthesis."""

    UNIFORM_LOW = {"security": 0.5, "quality": 0.5, "testing": 0.5}
    UNIFORM_MED = {"security": 0.7, "quality": 0.7, "testing": 0.7}
    UNIFORM_HIGH = {"security": 0.9, "quality": 0.9, "testing": 0.9}
    SPREAD = {"security": 0.3, "quality": 0.7, "testing": 1.0}
    DIVERGENT = {k: v[1] for k, v in DIVERGENT_PERSONAS.items()}


# =============================================================================
# Thought Rotation Frame Definitions (RFC-028)
# =============================================================================

ROTATION_FRAMES = {
    "think": "Initial reasoning and exploration. What is this about? What are the key elements?",
    "critic": "Challenge assumptions, find flaws. What could go wrong? What am I missing?",
    "advocate": "Defend and strengthen. What makes this good? How can I make it better?",
    "user": "What does the user actually need? Am I solving their real problem?",
    "expert": "Apply domain expertise. What do best practices say? What patterns apply?",
    "synthesize": "Integrate all perspectives into a coherent response.",
}

# Divergent rotation emphasizes adversarial thinking
DIVERGENT_ROTATION_FRAMES = {
    "think": "Initial exploration. Consider multiple approaches, don't commit early.",
    "adversary": "ATTACK this. Find security holes, edge cases, ways it could fail catastrophically.",
    "advocate": "DEFEND this. Why is this approach good? What strengths does it have?",
    "naive": "Be a BEGINNER. What's confusing? What seems weird? Ask obvious questions.",
    "synthesize": "Now integrate: what did adversary find? what did advocate strengthen? what did naive reveal?",
}

ROTATION_SYSTEM_PROMPT = """## Thought Rotation Protocol

As you reason through this task, use these cognitive frame markers to shift perspectives.
Each frame brings a different viewpoint. Use them naturally - don't force all frames.

{frames}

Example:
<think>
Let me understand what's being asked...
</think>

<critic>
Wait, there's a potential issue here...
</critic>

<synthesize>
Integrating these perspectives, the solution is...
</synthesize>

Now respond to the task using this rotation protocol:"""


def _build_rotation_prompt(frames: dict[str, str]) -> str:
    """Build the rotation system prompt from frame definitions."""
    frame_text = "\n".join(
        f"<{name}> {desc} </{name}>"
        for name, desc in frames.items()
    )
    return ROTATION_SYSTEM_PROMPT.format(frames=frame_text)


# =============================================================================
# Condition Implementations
# =============================================================================


async def run_baseline(
    model: ModelProtocol,
    task: BenchmarkTask,
) -> NaaruConditionOutput:
    """A: BASELINE - Raw model, no system prompt.

    This establishes the baseline capability of the model without any
    enhancement from Sunwell's techniques.
    """
    import time

    start_time = time.perf_counter()

    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    return NaaruConditionOutput(
        condition=NaaruCondition.BASELINE,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt="",
    )


async def run_baseline_lens(
    model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
) -> NaaruConditionOutput:
    """B: BASELINE_LENS - Add lens context (no Naaru techniques).

    This isolates the effect of lens context alone without multi-persona
    or feedback loop enhancements.
    """
    import time

    start_time = time.perf_counter()

    # Build context from lens
    context = lens.to_context()

    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=context,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    return NaaruConditionOutput(
        condition=NaaruCondition.BASELINE_LENS,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt=context,
    )


async def run_harmonic(
    model: ModelProtocol,
    task: BenchmarkTask,
    temperature_strategy: str = "uniform_med",
) -> NaaruConditionOutput:
    """C: HARMONIC - Multi-persona voting with hardcoded personas.

    Uses Self-Consistency technique: generate with multiple personas,
    then vote on the best output. This isolates the Harmonic Synthesis
    technique without lens influence.

    Args:
        model: The model to use for generation
        task: The benchmark task
        temperature_strategy: One of "uniform_low", "uniform_med", "uniform_high",
                             "spread", or "divergent"
    """
    import time

    start_time = time.perf_counter()
    total_tokens = 0

    # Select personas and temperatures based on strategy
    if temperature_strategy == "divergent":
        personas = {k: v[0] for k, v in DIVERGENT_PERSONAS.items()}
        temps = TemperatureStrategy.DIVERGENT
    else:
        personas = HARDCODED_PERSONAS
        temps = getattr(TemperatureStrategy, temperature_strategy.upper(), TemperatureStrategy.UNIFORM_MED)

    # Step 1: Generate with each persona IN PARALLEL (with varying temps)
    async def generate_with_persona(
        name: str, system: str, temp: float
    ) -> tuple[str, str, int, float]:
        result = await model.generate(
            task.prompt,
            options=GenerateOptions(
                temperature=temp,
                max_tokens=1024,
                system_prompt=system,
            ),
        )
        tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
        return name, result.text, tokens, temp

    generation_tasks = [
        generate_with_persona(name, system, temps.get(name, 0.7))
        for name, system in personas.items()
    ]

    results = await asyncio.gather(*generation_tasks)

    persona_names = []
    persona_outputs = []
    persona_temps = []
    for name, output, tokens, temp in results:
        persona_names.append(name)
        persona_outputs.append(output)
        persona_temps.append(temp)
        total_tokens += tokens

    # Step 2: Build vote prompt
    vote_prompt = _build_vote_prompt(task.prompt, persona_names, persona_outputs)

    # Step 3: Collect votes from each persona
    votes, vote_tokens = await _collect_votes(
        model, vote_prompt, list(personas.items()), len(persona_outputs)
    )
    total_tokens += vote_tokens

    # Majority vote
    vote_counts = Counter(votes)
    winner_idx = vote_counts.most_common(1)[0][0]
    winning_persona = persona_names[winner_idx]
    best_output = persona_outputs[winner_idx]

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.HARMONIC,
        output=best_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=HarmonicMetrics(
            consensus_strength=vote_counts.most_common(1)[0][1] / len(votes),
            persona_outputs=tuple(persona_outputs),
            persona_names=tuple(persona_names),
            winning_persona=winning_persona,
            vote_distribution={persona_names[i]: votes.count(i) for i in range(len(persona_names))},
            temperature_strategy=temperature_strategy,
            persona_temperatures=tuple(persona_temps),
        ),
    )


async def run_harmonic_lens(
    model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
) -> NaaruConditionOutput:
    """D: HARMONIC_LENS - Multi-persona voting using lens heuristics.

    Instead of hardcoded personas, uses the top 3 heuristics from the lens
    as persona definitions. This tests whether domain-specific personas
    improve on generic personas.
    """
    import time

    start_time = time.perf_counter()
    total_tokens = 0

    # Extract personas from lens heuristics
    personas: dict[str, str] = {}
    for h in lens.heuristics[:3]:
        personas[h.name] = h.to_prompt_fragment()

    # Fallback to hardcoded if lens has no heuristics
    if not personas:
        personas = HARDCODED_PERSONAS

    # Step 1: Generate with each lens persona IN PARALLEL
    async def generate_with_persona(name: str, system: str) -> tuple[str, str, int]:
        result = await model.generate(
            task.prompt,
            options=GenerateOptions(
                temperature=0.7,
                max_tokens=1024,
                system_prompt=system,
            ),
        )
        tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
        return name, result.text, tokens

    generation_tasks = [
        generate_with_persona(name, system)
        for name, system in personas.items()
    ]

    results = await asyncio.gather(*generation_tasks)

    persona_names = []
    persona_outputs = []
    for name, output, tokens in results:
        persona_names.append(name)
        persona_outputs.append(output)
        total_tokens += tokens

    # Step 2: Build vote prompt
    vote_prompt = _build_vote_prompt(task.prompt, persona_names, persona_outputs)

    # Step 3: Collect votes
    votes, vote_tokens = await _collect_votes(
        model, vote_prompt, list(personas.items()), len(persona_outputs)
    )
    total_tokens += vote_tokens

    # Majority vote
    vote_counts = Counter(votes)
    winner_idx = vote_counts.most_common(1)[0][0]
    winning_persona = persona_names[winner_idx]
    best_output = persona_outputs[winner_idx]

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.HARMONIC_LENS,
        output=best_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=HarmonicMetrics(
            consensus_strength=vote_counts.most_common(1)[0][1] / len(votes),
            persona_outputs=tuple(persona_outputs),
            persona_names=tuple(persona_names),
            winning_persona=winning_persona,
            vote_distribution={persona_names[i]: votes.count(i) for i in range(len(persona_names))},
        ),
        system_prompt="[lens heuristics as personas]",
    )


async def run_resonance(
    model: ModelProtocol,
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    max_attempts: int = 2,
) -> NaaruConditionOutput:
    """E: RESONANCE - Harmonic + feedback loop (full judge).

    Builds on HARMONIC by adding a feedback loop: if the judge rejects
    the output, refine based on feedback. Uses the full judge model
    (not tiered validation).
    """
    import time

    start_time = time.perf_counter()

    # First, run harmonic synthesis
    harmonic_result = await run_harmonic(model, task)

    total_tokens = harmonic_result.tokens_used
    current_output = harmonic_result.output

    # Run feedback loop
    initial_score = 0.0
    final_score = 0.0
    refinement_attempts = 0
    issues_addressed: list[str] = []

    for attempt in range(max_attempts):
        # Judge the current output
        verdict, score, issues, judge_tokens = await _judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

        if attempt == 0:
            initial_score = score

        if verdict == "approve" or score >= 7.0:
            final_score = score
            break

        # Refine based on feedback
        refined_output, refine_tokens = await _refine_output(
            model, task, current_output, issues
        )
        total_tokens += refine_tokens

        current_output = refined_output
        refinement_attempts += 1
        issues_addressed.extend(issues)
        final_score = score
    else:
        # Max attempts reached - get final score
        _, final_score, _, judge_tokens = await _judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.RESONANCE,
        output=current_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=harmonic_result.harmonic_metrics,
        resonance_metrics=ResonanceMetrics(
            refinement_attempts=refinement_attempts,
            initial_score=initial_score,
            final_score=final_score,
            issues_addressed=tuple(issues_addressed),
            escalated_to_full_judge=True,  # Always uses full judge in this condition
        ),
    )


async def run_naaru_full(
    model: ModelProtocol,
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    max_attempts: int = 2,
) -> NaaruConditionOutput:
    """F: NAARU_FULL - Full Naaru with tiered validation.

    Same as RESONANCE but uses tiered validation (lightweight check first,
    escalate to full judge if uncertain). This tests cost savings from
    tiered validation.
    """
    import time

    start_time = time.perf_counter()

    # First, run harmonic synthesis
    harmonic_result = await run_harmonic(model, task)

    total_tokens = harmonic_result.tokens_used
    current_output = harmonic_result.output

    # Run feedback loop with tiered validation
    initial_score = 0.0
    final_score = 0.0
    refinement_attempts = 0
    issues_addressed: list[str] = []
    escalated = False

    for attempt in range(max_attempts):
        # First try lightweight validation
        is_ok, lightweight_issues = _lightweight_validate(task, current_output)

        if is_ok:
            # Approved by lightweight check - assign high score
            final_score = 8.0 if attempt == 0 else final_score
            if attempt == 0:
                initial_score = 8.0
            break

        # Lightweight check found issues - escalate to full judge
        escalated = True
        verdict, score, issues, judge_tokens = await _judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

        if attempt == 0:
            initial_score = score

        if verdict == "approve" or score >= 7.0:
            final_score = score
            break

        # Refine based on feedback
        all_issues = list(set(lightweight_issues + issues))
        refined_output, refine_tokens = await _refine_output(
            model, task, current_output, all_issues
        )
        total_tokens += refine_tokens

        current_output = refined_output
        refinement_attempts += 1
        issues_addressed.extend(all_issues)
        final_score = score

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.NAARU_FULL,
        output=current_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=harmonic_result.harmonic_metrics,
        resonance_metrics=ResonanceMetrics(
            refinement_attempts=refinement_attempts,
            initial_score=initial_score,
            final_score=final_score,
            issues_addressed=tuple(issues_addressed),
            escalated_to_full_judge=escalated,
        ),
    )


async def run_naaru_full_lens(
    model: ModelProtocol,
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
    max_attempts: int = 2,
) -> NaaruConditionOutput:
    """G: NAARU_FULL_LENS - Full Naaru + lens context.

    The complete package: lens personas + harmonic synthesis + tiered
    validation + feedback loop. This is the condition we expect to
    perform best.
    """
    import time

    start_time = time.perf_counter()

    # First, run harmonic synthesis with lens personas
    harmonic_result = await run_harmonic_lens(model, task, lens)

    total_tokens = harmonic_result.tokens_used
    current_output = harmonic_result.output

    # Run feedback loop with tiered validation
    initial_score = 0.0
    final_score = 0.0
    refinement_attempts = 0
    issues_addressed: list[str] = []
    escalated = False

    for attempt in range(max_attempts):
        # First try lightweight validation
        is_ok, lightweight_issues = _lightweight_validate(task, current_output)

        if is_ok:
            final_score = 8.0 if attempt == 0 else final_score
            if attempt == 0:
                initial_score = 8.0
            break

        # Escalate to full judge
        escalated = True
        verdict, score, issues, judge_tokens = await _judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

        if attempt == 0:
            initial_score = score

        if verdict == "approve" or score >= 7.0:
            final_score = score
            break

        # Refine with lens context
        all_issues = list(set(lightweight_issues + issues))
        lens_context = lens.to_context()
        refined_output, refine_tokens = await _refine_output(
            model, task, current_output, all_issues, system_prompt=lens_context
        )
        total_tokens += refine_tokens

        current_output = refined_output
        refinement_attempts += 1
        issues_addressed.extend(all_issues)
        final_score = score

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.NAARU_FULL_LENS,
        output=current_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=harmonic_result.harmonic_metrics,
        resonance_metrics=ResonanceMetrics(
            refinement_attempts=refinement_attempts,
            initial_score=initial_score,
            final_score=final_score,
            issues_addressed=tuple(issues_addressed),
            escalated_to_full_judge=escalated,
        ),
        system_prompt="[lens context used]",
    )


# =============================================================================
# Rotation Conditions (RFC-028)
# =============================================================================


async def run_rotation(
    model: ModelProtocol,
    task: BenchmarkTask,
    divergent: bool = False,
) -> NaaruConditionOutput:
    """H/K: ROTATION - Single generation with thought rotation frames.

    Instead of multiple parallel generations + voting, uses a single generation
    with frame markers that prompt the model to shift perspectives mid-generation.

    This tests whether structured perspective shifting within one generation
    can achieve similar quality to Harmonic at lower token cost.

    Args:
        model: The model to use
        task: The benchmark task
        divergent: If True, use divergent frames (adversary/advocate/naive)
    """
    import time

    start_time = time.perf_counter()

    # Select frame set
    frames = DIVERGENT_ROTATION_FRAMES if divergent else ROTATION_FRAMES
    rotation_prompt = _build_rotation_prompt(frames)

    # Single generation with rotation prompt
    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=rotation_prompt,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    # Parse frame usage from output
    frame_usage = _parse_frame_usage(result.text, frames)

    condition = NaaruCondition.ROTATION_DIVERGENT if divergent else NaaruCondition.ROTATION

    return NaaruConditionOutput(
        condition=condition,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt=rotation_prompt,
        rotation_metrics=RotationMetrics(
            frames_used=tuple(frame_usage.keys()),
            frame_token_counts=frame_usage,
            divergent_mode=divergent,
        ),
    )


async def run_rotation_lens(
    model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
    divergent: bool = False,
) -> NaaruConditionOutput:
    """I: ROTATION_LENS - Rotation with lens context.

    Combines thought rotation with lens heuristics for domain-specific
    perspective shifting.
    """
    import time

    start_time = time.perf_counter()

    # Build combined system prompt
    frames = DIVERGENT_ROTATION_FRAMES if divergent else ROTATION_FRAMES
    rotation_prompt = _build_rotation_prompt(frames)
    lens_context = lens.to_context()

    combined_prompt = f"{lens_context}\n\n{rotation_prompt}"

    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=combined_prompt,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    frame_usage = _parse_frame_usage(result.text, frames)

    return NaaruConditionOutput(
        condition=NaaruCondition.ROTATION_LENS,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt=combined_prompt,
        rotation_metrics=RotationMetrics(
            frames_used=tuple(frame_usage.keys()),
            frame_token_counts=frame_usage,
            divergent_mode=divergent,
        ),
    )


async def run_harmonic_divergent(
    model: ModelProtocol,
    task: BenchmarkTask,
) -> NaaruConditionOutput:
    """J: HARMONIC_DIVERGENT - Harmonic with divergent personas + temp spread.

    Uses adversary/advocate/naive personas with spread temperatures
    for maximum perspective diversity on non-deterministic tasks.
    """
    return await run_harmonic(model, task, temperature_strategy="divergent")


def _parse_frame_usage(text: str, frames: dict[str, str]) -> dict[str, int]:
    """Parse which frames were used and approximate token counts."""
    import re

    frame_usage: dict[str, int] = {}

    for frame_name in frames:
        # Find all instances of <frame>...</frame>
        pattern = rf"<{frame_name}>(.*?)</{frame_name}>"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

        if matches:
            # Estimate tokens as words / 0.75
            total_content = " ".join(matches)
            estimated_tokens = len(total_content.split()) // 1
            frame_usage[frame_name] = estimated_tokens

    return frame_usage


# =============================================================================
# Helper Functions
# =============================================================================


def _build_vote_prompt(
    task_prompt: str,
    persona_names: list[str],
    outputs: list[str],
) -> str:
    """Build the voting prompt for multi-persona comparison."""
    options_text = ""
    for i, (name, output) in enumerate(zip(persona_names, outputs, strict=True)):
        # Truncate long outputs for voting
        truncated = output[:1500] if len(output) > 1500 else output
        options_text += f"\n## Option {chr(65 + i)} (from {name})\n```\n{truncated}\n```\n"

    return f"""You are evaluating solutions to this task:

TASK: {task_prompt[:500]}

{options_text}

Which option is BEST? Consider:
1. Correctness - Does it solve the task?
2. Completeness - Is it thorough?
3. Quality - Is it well-written?

Respond with ONLY the letter (A, B, or C):"""


async def _collect_votes(
    model: ModelProtocol,
    vote_prompt: str,
    personas: list[tuple[str, str]],
    n_candidates: int,
) -> tuple[list[int], int]:
    """Collect votes from each persona."""
    total_tokens = 0
    votes: list[int] = []

    async def vote_as_persona(name: str, system: str) -> tuple[int, int]:
        result = await model.generate(
            f"{system}\n\n{vote_prompt}",
            options=GenerateOptions(temperature=0.1, max_tokens=10),
        )
        tokens = result.usage.total_tokens if result.usage else 10

        # Parse vote
        vote_text = result.text.strip().upper()
        if vote_text.startswith("A"):
            vote = 0
        elif vote_text.startswith("B"):
            vote = 1 if n_candidates > 1 else 0
        elif vote_text.startswith("C"):
            vote = 2 if n_candidates > 2 else 0
        else:
            vote = 0  # Default to first

        return vote, tokens

    vote_tasks = [vote_as_persona(name, system) for name, system in personas]
    results = await asyncio.gather(*vote_tasks)

    for vote, tokens in results:
        votes.append(vote)
        total_tokens += tokens

    return votes, total_tokens


async def _judge_output(
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    output: str,
) -> tuple[str, float, list[str], int]:
    """Judge an output using the judge model.

    Returns:
        Tuple of (verdict, score, issues, tokens_used)
    """
    import json
    import re

    judge_prompt = f"""You are an expert code/content reviewer. Evaluate this output:

TASK: {task.prompt[:500]}

OUTPUT:
```
{output[:2500]}
```

CRITERIA (score each):
1. CORRECTNESS (0-3): Does it solve the task correctly?
2. COMPLETENESS (0-3): Is it thorough and complete?
3. QUALITY (0-2): Is it well-written and clear?
4. REQUIREMENTS (0-2): Does it meet specific requirements?

Score >= 6 = approve.

Respond with ONLY JSON:
{{"score": <0-10>, "issues": ["issue1", "issue2"], "verdict": "approve" or "reject"}}"""

    result = await judge_model.generate(
        judge_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=500),
    )

    tokens = result.usage.total_tokens if result.usage else 100

    try:
        response_text = result.text

        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            judge_result = json.loads(json_match.group())
            return (
                judge_result.get("verdict", "reject"),
                float(judge_result.get("score", 5)),
                judge_result.get("issues", []),
                tokens,
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback
    return "approve", 6.0, [], tokens


async def _refine_output(
    model: ModelProtocol,
    task: BenchmarkTask,
    current_output: str,
    issues: list[str],
    system_prompt: str = "",
) -> tuple[str, int]:
    """Refine an output based on feedback.

    Returns:
        Tuple of (refined_output, tokens_used)
    """
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "No specific issues"

    refine_prompt = f"""The following output needs improvement:

ORIGINAL TASK: {task.prompt[:300]}

CURRENT OUTPUT:
```
{current_output[:1500]}
```

ISSUES TO FIX:
{issues_text}

Write an IMPROVED version that fixes ALL the issues above.
Keep the same core approach but address the quality concerns.
Output only:"""

    result = await model.generate(
        refine_prompt,
        options=GenerateOptions(
            temperature=0.5,
            max_tokens=2048,
            system_prompt=system_prompt if system_prompt else None,
        ),
    )

    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
    return result.text, tokens


def _lightweight_validate(
    task: BenchmarkTask,
    output: str,
) -> tuple[bool, list[str]]:
    """Lightweight structural validation (no LLM).

    Returns:
        Tuple of (is_ok, issues)
    """
    issues: list[str] = []

    # Check for empty output
    if not output or len(output.strip()) < 10:
        issues.append("Output is empty or too short")

    # Check deterministic criteria from task
    if task.evaluation:
        for must in task.evaluation.must_contain:
            if must.lower() not in output.lower():
                issues.append(f"Missing required element: {must}")

        for must_not in task.evaluation.must_not_contain:
            if must_not.lower() in output.lower():
                issues.append(f"Contains forbidden element: {must_not}")

    # Check for code blocks in code tasks
    from sunwell.benchmark.types import TaskCategory
    if task.category == TaskCategory.CODE_GENERATION:
        if "```" not in output and "def " not in output and "class " not in output:
            issues.append("Missing code block or function/class definition")
        if output.count("pass") > 3:
            issues.append("Too many placeholder 'pass' statements")

    return len(issues) == 0, issues


# =============================================================================
# Condition Router
# =============================================================================


@dataclass
class ConditionRunner:
    """Runs conditions for the Naaru benchmark.

    Example:
        >>> runner = ConditionRunner(model=model, judge_model=judge)
        >>> output = await runner.run(NaaruCondition.HARMONIC, task)
    """

    model: ModelProtocol
    judge_model: ModelProtocol
    max_resonance_attempts: int = 2

    async def run(
        self,
        condition: NaaruCondition,
        task: BenchmarkTask,
        lens: Lens | None = None,
    ) -> NaaruConditionOutput:
        """Run a specific condition on a task."""
        match condition:
            case NaaruCondition.BASELINE:
                return await run_baseline(self.model, task)

            case NaaruCondition.BASELINE_LENS:
                if lens is None:
                    raise ValueError("BASELINE_LENS requires a lens")
                return await run_baseline_lens(self.model, task, lens)

            case NaaruCondition.HARMONIC:
                return await run_harmonic(self.model, task)

            case NaaruCondition.HARMONIC_LENS:
                if lens is None:
                    raise ValueError("HARMONIC_LENS requires a lens")
                return await run_harmonic_lens(self.model, task, lens)

            case NaaruCondition.RESONANCE:
                return await run_resonance(
                    self.model, self.judge_model, task, self.max_resonance_attempts
                )

            case NaaruCondition.NAARU_FULL:
                return await run_naaru_full(
                    self.model, self.judge_model, task, self.max_resonance_attempts
                )

            case NaaruCondition.NAARU_FULL_LENS:
                if lens is None:
                    raise ValueError("NAARU_FULL_LENS requires a lens")
                return await run_naaru_full_lens(
                    self.model, self.judge_model, task, lens, self.max_resonance_attempts
                )

            case NaaruCondition.ROTATION:
                return await run_rotation(self.model, task, divergent=False)

            case NaaruCondition.ROTATION_LENS:
                if lens is None:
                    raise ValueError("ROTATION_LENS requires a lens")
                return await run_rotation_lens(self.model, task, lens, divergent=False)

            case NaaruCondition.HARMONIC_DIVERGENT:
                return await run_harmonic_divergent(self.model, task)

            case NaaruCondition.ROTATION_DIVERGENT:
                return await run_rotation(self.model, task, divergent=True)
