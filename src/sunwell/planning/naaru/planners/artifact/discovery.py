"""Discovery logic for artifact planner."""

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import (
    ArtifactGraph,
    ArtifactSpec,
    CyclicDependencyError,
    DiscoveryFailedError,
    GraphExplosionError,
)
from sunwell.planning.naaru.planners.artifact import dependencies, events, parsing, prompts

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sunwell.agent.events import AgentEvent
    from sunwell.knowledge.project.schema import ProjectSchema
    from sunwell.models import ModelProtocol

# Pre-compiled regex patterns
_RE_FILENAME = re.compile(r"(\w+\.(?:py|js|ts|md|txt|json|yaml|yml))")
_RE_JSON_OBJECT = re.compile(r"\{[^{}]*\}", re.DOTALL)


def trivial_artifact(goal: str) -> ArtifactGraph:
    """Create single-artifact graph for trivial goals.

    Extracts filename from goal if mentioned, otherwise uses a sensible default.
    No protocols, no dependencies - just the artifact.

    Args:
        goal: The goal string

    Returns:
        ArtifactGraph with single artifact
    """
    # Try to extract filename from goal
    filename_match = _RE_FILENAME.search(goal.lower())
    filename = filename_match.group(1) if filename_match else "output.py"

    artifact = ArtifactSpec(
        id="main",
        description=goal,
        contract=goal,  # For trivial goals, contract = goal
        requires=frozenset(),
        produces_file=filename,
        domain_type="file",
    )

    graph = ArtifactGraph()
    graph.add(artifact)
    return graph


async def discover(
    model: ModelProtocol,
    goal: str,
    context: dict[str, Any] | None = None,
    project_schema: ProjectSchema | None = None,
) -> list[ArtifactSpec]:
    """Discover artifacts needed to complete a goal.

    Lower-level API that returns raw artifact specs without
    building the full graph.

    Args:
        model: Model to use for discovery
        goal: The goal to achieve
        context: Optional context
        project_schema: Optional project schema

    Returns:
        List of ArtifactSpec objects
    """
    prompt = prompts.build_discovery_prompt(goal, context, project_schema)

    from sunwell.models import GenerateOptions

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=3000),
    )

    # Pass schema through for validation (RFC-135)
    return parsing.parse_artifacts(result.content or "", schema=project_schema)


