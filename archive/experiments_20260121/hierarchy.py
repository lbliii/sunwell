"""Hierarchical Substrate — LLMs as Neural Network Layers.

The hypothesis: Like neural networks derive power from hierarchical
abstraction (pixels → edges → shapes → objects → concepts), small
models arranged in layers can achieve abstraction that single models cannot.

Layer 0: Many small models process fragments (like early conv layers)
Layer 1: Fewer models aggregate layer 0 outputs
Layer 2: One model synthesizes the final answer

The substrate hypothesis: The hierarchy IS the intelligence,
not any individual model.

Example:
    >>> from sunwell.experiments.hierarchy import (
    ...     hierarchical_process,
    ...     visualize_hierarchy,
    ... )
    >>>
    >>> result = await hierarchical_process(
    ...     problem="Analyze the trade-offs of event-driven architecture",
    ...     model=OllamaModel("gemma3:1b"),
    ...     layer_sizes=(8, 4, 2, 1),
    ... )
    >>> print(f"Processed through {len(result.layers)} layers")
    >>> print(f"Final answer: {result.final_output}")
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
class UnitOutput:
    """Output from a single unit in a layer."""

    layer: int
    """Which layer this unit is in."""

    unit_id: int
    """Unit index within the layer."""

    input_received: str
    """What this unit received as input."""

    output: str
    """What this unit produced."""

    latency_ms: float
    """Processing time for this unit."""


@dataclass(frozen=True, slots=True)
class Layer:
    """A complete layer in the hierarchy."""

    level: int
    """Layer level (0 = bottom, N = top)."""

    n_units: int
    """Number of units in this layer."""

    outputs: tuple[UnitOutput, ...]
    """Outputs from all units."""

    total_latency_ms: float
    """Total time for this layer."""


@dataclass(frozen=True, slots=True)
class HierarchyResult:
    """Result from hierarchical processing."""

    problem: str
    """Original problem."""

    layers: tuple[Layer, ...]
    """All layers from bottom to top."""

    final_output: str
    """Final synthesized answer from top layer."""

    total_units: int
    """Total units across all layers."""

    total_calls: int
    """Total model calls made."""

    total_latency_ms: float
    """Total processing time."""

    compression_ratio: float
    """Ratio of bottom to top layer size."""


# =============================================================================
# Layer Processing
# =============================================================================


LAYER_PROMPTS = {
    0: """You are a DETAIL EXTRACTOR (Layer 0, Unit {unit_id}/{total_units}).
Your job: Extract key FACTS and DETAILS from the input.

INPUT:
{input}

Extract 2-3 key facts or details. Be specific and concrete.
Output (max 40 words):""",

    1: """You are a PATTERN FINDER (Layer 1, Unit {unit_id}/{total_units}).
Your job: Find PATTERNS and CONNECTIONS across the facts below.

FACTS FROM LAYER 0:
{input}

Identify 1-2 patterns or relationships between these facts.
Output (max 50 words):""",

    2: """You are an INSIGHT GENERATOR (Layer 2, Unit {unit_id}/{total_units}).
Your job: Generate INSIGHTS from the patterns below.

PATTERNS FROM LAYER 1:
{input}

What insight or conclusion emerges from these patterns?
Output (max 60 words):""",

    "top": """You are the SYNTHESIZER (Top Layer).
Your job: Combine all insights into a coherent answer.

ORIGINAL PROBLEM:
{problem}

INSIGHTS FROM LOWER LAYERS:
{input}

