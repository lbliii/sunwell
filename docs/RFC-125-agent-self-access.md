# RFC-125: Agent Self-Access — Recursive Sunwell Capabilities

**Status**: Evaluated (87% confidence 🟢)  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Evaluated**: 2026-01-24  
**Depends on**: RFC-121 (Artifact Lineage), RFC-119 (Unified Event Bus), RFC-085 (Self-Knowledge)

## Summary

Equip Sunwell's agent with tools to access Sunwell's own capabilities: project intelligence, weakness analysis, semantic search, workflow orchestration, and self-knowledge. This enables the agent to leverage institutional memory, detect code issues, and orchestrate multi-step workflows autonomously.

## Motivation

### Problem: The Capability Gap

Sunwell has **40+ CLI commands** and **134 REST API endpoints** with powerful capabilities, but the agent only has access to **primitive tools**:

| Agent Has | Agent Lacks |
|-----------|-------------|
| `read_file`, `write_file`, `edit_file` | Project intelligence (past decisions, failures) |
| `run_command` (shell) | Weakness cascade analysis |
| `git_*` (status, diff, commit) | Semantic codebase search |
| `web_search`, `web_fetch` | Workflow orchestration |
| `get_expertise` | Self-knowledge introspection |

This means the agent:
- **Repeats past mistakes** because it can't query failure history
- **Misses code issues** because it can't run weakness analysis
- **Can't find code** semantically (only regex via `search_files`)
- **Can't orchestrate** multi-step workflows
- **Can't introspect** Sunwell's own architecture

### Inspiration: IDE Agents with MCP

Modern IDE agents (Cursor, Continue.dev) use MCP servers to expose capabilities:
- Cursor exposes browser automation tools
- Continue exposes code intelligence tools
- Agents can call other agents

Sunwell should expose its own capabilities to itself.

### User Stories

**"Don't repeat my mistakes":**
> "The agent keeps trying to use `asyncio.create_task()` in sync contexts. Last time we documented this as a dead-end. It should know!"

**"Find similar code":**
> "Find code similar to this authentication pattern" — agent should use semantic search, not regex.

**"Auto-fix cascade":**
> "Fix this weak module and all its dependents" — agent should orchestrate the weakness cascade.

**"How does Sunwell work?":**
> "How does the agent planner work?" — agent should introspect its own source.

---

## Goals

1. **Institutional memory**: Agent queries past decisions, failures, patterns
2. **Code intelligence**: Semantic search and dependency analysis
3. **Automated repair**: Weakness detection and cascade fixing
4. **Workflow orchestration**: Execute multi-step skill chains
5. **Self-introspection**: Query Sunwell's own codebase

## Non-Goals

- Recursive agent spawning (agent calling `sunwell agent run`)
- Modifying Sunwell's own source code (read-only self-access)
- Full CLI parity (prioritize high-value capabilities)
- External MCP server (internal tools only)

---

## Design

### Architecture: Direct Python API

Three options for exposing capabilities:

| Approach | Latency | Complexity | Isolation |
|----------|---------|------------|-----------|
| **CLI subprocess** (`run_command sunwell intel`) | ~500ms | Low | High |
| **REST API** (`httpx.post("/api/intel/decisions")`) | ~50ms | Medium | Medium |
| **Direct Python** (`ProjectIntelligence.load()`) | ~5ms | Low | Low |

**Recommendation**: **Direct Python API** for internal tools.

- Fastest (no serialization overhead)
- No server dependency (works offline)
- Type-safe (full IDE support)
- Easy testing (mock at Python level)

### New Tool Category: Sunwell Tools

