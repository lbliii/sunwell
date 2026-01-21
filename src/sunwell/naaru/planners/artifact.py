"""Artifact-first planner for RFC-036.

This planner implements artifact discovery: instead of decomposing goals into
steps, it identifies what artifacts must exist when the goal is complete.
Dependency resolution then determines execution order.

The key insight: Ask "what must exist?" not "what steps to take?"

Example:
    >>> planner = ArtifactPlanner(model=my_model)
    >>> artifacts = await planner.discover("Build a REST API with auth")
    >>> for artifact in artifacts:
    ...     print(f"{artifact.id}: {artifact.description}")
    ...     print(f"  requires: {artifact.requires}")
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import (
    DEFAULT_LIMITS,
    ArtifactGraph,
    ArtifactLimits,
    ArtifactSpec,
    CyclicDependencyError,
    DiscoveryFailedError,
    GraphExplosionError,
    VerificationResult,
    artifacts_to_tasks,
)
from sunwell.naaru.types import Task, TaskMode

if TYPE_CHECKING:
    from sunwell.adaptive.events import AgentEvent
    from sunwell.models.protocol import ModelProtocol
    from sunwell.project.schema import ProjectSchema


@dataclass
class ArtifactPlanner:
    """Plans by discovering artifacts, not decomposing steps (RFC-036).

    Instead of procedural decomposition ("what steps?"), this planner
    identifies what artifacts must exist ("what things?") and lets
    dependency resolution determine execution order.

    Benefits:
    - Structural parallelism: leaves execute in parallel automatically
    - Adaptive model selection: depth determines model tier
    - Isolated failures: errors don't cascade to independent branches
    - Complexity-aware: trivial goals skip discovery entirely

    Example:
        >>> planner = ArtifactPlanner(
        ...     model=my_model,
        ...     limits=ArtifactLimits(max_artifacts=30),
        ... )
        >>> graph = await planner.discover_graph("Build a REST API with auth")
        >>> print(graph.execution_waves())
        [["UserProtocol", "AuthInterface"], ["UserModel", "AuthService"], ["App"]]

        # Trivial goals are handled efficiently:
        >>> graph = await planner.discover_graph("Create hello.py that prints Hello")
        >>> print(graph.execution_waves())
        [["main"]]  # Single artifact, no protocol overhead
    """

    model: ModelProtocol
    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    max_retries: int = 3

    # RFC-035: Schema-aware planning
    project_schema: ProjectSchema | None = None
    """Project schema for domain-specific artifact types."""

    # Complexity routing (optional): tiny model to assess before full discovery
    router: Any | None = None  # UnifiedRouter - avoids circular import
    """Router for complexity assessment. If provided, trivial goals skip discovery."""

    # RFC-059: Event callback for discovery progress
    event_callback: Callable[[AgentEvent], None] | None = None
    """Optional callback for emitting discovery progress events (RFC-059)."""

    @property
    def mode(self) -> TaskMode:
        """This planner produces composite tasks."""
        return TaskMode.COMPOSITE

    # =========================================================================
    # RFC-059: Event Emission
    # =========================================================================

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event via callback if configured (RFC-059).

        RFC-060: Uses create_validated_event() for schema validation.
        Validation mode controlled by SUNWELL_EVENT_VALIDATION env var.
        """
        if self.event_callback is None:
            return

        try:
            from sunwell.adaptive.events import EventType
            from sunwell.adaptive.event_schema import create_validated_event

            # RFC-060: Validate event data against schema
            event = create_validated_event(EventType(event_type), data)
            self.event_callback(event)
        except ValueError as e:
            # Invalid event type or validation failure (strict mode)
            import logging

            logging.warning(f"Event validation failed for '{event_type}': {e}")
        except Exception as e:
            # Other errors - log but don't break discovery
            import logging

            logging.warning(f"Event emission failed for '{event_type}': {e}")

    def _emit_error(
        self,
        message: str,
        phase: str | None = None,
        error_type: str | None = None,
        **context: Any,
    ) -> None:
        """Emit error event with context (RFC-059).

        Args:
            message: Error message (required)
            phase: Phase where error occurred ("planning" | "discovery" | "execution" | "validation")
            error_type: Exception class name
            **context: Additional context (artifact_id, task_id, goal, etc.)
        """
        error_data: dict[str, Any] = {"message": message}
        if phase:
            error_data["phase"] = phase
        if error_type:
            error_data["error_type"] = error_type
        if context:
            error_data["context"] = context
        self._emit_event("error", error_data)

    # =========================================================================
    # Main API
    # =========================================================================

    async def plan(
        self,
        goals: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Discover artifacts and convert to RFC-034 tasks.

        This is the TaskPlanner protocol implementation, providing
        compatibility with existing execution infrastructure.

        Args:
            goals: User-specified goals
            context: Optional context (cwd, files, etc.)

        Returns:
            List of Tasks with dependencies in execution order

        Raises:
            PlanningError: If discovery fails
        """
        goal = goals[0] if goals else "No goal specified"
        graph = await self.discover_graph(goal, context)
        return artifacts_to_tasks(graph)

    async def discover_graph(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ArtifactGraph:
        """Discover artifacts and build dependency graph.

        Main entry point for artifact-first planning.

        If a router is configured, trivial goals skip full discovery and
        return a single artifact. This prevents over-engineering simple tasks
        like "create hello.py that prints Hello World".

        Args:
            goal: The goal to achieve
            context: Optional context

        Returns:
            ArtifactGraph ready for execution

        Raises:
            DiscoveryFailedError: If discovery fails after retries
            GraphExplosionError: If too many artifacts discovered
            CyclicDependencyError: If artifacts form a dependency cycle
        """
        # RFC-059: Emit discovery start
        self._emit_event("plan_discovery_progress", {
            "artifacts_discovered": 0,
            "phase": "discovering",
        })

        # Complexity gate: trivial goals skip full discovery
        if self.router is not None:
            try:
                decision = await self.router.route(goal, context)
                # Import here to avoid circular dependency
                from sunwell.routing.unified import Complexity

                if decision.complexity == Complexity.TRIVIAL:
                    graph = self._trivial_artifact(goal)
                    # RFC-059: Emit complete for trivial case
                    self._emit_event("plan_discovery_progress", {
                        "artifacts_discovered": len(graph),
                        "phase": "complete",
                    })
                    return graph
            except Exception:
                pass  # Fall through to full discovery on router failure

        return await self._discover_with_recovery(goal, context)

    def _trivial_artifact(self, goal: str) -> ArtifactGraph:
        """Create single-artifact graph for trivial goals.

        Extracts filename from goal if mentioned, otherwise uses a sensible default.
        No protocols, no dependencies - just the artifact.
        """
        import re

        # Try to extract filename from goal
        filename_match = re.search(r'(\w+\.(?:py|js|ts|md|txt|json|yaml|yml))', goal.lower())
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
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> list[ArtifactSpec]:
        """Discover artifacts needed to complete a goal.

        Lower-level API that returns raw artifact specs without
        building the full graph.

        Args:
            goal: The goal to achieve
            context: Optional context

        Returns:
            List of ArtifactSpec objects
        """
        prompt = self._build_discovery_prompt(goal, context)

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=3000),
        )

        return self._parse_artifacts(result.content or "")

    # =========================================================================
    # Discovery with Recovery (Failure Handling)
    # =========================================================================

    async def _discover_with_recovery(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ArtifactGraph:
        """Discover artifacts with failure recovery.

        Handles:
        - Empty graphs: Re-prompt with examples
        - Graph explosion: Raise with clear guidance
        - Cycles: Detect and raise with cycle path
        - Missing root: Discover the final artifact
        - Signal-based coupling detection (NEW)
        """
        simplify_hint = ""

        for attempt in range(self.max_retries):
            # Add simplification hint if previous attempt had issues
            effective_goal = f"{goal}\n\n{simplify_hint}" if simplify_hint else goal
            artifacts = await self.discover(effective_goal, context)

            # RFC-059: Emit parsing progress
            self._emit_event("plan_discovery_progress", {
                "artifacts_discovered": len(artifacts),
                "phase": "parsing",
            })

            # Check for empty graph
            if not artifacts:
                if attempt < self.max_retries - 1:
                    # Re-prompt with more guidance
                    hint = "Be more concrete about what files/components need to be created."
                    simplify_hint = f"Previous attempt found no artifacts. {hint}"
                    continue
                else:
                    self._emit_error(
                        "Discovery produced no artifacts after retries",
                        phase="discovery",
                        error_type="DiscoveryFailedError",
                        goal=goal,
                        attempts=self.max_retries,
                    )
                    raise DiscoveryFailedError("Discovery produced no artifacts after retries")

            # Check for graph explosion
            if len(artifacts) > self.limits.max_artifacts:
                self._emit_error(
                    f"Graph explosion: {len(artifacts)} artifacts exceeds limit {self.limits.max_artifacts}",
                    phase="discovery",
                    error_type="GraphExplosionError",
                    goal=goal,
                    artifact_count=len(artifacts),
                    limit=self.limits.max_artifacts,
                )
                raise GraphExplosionError(len(artifacts), self.limits.max_artifacts)

            # Signal-based plan health check (NEW)
            health = self._signal_plan_health(artifacts)
            if health["needs_simplification"] and attempt < self.max_retries - 1:
                simplify_hint = self._build_simplification_hint(health)
                continue

            # RFC-059: Emit building graph progress
            self._emit_event("plan_discovery_progress", {
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
                    self._emit_event("plan_discovery_progress", {
                        "artifacts_discovered": i + 1,
                        "phase": "building_graph",
                        "total_estimated": len(artifacts),
                    })

            # Check for cycles
            cycle = graph.detect_cycle()
            if cycle:
                if attempt < self.max_retries - 1:
                    # Try to break cycle with LLM
                    artifacts = await self._break_cycle(goal, artifacts, cycle)
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
                root = await self._discover_root(goal, artifacts)
                graph.add(root)

            # Check depth limit
            max_depth = graph.max_depth()
            if max_depth > self.limits.max_depth:
                error_msg = (
                    f"Graph depth ({max_depth}) exceeds limit ({self.limits.max_depth}). "
                    f"Consider breaking the goal into smaller subgoals."
                )
                self._emit_error(
                    error_msg,
                    phase="discovery",
                    error_type="DiscoveryFailedError",
                    goal=goal,
                    max_depth=max_depth,
                    depth_limit=self.limits.max_depth,
                )
                raise DiscoveryFailedError(error_msg)

            # Log orphans (warning, not error)
            orphans = graph.find_orphans()
            if orphans:
                # Orphans are allowed but noted
                pass

            # RFC-059: Emit discovery complete
            self._emit_event("plan_discovery_progress", {
                "artifacts_discovered": len(graph),
                "phase": "complete",
            })

            return graph

        self._emit_error(
            f"Discovery failed after {self.max_retries} attempts",
            phase="discovery",
            error_type="DiscoveryFailedError",
            goal=goal,
            attempts=self.max_retries,
        )
        raise DiscoveryFailedError(f"Discovery failed after {self.max_retries} attempts")

    def _signal_plan_health(self, artifacts: list[ArtifactSpec]) -> dict[str, Any]:
        """Signal-based plan health check using 0/1/2 (Trit) scoring.

        Checks for:
        - Over-coupling: Too many dependencies per artifact
        - Bidirectional deps: A→B and B→A (cycle risk)
        - Transitive cycles: A→B→C→A
        - Fan-in/fan-out: Single artifact with too many dependents

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
        cycle = self._find_cycle_in_deps(dep_map)
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

    def _find_cycle_in_deps(self, dep_map: dict[str, set[str]]) -> list[str] | None:
        """DFS cycle detection on dependency map. Returns cycle path if found."""
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

    def _build_simplification_hint(self, health: dict[str, Any]) -> str:
        """Build a hint for the model to simplify the plan."""
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

    async def _break_cycle(
        self,
        goal: str,
        artifacts: list[ArtifactSpec],
        cycle: list[str],
    ) -> list[ArtifactSpec]:
        """Ask LLM to break a dependency cycle."""
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

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=3000),
        )

        return self._parse_artifacts(result.content or "")

    async def _discover_root(
        self,
        goal: str,
        artifacts: list[ArtifactSpec],
    ) -> ArtifactSpec:
        """Discover the root artifact that completes the goal."""
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

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=1000),
        )

        # Parse single artifact
        content = result.content or ""
        try:
            # Try to find JSON object
            json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
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
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: create generic root
        artifact_ids = [a.id for a in artifacts]
        return ArtifactSpec(
            id="Goal",
            description=f"Complete: {goal[:50]}...",
            contract=f"Integration of: {', '.join(artifact_ids[:5])}",
            requires=frozenset(artifact_ids),
        )

    # =========================================================================
    # Dynamic Discovery (Mid-Execution)
    # =========================================================================

    async def discover_new_artifacts(
        self,
        goal: str,
        completed: dict[str, Any],
        just_created: ArtifactSpec,
    ) -> list[ArtifactSpec]:
        """Discover if creating an artifact revealed new needs.

        Called after creating an artifact to check for:
        - Missing dependencies that should have existed
        - Supporting artifacts needed for completeness
        - Expanded scope from contract refinement

        Args:
            goal: The original goal
            completed: Dict of completed artifact IDs to their results
            just_created: The artifact that was just created

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

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=2000),
        )

        artifacts = self._parse_artifacts(result.content or "")

        # Filter out already-completed artifacts
        existing_ids = set(completed.keys())
        return [a for a in artifacts if a.id not in existing_ids]

    # =========================================================================
    # Verification
    # =========================================================================

    async def verify_artifact(
        self,
        artifact: ArtifactSpec,
        created_content: str,
    ) -> VerificationResult:
        """Verify that created content satisfies the artifact's contract.

        Uses LLM-based verification to check if the implementation
        matches the specification.

        Args:
            artifact: The artifact specification
            created_content: The actual content that was created

        Returns:
            VerificationResult with pass/fail and explanation
        """
        # Truncate very long content
        content_preview = created_content[:3000]
        if len(created_content) > 3000:
            content_preview += "\n... [truncated]"

        prompt = f"""ARTIFACT: {artifact.id}

