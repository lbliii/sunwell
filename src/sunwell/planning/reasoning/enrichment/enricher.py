"""Context enrichment for reasoned decisions (RFC-073)."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.knowledge.codebase.advisor import TaskGraphAdvisor, TaskType
from sunwell.planning.reasoning.decisions import DecisionType

if TYPE_CHECKING:
    from sunwell.agent.incremental.cache import ExecutionCache
    from sunwell.knowledge.project.schema import ProjectContext
    from sunwell.planning.naaru.artifacts import ArtifactGraph


class ContextEnricher:
    """Assembles rich context from all available sources for reasoned decisions.

    Sources:
    - CodebaseGraph: Static/dynamic analysis (hot paths, coupling, ownership)
    - TaskGraphAdvisor: Structural graph analysis (complexity, impact, context)
    - ExecutionCache: Provenance and execution history
    - ProjectContext: Decisions, failures, patterns
    - ArtifactGraph: Dependency relationships
    """

    def __init__(
        self,
        project_context: ProjectContext | None = None,
        execution_cache: ExecutionCache | None = None,
        artifact_graph: ArtifactGraph | None = None,
        decision_history: dict[DecisionType, list[Any]] | None = None,
        task_advisor: TaskGraphAdvisor | None = None,
    ) -> None:
        """Initialize context enricher.

        Args:
            project_context: Unified context with decisions, failures, patterns
            execution_cache: Provenance tracking and execution history
            artifact_graph: Dependency relationships between artifacts
            decision_history: History of decisions by type for similarity matching
            task_advisor: Graph-based task analysis for complexity and impact
        """
        self._project_context = project_context
        self._execution_cache = execution_cache
        self._artifact_graph = artifact_graph
        self._decision_history = decision_history or {}
        self._task_advisor = task_advisor

    async def enrich(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble rich context from all available sources.

        Args:
            decision_type: Type of decision being made
            context: Base context to enrich

        Returns:
            Enriched context dict with all available information
        """
        enriched = dict(context)

        # === CodebaseGraph (RFC-045): Static + Dynamic Analysis ===
        if "file_path" in context and self._project_context:
            await self._enrich_from_codebase(enriched)

        # === ExecutionCache (RFC-074): Provenance + History ===
        if "artifact_id" in context and self._execution_cache:
            await self._enrich_from_cache(enriched, context["artifact_id"])

        # === ProjectContext (RFC-045): Memory + Learning ===
        if self._project_context:
            await self._enrich_from_project_context(enriched, decision_type)

        # === ArtifactGraph (RFC-036): Dependencies ===
        if "artifact_id" in context and self._artifact_graph:
            await self._enrich_from_artifact_graph(enriched, context["artifact_id"])

        # === TaskGraphAdvisor: Structural Graph Analysis ===
        if self._task_advisor:
            # Try to infer target entity from context if not explicitly provided
            target = self._infer_target_entity(context)
            if target:
                context_with_target = {**context, "target_entity": target}
                await self._enrich_from_task_advisor(enriched, context_with_target)

        return enriched

    async def _enrich_from_codebase(self, enriched: dict[str, Any]) -> None:
        """Add codebase graph context."""
        if not self._project_context:
            return

        file_path = Path(enriched.get("file_path", ""))
        codebase = self._project_context.codebase

        # Check hot paths
        enriched["in_hot_path"] = any(
            file_path.name in path.nodes for path in codebase.hot_paths
        )

        # Check error-prone
        enriched["is_error_prone"] = any(
            loc.file == file_path for loc in codebase.error_prone
        )

        # Get change frequency
        enriched["change_frequency"] = codebase.change_frequency.get(file_path, 0.0)

        # Get ownership
        enriched["file_ownership"] = codebase.file_ownership.get(file_path)

        # Get coupling score (sum of all couplings involving this file's module)
        module_name = str(file_path.with_suffix("")).replace("/", ".")
        coupling_scores = [
            score
            for (m1, m2), score in codebase.coupling_scores.items()
            if module_name in (m1, m2)
        ]
        if coupling_scores:
            enriched["coupling"] = sum(coupling_scores) / len(coupling_scores)
        else:
            enriched["coupling"] = 0.0

    async def _enrich_from_cache(
        self,
        enriched: dict[str, Any],
        artifact_id: str,
    ) -> None:
        """Add execution cache context."""
        if not self._execution_cache:
            return

        entry = self._execution_cache.get(artifact_id)
        if entry:
            enriched["skip_count"] = entry.skip_count
            enriched["last_execution_time_ms"] = entry.execution_time_ms
            enriched["last_status"] = entry.status.value

        # Lineage queries (O(1) via recursive CTE)
        enriched["upstream_artifacts"] = self._execution_cache.get_upstream(artifact_id)
        enriched["downstream_artifacts"] = self._execution_cache.get_downstream(artifact_id)

    async def _enrich_from_project_context(
        self,
        enriched: dict[str, Any],
        decision_type: DecisionType,
    ) -> None:
        """Add project context (decisions, failures, patterns)."""
        if not self._project_context:
            return

        # Similar past decisions
        try:
            similar = await self._query_similar_decisions(decision_type, enriched)
            enriched["similar_decisions"] = similar
        except Exception:
            enriched["similar_decisions"] = []

        # Related failures
        try:
            failures = await self._query_related_failures(enriched)
            enriched["related_failures"] = failures
        except Exception:
            enriched["related_failures"] = []

        # User patterns
        try:
            patterns = await self._query_user_patterns(decision_type)
            enriched["user_patterns"] = patterns
        except Exception:
            enriched["user_patterns"] = []

    async def _enrich_from_artifact_graph(
        self,
        enriched: dict[str, Any],
        artifact_id: str,
    ) -> None:
        """Add artifact graph context."""
        if not self._artifact_graph:
            return

        spec = self._artifact_graph.get(artifact_id)
        if spec:
            enriched["artifact_requires"] = list(spec.requires)
            enriched["artifact_contract"] = spec.contract

    async def _enrich_from_task_advisor(
        self,
        enriched: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Add structural graph analysis context.

        Uses TaskGraphAdvisor to provide:
        - Complexity estimation (fan-out analysis)
        - Impact scope (transitive reachability)
        - Suggested decomposition hints
        """
        if not self._task_advisor:
            return

        target = context.get("target_entity", "")
        if not target:
            return

        # Determine task type from context
        task_type = self._infer_task_type(context)

        try:
            # Run graph analysis
            advice = self._task_advisor.analyze(task_type, target)

            # Add complexity metrics
            if advice.complexity:
                enriched["complexity_score"] = advice.complexity.score
                enriched["complexity_level"] = advice.complexity.level
                enriched["complexity_fan_out"] = advice.complexity.fan_out
                enriched["complexity_fan_in"] = advice.complexity.fan_in
                enriched["complexity_rationale"] = advice.complexity.rationale

            # Add impact scope
            if advice.impact:
                enriched["impact_affected_count"] = advice.impact.transitive_dependents
                enriched["impact_direct_dependents"] = advice.impact.direct_dependents
                enriched["impact_affected_files"] = [
                    str(f) for f in advice.impact.affected_files[:10]
                ]
                enriched["impact_rationale"] = advice.impact.rationale

            # Add context info
            if advice.context:
                enriched["context_relevant_files"] = [
                    str(f) for f in advice.context.relevant_files[:10]
                ]
                enriched["context_node_count"] = len(advice.context.relevant_nodes)

            # Add suggested decomposition
            if advice.subtask_hints:
                enriched["suggested_subtasks"] = advice.subtask_hints

            # Add potential issues
            if advice.potential_issues:
                enriched["potential_issues"] = advice.potential_issues

            # Add suggested tests
            if advice.suggested_tests:
                enriched["suggested_tests"] = advice.suggested_tests

        except Exception:
            # Graph analysis failed - continue without it
            pass

    def _infer_target_entity(self, context: dict[str, Any]) -> str | None:
        """Infer target entity from context fields.

        Tries multiple strategies:
        1. Explicit target_entity
        2. Symbol name (function, class, method)
        3. File path (extract module name)
        4. Goal/description (extract likely entity names)
        """
        # 1. Explicit target
        if "target_entity" in context:
            return context["target_entity"]

        # 2. Symbol name
        for key in ("symbol_name", "function_name", "class_name", "method_name"):
            if key in context and context[key]:
                return context[key]

        # 3. File path → module name
        if "file_path" in context:
            file_path = Path(context["file_path"])
            # Use stem without extension as target
            return file_path.stem

        # 4. Content that might contain symbol references
        # (This is a heuristic - could be improved with NLP)
        for key in ("content", "signal", "description"):
            if key in context and context[key]:
                content = str(context[key])
                # Look for CamelCase or snake_case words that might be symbols
                import re
                # CamelCase: UserService, MyClass
                camel = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", content)
                if camel:
                    return camel[0]
                # snake_case with at least one underscore
                snake = re.findall(r"\b([a-z]+_[a-z_]+)\b", content)
                if snake:
                    return snake[0]

        return None

    def _infer_task_type(self, context: dict[str, Any]) -> TaskType:
        """Infer task type from context."""
        # Check explicit task_type
        explicit = context.get("task_type")
        if explicit:
            try:
                return TaskType[explicit.upper()]
            except KeyError:
                pass

        # Infer from goal or description
        goal = context.get("goal", "").lower()
        description = context.get("description", "").lower()
        text = f"{goal} {description}"

        if any(w in text for w in ("add", "create", "implement", "new")):
            return TaskType.ADD_FEATURE
        if any(w in text for w in ("fix", "bug", "error", "issue")):
            return TaskType.FIX_BUG
        if any(w in text for w in ("refactor", "clean", "improve", "reorganize")):
            return TaskType.REFACTOR
        if any(w in text for w in ("understand", "explain", "how", "what", "why")):
            return TaskType.UNDERSTAND
        if any(w in text for w in ("delete", "remove", "drop")):
            return TaskType.DELETE
        if any(w in text for w in ("test", "spec", "coverage")):
            return TaskType.TEST
        if any(w in text for w in ("modify", "change", "update")):
            return TaskType.MODIFY

        # Default to MODIFY as a safe fallback
        return TaskType.MODIFY

    async def _query_similar_decisions(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query similar past decisions from ProjectContext."""
        if not self._project_context:
            return []

        # Use index for O(1) type lookup instead of O(n) scan
        history = self._decision_history.get(decision_type, [])
        similar = []
        for decision in history[-100:]:  # Last 100 of this type
            # Simple similarity: same file path or signal type
            if context.get("file_path") and hasattr(decision, "context_used"):
                if "file_path" in decision.context_used:
                    similar.append(decision.to_dict() if hasattr(decision, "to_dict") else {})
        return similar[:5]  # Top 5 similar

    async def _query_related_failures(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query related failures from ProjectContext."""
        if not self._project_context or not hasattr(self._project_context, "failures"):
            return []

        try:
            file_path = context.get("file_path")
            if file_path:
                failures = self._project_context.failures.query_by_file(Path(file_path))
                return [f.to_dict() for f in failures[:3]] if failures else []
        except Exception:
            pass
        return []

    async def _query_user_patterns(
        self,
        decision_type: DecisionType,
    ) -> list[str]:
        """Query user patterns from ProjectContext."""
        if not self._project_context or not hasattr(self._project_context, "patterns"):
            return []

        try:
            patterns = self._project_context.patterns.get_patterns(decision_type.value)
            return patterns if patterns else []
        except Exception:
            return []
