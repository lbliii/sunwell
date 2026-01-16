"""Mirror neuron tool definitions for RFC-015.

Defines the tools available for self-introspection and self-modification,
along with their trust level requirements.
"""

from sunwell.models.protocol import Tool

# Mirror tool definitions
MIRROR_TOOLS: dict[str, Tool] = {
    # === INTROSPECTION TOOLS ===
    "introspect_source": Tool(
        name="introspect_source",
        description=(
            "Read Sunwell's own source code. Use to understand how a feature "
            "works internally. Can retrieve entire modules or specific symbols "
            "(classes, functions)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Module path (e.g., 'sunwell.tools.executor', 'sunwell.mirror.introspection')",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional: specific class or function to find within the module",
                },
            },
            "required": ["module"],
        },
    ),
    
    "introspect_lens": Tool(
        name="introspect_lens",
        description=(
            "Examine the currently loaded lens configuration. Returns heuristics, "
            "validators, personas, and framework settings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "enum": ["heuristics", "validators", "personas", "framework", "all"],
                    "description": "Which lens component to examine (default: all)",
                },
            },
        },
    ),
    
    "introspect_simulacrum": Tool(
        name="introspect_simulacrum",
        description=(
            "Examine current simulacrum state: learnings accumulated, dead ends "
            "marked, current focus, and conversation context."
        ),
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["learnings", "dead_ends", "focus", "context", "all"],
                    "description": "Which section to examine (default: all)",
                },
            },
        },
    ),
    
    "introspect_execution": Tool(
        name="introspect_execution",
        description=(
            "Get recent execution history: tool calls made, errors encountered, "
            "and execution statistics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return (default: 10)",
                },
                "filter": {
                    "type": "string",
                    "enum": ["all", "errors", "tools", "model_calls"],
                    "description": "Filter type (default: all)",
                },
            },
        },
    ),
    
    # === ANALYSIS TOOLS ===
    "analyze_patterns": Tool(
        name="analyze_patterns",
        description=(
            "Analyze patterns in Sunwell's behavior over time. Identifies trends "
            "in tool usage, latency, error rates, and common execution sequences."
        ),
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["session", "day", "week", "all"],
                    "description": "Time scope for analysis (default: session)",
                },
                "focus": {
                    "type": "string",
                    "enum": ["tool_usage", "error_types", "latency"],
                    "description": "What aspect to analyze",
                },
            },
            "required": ["focus"],
        },
    ),
    
    "analyze_failures": Tool(
        name="analyze_failures",
        description=(
            "Analyze recent failures to identify root causes and suggest fixes. "
            "Maps errors to known patterns and provides actionable recommendations."
        ),
        parameters={
            "type": "object",
            "properties": {
                "failure_type": {
                    "type": "string",
                    "enum": ["tool_error", "validation_failed", "timeout", "all"],
                    "description": "Type of failure to analyze (default: all)",
                },
            },
        },
    ),
    
    # === PROPOSAL TOOLS ===
    "propose_improvement": Tool(
        name="propose_improvement",
        description=(
            "Generate a proposed improvement based on analysis. Creates a formal "
            "proposal that can be reviewed and applied."
        ),
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["heuristic", "validator", "tool", "workflow", "config"],
                    "description": "Type of improvement",
                },
                "problem": {
                    "type": "string",
                    "description": "Description of the problem to solve",
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Evidence from analysis tools supporting this proposal",
                },
                "diff": {
                    "type": "string",
                    "description": "The proposed change (in appropriate format)",
                },
            },
            "required": ["scope", "problem", "evidence", "diff"],
        },
    ),
    
    "list_proposals": Tool(
        name="list_proposals",
        description="List improvement proposals, optionally filtered by status.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["draft", "pending_review", "approved", "applied", "all"],
                    "description": "Filter by status (default: pending_review)",
                },
            },
        },
    ),
    
    "get_proposal": Tool(
        name="get_proposal",
        description="Get details of a specific proposal by ID.",
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "The proposal ID (e.g., 'prop_abc123')",
                },
            },
            "required": ["proposal_id"],
        },
    ),
    
    # === APPLICATION TOOLS (elevated trust required) ===
    "submit_proposal": Tool(
        name="submit_proposal",
        description="Submit a draft proposal for review.",
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "ID of the draft proposal to submit",
                },
            },
            "required": ["proposal_id"],
        },
    ),
    
    "approve_proposal": Tool(
        name="approve_proposal",
        description=(
            "Approve a proposal for application. Requires user confirmation "
            "before the change can be applied."
        ),
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "ID of the proposal to approve",
                },
            },
            "required": ["proposal_id"],
        },
    ),
    
    "apply_proposal": Tool(
        name="apply_proposal",
        description=(
            "Apply an approved proposal. Creates a rollback point before "
            "making changes. Requires WORKSPACE trust level."
        ),
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "ID of the approved proposal to apply",
                },
                "backup": {
                    "type": "boolean",
                    "description": "Create backup before applying (default: true)",
                },
            },
            "required": ["proposal_id"],
        },
    ),
    
    "rollback_proposal": Tool(
        name="rollback_proposal",
        description="Rollback a previously applied proposal to its original state.",
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "ID of the applied proposal to rollback",
                },
            },
            "required": ["proposal_id"],
        },
    ),
    
    # === MODEL ROUTING TOOLS (Phase 5) ===
    "analyze_model_performance": Tool(
        name="analyze_model_performance",
        description=(
            "Analyze which models perform best for each task category. "
            "Returns success rates, edit rates, and latency data."
        ),
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["session", "day", "week", "all"],
                    "description": "Time scope for analysis (default: all)",
                },
                "category": {
                    "type": "string",
                    "description": "Optional: specific task category to analyze",
                },
            },
        },
    ),
    
    "propose_model_routing": Tool(
        name="propose_model_routing",
        description=(
            "Propose a model routing change based on performance analysis. "
            "Creates a proposal to update lens model preferences."
        ),
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Task category to optimize",
                },
                "current_model": {
                    "type": "string",
                    "description": "Current model for this category",
                },
                "proposed_model": {
                    "type": "string",
                    "description": "Proposed better model",
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Performance evidence supporting this change",
                },
            },
            "required": ["category", "proposed_model", "evidence"],
        },
    ),
    
    "get_routing_info": Tool(
        name="get_routing_info",
        description=(
            "Get current model routing configuration and recommendations."
        ),
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional: get recommendation for specific category",
                },
            },
        },
    ),
}

