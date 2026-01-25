"""Cellular Artifact Discovery — Graph emerges from local decisions.

The hypothesis: Don't ask one model for the full artifact graph.
Let it emerge from many "cells", each identifying ONE artifact.

Like biological cells:
- Each cell is dumb (one tiny model, one question)
- Cells only see their local neighborhood
- The structure emerges from local interactions
- No cell sees the whole picture

Example:
    >>> from sunwell.archive.naaru-experiments.cellular import cellular_discover
    >>>
    >>> graph = await cellular_discover(
    ...     goal="Build a REST API with auth",
    ...     model=OllamaModel("gemma3:1b"),
    ...     max_cells=20,
    ... )
    >>> print(f"Emerged: {len(graph)} artifacts from {stats['cells_fired']} cells")
"""


import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec


CELL_PROMPT = """You are ONE CELL in a larger system. Your job is simple:
identify ONE artifact that must exist to achieve the goal.

GOAL: {goal}

ALREADY IDENTIFIED ARTIFACTS:
{known_artifacts}

YOUR TASK:
Identify ONE artifact that:
1. Must exist to achieve the goal
2. Is NOT already in the list above
3. Is a concrete, specific thing (file, module, config, etc.)

If the goal is already fully covered by existing artifacts, respond with: NULL

Otherwise, respond with ONLY this JSON (no explanation):
{{
  "id": "unique_name",
  "description": "what this artifact is",
  "requires": ["ids", "of", "dependencies"],
  "produces_file": "path/to/file.ext"
}}"""


@dataclass(frozen=True, slots=True)
class CellResult:
    """Result from a single cell."""

    artifact: ArtifactSpec | None
    """The discovered artifact, or None if cell returned NULL."""

    cell_index: int
    """Which cell this was."""

    latency_ms: float
    """Time for this cell to respond."""


@dataclass(frozen=True, slots=True)
class CellularDiscoveryResult:
    """Result from cellular discovery."""

    graph: ArtifactGraph
    """The emerged artifact graph."""

    cells_fired: int
    """Total number of cells fired."""

    cells_contributed: int
    """Number of cells that found new artifacts."""

    cells_null: int
    """Number of cells that returned NULL (no more artifacts)."""

    rounds: int
    """Number of discovery rounds."""

    total_latency_ms: float
    """Total time for discovery."""

    stabilized: bool
    """Whether discovery stabilized (vs hit max limit)."""


async def _fire_cell(
    goal: str,
    known_artifacts: set[str],
    model: ModelProtocol,
    cell_index: int,
) -> CellResult:
    """Fire a single cell to discover one artifact."""
    import json
    import time

    from sunwell.models import GenerateOptions
    from sunwell.planning.naaru.artifacts import ArtifactSpec

    start = time.perf_counter()

    # Format known artifacts for prompt
    if known_artifacts:
        known_str = "\n".join(f"- {aid}" for aid in sorted(known_artifacts))
    else:
        known_str = "(none yet)"

    prompt = CELL_PROMPT.format(goal=goal, known_artifacts=known_str)

    try:
        result = await model.generate(
            prompt,
            options=GenerateOptions(temperature=0.7, max_tokens=200),
        )

        latency = (time.perf_counter() - start) * 1000
        text = result.text.strip()

        # Check for NULL response
        if "NULL" in text.upper() or text == "null":
            return CellResult(artifact=None, cell_index=cell_index, latency_ms=latency)

        # Try to parse JSON
        # Find JSON in response (model might add explanation)
        json_start = text.find("{")
        json_end = text.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = text[json_start:json_end]
            data = json.loads(json_str)

            artifact = ArtifactSpec(
                id=data.get("id", f"artifact_{cell_index}"),
                description=data.get("description", ""),
                contract=data.get("description", ""),
                requires=frozenset(data.get("requires", [])),
                produces_file=data.get("produces_file"),
                domain_type=data.get("domain_type", "component"),
            )

            return CellResult(artifact=artifact, cell_index=cell_index, latency_ms=latency)

        return CellResult(artifact=None, cell_index=cell_index, latency_ms=latency)

    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return CellResult(artifact=None, cell_index=cell_index, latency_ms=latency)