```python
# sunwell/tools/sunwell_tools.py

"""Tools for accessing Sunwell's own capabilities (RFC-125).

These tools let the agent leverage Sunwell's institutional memory,
code intelligence, and orchestration capabilities.
"""

from sunwell.models.protocol import Tool

SUNWELL_TOOLS: dict[str, Tool] = {
    # ─── Project Intelligence ───────────────────────────────────────
    
    "sunwell_intel_decisions": Tool(
        name="sunwell_intel_decisions",
        description=(
            "Query past architectural decisions for the current project. "
            "Use BEFORE making design choices to learn from history. "
            "Returns decisions with rationale, rejected alternatives, and confidence."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query (e.g., 'authentication approach')",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., 'database', 'api', 'security')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max decisions to return (default: 5)",
                    "default": 5,
                },
            },
        },
    ),
    
    "sunwell_intel_failures": Tool(
        name="sunwell_intel_failures",
        description=(
            "Query past failed approaches for the current project. "
            "Use BEFORE attempting something to avoid repeating mistakes. "
            "Returns failures with error messages, stack traces, and lessons learned."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What you're about to try (e.g., 'async database connection')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max failures to return (default: 5)",
                    "default": 5,
                },
            },
        },
    ),
    
    "sunwell_intel_patterns": Tool(
        name="sunwell_intel_patterns",
        description=(
            "Get learned code patterns for the current project. "
            "Returns naming conventions, type annotation level, docstring style, etc."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    
    # ─── Semantic Search ────────────────────────────────────────────
    
    "sunwell_search_semantic": Tool(
        name="sunwell_search_semantic",
        description=(
            "Semantic search across the indexed codebase. "
            "Finds code by MEANING, not just text matching. "
            "Use for: 'code similar to X', 'implementation of Y', 'where is Z handled'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what you're looking for",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max results to return (default: 10)",
                    "default": 10,
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter files (e.g., '*.py')",
                },
            },
            "required": ["query"],
        },
    ),
    
    # ─── Artifact Lineage ───────────────────────────────────────────
    
    "sunwell_lineage_file": Tool(
        name="sunwell_lineage_file",
        description=(
            "Get lineage for a file: who created it, why, what edits, dependencies. "
            "Use to understand file history before modifying."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root",
                },
            },
            "required": ["path"],
        },
    ),
    
    "sunwell_lineage_impact": Tool(
        name="sunwell_lineage_impact",
        description=(
            "Impact analysis: what breaks if this file changes/deletes? "
            "Returns all dependent files and goals that reference it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to analyze",
                },
            },
            "required": ["path"],
        },
    ),
    
    # ─── Weakness Analysis ──────────────────────────────────────────
    
    "sunwell_weakness_scan": Tool(
        name="sunwell_weakness_scan",
        description=(
            "Scan for code weaknesses in the project. "
            "Detects: missing error handling, type issues, complexity, dead code. "
            "Returns weaknesses ranked by cascade risk (how many files break if this breaks)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to scan (default: entire project)",
                },
                "min_severity": {
                    "type": "number",
                    "description": "Minimum severity 0.0-1.0 (default: 0.3)",
                    "default": 0.3,
                },
            },
        },
    ),
    
    "sunwell_weakness_preview": Tool(
        name="sunwell_weakness_preview",
        description=(
            "Preview cascade impact for a weak artifact. "
            "Shows: direct dependents, transitive dependents, regeneration waves, effort estimate."
        ),
        parameters={
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Artifact ID from weakness scan results",
                },
            },
            "required": ["artifact_id"],
        },
    ),
    
    # ─── Self-Knowledge ─────────────────────────────────────────────
    
    "sunwell_self_modules": Tool(
        name="sunwell_self_modules",
        description=(
            "List Sunwell's own modules. "
            "Use to understand Sunwell's architecture before asking questions about it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Filter by module prefix (e.g., 'sunwell.agent')",
                },
            },
        },
    ),
    
    "sunwell_self_search": Tool(
        name="sunwell_self_search",
        description=(
            "Semantic search in Sunwell's own source code. "
            "Use when user asks 'how does Sunwell do X?' or 'where is Y implemented?'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query about Sunwell internals",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    
    "sunwell_self_read": Tool(
        name="sunwell_self_read",
        description=(
            "Read Sunwell's own source code for a module. "
            "Use to understand how Sunwell implements something."
        ),
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Full module path (e.g., 'sunwell.agent.core')",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional: specific class or function to find",
                },
            },
            "required": ["module"],
        },
    ),
    
    # ─── Workflow Orchestration ─────────────────────────────────────
    
    "sunwell_workflow_chains": Tool(
        name="sunwell_workflow_chains",
        description=(
            "List available workflow chains and their steps. "
            "Chains are pre-built multi-step workflows (e.g., 'feature-docs', 'health-check')."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    
    "sunwell_workflow_route": Tool(
        name="sunwell_workflow_route",
        description=(
            "Route a user request to the appropriate workflow. "
            "Returns recommended workflow and confidence."
        ),
        parameters={
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "User's natural language request",
                },
            },
            "required": ["request"],
        },
    ),
}
```

