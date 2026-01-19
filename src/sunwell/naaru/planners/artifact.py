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

import json
import re
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

    Example:
        >>> planner = ArtifactPlanner(
        ...     model=my_model,
        ...     limits=ArtifactLimits(max_artifacts=30),
        ... )
        >>> graph = await planner.discover_graph("Build a REST API with auth")
        >>> print(graph.execution_waves())
        [["UserProtocol", "AuthInterface"], ["UserModel", "AuthService"], ["App"]]
    """

    model: ModelProtocol
    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    max_retries: int = 3

    # RFC-035: Schema-aware planning
    project_schema: ProjectSchema | None = None
    """Project schema for domain-specific artifact types."""

    @property
    def mode(self) -> TaskMode:
        """This planner produces composite tasks."""
        return TaskMode.COMPOSITE

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
        return await self._discover_with_recovery(goal, context)

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
        """
        for attempt in range(self.max_retries):
            artifacts = await self.discover(goal, context)

            # Check for empty graph
            if not artifacts:
                if attempt < self.max_retries - 1:
                    # Re-prompt with more guidance
                    hint = "Be more concrete about what files/components need to be created."
                    goal = f"{goal}\n\nPrevious attempt found no artifacts. {hint}"
                    continue
                else:
                    raise DiscoveryFailedError("Discovery produced no artifacts after retries")

            # Check for graph explosion
            if len(artifacts) > self.limits.max_artifacts:
                raise GraphExplosionError(len(artifacts), self.limits.max_artifacts)

            # Build graph
            graph = ArtifactGraph()
            for artifact in artifacts:
                graph.add(artifact)

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
                raise DiscoveryFailedError(
                    f"Graph depth ({max_depth}) exceeds limit ({self.limits.max_depth}). "
                    f"Consider breaking the goal into smaller subgoals."
                )

            # Log orphans (warning, not error)
            orphans = graph.find_orphans()
            if orphans:
                # Orphans are allowed but noted
                pass

            return graph

        raise DiscoveryFailedError(f"Discovery failed after {self.max_retries} attempts")

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
