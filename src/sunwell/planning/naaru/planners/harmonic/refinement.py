"""Plan refinement logic for harmonic planning."""

import json
import re
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.planning.naaru.planners.metrics import PlanMetrics, PlanMetricsV2

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.planning.naaru.planners.harmonic.parsing import parse_artifacts
    from sunwell.planning.naaru.planners.harmonic.planner import HarmonicPlanner
    from sunwell.planning.naaru.planners.harmonic.scoring import compute_metrics_v1, compute_metrics_v2
    from sunwell.planning.naaru.planners.harmonic.utils import get_effective_score

# Import here to avoid circular dependency
from sunwell.planning.naaru.planners.harmonic.parsing import parse_artifacts as _parse_artifacts
from sunwell.planning.naaru.planners.harmonic.scoring import compute_metrics_v1 as _compute_metrics_v1
from sunwell.planning.naaru.planners.harmonic.scoring import compute_metrics_v2 as _compute_metrics_v2
from sunwell.planning.naaru.planners.harmonic.utils import get_effective_score as _get_effective_score


def identify_improvements(metrics: PlanMetrics | PlanMetricsV2) -> str | None:
    """Identify what could be improved in the plan.

    RFC-116: V2 metrics add wave analysis and semantic checks.
    """
    suggestions = []

    # V1-compatible checks
    if metrics.depth > 3:
        suggestions.append(
            f"Critical path is {metrics.depth} steps. "
            "Can any artifacts be parallelized instead of sequential?"
        )

    if metrics.parallelism_factor < 0.3:
        suggestions.append(
            f"Only {metrics.leaf_count}/{metrics.artifact_count} artifacts are leaves. "
            "Can more artifacts have no dependencies?"
        )

    if metrics.file_conflicts > 0:
        suggestions.append(
            f"Found {metrics.file_conflicts} file conflicts. "
            "Can artifacts write to different files?"
        )

    if metrics.balance_factor < 0.5:
        suggestions.append(
            "Graph is unbalanced (deep and narrow). "
            "Can the structure be flattened?"
        )

    # V2-specific checks (RFC-116)
    if isinstance(metrics, PlanMetricsV2):
        if metrics.wave_variance > 5.0:
            suggestions.append(
                f"Wave sizes are unbalanced (variance={metrics.wave_variance:.1f}). "
                "Can work be distributed more evenly across waves?"
            )

        if metrics.keyword_coverage < 0.5:
            suggestions.append(
                f"Low keyword coverage ({metrics.keyword_coverage:.0%}). "
                "Are all aspects of the goal addressed by artifacts?"
            )

        if not metrics.has_convergence:
            suggestions.append(
                "Graph has multiple roots (no single convergence point). "
                "Should there be a final integration artifact?"
            )

        if metrics.depth_utilization < 1.0 and metrics.depth > 2:
            suggestions.append(
                f"Depth utilization is low ({metrics.depth_utilization:.1f}). "
                "Depth is not being used productively for parallelism."
            )

    return " ".join(suggestions) if suggestions else None


async def refine_with_feedback(
    planner: Any,  # HarmonicPlanner - avoid circular import
    goal: str,
    graph: ArtifactGraph,
    feedback: str,
    context: dict[str, Any] | None,
) -> ArtifactGraph | None:
    """Ask LLM to refine a plan based on feedback."""
    artifacts_desc = "\n".join(
        f"- {a.id}: requires {list(a.requires)}" for a in graph.artifacts.values()
    )

    prompt = f"""GOAL: {goal}

CURRENT PLAN:
{artifacts_desc}

METRICS:
- Depth (critical path): {graph.max_depth()}
- Leaves (parallel start): {len(graph.leaves())}
- Total artifacts: {len(graph.artifacts)}

IMPROVEMENT FEEDBACK:
{feedback}

=== REFINEMENT TASK ===

Restructure the artifact graph to address the feedback.
Keep the same essential artifacts but reorganize dependencies
for better parallelism and shallower depth.

Consider:
1. Can sequential artifacts become parallel (remove a dependency)?
2. Can a deep chain be split into parallel branches?
3. Can a bottleneck artifact be split into independent pieces?

Output the COMPLETE revised artifact list as JSON array:
[
  {{
    "id": "ArtifactName",
    "description": "What it is",
    "contract": "What it must satisfy",
    "requires": ["DependencyId"],
    "produces_file": "path/to/file.py",
    "domain_type": "protocol|model|service|etc"
  }}
]"""

    from sunwell.models.protocol import GenerateOptions

    result = await planner.model.generate(
        prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=3000),
    )

    # Parse and build graph
    artifacts = _parse_artifacts(result.content or "")
    if not artifacts:
        return None

    refined_graph = ArtifactGraph()
    for artifact in artifacts:
        try:
            refined_graph.add(artifact)
        except ValueError:
            # Duplicate ID - skip
            continue

    # Validate no cycles introduced
    if refined_graph.detect_cycle():
        return None

    return refined_graph


def extract_applied_improvements(
    refined: ArtifactGraph,
    original: ArtifactGraph,
) -> str:
    """Extract description of improvements applied (RFC-058)."""
    # Simple heuristic: compare artifact counts and structure
    if len(refined) > len(original):
        return f"Added {len(refined) - len(original)} artifacts"
    elif len(refined) < len(original):
        return f"Removed {len(original) - len(refined)} artifacts"
    else:
        return "Restructured dependencies"