async def discover_with_recovery(
    model: ModelProtocol,
    goal: str,
    context: dict[str, Any] | None = None,
    project_schema: ProjectSchema | None = None,
    max_retries: int = 3,
    limits: Any = None,  # ArtifactLimits
    event_callback: Callable[[AgentEvent], None] | None = None,
) -> ArtifactGraph:
    """Discover artifacts with failure recovery.

    Handles:
    - Empty graphs: Re-prompt with examples
    - Graph explosion: Raise with clear guidance
    - Cycles: Detect and raise with cycle path
    - Missing root: Discover the final artifact
    - Signal-based coupling detection

    Args:
        model: Model to use for discovery
        goal: The goal to achieve
        context: Optional context
        project_schema: Optional project schema
        max_retries: Maximum retry attempts
        limits: ArtifactLimits configuration
        event_callback: Optional event callback

    Returns:
        ArtifactGraph ready for execution

    Raises:
        DiscoveryFailedError: If discovery fails after retries
        GraphExplosionError: If too many artifacts discovered
        CyclicDependencyError: If artifacts form a dependency cycle
    """
    simplify_hint = ""

    for attempt in range(max_retries):
        # Add simplification hint if previous attempt had issues
        effective_goal = f"{goal}\n\n{simplify_hint}" if simplify_hint else goal
        artifacts = await discover(model, effective_goal, context, project_schema)

        # RFC-059: Emit parsing progress
        events.emit_event(event_callback, "plan_discovery_progress", {
            "artifacts_discovered": len(artifacts),
            "phase": "parsing",
        })

        # Check for empty graph
        if not artifacts:
            if attempt < max_retries - 1:
                # Re-prompt with more guidance
                hint = "Be more concrete about what files/components need to be created."
                simplify_hint = f"Previous attempt found no artifacts. {hint}"
                continue
            else:
                events.emit_error(
                    event_callback,
                    "Discovery produced no artifacts after retries",
                    phase="discovery",
                    error_type="DiscoveryFailedError",
                    goal=goal,
                    attempts=max_retries,
                )
                raise DiscoveryFailedError("Discovery produced no artifacts after retries")

        # Check for graph explosion
        if limits and len(artifacts) > limits.max_artifacts:
            events.emit_error(
                event_callback,
                f"Graph explosion: {len(artifacts)} artifacts exceeds limit {limits.max_artifacts}",
                phase="discovery",
                error_type="GraphExplosionError",
                goal=goal,
                artifact_count=len(artifacts),
                limit=limits.max_artifacts,
            )
            raise GraphExplosionError(len(artifacts), limits.max_artifacts)

        # Signal-based plan health check
        health = dependencies.signal_plan_health(artifacts)
        if health["needs_simplification"] and attempt < max_retries - 1:
            simplify_hint = dependencies.build_simplification_hint(health)
            continue

        # RFC-059: Emit building graph progress
        events.emit_event(event_callback, "plan_discovery_progress", {
            "artifacts_discovered": len(artifacts),
            "phase": "building_graph",
            "total_estimated": len(artifacts),
        })

        # Build graph
        graph = ArtifactGraph()
        for i, artifact in enumerate(artifacts):
            graph.add(artifact)

            # RFC-059: Emit progress every 5 artifacts or at milestones
            if (i + 1) % 5 == 0 or i == len(artifacts) - 1:
                events.emit_event(event_callback, "plan_discovery_progress", {
                    "artifacts_discovered": i + 1,
                    "phase": "building_graph",
                    "total_estimated": len(artifacts),
                })

        # Check for cycles
        cycle = graph.detect_cycle()
        if cycle:
            if attempt < max_retries - 1:
                # Try to break cycle with LLM
                artifacts = await dependencies.break_cycle(model, goal, artifacts, cycle, project_schema)
                graph = ArtifactGraph()
                for artifact in artifacts:
                    graph.add(artifact)
                cycle = graph.detect_cycle()
                if not cycle:
                    # Fixed!
                    pass
                else:
                    continue  # Try again
            else:
                raise CyclicDependencyError(cycle)

        # Check for missing root
        if not graph.has_root():
            root = await discover_root(model, goal, artifacts)
            graph.add(root)

        # Check depth limit
        if limits:
            max_depth = graph.max_depth()
            if max_depth > limits.max_depth:
                error_msg = (
                    f"Graph depth ({max_depth}) exceeds limit ({limits.max_depth}). "
                    f"Consider breaking the goal into smaller subgoals."
                )
                events.emit_error(
                    event_callback,
                    error_msg,
                    phase="discovery",
                    error_type="DiscoveryFailedError",
                    goal=goal,
                    max_depth=max_depth,
                    depth_limit=limits.max_depth,
                )
                raise DiscoveryFailedError(error_msg)

        # Log orphans (warning, not error)
        orphans = graph.find_orphans()
        if orphans:
            # Orphans are allowed but noted for visibility
            orphan_ids = [o.id for o in orphans]
            logger.info(
                f"Discovered {len(orphans)} orphaned artifact(s) that are not consumed by any other artifact: {', '.join(orphan_ids)}",
                extra={
                    "orphan_count": len(orphans),
                    "orphan_ids": orphan_ids,
                    "phase": "discovery",
                }
            )

        # RFC-059: Emit discovery complete
        events.emit_event(event_callback, "plan_discovery_progress", {
            "artifacts_discovered": len(graph),
            "phase": "complete",
        })

        return graph

    events.emit_error(
        event_callback,
        f"Discovery failed after {max_retries} attempts",
        phase="discovery",
        error_type="DiscoveryFailedError",
        goal=goal,
        attempts=max_retries,
    )
    raise DiscoveryFailedError(f"Discovery failed after {max_retries} attempts")