### Tool Handlers

```python
# sunwell/tools/sunwell_handlers.py

"""Handlers for Sunwell self-access tools (RFC-125)."""

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sunwell.tools.types import ToolResult

if TYPE_CHECKING:
    from sunwell.intelligence.context import ProjectContext
    from sunwell.lineage.store import LineageStore
    from sunwell.self import Self


def _result(success: bool, output: str) -> ToolResult:
    """Factory for ToolResult with auto-generated ID."""
    return ToolResult(tool_call_id=str(uuid4()), success=success, output=output)


class SunwellToolHandlers:
    """Handlers for Sunwell's internal capability tools.
    
    These directly call Python APIs rather than CLI/REST for performance.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._intel: ProjectContext | None = None
        self._lineage: LineageStore | None = None
        self._self: Self | None = None
    
    # ─── Project Intelligence ───────────────────────────────────────
    
    async def handle_intel_decisions(
        self,
        query: str | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> ToolResult:
        """Query past architectural decisions."""
        from sunwell.intelligence.context import ProjectContext
        
        if not self._intel:
            self._intel = await ProjectContext.load(self.workspace)
        
        if query:
            decisions = await self._intel.decisions.find_relevant_decisions(
                query, top_k=limit
            )
        else:
            decisions = await self._intel.decisions.get_decisions(
                category=category, active_only=True
            )[:limit]
        
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
        from sunwell.intelligence.context import ProjectContext
        
        if not self._intel:
            self._intel = await ProjectContext.load(self.workspace)
        
        if query:
            failures = await self._intel.failures.check_similar_failures(
                query, top_k=limit
            )
        else:
            failures = list(self._intel.failures._failures.values())[-limit:]
        
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
        from sunwell.intelligence.context import ProjectContext
        
        if not self._intel:
            self._intel = await ProjectContext.load(self.workspace)
        
        patterns = self._intel.patterns
        
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
    
    # ─── Semantic Search ────────────────────────────────────────────
    
    async def handle_search_semantic(
        self,
        query: str,
        top_k: int = 10,
        file_pattern: str | None = None,
    ) -> ToolResult:
        """Semantic search across the codebase."""
        from sunwell.workspace.indexer import CodebaseIndex
        
        index = CodebaseIndex(self.workspace)
        results = await index.search(query, top_k=top_k)
        
        if file_pattern:
            import fnmatch
            results = [r for r in results if fnmatch.fnmatch(r.path, file_pattern)]
        
        if not results:
            return _result(True, f"No semantic matches found for: {query}")
        
        output = f"Found {len(results)} semantic match(es):\n\n"
        for r in results:
            output += f"## {r.path}:{r.start_line}-{r.end_line} (score: {r.score:.2f})\n"
            output += f"```\n{r.content[:500]}{'...' if len(r.content) > 500 else ''}\n```\n\n"
        
        return _result(True, output)
    
    # ─── Artifact Lineage ───────────────────────────────────────────
    
    async def handle_lineage_file(self, path: str) -> ToolResult:
        """Get lineage for a file."""
        from sunwell.lineage.store import LineageStore
        
        if not self._lineage:
            self._lineage = LineageStore(self.workspace)
        
        lineage = self._lineage.get_by_path(path)
        
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
        from sunwell.lineage.store import LineageStore
        from sunwell.lineage.dependencies import get_impact_analysis
        
        if not self._lineage:
            self._lineage = LineageStore(self.workspace)
        
        impact = get_impact_analysis(self._lineage, path)
        
        output = f"## Impact Analysis: {path}\n\n"
        output += f"**Direct dependents**: {len(impact['direct_dependents'])}\n"
        for dep in impact['direct_dependents'][:10]:
            output += f"  - {dep}\n"
        
        output += f"\n**Transitive dependents**: {len(impact['transitive_dependents'])}\n"
        output += f"**Affected goals**: {len(impact['affected_goals'])}\n"
        
        if impact['risk_level'] == 'high':
            output += "\n⚠️ **HIGH IMPACT** — Many files depend on this!\n"
        
        return _result(True, output)
    
    # ─── Weakness Analysis ──────────────────────────────────────────
    
    async def handle_weakness_scan(
        self,
        path: str | None = None,
        min_severity: float = 0.3,
    ) -> ToolResult:
        """Scan for code weaknesses."""
        from sunwell.weakness.analyzer import WeaknessAnalyzer
        from sunwell.planning.naaru.artifacts import ArtifactGraph
        
        # Build artifact graph (simplified for scan)
        graph = await self._build_artifact_graph()
        
        analyzer = WeaknessAnalyzer(
            graph=graph,
            project_root=self.workspace,
        )
        
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
        
        return _result(True, output)
    
    # ─── Self-Knowledge ─────────────────────────────────────────────
    
    async def handle_self_modules(
        self,
        pattern: str | None = None,
    ) -> ToolResult:
        """List Sunwell modules."""
        from sunwell.self import Self
        
        if not self._self:
            self._self = Self.get()
        
        modules = self._self.source.list_modules()
        
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
    
    async def handle_self_search(
        self,
        query: str,
        limit: int = 10,
    ) -> ToolResult:
        """Semantic search in Sunwell source."""
        from sunwell.self import Self
        
        if not self._self:
            self._self = Self.get()
        
        results = self._self.source.search(query, limit=limit)
        
        if not results:
            return _result(True, f"No matches found in Sunwell source for: {query}")
        
        output = f"Found {len(results)} match(es) in Sunwell source:\n\n"
        for r in results:
            output += f"## {r.module}::{r.symbol} (score: {r.score:.2f})\n"
            output += f"```python\n{r.snippet[:300]}{'...' if len(r.snippet) > 300 else ''}\n```\n\n"
        
        return _result(True, output)
    
    async def handle_self_read(
        self,
        module: str,
        symbol: str | None = None,
    ) -> ToolResult:
        """Read Sunwell module source."""
        from sunwell.self import Self
        
        if not self._self:
            self._self = Self.get()
        
        try:
            if symbol:
                result = self._self.source.find_symbol(module, symbol)
                if not result:
                    return _result(False, f"Symbol '{symbol}' not found in '{module}'")
                output = f"## {module}::{result.name}\n"
                output += f"**Kind**: {result.kind}\n"
                output += f"**Line**: {result.line}\n"
                if result.signature:
                    output += f"**Signature**: `{result.signature}`\n"
                if result.docstring:
                    output += f"\n{result.docstring}\n"
            else:
                source = self._self.source.read_module(module)
                output = f"## {module}\n\n```python\n{source[:3000]}"
                if len(source) > 3000:
                    output += f"\n... ({len(source) - 3000} more characters)\n"
                output += "```"
            
            return _result(True, output)
        
        except FileNotFoundError:
            return _result(False, f"Module not found: {module}")
    
    # ─── Workflow Orchestration ─────────────────────────────────────
    
    async def handle_workflow_chains(self) -> ToolResult:
        """List available workflow chains."""
        from sunwell.workflow.types import WORKFLOW_CHAINS
        
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
        from sunwell.workflow.router import IntentRouter
        
        router = IntentRouter()
        intent, workflow = router.classify_and_select(request)
        
        output = "## Workflow Routing\n\n"
        output += f"**Request**: {request}\n"
        output += f"**Category**: {intent.category.value}\n"
        output += f"**Confidence**: {intent.confidence:.0%}\n"
        output += f"**Signals**: {', '.join(intent.signals)}\n"
        
        if workflow:
            output += f"\n**Recommended Workflow**: {workflow.name}\n"
            output += f"{workflow.description}\n"
        else:
            output += "\nNo specific workflow recommended — handle directly.\n"
        
        return _result(True, output)
    
    # ─── Helpers ────────────────────────────────────────────────────
    
    async def _build_artifact_graph(self):
        """Build artifact graph for weakness analysis."""
        from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec
        
        graph = ArtifactGraph()
        src_dir = self.workspace / "src"
        if not src_dir.exists():
            src_dir = self.workspace
        
        for py_file in src_dir.rglob("*.py"):
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
```

### Trust Level Integration

Add Sunwell tools to trust levels:

```python
# sunwell/tools/types.py (additions)