# Trust levels required for each mirror tool
MIRROR_TOOL_TRUST: dict[str, str] = {
    # Introspection - safe, read-only
    "introspect_source": "discovery",
    "introspect_lens": "discovery",
    "introspect_simulacrum": "discovery",
    "introspect_execution": "discovery",
    
    # Analysis - read-only, just computes insights
    "analyze_patterns": "read_only",
    "analyze_failures": "read_only",
    "analyze_model_performance": "read_only",  # Phase 5
    
    # Proposals - creating proposals is read-only (doesn't apply changes)
    "propose_improvement": "read_only",
    "propose_model_routing": "read_only",  # Phase 5
    "list_proposals": "read_only",
    "get_proposal": "read_only",
    "submit_proposal": "read_only",
    
    # Routing info - read-only
    "get_routing_info": "read_only",  # Phase 5
    
    # Application - requires workspace access to modify lens/config
    "approve_proposal": "workspace",
    "apply_proposal": "workspace",
    "rollback_proposal": "workspace",
}


def get_mirror_tools_for_trust(trust_level: str) -> dict[str, Tool]:
    """Get mirror tools available at a given trust level.
    
    Args:
        trust_level: One of 'discovery', 'read_only', 'workspace', 'shell', 'full'
        
    Returns:
        Dict of tool_name -> Tool for tools available at that level
    """
    trust_order = ["discovery", "read_only", "workspace", "shell", "full"]
    
    try:
        level_idx = trust_order.index(trust_level.lower())
    except ValueError:
        level_idx = 0  # Default to discovery
    
    available = {}
    for name, required_level in MIRROR_TOOL_TRUST.items():
        required_idx = trust_order.index(required_level)
        if level_idx >= required_idx:
            available[name] = MIRROR_TOOLS[name]
    
    return available
