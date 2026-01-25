"""Dependency resolution and cycle detection for artifact planner."""

import json
from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import ArtifactSpec
from sunwell.naaru.planners.artifact.parsing import parse_artifacts

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


def signal_plan_health(artifacts: list[ArtifactSpec]) -> dict[str, Any]:
    """Signal-based plan health check using 0/1/2 (Trit) scoring.

    Checks for:
    - Over-coupling: Too many dependencies per artifact
    - Bidirectional deps: A→B and B→A (cycle risk)
    - Transitive cycles: A→B→C→A
    - Fan-in/fan-out: Single artifact with too many dependents

    Args:
        artifacts: List of artifact specs to check

    Returns:
        Dict with health signals and whether simplification is needed
    """
    if not artifacts:
        return {"needs_simplification": False, "signals": []}

    signals = []
    issues = []

    # Build dependency map
    dep_map = {a.id: set(a.requires) for a in artifacts}
    artifact_ids = set(dep_map.keys())

    # Check 1: Per-artifact coupling (0/1/2)
    for artifact in artifacts:
        dep_count = len(artifact.requires)
        if dep_count >= 5:
            signals.append(2)  # YES - too coupled
            issues.append(f"{artifact.id} has {dep_count} deps (max 4)")
        elif dep_count >= 3:
            signals.append(1)  # MAYBE - watch it
        else:
            signals.append(0)  # NO - clean

    # Check 2: Bidirectional dependencies (strong cycle indicator)
    for a_id, a_deps in dep_map.items():
        for dep_id in a_deps:
            if dep_id in dep_map and a_id in dep_map.get(dep_id, set()):
                signals.append(2)  # Bidirectional = definite problem
                issues.append(f"Bidirectional: {a_id} ↔ {dep_id}")

    # Check 3: Transitive cycle detection (DFS)
    cycle = find_cycle_in_deps(dep_map)
    if cycle:
        signals.append(2)
        cycle_str = " → ".join(cycle + [cycle[0]])
        issues.append(f"Cycle: {cycle_str}")

    # Check 4: Unknown dependencies (deps on non-existent artifacts)
    for artifact in artifacts:
        unknown = artifact.requires - artifact_ids
        if unknown:
            signals.append(2)
            issues.append(f"{artifact.id} depends on unknown: {unknown}")

    # Check 5: Average coupling
    avg_deps = sum(len(a.requires) for a in artifacts) / len(artifacts)
    if avg_deps > 2.5:
        signals.append(2)
        issues.append(f"Average deps={avg_deps:.1f} (max 2.5)")
    elif avg_deps > 1.5:
        signals.append(1)

    # Determine if simplification needed
    hot_count = sum(1 for s in signals if s == 2)
    # Trigger on: cycles, bidirectional deps, OR unknown deps (any of these = can't execute)
    needs_simplification = (
        hot_count >= 2 or
        any("Cycle" in i or "Bidirectional" in i or "unknown" in i for i in issues)
    )

    return {
        "needs_simplification": needs_simplification,
        "signals": signals,
        "issues": issues,
        "hot_count": hot_count,
        "avg_deps": avg_deps,
        "artifact_count": len(artifacts),
    }


def find_cycle_in_deps(dep_map: dict[str, set[str]]) -> list[str] | None:
    """DFS cycle detection on dependency map. Returns cycle path if found.

    Args:
        dep_map: Mapping of artifact ID to set of required artifact IDs

    Returns:
        Cycle path if found, None otherwise
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(dep_map, WHITE)
    parent = {}

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        for dep in dep_map.get(node, set()):
            if dep not in color:
                continue  # Unknown dep, skip
            if color[dep] == GRAY:
                # Back edge = cycle! Reconstruct path
                cycle = [dep]
                curr = node
                while curr != dep:
                    cycle.append(curr)
                    curr = parent.get(curr, dep)
                return list(reversed(cycle))
            if color[dep] == WHITE:
                parent[dep] = node
                result = dfs(dep)
                if result:
                    return result
        color[node] = BLACK
        return None

    for node in dep_map:
        if color[node] == WHITE:
            result = dfs(node)
            if result:
                return result
    return None


def build_simplification_hint(health: dict[str, Any]) -> str:
    """Build a hint for the model to simplify the plan.

    Args:
        health: Health check result from signal_plan_health()

    Returns:
        Formatted hint string for the model
    """
    issues = health.get("issues", [])

    hint_parts = ["PLAN HEALTH CHECK FAILED. Please simplify:\n"]

    # Extract cycle info for specific guidance
    cycle_issues = [i for i in issues if "Cycle" in i or "Bidirectional" in i]
    if cycle_issues:
        hint_parts.append(f"- CRITICAL: {cycle_issues[0]}")
        hint_parts.append("- Artifacts CANNOT depend on each other in a loop")
        hint_parts.append("- Use a LAYERED architecture: models → services → routes → app")
        hint_parts.append("- Lower layers must NOT import from higher layers")

    # Handle unknown/missing dependencies
    unknown_issues = [i for i in issues if "unknown" in i.lower()]
    if unknown_issues:
        hint_parts.append(f"- CRITICAL: {unknown_issues[0]}")
        hint_parts.append("- Every dependency MUST be a defined artifact ID")
        hint_parts.append("- Use EXACTLY the same names in 'requires' as in artifact 'id' fields")
        hint_parts.append("- If an artifact isn't needed, remove it from requires")

    if any("deps" in i.lower() for i in issues):
        hint_parts.append("- REDUCE dependencies per artifact (max 3 each)")
        hint_parts.append("- Consider merging tightly-coupled artifacts")

    if health.get("artifact_count", 0) > 8:
        hint_parts.append("- Use FEWER, LARGER artifacts instead of many small ones")

    hint_parts.append("\nCreate a SIMPLER plan with clear ONE-WAY dependency flow.")

    return "\n".join(hint_parts)


async def break_cycle(
    model: ModelProtocol,
    goal: str,
    artifacts: list[ArtifactSpec],
    cycle: list[str],
) -> list[ArtifactSpec]:
    """Ask LLM to break a dependency cycle.

    Args:
        model: Model to use for cycle breaking
        goal: Original goal
        artifacts: Current artifact list
        cycle: Cycle path detected

    Returns:
        Corrected artifact list with cycle broken
    """
    cycle_str = " → ".join(cycle + [cycle[0]])
    artifacts_desc = "\n".join(
        f"- {a.id}: requires {list(a.requires)}" for a in artifacts
    )

    prompt = f"""GOAL: {goal}

CYCLE DETECTED in artifact dependencies:
{cycle_str}

CURRENT ARTIFACTS:
{artifacts_desc}

This cycle is impossible to execute. One of these dependencies must be wrong.

Consider:
1. Is one dependency actually optional?
2. Should one artifact be split into two (interface + implementation)?
3. Are two artifacts actually the same thing?

Return the COMPLETE corrected artifact list (all artifacts, not just the cycle)
with the cycle broken. Output ONLY valid JSON array:"""

    from sunwell.models.protocol import GenerateOptions

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.2, max_tokens=3000),
    )

    return parse_artifacts(result.content or "")