# Sunwell tools require at least WORKSPACE trust (they read project state)
TRUST_LEVEL_TOOLS[ToolTrust.WORKSPACE] |= frozenset({
    "sunwell_intel_decisions",
    "sunwell_intel_failures",
    "sunwell_intel_patterns",
    "sunwell_search_semantic",
    "sunwell_lineage_file",
    "sunwell_lineage_impact",
    "sunwell_weakness_scan",
    "sunwell_weakness_preview",
    "sunwell_workflow_chains",
    "sunwell_workflow_route",
})

# Self-knowledge tools are read-only, safe at READ_ONLY level
TRUST_LEVEL_TOOLS[ToolTrust.READ_ONLY] |= frozenset({
    "sunwell_self_modules",
    "sunwell_self_search",
    "sunwell_self_read",
})
```

### Executor Integration

```python
# sunwell/tools/executor.py (additions)

from sunwell.tools.sunwell_handlers import SunwellToolHandlers
from sunwell.tools.sunwell_tools import SUNWELL_TOOLS

class ToolExecutor:
    sunwell_handler: SunwellToolHandlers | None = None
    
    def __post_init__(self) -> None:
        # ... existing init ...
        
        # Initialize Sunwell handler if workspace available
        if self._effective_workspace:
            self.sunwell_handler = SunwellToolHandlers(self._effective_workspace)
    
    def get_available_tools(self) -> frozenset[str]:
        """Get tools available at current trust level."""
        # ... existing code ...
        
        # Add Sunwell tools if handler available
        if self.sunwell_handler:
            available |= frozenset(SUNWELL_TOOLS.keys())
        
        return available
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        # ... existing dispatch ...
        
        # Route Sunwell tools
        if tool_call.name.startswith("sunwell_") and self.sunwell_handler:
            return await self._execute_sunwell_tool(tool_call)
    
    async def _execute_sunwell_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a Sunwell internal tool."""
        handler_map = {
            "sunwell_intel_decisions": self.sunwell_handler.handle_intel_decisions,
            "sunwell_intel_failures": self.sunwell_handler.handle_intel_failures,
            "sunwell_intel_patterns": self.sunwell_handler.handle_intel_patterns,
            "sunwell_search_semantic": self.sunwell_handler.handle_search_semantic,
            "sunwell_lineage_file": self.sunwell_handler.handle_lineage_file,
            "sunwell_lineage_impact": self.sunwell_handler.handle_lineage_impact,
            "sunwell_weakness_scan": self.sunwell_handler.handle_weakness_scan,
            "sunwell_weakness_preview": self.sunwell_handler.handle_weakness_preview,
            "sunwell_self_modules": self.sunwell_handler.handle_self_modules,
            "sunwell_self_search": self.sunwell_handler.handle_self_search,
            "sunwell_self_read": self.sunwell_handler.handle_self_read,
            "sunwell_workflow_chains": self.sunwell_handler.handle_workflow_chains,
            "sunwell_workflow_route": self.sunwell_handler.handle_workflow_route,
        }
        
        handler = handler_map.get(tool_call.name)
        if not handler:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Unknown Sunwell tool: {tool_call.name}",
            )
        
        try:
            # Handler returns ToolResult; we override tool_call_id
            result = await handler(**tool_call.arguments)
            return ToolResult(
                tool_call_id=tool_call.id,
                success=result.success,
                output=result.output,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Error executing {tool_call.name}: {e}",
            )
```

---

## Security Considerations

### No Recursive Agent Spawning

**Risk**: Agent calls `sunwell agent run` which spawns another agent, causing infinite recursion.

**Mitigation**: Sunwell tools are **read-only queries** and **passive orchestration** — they don't spawn new agent runs:

```python
# These are SAFE (read-only queries):
sunwell_intel_decisions()   # Queries past decisions
sunwell_search_semantic()   # Searches index
sunwell_self_read()         # Reads Sunwell source

# These are NOT exposed (would enable recursion):
# sunwell_agent_run()       # NOT IMPLEMENTED
# sunwell_chat_start()      # NOT IMPLEMENTED
```

### Self-Modification Prevention

**Risk**: Agent modifies Sunwell's own source code via self-access.

**Mitigation**: Self-knowledge tools are **read-only**:

```python
"sunwell_self_read"     # ✓ Read Sunwell source
"sunwell_self_search"   # ✓ Search Sunwell source
# "sunwell_self_edit"   # ✗ NOT IMPLEMENTED
# "sunwell_self_write"  # ✗ NOT IMPLEMENTED
```

Additionally, the existing workspace validation prevents operating on Sunwell's repo:

```python
# sunwell/tools/executor.py (existing)
validate_not_sunwell_repo(workspace)
```

### Resource Limits

**Risk**: Expensive operations (full project scan, semantic search) consume resources.

**Mitigation**: Built-in limits:

```python
# Semantic search limited to top_k results
sunwell_search_semantic(query, top_k=10)  # Max 10 results

# Weakness scan limited by severity threshold
sunwell_weakness_scan(min_severity=0.3)  # Filter low-severity

# Self-read limited to 3000 characters
output = f"```python\n{source[:3000]}"
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Recursive agent spawning | Low | High | Don't expose `agent run` as tool |
| Self-modification | Low | High | Read-only self-access, workspace validation |
| Resource exhaustion | Medium | Medium | Built-in limits on results/size |
| Intelligence not initialized | Medium | Low | Graceful fallback with helpful message |
| Index not built | Medium | Low | Return "index not available" message |
| Lineage not tracked | Low | Low | Return "no lineage found" message |

---

## Implementation Plan

### Phase 1: Project Intelligence Tools (1 day)

| Task | File | Status |
|------|------|--------|
| Create tool definitions | `src/sunwell/tools/sunwell_tools.py` | ⬜ |
| Create handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| Add intel handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| Wire into ToolExecutor | `src/sunwell/tools/executor.py` | ⬜ |
| Add to trust levels | `src/sunwell/tools/types.py` | ⬜ |
| Unit tests | `tests/test_sunwell_tools.py` | ⬜ |

### Phase 2: Self-Knowledge Tools (0.5 day)

| Task | File | Status |
|------|------|--------|
| Add self handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| Integration tests | `tests/integration/test_self_access.py` | ⬜ |

### Phase 3: Lineage & Weakness Tools (1 day)

| Task | File | Status |
|------|------|--------|
| Add lineage handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| Add weakness handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| Integration tests | `tests/integration/test_lineage_tools.py` | ⬜ |

### Phase 4: Semantic Search & Workflow (1 day)

| Task | File | Status |
|------|------|--------|
| Add search handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| Add workflow handlers | `src/sunwell/tools/sunwell_handlers.py` | ⬜ |
| End-to-end tests | `tests/integration/test_sunwell_tools_e2e.py` | ⬜ |

**Total estimated time**: 3.5 days

---

## Testing

```python
# tests/test_sunwell_tools.py

import pytest
from pathlib import Path
from sunwell.tools.sunwell_handlers import SunwellToolHandlers


class TestIntelligenceTools:
    """Project intelligence tool tests."""
    
    @pytest.fixture
    def handlers(self, tmp_path: Path) -> SunwellToolHandlers:
        # Create minimal project structure
        (tmp_path / ".sunwell" / "intelligence").mkdir(parents=True)
        return SunwellToolHandlers(tmp_path)
    
    async def test_decisions_returns_relevant(self, handlers):
        """Should return relevant decisions for query."""
        result = await handlers.handle_intel_decisions(query="authentication")
        assert result.success
        # Empty project returns helpful message
        assert "No matching decisions" in result.output or "decision" in result.output.lower()
    
    async def test_failures_warns_about_similar(self, handlers):
        """Should warn about similar past failures."""
        result = await handlers.handle_intel_failures(query="async database")
        assert result.success


class TestSelfKnowledgeTools:
    """Self-knowledge tool tests."""
    
    @pytest.fixture
    def handlers(self, tmp_path: Path) -> SunwellToolHandlers:
        return SunwellToolHandlers(tmp_path)
    
    async def test_modules_lists_sunwell(self, handlers):
        """Should list Sunwell modules."""
        result = await handlers.handle_self_modules()
        assert result.success
        assert "sunwell.agent" in result.output
        assert "sunwell.tools" in result.output
    
    async def test_self_search_finds_code(self, handlers):
        """Should find code by semantic query."""
        result = await handlers.handle_self_search(query="tool executor dispatch")
        assert result.success
        # Should find ToolExecutor or similar
    
    async def test_self_read_returns_source(self, handlers):
        """Should return module source code."""
        result = await handlers.handle_self_read(module="sunwell.tools.types")
        assert result.success
        assert "ToolTrust" in result.output or "class" in result.output


class TestSecurityGuardrails:
    """Security constraint tests."""
    
    async def test_no_recursive_agent_spawn(self, handlers):
        """Should not have agent spawning tools."""
        from sunwell.tools.sunwell_tools import SUNWELL_TOOLS
        
        dangerous_names = ["agent_run", "agent_spawn", "chat_start"]
        for name in dangerous_names:
            assert f"sunwell_{name}" not in SUNWELL_TOOLS
    
    async def test_self_access_read_only(self, handlers):
        """Self-access tools should be read-only."""
        from sunwell.tools.sunwell_tools import SUNWELL_TOOLS
        
        write_names = ["self_edit", "self_write", "self_modify"]
        for name in write_names:
            assert f"sunwell_{name}" not in SUNWELL_TOOLS
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Repeated failure rate | -50% | Track agent repeating known failures |
| Semantic search usage | 10+ calls/session | Tool call frequency |
| Self-introspection accuracy | >90% | Manual review of 20 queries |
| Workflow routing accuracy | >80% | Compare routed vs optimal |

---

## Future Extensions

- **Workflow execution**: Let agent trigger workflows (with confirmation)
- **Memory write**: Let agent record new learnings/decisions
- **Cross-project intelligence**: Query patterns from similar projects
- **Real-time weakness monitoring**: Continuous analysis during generation
- **MCP server**: Expose tools via MCP for external agents

---

## References

- RFC-085: Self-Knowledge (sunwell.self module)
- RFC-121: Artifact Lineage (lineage store and queries)
- RFC-045: Project Intelligence (decisions, failures, patterns)
- RFC-086: Workflow Execution (workflow chains)
- RFC-108: Codebase Indexing (semantic search)
- RFC-063: Weakness Cascade (weakness analysis)
