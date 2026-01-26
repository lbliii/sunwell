"""Harmonic condition implementations (C, D).

C: HARMONIC - Multi-persona voting with hardcoded personas
D: HARMONIC_LENS - Multi-persona from lens heuristics
"""

import asyncio
import time
from collections import Counter
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.conditions.personas import (
    DIVERGENT_PERSONAS,
    HARDCODED_PERSONAS,
    TemperatureStrategy,
)
from sunwell.benchmark.naaru.types import HarmonicMetrics, NaaruCondition, NaaruConditionOutput
from sunwell.models import GenerateOptions

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.foundation.core.lens import Lens
    from sunwell.models import ModelProtocol


def build_vote_prompt(
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

    # Build dynamic letter options based on number of candidates
    n_options = len(outputs)
    if n_options == 1:
        letter_options = "A"
    elif n_options == 2:
        letter_options = "A or B"
    else:
        letters = ", ".join(chr(65 + i) for i in range(n_options - 1))
        letter_options = f"{letters}, or {chr(65 + n_options - 1)}"

    return f"""You are evaluating solutions to this task:

TASK: {task_prompt[:500]}

{options_text}

Which option is BEST? Consider:
1. Correctness - Does it solve the task?
2. Completeness - Is it thorough?
3. Quality - Is it well-written?

Respond with ONLY the letter ({letter_options}):"""


async def collect_votes(
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

        # Parse vote - handle arbitrary number of candidates (A-Z)
        vote_text = result.text.strip().upper()
        vote = 0  # Default to first candidate

        if vote_text:
            first_char = vote_text[0]
            if "A" <= first_char <= "Z":
                candidate_idx = ord(first_char) - ord("A")
                if 0 <= candidate_idx < n_candidates:
                    vote = candidate_idx

        return vote, tokens

    vote_tasks = [vote_as_persona(name, system) for name, system in personas]
    results = await asyncio.gather(*vote_tasks)

    for vote, tokens in results:
        votes.append(vote)
        total_tokens += tokens

    return votes, total_tokens


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
    start_time = time.perf_counter()
    total_tokens = 0

    # Select personas and temperatures based on strategy
    if temperature_strategy == "divergent":
        personas = {k: v[0] for k, v in DIVERGENT_PERSONAS.items()}
        temps = TemperatureStrategy.DIVERGENT
    else:
        personas = HARDCODED_PERSONAS
        strategy_name = temperature_strategy.upper()
        temps = getattr(TemperatureStrategy, strategy_name, TemperatureStrategy.UNIFORM_MED)

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
    vote_prompt = build_vote_prompt(task.prompt, persona_names, persona_outputs)

    # Step 3: Collect votes from each persona
    votes, vote_tokens = await collect_votes(
        model, vote_prompt, list(personas.items()), len(persona_outputs)
    )
    total_tokens += vote_tokens

    # Majority vote
    vote_counts = Counter(votes)
    winner_idx = vote_counts.most_common(1)[0][0]
    winning_persona = persona_names[winner_idx]
    best_output = persona_outputs[winner_idx]

    elapsed = time.perf_counter() - start_time

    # Determine condition based on temperature strategy
    condition = (
        NaaruCondition.HARMONIC_DIVERGENT
        if temperature_strategy == "divergent"
        else NaaruCondition.HARMONIC
    )

    return NaaruConditionOutput(
        condition=condition,
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
    from sunwell.benchmark.naaru.conditions.personas import HARDCODED_PERSONAS

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
    vote_prompt = build_vote_prompt(task.prompt, persona_names, persona_outputs)

    # Step 3: Collect votes
    votes, vote_tokens = await collect_votes(
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


async def run_harmonic_divergent(
    model: ModelProtocol,
    task: BenchmarkTask,
) -> NaaruConditionOutput:
    """J: HARMONIC_DIVERGENT - Harmonic with divergent personas + temp spread.

    Uses adversary/advocate/naive personas with spread temperatures
    for maximum perspective diversity on non-deterministic tasks.
    """
    return await run_harmonic(model, task, temperature_strategy="divergent")