async def discover_root(
    model: ModelProtocol,
    goal: str,
    artifacts: list[ArtifactSpec],
) -> ArtifactSpec:
    """Discover the root artifact that completes the goal.

    Args:
        model: Model to use for root discovery
        goal: Original goal
        artifacts: List of discovered artifacts

    Returns:
        Root artifact specification
    """
    artifacts_desc = "\n".join(
        f"- {a.id}: {a.description}" for a in artifacts
    )

    prompt = f"""GOAL: {goal}

DISCOVERED ARTIFACTS (no clear root):
{artifacts_desc}

These artifacts don't have a clear final convergence point.
What single artifact, when created, signals the goal is complete?

This root artifact should:
1. Depend on the key artifacts above
2. Represent the completed goal
3. Be the final integration point

Output a SINGLE artifact JSON object (not an array):
{{
  "id": "...",
  "description": "...",
  "contract": "...",
  "requires": ["..."],
  "produces_file": "..."
}}"""

    from sunwell.models import GenerateOptions

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.2, max_tokens=1000),
    )

    # Parse single artifact
    content = result.content or ""
    try:
        # Try to find JSON object
        json_match = _RE_JSON_OBJECT.search(content)
        if json_match:
            data = json.loads(json_match.group())
            return ArtifactSpec(
                id=data["id"],
                description=data["description"],
                contract=data.get("contract", ""),
                produces_file=data.get("produces_file"),
                requires=frozenset(data.get("requires", [])),
                domain_type=data.get("domain_type"),
            )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(
            f"Failed to parse root artifact from LLM response: {e}. Using generic fallback.",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "response_preview": content[:300],
            }
        )

    # Fallback: create generic root
    artifact_ids = [a.id for a in artifacts]
    logger.info(
        f"Creating generic root artifact as fallback, integrating {len(artifact_ids)} artifacts",
        extra={"artifact_count": len(artifact_ids), "artifact_ids": artifact_ids}
    )
    return ArtifactSpec(
        id="Goal",
        description=f"Complete: {goal[:50]}...",
        contract=f"Integration of: {', '.join(artifact_ids[:5])}",
        requires=frozenset(artifact_ids),
    )


async def discover_new_artifacts(
    model: ModelProtocol,
    goal: str,
    completed: dict[str, Any],
    just_created: ArtifactSpec,
    project_schema: ProjectSchema | None = None,
) -> list[ArtifactSpec]:
    """Discover if creating an artifact revealed new needs.

    Called after creating an artifact to check for:
    - Missing dependencies that should have existed
    - Supporting artifacts needed for completeness
    - Expanded scope from contract refinement

    Args:
        model: Model to use for discovery
        goal: The original goal
        completed: Dict of completed artifact IDs to their results
        just_created: The artifact that was just created
        project_schema: Optional schema for validation (RFC-135)

    Returns:
        List of new artifacts to add (empty if none needed)
    """
    completed_desc = "\n".join(
        f"- {aid}: completed" for aid in completed
    )

    prompt = f"""GOAL: {goal}

COMPLETED ARTIFACTS:
{completed_desc}

JUST CREATED:
- {just_created.id}: {just_created.description}
- File: {just_created.produces_file}
- Contract: {just_created.contract}

=== DISCOVERY CHECK ===

Now that {just_created.id} exists, consider:

1. Did creating it reveal any MISSING ARTIFACTS?
   - Dependencies that should have existed but don't
   - Supporting artifacts that would make this more complete
   - Error handlers, validators, or utilities needed

2. Did the contract EXPAND?
   - The spec mentioned something not yet in the graph
   - Integration points with systems not yet created

3. Is the goal CLOSER but still incomplete?
   - What else must exist for the original goal to be satisfied?

If new artifacts are needed, output them as a JSON array.
If no new artifacts are needed, output an empty array: []

IMPORTANT: Only identify artifacts that are TRULY NEEDED, not nice-to-haves.

Output ONLY valid JSON array:"""

    from sunwell.models import GenerateOptions

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=2000),
    )

    # Pass schema through for validation (RFC-135)
    artifacts = parsing.parse_artifacts(result.content or "", schema=project_schema)

    # Filter out already-completed artifacts
    existing_ids = set(completed.keys())
    return [a for a in artifacts if a.id not in existing_ids]
