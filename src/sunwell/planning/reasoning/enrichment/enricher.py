"""Context enrichment for reasoned decisions (RFC-073)."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.planning.reasoning.decisions import DecisionType

if TYPE_CHECKING:
    from sunwell.planning.naaru.artifacts import ArtifactGraph
    from sunwell.knowledge.project.schema import ProjectContext
    from sunwell.agent.incremental.cache import ExecutionCache


class ContextEnricher:
    """Assembles rich context from all available sources for reasoned decisions.

    Sources:
    - CodebaseGraph: Static/dynamic analysis (hot paths, coupling, ownership)
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
    ) -> None:
        """Initialize context enricher.

        Args:
            project_context: Unified context with decisions, failures, patterns
            execution_cache: Provenance tracking and execution history
            artifact_graph: Dependency relationships between artifacts
            decision_history: History of decisions by type for similarity matching
        """
        self._project_context = project_context
        self._execution_cache = execution_cache
        self._artifact_graph = artifact_graph
        self._decision_history = decision_history or {}

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
