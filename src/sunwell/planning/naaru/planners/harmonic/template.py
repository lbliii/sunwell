"""Template-guided planning for RFC-122."""

import json
import re
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.planning.naaru.planners.metrics import PlanMetrics, PlanMetricsV2

if TYPE_CHECKING:
    pass

# Pre-compiled regex patterns
_RE_JSON_OBJECT = re.compile(r"\{[^}]+\}")


async def plan_with_template(
    planner: Any,  # HarmonicPlanner - avoid circular import
    goal: str,
    template: Any,  # Learning - avoid circular import
    planning_context: Any,  # PlanningContext - avoid circular import
    additional_context: dict[str, Any] | None,
) -> tuple[ArtifactGraph, PlanMetrics | PlanMetricsV2]:
    """Plan using template structure (RFC-122).

    When a high-confidence template matches, we use its structure
    to generate artifacts directly instead of harmonic candidate generation.

    Args:
        planner: HarmonicPlanner instance
        goal: Task goal
        template: Matched template Learning
        planning_context: Full planning context
        additional_context: Additional context from caller

    Returns:
        Tuple of (artifact_graph, metrics)
    """
    from sunwell.planning.naaru.planners.harmonic.scoring import (
        compute_metrics_v1,
        compute_metrics_v2,
    )
    from sunwell.planning.naaru.planners.harmonic.utils import get_effective_score, metrics_to_dict

    template_data = template.template_data

    # Extract variables from goal
    variables = await extract_template_variables(planner, goal, template_data)

    # Build artifacts from template
    artifacts: list[ArtifactSpec] = []
    for artifact_pattern in template_data.expected_artifacts:
        resolved = substitute_variables(artifact_pattern, variables)
        artifacts.append(ArtifactSpec(
            id=resolved.replace("/", "_").replace(".", "_"),
            description=f"Create {resolved}",
            produces=(resolved,),
            produces_file=resolved,
            requires=frozenset(
                substitute_variables(r, variables)
                for r in template_data.requires
            ),
        ))

    # Build graph
    graph = ArtifactGraph(limits=planner.limits)
    for artifact in artifacts:
        try:
            graph.add(artifact)
        except ValueError:
            continue  # Skip duplicates

    # Compute metrics
    if planner.scoring_version.value in ("v2", "auto"):
        metrics = compute_metrics_v2(graph, goal)
    else:
        metrics = compute_metrics_v1(graph)

    # Emit template planning complete event
    planner._emit_event("plan_winner", {
        "tasks": len(graph),
        "artifact_count": len(graph),
        "selected_candidate_id": "template-guided",
        "total_candidates": 1,
        "score": get_effective_score(metrics),
        "scoring_version": planner.scoring_version.value,
        "metrics": metrics_to_dict(metrics),
        "selection_reason": f"Template-guided: {template_data.name}",
        "variance_strategy": "template",
        "variance_config": {
            "template_name": template_data.name,
            "template_id": template.id,
            "variables": variables,
        },
        "refinement_rounds": 0,
        "final_score_improvement": 0.0,
    })

    return graph, metrics


async def extract_template_variables(
    planner: Any,  # HarmonicPlanner - avoid circular import
    goal: str,
    template_data: Any,  # TemplateData - avoid circular import
) -> dict[str, str]:
    """Extract variable values from goal text using LLM (RFC-122).

    Args:
        planner: HarmonicPlanner instance
        goal: The task goal
        template_data: Template with variable definitions

    Returns:
        Dict mapping variable names to extracted values
    """
    if not template_data.variables:
        return {}

    from sunwell.models import GenerateOptions

    var_specs = "\n".join(
        f"- {v.name}: {v.description} (hints: {', '.join(v.extraction_hints)})"
        for v in template_data.variables
    )

    prompt = f"""Extract template variables from this goal.

Template: {template_data.name}
Variables to extract:
{var_specs}

Goal: "{goal}"

Return JSON mapping variable names to extracted values.
Example: {{"entity": "Product"}}

IMPORTANT: Return ONLY the JSON object, no other text."""

    try:
        result = await planner.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=200),
        )

        # Parse JSON from response
        json_match = _RE_JSON_OBJECT.search(result.text or result.content)
        if json_match:
            return json.loads(json_match.group())
        return {}
    except (json.JSONDecodeError, Exception):
        return {}


def substitute_variables(
    pattern: str,
    variables: dict[str, str],
) -> str:
    """Substitute {{var}} patterns in template strings (RFC-122).

    Supports:
    - {{var}} - direct substitution
    - {{var_lower}} - lowercase version
    - {{var_upper}} - uppercase version

    Args:
        pattern: Template pattern with {{var}} placeholders
        variables: Variable name to value mapping

    Returns:
        Pattern with variables substituted
    """
    result = pattern
    for name, value in variables.items():
        # Direct substitution: {{name}}
        result = result.replace("{{" + name + "}}", value)
        # Lowercase: {{name_lower}}
        result = result.replace("{{" + name + "_lower}}", value.lower())
        # Uppercase: {{name_upper}}
        result = result.replace("{{" + name + "_upper}}", value.upper())
    return result
