"""Model Swarm — Stigmergic Intelligence Through Traces.

The hypothesis: Like ant colonies that solve shortest-path problems through
pheromone trails, small models can solve problems by leaving and following
"thought traces" that fade over time unless reinforced.

No central coordinator. No direct communication. Just traces.
Solutions emerge from collective trace patterns.

Example:
    >>> from sunwell.experiments.swarm import (
    ...     swarm_solve,
    ...     visualize_traces,
    ... )
    >>>
    >>> result = await swarm_solve(
    ...     problem="Design a user authentication system",
    ...     model=OllamaModel("gemma3:1b"),
    ...     n_agents=8,
    ...     iterations=15,
    ... )
    >>> print(f"Solution emerged from {result.traces_created} traces")
    >>> print(f"Strongest traces: {result.strongest_traces[:3]}")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class Trace:
    """A thought trace left by an agent.

    Traces are mutable: strength decays and can be reinforced.
    """

    id: str
    """Unique trace identifier."""

    content: str
    """The thought/insight."""

    strength: float
    """Current strength (decays over time, reinforced on use)."""

    created_by: int
    """Agent ID that created this trace."""

    iteration: int
    """When this trace was created."""

    reinforcements: int = 0
    """How many times this trace was reinforced."""

    category: str = "general"
    """Optional category tag."""


@dataclass(frozen=True, slots=True)
class AgentContribution:
    """A single agent's contribution."""

    agent_id: int
    """Which agent."""

    thought: str
    """The contributed thought."""

    influenced_by: tuple[str, ...]
    """Trace IDs that influenced this thought."""

    iteration: int
    """When this was contributed."""


@dataclass(frozen=True, slots=True)
class SwarmResult:
    """Result from swarm problem-solving."""

    problem: str
    """Original problem."""

    solution: str
    """Synthesized solution from traces."""

    traces: tuple[Trace, ...]
    """All traces (sorted by strength)."""

    contributions: tuple[AgentContribution, ...]
    """All agent contributions."""

    iterations: int
    """Total iterations run."""

    traces_created: int
    """Total traces created."""

    traces_evaporated: int
    """Traces that decayed to zero."""

    strongest_traces: tuple[str, ...]
    """Top 5 traces by final strength."""

    convergence_score: float
    """How much agents converged on similar traces."""

    total_latency_ms: float
    """Total time."""


@dataclass
class SwarmState:
    """Mutable swarm state during solving."""

    problem: str
    traces: list[Trace]
    contributions: list[AgentContribution]
    next_trace_id: int = 0


# =============================================================================
# Agent Logic
# =============================================================================


AGENT_PROMPT = """You are one agent in a problem-solving swarm. You work alone, but you can see "traces" left by other agents—ideas they found promising.

PROBLEM TO SOLVE:
{problem}

STRONGEST TRACES FROM OTHER AGENTS:
{traces}

Based on these traces (or ignoring them if they seem wrong), contribute ONE useful thought.
- Build on promising traces
- Diverge if you see a better path
- Be specific and actionable

Your thought (max 25 words, no explanation):"""


SYNTHESIS_PROMPT = """A swarm of agents has been exploring solutions to a problem. Here are the strongest surviving traces—the ideas that were reinforced most.

PROBLEM: {problem}

STRONGEST TRACES (most reinforced ideas):
{traces}

Synthesize these traces into a coherent solution. What did the swarm discover?

Solution:"""


async def _agent_contribute(
    model: ModelProtocol,
    state: SwarmState,
    agent_id: int,
    iteration: int,
    traces_visible: int = 5,
) -> AgentContribution:
    """Have one agent contribute a thought based on visible traces."""
    from sunwell.models.protocol import GenerateOptions

    # Get strongest traces for this agent to see
    visible = sorted(state.traces, key=lambda t: t.strength, reverse=True)[:traces_visible]

    if visible:
        traces_str = "\n".join(
            f"- [{t.strength:.2f}] {t.content}" for t in visible
        )
        influenced_by = tuple(t.id for t in visible)
    else:
        traces_str = "(no traces yet—you're exploring fresh)"
        influenced_by = ()

    prompt = AGENT_PROMPT.format(problem=state.problem, traces=traces_str)

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.8, max_tokens=50),
    )

    thought = result.text.strip()
    if len(thought) > 150:
        thought = thought[:150] + "..."

    return AgentContribution(
        agent_id=agent_id,
        thought=thought,
        influenced_by=influenced_by,
        iteration=iteration,
    )


def _add_trace(state: SwarmState, contribution: AgentContribution) -> Trace:
    """Create a new trace from an agent's contribution."""
    trace = Trace(
        id=f"t{state.next_trace_id}",
        content=contribution.thought,
        strength=1.0,  # New traces start at full strength
        created_by=contribution.agent_id,
        iteration=contribution.iteration,
    )
    state.traces.append(trace)
    state.next_trace_id += 1
    return trace


