"""Handlers for Sunwell self-access tools (RFC-125).

Direct Python API calls for performance (~5ms vs ~500ms CLI).
All handlers are async and return ToolResult.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sunwell.tools.core.types import ToolResult

if TYPE_CHECKING:
    from sunwell.features.mirror.self import Self
    from sunwell.knowledge.codebase.context import ProjectContext
    from sunwell.memory.lineage.store import LineageStore


def _result(success: bool, output: str) -> ToolResult:
    """Factory for ToolResult with auto-generated ID."""
    return ToolResult(tool_call_id=str(uuid4()), success=success, output=output)


@dataclass(slots=True)
class SunwellToolHandlers:
    """Handlers for Sunwell's internal capability tools.

    These directly call Python APIs rather than CLI/REST for performance.
    Dependencies are lazy-loaded on first use.
    """

    workspace: Path

    # Lazy-loaded dependencies (init=False means they're set after init)
    _intel: ProjectContext | None = field(default=None, init=False)
    _lineage: LineageStore | None = field(default=None, init=False)
    _self: Self | None = field(default=None, init=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Project Intelligence
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_intel_decisions(
        self,
        query: str | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> ToolResult:
        """Query past architectural decisions."""
        intel = await self._get_intel()

        if query:
            decisions = await intel.decisions.find_relevant_decisions(query, top_k=limit)
        elif category:
            decisions = [
                d
                for d in await intel.decisions.get_decisions(active_only=True)
                if d.category == category
            ][:limit]
        else:
            decisions = (await intel.decisions.get_decisions(active_only=True))[:limit]

        if not decisions:
            return _result(True, "No matching decisions found. This might be a new decision area.")

        output = f"Found {len(decisions)} relevant decision(s):\n\n"
        for d in decisions:
            output += f"## {d.category}: {d.question}\n"
            output += f"**Choice**: {d.choice}\n"
            output += f"**Rationale**: {d.rationale}\n"
            if d.rejected:
                rejected = ", ".join(f"{r.option} ({r.reason})" for r in d.rejected)
                output += f"**Rejected**: {rejected}\n"
            output += f"**Confidence**: {d.confidence:.0%}\n\n"

        return _result(True, output)

    async def handle_intel_failures(
        self,
        query: str | None = None,
        limit: int = 5,
    ) -> ToolResult:
        """Query past failed approaches."""
        intel = await self._get_intel()

        if query:
            failures = await intel.failures.check_similar_failures(query, top_k=limit)
        else:
            failures = intel.failures.get_recent(limit=limit)

        if not failures:
            return _result(True, "No similar failures found. Proceed with caution!")

        output = f"⚠️ Found {len(failures)} similar failure(s) in history:\n\n"
        for f in failures:
            output += f"## {f.error_type}\n"
            output += f"**Description**: {f.description}\n"
            output += f"**Error**: {f.error_message}\n"
            if f.solution_hint:
                output += f"**What worked instead**: {f.solution_hint}\n"
            output += "\n"

        return _result(True, output)

    async def handle_intel_patterns(self) -> ToolResult:
        """Get learned code patterns."""
        intel = await self._get_intel()
        patterns = intel.patterns

        output = "## Learned Code Patterns\n\n"

        if patterns.naming_conventions:
            output += "**Naming Conventions**:\n"
            for key, value in patterns.naming_conventions.items():
                output += f"  - {key}: {value}\n"

        output += f"\n**Type Annotations**: {patterns.type_annotation_level}\n"
        output += f"**Docstring Style**: {patterns.docstring_style}\n"
        output += f"**Explanation Verbosity**: {patterns.explanation_verbosity:.0%}\n"
        output += f"**Code Comment Level**: {patterns.code_comment_level:.0%}\n"

        return _result(True, output)

    # ─────────────────────────────────────────────────────────────────────────
    # Semantic Search
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_search_semantic(
        self,
        query: str,
        top_k: int = 10,
        file_pattern: str | None = None,
    ) -> ToolResult:
        """Semantic search across the codebase."""
        from sunwell.knowledge.workspace.indexer import CodebaseIndex

        index = CodebaseIndex(self.workspace)
        results = await index.search(query, top_k=top_k)

        if file_pattern:
            import fnmatch

            results = [r for r in results if fnmatch.fnmatch(str(r.file_path), file_pattern)]

        if not results:
            return _result(True, f"No semantic matches found for: {query}")

        output = f"Found {len(results)} semantic match(es):\n\n"
        for r in results:
            output += f"## {r.file_path}:{r.start_line}-{r.end_line} (score: {r.score:.2f})\n"
            content_preview = r.content[:500]
            if len(r.content) > 500:
                content_preview += "..."
            output += f"```\n{content_preview}\n```\n\n"

        return _result(True, output)

    # ─────────────────────────────────────────────────────────────────────────
    # Artifact Lineage
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_lineage_file(self, path: str) -> ToolResult:
        """Get lineage for a file."""
        lineage_store = self._get_lineage()
        lineage = lineage_store.get_by_path(path)

        if not lineage:
            return _result(True, f"No lineage found for {path}. File may predate Sunwell tracking.")

        output = f"## Lineage: {path}\n\n"
        output += f"**Created**: {lineage.created_at}\n"
        output += f"**Goal**: {lineage.created_by_goal or 'Unknown'}\n"
        output += f"**Reason**: {lineage.created_reason}\n"
        output += f"**Model**: {lineage.model or 'Unknown'}\n"
        output += f"**Human Edited**: {'Yes' if lineage.human_edited else 'No'}\n"
        output += f"**Edits**: {len(lineage.edits)}\n"

        if lineage.imports:
            output += f"\n**Imports**: {', '.join(lineage.imports)}\n"
        if lineage.imported_by:
            output += f"**Imported by**: {', '.join(lineage.imported_by)}\n"

        return _result(True, output)

    async def handle_lineage_impact(self, path: str) -> ToolResult:
        """Impact analysis for a file."""
        lineage_store = self._get_lineage()
        lineage = lineage_store.get_by_path(path)

        if not lineage:
            return _result(True, f"No lineage found for {path}. Cannot compute impact.")

        direct_dependents = lineage_store.get_dependents(path)
        dependencies = lineage_store.get_dependencies(path)

        # Compute transitive dependents (BFS)
        transitive: set[str] = set()
        queue = list(direct_dependents)
        while queue:
            dep = queue.pop(0)
            if dep not in transitive:
                transitive.add(dep)
                queue.extend(lineage_store.get_dependents(dep))

        output = f"## Impact Analysis: {path}\n\n"
        output += f"**Direct dependents**: {len(direct_dependents)}\n"
        for dep in direct_dependents[:10]:
            output += f"  - {dep}\n"
        if len(direct_dependents) > 10:
            output += f"  - ... and {len(direct_dependents) - 10} more\n"

        output += f"\n**Transitive dependents**: {len(transitive)}\n"
        output += f"**Dependencies**: {len(dependencies)}\n"

        risk_level = "high" if len(transitive) > 10 else "medium" if len(transitive) > 3 else "low"
        if risk_level == "high":
            output += "\n⚠️ **HIGH IMPACT** — Many files depend on this!\n"

        return _result(True, output)

    # ─────────────────────────────────────────────────────────────────────────
    # Weakness Analysis
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_weakness_scan(
        self,
        path: str | None = None,
        min_severity: float = 0.3,
    ) -> ToolResult:
        """Scan for code weaknesses."""
        from sunwell.quality.weakness.analyzer import WeaknessAnalyzer

        graph = await self._build_artifact_graph(path)
        analyzer = WeaknessAnalyzer(graph=graph, project_root=self.workspace)
        scores = await analyzer.scan()
        scores = [s for s in scores if s.total_severity >= min_severity]

        if not scores:
            return _result(True, "No weaknesses found above threshold. 🎉")

        output = f"Found {len(scores)} weakness(es):\n\n"
        for s in scores[:10]:
            types = ", ".join(sig.weakness_type.value for sig in s.signals)
            output += f"## {s.file_path}\n"
            output += f"**Types**: {types}\n"
            output += f"**Severity**: {s.total_severity:.0%}\n"
            output += f"**Cascade Risk**: {s.cascade_risk.upper()}\n"
            output += f"**Dependents**: {s.fan_out}\n\n"

        if len(scores) > 10:
            output += f"\n... and {len(scores) - 10} more weaknesses.\n"

        return _result(True, output)

    async def handle_weakness_preview(self, artifact_id: str) -> ToolResult:
        """Preview cascade impact for a weak artifact."""
        lineage_store = self._get_lineage()

        # Find artifact path from lineage store
        artifact_path: str | None = None
        for path, aid in lineage_store._index.items():
            if aid == artifact_id or aid.startswith(artifact_id):
                artifact_path = path
                break

        if not artifact_path:
            return _result(False, f"Artifact not found: {artifact_id}")

        # Reuse impact analysis
        return await self.handle_lineage_impact(artifact_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Self-Knowledge
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_self_modules(self, pattern: str | None = None) -> ToolResult:
        """List Sunwell modules."""
        self_inst = self._get_self()
        modules = self_inst.source.list_modules()

        if pattern:
            modules = [m for m in modules if m.startswith(pattern)]

        output = f"Sunwell modules ({len(modules)}):\n\n"

        # Group by top-level package
        by_package: dict[str, list[str]] = {}
        for mod in modules:
            parts = mod.split(".")
            pkg = ".".join(parts[:2]) if len(parts) > 1 else parts[0]
            by_package.setdefault(pkg, []).append(mod)

        for pkg, mods in sorted(by_package.items()):
            output += f"**{pkg}** ({len(mods)} modules)\n"
            for mod in sorted(mods)[:5]:
                output += f"  - {mod}\n"
            if len(mods) > 5:
                output += f"  - ... and {len(mods) - 5} more\n"
            output += "\n"

        return _result(True, output)

    async def handle_self_search(self, query: str, limit: int = 10) -> ToolResult:
        """Semantic search in Sunwell source."""
        self_inst = self._get_self()
        results = self_inst.source.search(query, limit=limit)

        if not results:
            return _result(True, f"No matches found in Sunwell source for: {query}")

        output = f"Found {len(results)} match(es) in Sunwell source:\n\n"
        for r in results:
            symbol_str = f"::{r.symbol}" if r.symbol else ""
            output += f"## {r.module}{symbol_str} (score: {r.score:.2f})\n"
            snippet_preview = r.snippet[:300]
            if len(r.snippet) > 300:
                snippet_preview += "..."
            output += f"```python\n{snippet_preview}\n```\n\n"

        return _result(True, output)

    async def handle_self_read(self, module: str, symbol: str | None = None) -> ToolResult:
        """Read Sunwell module source."""
        self_inst = self._get_self()

        try:
            if symbol:
                result = self_inst.source.find_symbol(module, symbol)
                output = f"## {module}::{result.name}\n"
                output += f"**Kind**: {result.type}\n"
                output += f"**Line**: {result.start_line}\n"
                if hasattr(result, "signature") and result.signature:
                    output += f"**Signature**: `{result.signature}`\n"
                if result.docstring:
                    output += f"\n{result.docstring}\n"
                output += f"\n```python\n{result.source[:2000]}"
                if len(result.source) > 2000:
                    output += f"\n... ({len(result.source) - 2000} more characters)\n"
                output += "```"
            else:
                source = self_inst.source.read_module(module)
                output = f"## {module}\n\n```python\n{source[:3000]}"
                if len(source) > 3000:
                    output += f"\n... ({len(source) - 3000} more characters)\n"
                output += "```"

            return _result(True, output)

        except FileNotFoundError:
            return _result(False, f"Module not found: {module}")
        except ValueError as e:
            return _result(False, str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow Orchestration
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_workflow_chains(self) -> ToolResult:
        """List available workflow chains."""
        from sunwell.features.workflow.types import WORKFLOW_CHAINS

        output = "## Available Workflow Chains\n\n"

        for chain in WORKFLOW_CHAINS.values():
            output += f"### {chain.name}\n"
            output += f"{chain.description}\n"
            output += f"**Tier**: {chain.tier.value}\n"
            output += "**Steps**:\n"
            for i, step in enumerate(chain.steps, 1):
                checkpoint = " ✓ checkpoint" if i - 1 in chain.checkpoint_after else ""
                output += f"  {i}. {step.skill} — {step.purpose}{checkpoint}\n"
            output += "\n"

        return _result(True, output)

    async def handle_workflow_route(self, request: str) -> ToolResult:
        """Route request to appropriate workflow."""
        from sunwell.features.workflow.router import IntentRouter

        router = IntentRouter()
        intent, workflow = router.classify_and_select(request)

        output = "## Workflow Routing\n\n"
        output += f"**Request**: {request}\n"
        output += f"**Category**: {intent.category.value}\n"
        output += f"**Confidence**: {intent.confidence:.0%}\n"
        output += f"**Signals**: {', '.join(intent.signals) if intent.signals else 'none'}\n"

        if workflow:
            output += f"\n**Recommended Workflow**: {workflow.name}\n"
            output += f"{workflow.description}\n"
        else:
            output += "\nNo specific workflow recommended — handle directly.\n"

        return _result(True, output)

    # ─────────────────────────────────────────────────────────────────────────
    # Lazy Dependency Loading
    # ─────────────────────────────────────────────────────────────────────────

    async def _get_intel(self) -> ProjectContext:
        """Lazy-load project intelligence."""
        if self._intel is None:
            from sunwell.knowledge.codebase.context import ProjectContext

            self._intel = await ProjectContext.load(self.workspace)
        return self._intel

    def _get_lineage(self) -> LineageStore:
        """Lazy-load lineage store."""
        if self._lineage is None:
            from sunwell.memory.lineage.store import LineageStore

            self._lineage = LineageStore(self.workspace)
        return self._lineage

    def _get_self(self) -> Self:
        """Lazy-load Self singleton."""
        if self._self is None:
            from sunwell.features.mirror.self import Self

            self._self = Self.get()
        return self._self

    async def _build_artifact_graph(self, path: str | None = None) -> Any:
        """Build artifact graph for weakness analysis.

        Returns:
            ArtifactGraph populated with Python modules
        """
        from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec

        graph = ArtifactGraph()
        src_dir = self.workspace / "src" if (self.workspace / "src").exists() else self.workspace

        if path:
            scan_path = self.workspace / path
            if scan_path.is_file():
                files = [scan_path] if scan_path.suffix == ".py" else []
            else:
                files = list(scan_path.rglob("*.py"))
        else:
            files = list(src_dir.rglob("*.py"))

        for py_file in files:
            if "__pycache__" in str(py_file):
                continue
            rel_path = py_file.relative_to(self.workspace)
            artifact = ArtifactSpec(
                id=str(rel_path),
                description=f"Python module: {rel_path}",
                contract="",
                produces_file=str(rel_path),
                requires=frozenset(),
            )
            graph.add(artifact)

        return graph
