"""Sunwell self-access tools (RFC-125).

These tools let the agent leverage Sunwell's institutional memory,
code intelligence, and orchestration capabilities.

Tools are organized by category:
- Project Intelligence: Query past decisions, failures, patterns
- Semantic Search: Find code by meaning
- Artifact Lineage: Track file history and dependencies
- Weakness Analysis: Detect and analyze code weaknesses
- Self-Knowledge: Introspect Sunwell's own source
- Workflow Orchestration: Route requests and list chains
"""

from sunwell.models import Tool

# =============================================================================
# Project Intelligence Tools
# =============================================================================

INTEL_TOOLS: dict[str, Tool] = {
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
}


# =============================================================================
# Semantic Search Tools
# =============================================================================

SEARCH_TOOLS: dict[str, Tool] = {
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
}


# =============================================================================
# Artifact Lineage Tools
# =============================================================================

LINEAGE_TOOLS: dict[str, Tool] = {
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
}


# =============================================================================
# Weakness Analysis Tools
# =============================================================================

WEAKNESS_TOOLS: dict[str, Tool] = {
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
}


# =============================================================================
# Self-Knowledge Tools
# =============================================================================

SELF_TOOLS: dict[str, Tool] = {
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
}


# =============================================================================
# Workflow Orchestration Tools
# =============================================================================

WORKFLOW_TOOLS: dict[str, Tool] = {
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


# =============================================================================
# Combined Export
# =============================================================================

SUNWELL_TOOLS: dict[str, Tool] = {
    **INTEL_TOOLS,
    **SEARCH_TOOLS,
    **LINEAGE_TOOLS,
    **WEAKNESS_TOOLS,
    **SELF_TOOLS,
    **WORKFLOW_TOOLS,
}

# Tool names by trust level (for use in types.py)
SUNWELL_WORKSPACE_TOOLS: frozenset[str] = frozenset({
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

SUNWELL_READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "sunwell_self_modules",
    "sunwell_self_search",
    "sunwell_self_read",
})