Synthesize a complete, coherent answer to the problem.
Answer:""",
}


async def _process_unit(
    model: ModelProtocol,
    layer_level: int,
    unit_id: int,
    total_units: int,
    input_text: str,
    problem: str | None = None,
) -> UnitOutput:
    """Process one unit in a layer."""
    import time

    from sunwell.models.protocol import GenerateOptions

    start = time.perf_counter()

    # Select prompt based on layer
    if layer_level < 3:
        prompt_template = LAYER_PROMPTS.get(layer_level, LAYER_PROMPTS[2])
        prompt = prompt_template.format(
            unit_id=unit_id + 1,
            total_units=total_units,
            input=input_text,
        )
    else:
        prompt = LAYER_PROMPTS["top"].format(
            problem=problem or "See input",
            input=input_text,
        )

    # Adjust temperature by layer (lower layers = more diverse, higher = more focused)
    temp = max(0.3, 0.8 - (layer_level * 0.15))

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=temp, max_tokens=100),
    )

    latency = (time.perf_counter() - start) * 1000

    output_text = result.text.strip()
    if len(output_text) > 300:
        output_text = output_text[:300] + "..."

    return UnitOutput(
        layer=layer_level,
        unit_id=unit_id,
        input_received=input_text[:100] + "..." if len(input_text) > 100 else input_text,
        output=output_text,
        latency_ms=latency,
    )


def _distribute_inputs(
    outputs: list[str],
    n_units: int,
) -> list[str]:
    """Distribute outputs from previous layer to next layer's units.

    Each unit in the next layer receives a subset of the previous outputs.
    """
    if n_units >= len(outputs):
        # Each unit gets one output (or some get none)
        return outputs + ["(no additional input)"] * (n_units - len(outputs))

    # Combine multiple outputs per unit
    unit_inputs = []
    per_unit = len(outputs) // n_units
    extra = len(outputs) % n_units

    idx = 0
    for i in range(n_units):
        count = per_unit + (1 if i < extra else 0)
        chunk = outputs[idx:idx + count]
        unit_inputs.append("\n---\n".join(chunk))
        idx += count

    return unit_inputs


def _chunk_problem(problem: str, n_chunks: int) -> list[str]:
    """Split problem into chunks for bottom layer."""
    words = problem.split()

    if n_chunks >= len(words):
        # Each chunk gets one word or the whole thing
        return [problem] * n_chunks

    chunks = []
    per_chunk = len(words) // n_chunks
    extra = len(words) % n_chunks

    idx = 0
    for i in range(n_chunks):
        count = per_chunk + (1 if i < extra else 0)
        chunk_words = words[idx:idx + count]
        # Include context with each chunk
        chunks.append(f"[Context: {problem[:100]}...]\n\nFocus on: {' '.join(chunk_words)}")
        idx += count

    return chunks


# =============================================================================
# Main Hierarchical Processor
# =============================================================================


async def hierarchical_process(
    problem: str,
    model: ModelProtocol,
    layer_sizes: tuple[int, ...] = (8, 4, 2, 1),
    parallel: bool = False,
) -> HierarchyResult:
    """Process problem through hierarchical substrate.

    Creates a multi-layer architecture where each "neuron" is a small
    model. Information flows from broad (many units) to narrow (few units),
    creating abstraction.

    Args:
        problem: The problem to solve
        model: Same small model used at all layers
        layer_sizes: Units per layer, e.g. (8, 4, 2, 1) = 8 → 4 → 2 → 1
        parallel: Run units in parallel

    Returns:
        HierarchyResult with layer-by-layer outputs
    """
    import time

    start_time = time.perf_counter()

    # Initialize: chunk problem for bottom layer
    current_outputs = _chunk_problem(problem, layer_sizes[0])
    layers: list[Layer] = []
    total_calls = 0

    for level, n_units in enumerate(layer_sizes):
        layer_start = time.perf_counter()

        # Distribute inputs to this layer's units
        unit_inputs = _distribute_inputs(current_outputs, n_units)

        # Process all units in this layer
        if parallel:
            tasks = [
                _process_unit(
                    model, level, unit_id, n_units, unit_input,
                    problem if level == len(layer_sizes) - 1 else None,
                )
                for unit_id, unit_input in enumerate(unit_inputs)
            ]
            unit_outputs = list(await asyncio.gather(*tasks))
        else:
            unit_outputs = []
            for unit_id, unit_input in enumerate(unit_inputs):
                output = await _process_unit(
                    model, level, unit_id, n_units, unit_input,
                    problem if level == len(layer_sizes) - 1 else None,
                )
                unit_outputs.append(output)

        total_calls += len(unit_outputs)
        layer_latency = (time.perf_counter() - layer_start) * 1000

        layers.append(Layer(
            level=level,
            n_units=n_units,
            outputs=tuple(unit_outputs),
            total_latency_ms=layer_latency,
        ))

        # Prepare outputs for next layer
        current_outputs = [u.output for u in unit_outputs]

    total_latency = (time.perf_counter() - start_time) * 1000

    return HierarchyResult(
        problem=problem,
        layers=tuple(layers),
        final_output=current_outputs[0] if current_outputs else "",
        total_units=sum(layer_sizes),
        total_calls=total_calls,
        total_latency_ms=total_latency,
        compression_ratio=layer_sizes[0] / layer_sizes[-1] if layer_sizes[-1] > 0 else float('inf'),
    )


# =============================================================================
# Specialized Hierarchies
# =============================================================================


async def analytical_hierarchy(
    problem: str,
    model: ModelProtocol,
) -> HierarchyResult:
    """Hierarchy optimized for analytical problems.

    Layer 0: Extract facts (8 units)
    Layer 1: Find relationships (4 units)
    Layer 2: Generate hypotheses (2 units)
    Layer 3: Synthesize conclusion (1 unit)
    """
    return await hierarchical_process(
        problem=problem,
        model=model,
        layer_sizes=(8, 4, 2, 1),
    )


async def creative_hierarchy(
    problem: str,
    model: ModelProtocol,
) -> HierarchyResult:
    """Hierarchy optimized for creative problems.

    Wider bottom layer for more diverse exploration.
    """
    return await hierarchical_process(
        problem=problem,
        model=model,
        layer_sizes=(12, 6, 3, 1),
    )


async def deep_hierarchy(
    problem: str,
    model: ModelProtocol,
) -> HierarchyResult:
    """Deep hierarchy for complex reasoning.

    More layers = more abstraction levels.
    """
    return await hierarchical_process(
        problem=problem,
        model=model,
        layer_sizes=(8, 6, 4, 3, 2, 1),
    )


async def wide_hierarchy(
    problem: str,
    model: ModelProtocol,
) -> HierarchyResult:
    """Wide hierarchy for broad exploration.

    Wide bottom, rapid compression.
    """
    return await hierarchical_process(
        problem=problem,
        model=model,
        layer_sizes=(16, 4, 1),
    )


# =============================================================================
# Visualization & Analysis
# =============================================================================


def visualize_hierarchy(result: HierarchyResult) -> str:
    """Visualize the hierarchical processing as ASCII art."""
    lines = [
        "=== Hierarchical Substrate ===",
        f"Problem: {result.problem[:60]}...",
        "",
        f"Total units: {result.total_units}",
        f"Compression ratio: {result.compression_ratio:.1f}x",
        f"Total time: {result.total_latency_ms:.0f}ms",
        "",
    ]

    max_width = max(layer.n_units for layer in result.layers)

    for layer in reversed(result.layers):  # Top to bottom
        # Visual representation
        unit_width = max_width // layer.n_units if layer.n_units > 0 else max_width
        visual = "".join(f"[{'█' * unit_width}]" for _ in range(layer.n_units))
        padding = " " * ((max_width * 3 - len(visual)) // 2)

        lines.append(f"Layer {layer.level} ({layer.n_units} units, {layer.total_latency_ms:.0f}ms):")
        lines.append(f"  {padding}{visual}")

        # Sample outputs
        for i, unit in enumerate(layer.outputs[:3]):  # Show first 3
            lines.append(f"    Unit {i}: {unit.output[:50]}...")

        if layer.n_units > 3:
            lines.append(f"    ... and {layer.n_units - 3} more units")

        lines.append("")

    lines.extend([
        "=== Final Output ===",
        result.final_output,
    ])

    return "\n".join(lines)


def layer_statistics(result: HierarchyResult) -> list[dict]:
    """Get statistics for each layer."""
    stats = []

    for layer in result.layers:
        output_lengths = [len(u.output) for u in layer.outputs]
        stats.append({
            "level": layer.level,
            "n_units": layer.n_units,
            "avg_output_length": sum(output_lengths) / len(output_lengths) if output_lengths else 0,
            "total_latency_ms": layer.total_latency_ms,
            "avg_latency_per_unit": layer.total_latency_ms / layer.n_units if layer.n_units > 0 else 0,
        })

    return stats


def trace_information_flow(result: HierarchyResult, keyword: str) -> list[tuple[int, int, str]]:
    """Trace how a keyword/concept flows through layers.

    Returns list of (layer, unit_id, output snippet) where keyword appears.
    """
    occurrences = []

    for layer in result.layers:
        for unit in layer.outputs:
            if keyword.lower() in unit.output.lower():
                occurrences.append((layer.level, unit.unit_id, unit.output[:100]))

    return occurrences


# =============================================================================
# Experiments
# =============================================================================


async def compare_architectures(
    problem: str,
    model: ModelProtocol,
) -> dict[str, HierarchyResult]:
    """Compare different hierarchical architectures on the same problem."""
    results = {}

    architectures = {
        "analytical": (8, 4, 2, 1),
        "creative": (12, 6, 3, 1),
        "deep": (8, 6, 4, 3, 2, 1),
        "wide": (16, 4, 1),
        "flat": (4, 1),  # Almost no hierarchy
    }

    for name, sizes in architectures.items():
        result = await hierarchical_process(
            problem=problem,
            model=model,
            layer_sizes=sizes,
        )
        results[name] = result

    return results


async def hierarchy_vs_single(
    problem: str,
    model: ModelProtocol,
    layer_sizes: tuple[int, ...] = (8, 4, 2, 1),
) -> dict[str, dict]:
    """Compare hierarchical processing vs single model call.

    Tests whether hierarchical abstraction produces different/better answers.
    """
    import time

    from sunwell.models.protocol import GenerateOptions

    # Single model call
    start = time.perf_counter()
    single_result = await model.generate(
        problem,
        options=GenerateOptions(temperature=0.7, max_tokens=400),
    )
    single_latency = (time.perf_counter() - start) * 1000

    # Hierarchical
    hier_result = await hierarchical_process(
        problem=problem,
        model=model,
        layer_sizes=layer_sizes,
    )

    return {
        "single": {
            "answer": single_result.text.strip(),
            "calls": 1,
            "latency_ms": single_latency,
        },
        "hierarchy": {
            "answer": hier_result.final_output,
            "calls": hier_result.total_calls,
            "latency_ms": hier_result.total_latency_ms,
            "layers": len(hier_result.layers),
            "compression": hier_result.compression_ratio,
        },
    }


async def optimal_depth_experiment(
    problem: str,
    model: ModelProtocol,
    total_units: int = 15,
) -> dict[int, HierarchyResult]:
    """Find optimal depth for a fixed total compute budget.

    Tests: Is it better to have many shallow layers or few deep layers?
    """
    results = {}

    # Different ways to arrange ~15 total units
    configurations = [
        (15, 1),              # 2 layers: 15 → 1
        (8, 4, 2, 1),         # 4 layers: 8 → 4 → 2 → 1 = 15
        (6, 4, 3, 2, 1),      # 5 layers: 6 → 4 → 3 → 2 → 1 = 16
        (4, 3, 3, 2, 2, 1),   # 6 layers = 15
    ]

    for config in configurations:
        depth = len(config)
        result = await hierarchical_process(
            problem=problem,
            model=model,
            layer_sizes=config,
        )
        results[depth] = result

    return results


async def hierarchy_consistency_experiment(
    problem: str,
    model: ModelProtocol,
    n_runs: int = 3,
) -> dict[str, list[str]]:
    """Test if hierarchy produces consistent answers across runs.

    Compares consistency of hierarchy vs single model.
    """
    from sunwell.models.protocol import GenerateOptions

    single_answers = []
    hier_answers = []

    for _ in range(n_runs):
        # Single
        single = await model.generate(
            problem,
            options=GenerateOptions(temperature=0.7, max_tokens=400),
        )
        single_answers.append(single.text.strip())

        # Hierarchy
        hier = await hierarchical_process(
            problem=problem,
            model=model,
            layer_sizes=(8, 4, 2, 1),
        )
        hier_answers.append(hier.final_output)

    return {
        "problem": problem,
        "single_answers": single_answers,
        "hierarchy_answers": hier_answers,
    }