async def cellular_discover(
    goal: str,
    model: ModelProtocol,
    cells_per_round: int = 5,
    max_rounds: int = 5,
    max_artifacts: int = 20,
    stabilization_threshold: int = 2,
    parallel: bool = False,
) -> CellularDiscoveryResult:
    """Discover artifacts through cellular emergence.

    Fires multiple "cells" per round. Each cell identifies ONE artifact.
    Discovery continues until cells return NULL (nothing more to add)
    or limits are reached.

    Sequential by default for local Ollama compatibility.
    Set parallel=True if your Ollama has OLLAMA_NUM_PARALLEL > cells_per_round.

    Args:
        goal: The goal to achieve
        model: The model for cells (same model, many calls)
        cells_per_round: Number of cells to fire per round
        max_rounds: Maximum discovery rounds
        max_artifacts: Maximum total artifacts
        stabilization_threshold: Stop if N consecutive rounds add nothing
        parallel: Run cells in parallel (requires Ollama parallel support)

    Returns:
        CellularDiscoveryResult with emerged graph
    """
    import time

    from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec

    start_time = time.perf_counter()

    known_artifacts: dict[str, ArtifactSpec] = {}
    cells_fired = 0
    cells_contributed = 0
    cells_null = 0
    rounds_without_progress = 0

    for round_num in range(max_rounds):
        # Fire N cells (sequential by default for local Ollama)
        if parallel:
            cell_tasks = [
                _fire_cell(goal, set(known_artifacts.keys()), model, cells_fired + i)
                for i in range(cells_per_round)
            ]
            results = await asyncio.gather(*cell_tasks)
        else:
            results = []
            for i in range(cells_per_round):
                r = await _fire_cell(goal, set(known_artifacts.keys()), model, cells_fired + i)
                results.append(r)

        cells_fired += len(results)

        # Process results
        new_this_round = 0
        for result in results:
            if result.artifact is None:
                cells_null += 1
            elif result.artifact.id not in known_artifacts:
                known_artifacts[result.artifact.id] = result.artifact
                cells_contributed += 1
                new_this_round += 1

        # Check for stabilization
        if new_this_round == 0:
            rounds_without_progress += 1
            if rounds_without_progress >= stabilization_threshold:
                break
        else:
            rounds_without_progress = 0

        # Check artifact limit
        if len(known_artifacts) >= max_artifacts:
            break

    # Build graph from discovered artifacts
    graph = ArtifactGraph()
    for artifact in known_artifacts.values():
        # Filter requires to only include known artifacts
        filtered_requires = frozenset(
            req for req in artifact.requires if req in known_artifacts
        )

        # Create new artifact with filtered requires
        filtered_artifact = ArtifactSpec(
            id=artifact.id,
            description=artifact.description,
            contract=artifact.contract,
            requires=filtered_requires,
            produces_file=artifact.produces_file,
            domain_type=artifact.domain_type,
        )
        graph.add(filtered_artifact)

    total_latency = (time.perf_counter() - start_time) * 1000
    stabilized = rounds_without_progress >= stabilization_threshold

    return CellularDiscoveryResult(
        graph=graph,
        cells_fired=cells_fired,
        cells_contributed=cells_contributed,
        cells_null=cells_null,
        rounds=round_num + 1,
        total_latency_ms=total_latency,
        stabilized=stabilized,
    )


async def cellular_vs_monolithic(
    goal: str,
    model: ModelProtocol,
) -> dict[str, Any]:
    """Compare cellular discovery vs monolithic discovery.

    Runs both approaches and compares results.

    Returns:
        Dict with comparison metrics
    """
    import time

    from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

    # Monolithic discovery
    start = time.perf_counter()
    planner = ArtifactPlanner(model=model)
    mono_graph = await planner.discover_graph(goal)
    mono_latency = (time.perf_counter() - start) * 1000

    # Cellular discovery
    cellular_result = await cellular_discover(goal, model)

    return {
        "monolithic": {
            "artifacts": len(mono_graph),
            "latency_ms": mono_latency,
            "artifact_ids": list(mono_graph._artifacts.keys()),
        },
        "cellular": {
            "artifacts": len(cellular_result.graph),
            "latency_ms": cellular_result.total_latency_ms,
            "cells_fired": cellular_result.cells_fired,
            "stabilized": cellular_result.stabilized,
            "artifact_ids": list(cellular_result.graph._artifacts.keys()),
        },
        "comparison": {
            "artifact_diff": len(cellular_result.graph) - len(mono_graph),
            "latency_ratio": cellular_result.total_latency_ms / mono_latency,
            "overlap": len(
                set(mono_graph._artifacts.keys()) &
                set(cellular_result.graph._artifacts.keys())
            ),
        },
    }
