"""LLM Automata — Small Models as Computational Substrate.

The hypothesis: Complex reasoning can emerge from simple local rules
applied by many small models, like cellular automata. Each cell has
state (a short thought), sees only its neighbors, and updates according
to simple rules. Solutions emerge from collective evolution.

Like Conway's Game of Life discovered computation in simple rules,
can we discover reasoning in simple model interactions?

Example:
    >>> from sunwell.experiments.automata import (
    ...     llm_automaton,
    ...     visualize_grid,
    ... )
    >>>
    >>> result = await llm_automaton(
    ...     seed="What are the pros and cons of microservices?",
    ...     model=OllamaModel("gemma3:1b"),
    ...     grid_size=4,
    ...     generations=8,
    ... )
    >>> print(f"Converged in {result.generations} generations")
    >>> print(f"Agreement: {result.final_agreement:.2%}")
    >>> print(f"Emergent answer: {result.synthesized_answer}")
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


@dataclass(frozen=True, slots=True)
class Cell:
    """A single cell in the LLM automaton."""

    row: int
    """Row position in grid."""

    col: int
    """Column position in grid."""

    state: str
    """Current thought (max ~50 tokens)."""

    generation: int
    """Which generation this state is from."""


@dataclass(frozen=True, slots=True)
class GridState:
    """The full grid state at a generation."""

    cells: tuple[tuple[Cell, ...], ...]
    """2D grid of cells."""

    generation: int
    """Current generation number."""

    agreement: float
    """How much cells agree (0-1)."""


@dataclass(frozen=True, slots=True)
class AutomatonResult:
    """Result from running the LLM automaton."""

    seed: str
    """Original problem/seed."""

    history: tuple[GridState, ...]
    """All grid states through evolution."""

    generations: int
    """Total generations run."""

    converged: bool
    """Whether cells converged (vs hit max)."""

    final_agreement: float
    """Agreement at final generation."""

    synthesized_answer: str
    """Answer synthesized from converged grid."""

    total_calls: int
    """Total model calls made."""

    total_latency_ms: float
    """Total time for all generations."""


# =============================================================================
# Cell Update Logic
# =============================================================================


CELL_UPDATE_PROMPT = """You are one cell in a thinking grid. You can see your neighbors' thoughts.

THE PROBLEM WE'RE COLLECTIVELY SOLVING:
{seed}

YOUR CURRENT THOUGHT:
{current}

YOUR NEIGHBORS' THOUGHTS:
{neighbors}

Based on what your neighbors are thinking, UPDATE your thought to be more useful.
- If neighbors agree with you, reinforce and elaborate
- If neighbors disagree, consider their perspective
- If neighbors have new ideas, integrate them

Output ONLY your updated thought (max 30 words, no explanation):"""


SYNTHESIS_PROMPT = """A grid of thinkers has evolved their thoughts about a problem.

PROBLEM: {seed}

FINAL THOUGHTS FROM ALL CELLS:
{thoughts}

Synthesize these thoughts into a coherent answer. What did the collective conclude?