CONTRACT (what it must satisfy):
{artifact.contract}

CREATED CONTENT:
{content_preview}

=== VERIFICATION ===

Does the created content satisfy the contract?

Check:
1. Are all required elements present?
2. Does the implementation match the specification?
3. Are there any violations or missing pieces?

Output JSON:
{{
  "passed": true/false,
  "reason": "Explanation of the result",
  "gaps": ["Missing element 1", "Missing element 2"],
  "confidence": 0.0-1.0
}}"""

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=1000),
        )

        # Parse verification result
        content = result.content or ""
        try:
            json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return VerificationResult(
                    passed=data.get("passed", False),
                    reason=data.get("reason", "No reason provided"),
                    gaps=tuple(data.get("gaps", [])),
                    confidence=data.get("confidence", 0.5),
                )
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: assume passed (optimistic)
        return VerificationResult(
            passed=True,
            reason="Could not parse verification response",
            confidence=0.3,
        )

    # =========================================================================
    # Artifact Creation
    # =========================================================================

    async def create_artifact(
        self,
        artifact: ArtifactSpec,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Create the content for an artifact based on its specification.

        Uses the model to generate code/content that satisfies the artifact's
        contract and description.

        Args:
            artifact: The artifact specification
            context: Optional context (completed artifacts, cwd, etc.)

        Returns:
            Generated content as a string
        """
        prompt = self._build_creation_prompt(artifact, context)

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=4000),
        )

        # Extract code from response (may be wrapped in markdown code blocks)
        content = result.content or ""
        return self._extract_code(content, artifact.produces_file)

    def _build_creation_prompt(
        self,
        artifact: ArtifactSpec,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Build prompt for creating artifact content."""
        # Determine file extension for language hints
        file_ext = ""
        if artifact.produces_file and "." in artifact.produces_file:
            file_ext = artifact.produces_file.split(".")[-1]
        else:
            file_ext = "py"

        language_hint = {
            "py": "Python",
            "js": "JavaScript",
            "ts": "TypeScript",
            "rs": "Rust",
            "go": "Go",
            "java": "Java",
            "md": "Markdown",
            "json": "JSON",
            "yaml": "YAML",
            "yml": "YAML",
        }.get(file_ext, "Python")

        # Build context section
        context_section = ""
        if context and "completed" in context:
            completed_desc = "\n".join(
                f"- {aid}: {info.get('description', 'completed')}"
                for aid, info in context.get("completed", {}).items()
            )
            context_section = f"\n\nCOMPLETED DEPENDENCIES:\n{completed_desc}"

        return f"""Create the following artifact:

ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}
CONTRACT: {artifact.contract}
FILE: {artifact.produces_file or f"{artifact.id.lower()}.py"}
TYPE: {artifact.domain_type or "component"}
REQUIRES: {list(artifact.requires) if artifact.requires else "none"}
{context_section}