def _reinforce_similar_traces(
    state: SwarmState,
    contribution: AgentContribution,
    similarity_threshold: float = 0.4,
    reinforcement: float = 0.3,
) -> int:
    """Reinforce existing traces similar to the new contribution."""
    from difflib import SequenceMatcher

    reinforced = 0
    new_content = contribution.thought.lower()

    for trace in state.traces:
        if trace.created_by == contribution.agent_id:
            continue  # Don't reinforce your own traces

        similarity = SequenceMatcher(
            None, new_content, trace.content.lower()
        ).ratio()

        if similarity >= similarity_threshold:
            trace.strength = min(2.0, trace.strength + reinforcement)
            trace.reinforcements += 1
            reinforced += 1

    return reinforced


def _evaporate_traces(
    state: SwarmState,
    evaporation_rate: float = 0.1,
    min_strength: float = 0.1,
) -> int:
    """Apply evaporation to all traces. Remove dead traces."""
    evaporated = 0
    surviving = []

    for trace in state.traces:
        trace.strength -= evaporation_rate

        if trace.strength >= min_strength:
            surviving.append(trace)
        else:
            evaporated += 1

    state.traces = surviving
    return evaporated


def _measure_convergence(state: SwarmState) -> float:
    """Measure how much the swarm has converged on similar ideas."""
    from difflib import SequenceMatcher

    if len(state.traces) < 2:
        return 0.0

    # Check similarity between top traces
    top_traces = sorted(state.traces, key=lambda t: t.strength, reverse=True)[:5]

    if len(top_traces) < 2:
        return 0.0

    similarities = []
    for i in range(len(top_traces)):
        for j in range(i + 1, len(top_traces)):
            sim = SequenceMatcher(
                None,
                top_traces[i].content.lower(),
                top_traces[j].content.lower(),
            ).ratio()
            similarities.append(sim)

    return sum(similarities) / len(similarities) if similarities else 0.0


# =============================================================================
# Main Swarm Solver
# =============================================================================


async def swarm_solve(
    problem: str,
    model: ModelProtocol,
    n_agents: int = 8,
    iterations: int = 15,
    evaporation_rate: float = 0.15,
    traces_visible: int = 5,
    convergence_threshold: float = 0.7,
    parallel: bool = False,
) -> SwarmResult:
    """Solve problem through stigmergic swarm intelligence.

    Agents leave "thought traces" that fade over time. Good ideas get
    reinforced when multiple agents converge on them. Solutions emerge
    from the strongest surviving traces.

    Args:
        problem: The problem to solve
        model: Small model for agents
        n_agents: Number of agents in swarm
        iterations: Maximum iterations
        evaporation_rate: How fast traces fade (0-1)
        traces_visible: How many traces each agent sees
        convergence_threshold: Stop if convergence exceeds this
        parallel: Run agents in parallel (requires Ollama parallel)

    Returns:
        SwarmResult with solution and trace analysis
    """
    import time

    from sunwell.models.protocol import GenerateOptions

    start_time = time.perf_counter()

    state = SwarmState(
        problem=problem,
        traces=[],
        contributions=[],
    )

    traces_evaporated = 0

    for iteration in range(iterations):
        # Each agent contributes
        if parallel:
            tasks = [
                _agent_contribute(model, state, agent_id, iteration, traces_visible)
                for agent_id in range(n_agents)
            ]
            contributions = await asyncio.gather(*tasks)
        else:
            contributions = []
            for agent_id in range(n_agents):
                contrib = await _agent_contribute(
                    model, state, agent_id, iteration, traces_visible
                )
                contributions.append(contrib)

        # Process contributions
        for contrib in contributions:
            state.contributions.append(contrib)

            # Add as new trace
            _add_trace(state, contrib)

            # Reinforce similar existing traces
            _reinforce_similar_traces(state, contrib)

        # Evaporation
        traces_evaporated += _evaporate_traces(state, evaporation_rate)

        # Check convergence
        convergence = _measure_convergence(state)
        if convergence >= convergence_threshold:
            break

    # Synthesize solution from strongest traces
    top_traces = sorted(state.traces, key=lambda t: t.strength, reverse=True)[:10]

    if top_traces:
        traces_str = "\n".join(
            f"- [{t.strength:.2f}, reinforced {t.reinforcements}x] {t.content}"
            for t in top_traces
        )
    else:
        traces_str = "(no strong traces survived)"

    synth_prompt = SYNTHESIS_PROMPT.format(problem=problem, traces=traces_str)
    synth_result = await model.generate(
        synth_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=400),
    )

    total_latency = (time.perf_counter() - start_time) * 1000

    # Sort final traces by strength
    final_traces = tuple(sorted(state.traces, key=lambda t: t.strength, reverse=True))

    return SwarmResult(
        problem=problem,
        solution=synth_result.text.strip(),
        traces=final_traces,
        contributions=tuple(state.contributions),
        iterations=iteration + 1,
        traces_created=state.next_trace_id,
        traces_evaporated=traces_evaporated,
        strongest_traces=tuple(t.content for t in final_traces[:5]),
        convergence_score=_measure_convergence(state),
        total_latency_ms=total_latency,
    )


# =============================================================================
# Visualization & Analysis
# =============================================================================