Answer:"""


async def _update_cell(
    cell: Cell,
    neighbors: list[Cell],
    seed: str,
    model: ModelProtocol,
) -> Cell:
    """Update a single cell based on its neighbors."""
    from sunwell.models.protocol import GenerateOptions

    # Format neighbor thoughts
    if neighbors:
        neighbor_str = "\n".join(
            f"- [{n.row},{n.col}]: {n.state}" for n in neighbors
        )
    else:
        neighbor_str = "(no neighbors visible)"

    prompt = CELL_UPDATE_PROMPT.format(
        seed=seed,
        current=cell.state,
        neighbors=neighbor_str,
    )

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.7, max_tokens=60),
    )

    new_state = result.text.strip()
    # Truncate if too long
    if len(new_state) > 200:
        new_state = new_state[:200] + "..."

    return Cell(
        row=cell.row,
        col=cell.col,
        state=new_state,
        generation=cell.generation + 1,
    )


def _get_neighbors(
    grid: tuple[tuple[Cell, ...], ...],
    row: int,
    col: int,
    neighborhood: str = "von_neumann",
) -> list[Cell]:
    """Get neighboring cells.

    Args:
        grid: Current grid state
        row, col: Cell position
        neighborhood: 'von_neumann' (4 neighbors) or 'moore' (8 neighbors)
    """
    rows = len(grid)
    cols = len(grid[0]) if grid else 0
    neighbors = []

    if neighborhood == "von_neumann":
        # 4 neighbors: N, S, E, W
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    else:
        # 8 neighbors: including diagonals
        offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]

    for dr, dc in offsets:
        nr, nc = row + dr, col + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            neighbors.append(grid[nr][nc])

    return neighbors


def _measure_agreement(grid: tuple[tuple[Cell, ...], ...]) -> float:
    """Measure how much cells agree (semantic similarity)."""
    from difflib import SequenceMatcher

    all_states = [cell.state.lower() for row in grid for cell in row]

    if len(all_states) < 2:
        return 1.0

    # Average pairwise similarity
    similarities = []
    for i in range(len(all_states)):
        for j in range(i + 1, len(all_states)):
            sim = SequenceMatcher(None, all_states[i], all_states[j]).ratio()
            similarities.append(sim)

    return sum(similarities) / len(similarities) if similarities else 0.0


# =============================================================================
# Main Automaton
# =============================================================================


async def llm_automaton(
    seed: str,
    model: ModelProtocol,
    grid_size: int = 4,
    generations: int = 10,
    convergence_threshold: float = 0.75,
    neighborhood: str = "von_neumann",
    parallel: bool = False,
) -> AutomatonResult:
    """Run LLM automaton to evolve toward a solution.

    Creates a grid of "cells" where each cell is a small model thinking
    about part of the problem. Cells can only see their neighbors, and
    update their thoughts based on local information. Solutions emerge
    from collective evolution.

    Args:
        seed: The problem/question to solve
        model: Small model (1B or less recommended)
        grid_size: NxN grid size
        generations: Maximum evolution steps
        convergence_threshold: Stop if agreement exceeds this
        neighborhood: 'von_neumann' (4) or 'moore' (8) neighbors
        parallel: Run cell updates in parallel

    Returns:
        AutomatonResult with evolution history and synthesized answer
    """
    import time

    from sunwell.models.protocol import GenerateOptions

    start_time = time.perf_counter()
    total_calls = 0

    # Initialize grid: each cell gets a piece of the problem
    grid = _initialize_grid(seed, grid_size)
    history: list[GridState] = []

    initial_agreement = _measure_agreement(grid)
    history.append(GridState(
        cells=grid,
        generation=0,
        agreement=initial_agreement,
    ))

    converged = False

    for gen in range(1, generations + 1):
        # Update all cells
        new_rows: list[tuple[Cell, ...]] = []

        for row_idx, row in enumerate(grid):
            if parallel:
                # Parallel updates (requires Ollama parallel support)
                tasks = [
                    _update_cell(
                        cell,
                        _get_neighbors(grid, row_idx, col_idx, neighborhood),
                        seed,
                        model,
                    )
                    for col_idx, cell in enumerate(row)
                ]
                new_row = await asyncio.gather(*tasks)
                total_calls += len(tasks)
            else:
                # Sequential updates (safer for local Ollama)
                new_row = []
                for col_idx, cell in enumerate(row):
                    neighbors = _get_neighbors(grid, row_idx, col_idx, neighborhood)
                    updated = await _update_cell(cell, neighbors, seed, model)
                    new_row.append(updated)
                    total_calls += 1

            new_rows.append(tuple(new_row))

        grid = tuple(new_rows)
        agreement = _measure_agreement(grid)

        history.append(GridState(
            cells=grid,
            generation=gen,
            agreement=agreement,
        ))

        # Check convergence
        if agreement >= convergence_threshold:
            converged = True
            break

    # Synthesize final answer from converged grid
    all_thoughts = "\n".join(
        f"[{cell.row},{cell.col}]: {cell.state}"
        for row in grid
        for cell in row
    )

    synth_prompt = SYNTHESIS_PROMPT.format(seed=seed, thoughts=all_thoughts)
    synth_result = await model.generate(
        synth_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=300),
    )
    total_calls += 1

    total_latency = (time.perf_counter() - start_time) * 1000

    return AutomatonResult(
        seed=seed,
        history=tuple(history),
        generations=len(history) - 1,
        converged=converged,
        final_agreement=history[-1].agreement,
        synthesized_answer=synth_result.text.strip(),
        total_calls=total_calls,
        total_latency_ms=total_latency,
    )


def _initialize_grid(seed: str, size: int) -> tuple[tuple[Cell, ...], ...]:
    """Initialize grid with seed distributed across cells."""
    # Split seed into fragments or use positional prompts
    words = seed.split()
    n_cells = size * size

    rows: list[tuple[Cell, ...]] = []
    cell_idx = 0

    for row in range(size):
        row_cells: list[Cell] = []
        for col in range(size):
            # Each cell starts with a portion of the seed or a positional prompt
            if cell_idx < len(words):
                # First cells get seed words
                start = (cell_idx * len(words)) // n_cells
                end = ((cell_idx + 1) * len(words)) // n_cells
                fragment = " ".join(words[start:end]) if start < end else words[start % len(words)]
                initial = f"Thinking about: {fragment}"
            else:
                initial = "Considering the overall question..."

            row_cells.append(Cell(
                row=row,
                col=col,
                state=initial,
                generation=0,
            ))
            cell_idx += 1

        rows.append(tuple(row_cells))

    return tuple(rows)


# =============================================================================
# Visualization & Analysis
# =============================================================================


def visualize_grid(state: GridState, max_width: int = 40) -> str:
    """Visualize grid state as ASCII art."""
    lines = [f"Generation {state.generation} (agreement: {state.agreement:.2%})", ""]

    for row in state.cells:
        row_str = ""
        for cell in row:
            # Truncate cell state for display
            display = cell.state[:max_width]
            if len(cell.state) > max_width:
                display = display[:-3] + "..."
            row_str += f"[{display:^{max_width}}] "
        lines.append(row_str)
        lines.append("")

    return "\n".join(lines)


def visualize_evolution(result: AutomatonResult) -> str:
    """Visualize how agreement evolved over generations."""
    lines = [
        "=== LLM Automaton Evolution ===",
        f"Seed: {result.seed[:60]}...",
        f"Grid: {len(result.history[0].cells)}x{len(result.history[0].cells[0])}",
        "",
        "Agreement over generations:",
    ]

    max_bar = 40
    for state in result.history:
        bar_len = int(state.agreement * max_bar)
        bar = "█" * bar_len + "░" * (max_bar - bar_len)
        lines.append(f"  Gen {state.generation:2d}: [{bar}] {state.agreement:.2%}")

    lines.extend([
        "",
        f"Converged: {'Yes' if result.converged else 'No (hit max generations)'}",
        f"Final agreement: {result.final_agreement:.2%}",
        f"Total calls: {result.total_calls}",
        f"Total time: {result.total_latency_ms:.0f}ms",
        "",
        "=== Synthesized Answer ===",
        result.synthesized_answer,
    ])

    return "\n".join(lines)


def extract_thought_clusters(result: AutomatonResult) -> dict[str, list[str]]:
    """Extract clusters of similar thoughts from final state."""
    from difflib import SequenceMatcher

    final_grid = result.history[-1].cells
    all_cells = [cell for row in final_grid for cell in row]

    # Simple clustering by similarity
    clusters: dict[str, list[str]] = {}
    assigned = set()

    for i, cell in enumerate(all_cells):
        if i in assigned:
            continue

        cluster = [cell.state]
        assigned.add(i)

        for j, other in enumerate(all_cells):
            if j in assigned:
                continue
            sim = SequenceMatcher(None, cell.state.lower(), other.state.lower()).ratio()
            if sim > 0.5:
                cluster.append(other.state)
                assigned.add(j)

        # Use first thought as cluster key
        clusters[cell.state[:50]] = cluster

    return clusters


# =============================================================================
# Experiments
# =============================================================================


async def compare_grid_sizes(
    seed: str,
    model: ModelProtocol,
    sizes: list[int] | None = None,
    generations: int = 8,
) -> dict[int, AutomatonResult]:
    """Compare automaton performance across grid sizes.

    Tests whether larger grids (more cells) produce better results.
    """
    sizes = sizes or [2, 3, 4, 5]
    results = {}

    for size in sizes:
        result = await llm_automaton(
            seed=seed,
            model=model,
            grid_size=size,
            generations=generations,
        )
        results[size] = result

    return results


async def compare_neighborhoods(
    seed: str,
    model: ModelProtocol,
    grid_size: int = 4,
    generations: int = 8,
) -> dict[str, AutomatonResult]:
    """Compare von Neumann (4) vs Moore (8) neighborhood."""
    results = {}

    for neighborhood in ["von_neumann", "moore"]:
        result = await llm_automaton(
            seed=seed,
            model=model,
            grid_size=grid_size,
            generations=generations,
            neighborhood=neighborhood,
        )
        results[neighborhood] = result

    return results


async def automaton_vs_single(
    seed: str,
    model: ModelProtocol,
    grid_size: int = 4,
    generations: int = 8,
) -> dict[str, str]:
    """Compare automaton answer vs single model call.

    Tests whether collective evolution produces different/better answers.
    """
    import time

    from sunwell.models.protocol import GenerateOptions

    # Single model call
    start = time.perf_counter()
    single_result = await model.generate(
        seed,
        options=GenerateOptions(temperature=0.7, max_tokens=300),
    )
    single_latency = (time.perf_counter() - start) * 1000

    # Automaton
    auto_result = await llm_automaton(
        seed=seed,
        model=model,
        grid_size=grid_size,
        generations=generations,
    )

    return {
        "single": {
            "answer": single_result.text.strip(),
            "calls": 1,
            "latency_ms": single_latency,
        },
        "automaton": {
            "answer": auto_result.synthesized_answer,
            "calls": auto_result.total_calls,
            "latency_ms": auto_result.total_latency_ms,
            "generations": auto_result.generations,
            "agreement": auto_result.final_agreement,
        },
    }