=== REQUIREMENTS ===

Generate {language_hint} code that:
1. Fully satisfies the CONTRACT specified above
2. Is complete and ready to use (no placeholders or TODOs)
3. Follows best practices for {language_hint}
4. Includes necessary imports
5. Has clear docstrings/comments

=== OUTPUT FORMAT ===

Output ONLY the code for this file. No explanations before or after.
Start directly with the code (imports, class definitions, etc.).

```{file_ext}
"""

    def _extract_code(self, response: str, filename: str | None = None) -> str:
        """Extract code from LLM response, handling markdown code blocks."""
        # Try to extract from markdown code block
        import re

        # Pattern for code blocks with any language tag
        code_match = re.search(r"```(?:\w+)?\s*\n(.*?)```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # If no code block, check if response starts with typical code patterns
        lines = response.strip().split("\n")
        code_starters = (
            "import ", "from ", "#!", "//", "/*", "class ", "def ",
            "const ", "let ", "var ", "function ", "package ",
        )
        data_starters = ("{", "[", "---")  # JSON, YAML
        if lines and (
            lines[0].startswith(code_starters)
            or lines[0].strip().startswith(data_starters)
        ):
            return response.strip()

        # If response contains code block markers without closing, extract what's after
        if "```" in response:
            parts = response.split("```")
            if len(parts) >= 2:
                # Take content after first ```, strip language tag if present
                code = parts[1]
                first_newline = code.find("\n")
                if first_newline > 0 and first_newline < 20:  # Likely a language tag
                    code = code[first_newline + 1:]
                return code.strip()

        # Fallback: return as-is
        return response.strip()

    # =========================================================================
    # Prompt Building
    # =========================================================================

    def _build_discovery_prompt(
        self,
        goal: str,
        context: dict[str, Any] | None,
    ) -> str:
        """Build the artifact discovery prompt."""
        context_str = self._format_context(context)

        # RFC-035: Add schema context if available
        schema_section = ""
        if self.project_schema:
            schema_section = self._build_schema_section()

        return f"""GOAL: {goal}

CONTEXT:
{context_str}
{schema_section}
=== ARTIFACT DISCOVERY ===

Think about this goal differently. Don't ask "what steps should I take?"
Instead ask: "When this goal is complete, what THINGS will exist?"

For each thing that must exist, identify:
- id: A unique name (e.g., "UserProtocol", "Chapter1", "Hypothesis_A")
- description: What is this thing?
- contract: What must it provide/satisfy? (This is its specification)
- requires: What other artifacts must exist BEFORE this one can be created?
- produces_file: What file will contain this artifact?
- domain_type: Type category (e.g., "protocol", "model", "service", "component")

=== DISCOVERY PRINCIPLES ===

1. CONTRACTS BEFORE IMPLEMENTATIONS
   Interfaces, protocols, outlines, specs — these have no dependencies.
   Implementations require their contracts to exist first.

2. IDENTIFY ALL LEAVES
   Leaves are artifacts with no requirements. They can all be created in parallel.
   Ask: "What can I create right now with no prerequisites?"

3. TRACE TO ROOT
   The root is the final artifact that satisfies the goal.
   Everything flows toward it.

4. SEMANTIC DEPENDENCIES
   A requires B if creating A needs to reference, implement, or build on B.
   "UserModel requires UserProtocol" because it implements that protocol.

=== EXAMPLE ===

Goal: "Build a REST API with user authentication"

```json
[
  {{
    "id": "UserProtocol",
    "description": "Protocol defining User entity",
    "contract": "Protocol with fields: id, email, password_hash, created_at",
    "requires": [],
    "produces_file": "src/protocols/user.py",
    "domain_type": "protocol"
  }},
  {{
    "id": "AuthInterface",
    "description": "Interface for authentication operations",
    "contract": "Protocol: authenticate(), generate_token(), verify_token()",
    "requires": [],
    "produces_file": "src/protocols/auth.py",
    "domain_type": "protocol"
  }},
  {{
    "id": "UserModel",
    "description": "SQLAlchemy model implementing UserProtocol",
    "contract": "Class User(Base) implementing UserProtocol",
    "requires": ["UserProtocol"],
    "produces_file": "src/models/user.py",
    "domain_type": "model"
  }},
  {{
    "id": "AuthService",
    "description": "JWT-based authentication service",
    "contract": "Class implementing AuthInterface with JWT + bcrypt",
    "requires": ["AuthInterface", "UserProtocol"],
    "produces_file": "src/services/auth.py",
    "domain_type": "service"
  }},
  {{
    "id": "UserRoutes",
    "description": "REST endpoints for user operations",
    "contract": "Flask Blueprint: POST /users, GET /users/me, PUT /users/me",
    "requires": ["UserModel", "AuthService"],
    "produces_file": "src/routes/users.py",
    "domain_type": "routes"
  }},
  {{
    "id": "App",
    "description": "Flask application factory",
    "contract": "create_app() initializing Flask, blueprints, database",
    "requires": ["UserRoutes"],
    "produces_file": "src/app.py",
    "domain_type": "application"
  }}
]
```

Analysis:
- Leaves (parallel): UserProtocol, AuthInterface (no requirements)
- Second wave: UserModel, AuthService (require protocols)
- Third wave: UserRoutes (requires model + service)
- Root: App (final convergence)

=== NOW DISCOVER ARTIFACTS FOR ===

Goal: {goal}

Output ONLY valid JSON array of artifacts:"""

    def _build_schema_section(self) -> str:
        """Build schema context for RFC-035 integration."""
        if not self.project_schema:
            return ""

        schema = self.project_schema
        lines = [
            "",
            f"=== PROJECT SCHEMA: {schema.name} ===",
            f"Type: {schema.project_type}",
            "",
            "AVAILABLE ARTIFACT TYPES:",
        ]

        for name, artifact_type in schema.artifact_types.items():
            lines.append(f"- {name}: {artifact_type.description}")
            if artifact_type.is_contract:
                lines.append("  (Contract type - no dependencies)")
            if artifact_type.requires_patterns:
                requires = ", ".join(artifact_type.requires_patterns)
                lines.append(f"  Typical requires: {requires}")

        if schema.planning_config.phases:
            lines.extend(["", "PLANNING PHASES:"])
            for phase in schema.planning_config.phases:
                parallel = "⚡ parallel" if phase.parallel else "→ sequential"
                lines.append(f"- {phase.name} ({parallel})")
                if phase.artifact_types:
                    types = ", ".join(phase.artifact_types)
                    lines.append(f"  Artifact types: {types}")

        lines.extend([
            "",
            "When discovering artifacts, prefer types from this schema.",
            "Set domain_type to match schema artifact types.",
            "",
        ])

        return "\n".join(lines)

    def _format_context(self, context: dict[str, Any] | None) -> str:
        """Format context for the discovery prompt."""
        if not context:
            return "No additional context."

        lines = []
        if "cwd" in context:
            lines.append(f"Working directory: {context['cwd']}")
        if "files" in context:
            files = context["files"][:15]
            lines.append(f"Existing files: {', '.join(str(f) for f in files)}")
        if "description" in context:
            lines.append(f"Project: {context['description']}")

        return "\n".join(lines) or "No additional context."

    # =========================================================================
    # Parsing
    # =========================================================================

    def _parse_artifacts(self, response: str) -> list[ArtifactSpec]:
        """Parse LLM response into ArtifactSpec objects."""
        artifacts_data = self._extract_json(response)

        if not artifacts_data:
            return []

        artifacts = []
        for item in artifacts_data:
            try:
                artifact = ArtifactSpec(
                    id=item["id"],
                    description=item.get("description", f"Artifact {item['id']}"),
                    contract=item.get("contract", ""),
                    produces_file=item.get("produces_file"),
                    requires=frozenset(item.get("requires", [])),
                    domain_type=item.get("domain_type"),
                    metadata=item.get("metadata", {}),
                )
                artifacts.append(artifact)
            except (KeyError, TypeError):
                # Skip malformed artifacts
                continue

        return artifacts

    def _extract_json(self, response: str) -> list[dict] | None:
        """Extract JSON array from LLM response."""
        # Strategy 1: Find JSON array with regex
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Strategy 2: Look for code block with JSON
        code_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Try parsing entire response
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        return None