def visualize_traces(result: SwarmResult, top_n: int = 10) -> str:
    """Visualize the strongest traces."""
    lines = [
        "=== Swarm Trace Analysis ===",
        f"Problem: {result.problem[:60]}...",
        "",
        f"Iterations: {result.iterations}",
        f"Traces created: {result.traces_created}",
        f"Traces evaporated: {result.traces_evaporated}",
        f"Surviving traces: {len(result.traces)}",
        f"Convergence: {result.convergence_score:.2%}",
        "",
        f"Top {top_n} Traces by Strength:",
    ]

    max_bar = 30
    for i, trace in enumerate(result.traces[:top_n]):
        bar_len = int((trace.strength / 2.0) * max_bar)  # Max strength is 2.0
        bar = "█" * bar_len + "░" * (max_bar - bar_len)
        lines.append(
            f"  {i+1:2d}. [{bar}] {trace.strength:.2f} "
            f"(+{trace.reinforcements}) {trace.content[:40]}..."
        )

    lines.extend([
        "",
        "=== Synthesized Solution ===",
        result.solution,
    ])

    return "\n".join(lines)


def trace_lineage(result: SwarmResult, trace_id: str) -> list[AgentContribution]:
    """Find all contributions that influenced or were influenced by a trace."""
    # Find the trace
    trace = next((t for t in result.traces if t.id == trace_id), None)
    if not trace:
        return []

    # Find contributions influenced by this trace
    influenced = [
        c for c in result.contributions
        if trace_id in c.influenced_by
    ]

    return influenced


def agent_performance(result: SwarmResult) -> dict[int, dict]:
    """Analyze each agent's contribution to the swarm."""
    agent_stats: dict[int, dict] = {}

    # Count traces created by each agent
    for trace in result.traces:
        if trace.created_by not in agent_stats:
            agent_stats[trace.created_by] = {
                "traces_created": 0,
                "total_strength": 0.0,
                "total_reinforcements": 0,
            }

        stats = agent_stats[trace.created_by]
        stats["traces_created"] += 1
        stats["total_strength"] += trace.strength
        stats["total_reinforcements"] += trace.reinforcements

    return agent_stats


# =============================================================================
# Experiments
# =============================================================================


async def compare_swarm_sizes(
    problem: str,
    model: ModelProtocol,
    sizes: list[int] | None = None,
    iterations: int = 15,
) -> dict[int, SwarmResult]:
    """Compare swarm performance across different sizes.

    Tests whether more agents produce better solutions.
    """
    sizes = sizes or [4, 8, 12, 16]
    results = {}

    for size in sizes:
        result = await swarm_solve(
            problem=problem,
            model=model,
            n_agents=size,
            iterations=iterations,
        )
        results[size] = result

    return results


async def compare_evaporation_rates(
    problem: str,
    model: ModelProtocol,
    rates: list[float] | None = None,
    n_agents: int = 8,
) -> dict[float, SwarmResult]:
    """Compare different evaporation rates.

    Low rates: Ideas persist longer, more exploration
    High rates: Only strong ideas survive, faster convergence
    """
    rates = rates or [0.05, 0.1, 0.15, 0.2, 0.3]
    results = {}

    for rate in rates:
        result = await swarm_solve(
            problem=problem,
            model=model,
            n_agents=n_agents,
            evaporation_rate=rate,
        )
        results[rate] = result

    return results


async def swarm_vs_single(
    problem: str,
    model: ModelProtocol,
    n_agents: int = 8,
    iterations: int = 15,
) -> dict[str, dict]:
    """Compare swarm solution vs single model call.

    Tests whether collective exploration produces different/better answers.
    """
    import time

    from sunwell.models.protocol import GenerateOptions

    # Single model call
    start = time.perf_counter()
    single_result = await model.generate(
        f"Solve this problem:\n\n{problem}",
        options=GenerateOptions(temperature=0.7, max_tokens=400),
    )
    single_latency = (time.perf_counter() - start) * 1000

    # Swarm
    swarm_result = await swarm_solve(
        problem=problem,
        model=model,
        n_agents=n_agents,
        iterations=iterations,
    )

    return {
        "single": {
            "solution": single_result.text.strip(),
            "calls": 1,
            "latency_ms": single_latency,
        },
        "swarm": {
            "solution": swarm_result.solution,
            "calls": n_agents * swarm_result.iterations + 1,
            "latency_ms": swarm_result.total_latency_ms,
            "traces_created": swarm_result.traces_created,
            "convergence": swarm_result.convergence_score,
        },
    }


async def swarm_diversity_experiment(
    problem: str,
    model: ModelProtocol,
    n_runs: int = 3,
) -> dict[str, list[str]]:
    """Run swarm multiple times to see solution diversity.

    Tests whether swarm produces diverse or convergent solutions.
    """
    solutions = []

    for _ in range(n_runs):
        result = await swarm_solve(
            problem=problem,
            model=model,
            n_agents=8,
            iterations=15,
        )
        solutions.append(result.solution)

    return {
        "problem": problem,
        "solutions": solutions,
        "n_runs": n_runs,
    }
