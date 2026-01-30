"""Permission mapping for Intent DAG nodes.

Maps DAG paths to ToolTrust levels and determines when approvals are required.
Deeper nodes in the tree require higher permission levels.

Permission Escalation:
    Depth 1 (Understand)  → None (no tools)
    Depth 1 (Analyze)     → READ_ONLY
    Depth 2 (Plan, Read)  → READ_ONLY
    Depth 3 (Write)       → WORKSPACE
    Depth 4 (Delete)      → WORKSPACE + explicit approval
"""

from sunwell.agent.intent.dag import IntentNode, IntentPath
from sunwell.tools.core.types import ToolTrust


# ═══════════════════════════════════════════════════════════════════════════════
# Node → ToolTrust Mapping
# ═══════════════════════════════════════════════════════════════════════════════

# Map each node to the minimum ToolTrust level required
_NODE_TRUST_MAP: dict[IntentNode, ToolTrust | None] = {
    # Root
    IntentNode.CONVERSATION: None,
    
    # Understanding branch - no tools needed
    IntentNode.UNDERSTAND: None,
    IntentNode.CLARIFY: None,
    IntentNode.EXPLAIN: None,
    
    # Analysis branch - read-only tools
    IntentNode.ANALYZE: ToolTrust.READ_ONLY,
    IntentNode.REVIEW: ToolTrust.READ_ONLY,
    IntentNode.AUDIT: ToolTrust.READ_ONLY,
    
    # Planning branch - read-only (may escalate to action)
    IntentNode.PLAN: ToolTrust.READ_ONLY,
    IntentNode.DESIGN: ToolTrust.READ_ONLY,
    IntentNode.DECOMPOSE: ToolTrust.READ_ONLY,
    
    # Action branch
    IntentNode.ACT: ToolTrust.READ_ONLY,  # Parent node
    IntentNode.READ: ToolTrust.READ_ONLY,
    IntentNode.WRITE: ToolTrust.WORKSPACE,
    IntentNode.CREATE: ToolTrust.WORKSPACE,
    IntentNode.MODIFY: ToolTrust.WORKSPACE,
    IntentNode.DELETE: ToolTrust.WORKSPACE,  # Same trust, but explicit approval
}


def get_tool_scope(path: IntentPath) -> ToolTrust | None:
    """Get the ToolTrust level required for a path.
    
    Returns the highest trust level required by any node in the path.
    
    Args:
        path: The intent path (tuple of IntentNode)
        
    Returns:
        ToolTrust level, or None if no tools needed
    """
    if not path:
        return None
    
    # Find the highest trust level in the path
    max_trust: ToolTrust | None = None
    trust_order = [ToolTrust.DISCOVERY, ToolTrust.READ_ONLY, ToolTrust.WORKSPACE, ToolTrust.SHELL]
    
    for node in path:
        node_trust = _NODE_TRUST_MAP.get(node)
        if node_trust is not None:
            if max_trust is None:
                max_trust = node_trust
            elif trust_order.index(node_trust) > trust_order.index(max_trust):
                max_trust = node_trust
    
    return max_trust


# ═══════════════════════════════════════════════════════════════════════════════
# Approval Requirements
# ═══════════════════════════════════════════════════════════════════════════════

# Nodes that always require explicit user approval
_APPROVAL_REQUIRED: frozenset[IntentNode] = frozenset({
    IntentNode.WRITE,
    IntentNode.CREATE,
    IntentNode.MODIFY,
    IntentNode.DELETE,
})

# Nodes that require explicit approval (higher confirmation bar)
_EXPLICIT_APPROVAL_REQUIRED: frozenset[IntentNode] = frozenset({
    IntentNode.DELETE,
})


def requires_approval(path: IntentPath) -> bool:
    """Check if a path requires user approval before execution.
    
    Write operations (CREATE, MODIFY, DELETE) require approval.
    
    Args:
        path: The intent path
        
    Returns:
        True if approval is required
    """
    return any(node in _APPROVAL_REQUIRED for node in path)


def requires_explicit_approval(path: IntentPath) -> bool:
    """Check if a path requires explicit (enhanced) approval.
    
    DELETE operations require explicit "yes I want to delete" confirmation.
    
    Args:
        path: The intent path
        
    Returns:
        True if explicit approval is required
    """
    return any(node in _EXPLICIT_APPROVAL_REQUIRED for node in path)


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoint Triggers
# ═══════════════════════════════════════════════════════════════════════════════

# Transitions that should trigger a checkpoint
_CHECKPOINT_TRANSITIONS: frozenset[tuple[IntentNode, IntentNode]] = frozenset({
    # Moving from planning to action
    (IntentNode.PLAN, IntentNode.ACT),
    (IntentNode.DESIGN, IntentNode.ACT),
    (IntentNode.DECOMPOSE, IntentNode.ACT),
    
    # Moving from analysis to action
    (IntentNode.ANALYZE, IntentNode.ACT),
    (IntentNode.REVIEW, IntentNode.ACT),
    (IntentNode.AUDIT, IntentNode.ACT),
    
    # Moving from read to write
    (IntentNode.READ, IntentNode.WRITE),
    
    # Moving to destructive operations
    (IntentNode.WRITE, IntentNode.DELETE),
    (IntentNode.CREATE, IntentNode.DELETE),
    (IntentNode.MODIFY, IntentNode.DELETE),
})


def get_checkpoint_trigger(from_node: IntentNode, to_node: IntentNode) -> bool:
    """Check if transitioning between nodes should trigger a checkpoint.
    
    Checkpoints give users a chance to approve or modify the intent
    before proceeding with more impactful operations.
    
    Args:
        from_node: The current node
        to_node: The target node
        
    Returns:
        True if a checkpoint should be triggered
    """
    return (from_node, to_node) in _CHECKPOINT_TRANSITIONS


def get_approval_message(path: IntentPath) -> str:
    """Get an appropriate approval message for a path.
    
    Args:
        path: The intent path
        
    Returns:
        Human-readable approval message
    """
    terminal = path[-1] if path else IntentNode.CONVERSATION
    
    messages = {
        IntentNode.CREATE: "This will create new files.",
        IntentNode.MODIFY: "This will modify existing files.",
        IntentNode.DELETE: "This will DELETE files. This cannot be undone.",
        IntentNode.WRITE: "This will write to files.",
    }
    
    return messages.get(terminal, "This action requires approval.")


# ═══════════════════════════════════════════════════════════════════════════════
# Path Validation for Permissions
# ═══════════════════════════════════════════════════════════════════════════════

def can_escalate_to(
    current_trust: ToolTrust | None,
    target_path: IntentPath,
) -> bool:
    """Check if current trust level allows escalation to target path.
    
    Args:
        current_trust: The current ToolTrust level
        target_path: The desired intent path
        
    Returns:
        True if escalation is permitted
    """
    required_trust = get_tool_scope(target_path)
    
    if required_trust is None:
        return True  # No trust required
    
    if current_trust is None:
        return False  # No current trust, can't escalate
    
    trust_order = [ToolTrust.DISCOVERY, ToolTrust.READ_ONLY, ToolTrust.WORKSPACE, ToolTrust.SHELL]
    
    return trust_order.index(current_trust) >= trust_order.index(required_trust)


def get_branch_description(node: IntentNode) -> str:
    """Get a human-readable description of a branch.
    
    Args:
        node: The branch node
        
    Returns:
        Description string
    """
    descriptions = {
        IntentNode.CONVERSATION: "Conversing",
        IntentNode.UNDERSTAND: "Understanding",
        IntentNode.CLARIFY: "Asking for clarification",
        IntentNode.EXPLAIN: "Explaining",
        IntentNode.ANALYZE: "Analyzing",
        IntentNode.REVIEW: "Reviewing code",
        IntentNode.AUDIT: "Investigating",
        IntentNode.PLAN: "Planning",
        IntentNode.DESIGN: "Designing",
        IntentNode.DECOMPOSE: "Breaking down task",
        IntentNode.ACT: "Taking action",
        IntentNode.READ: "Reading files",
        IntentNode.WRITE: "Writing files",
        IntentNode.CREATE: "Creating files",
        IntentNode.MODIFY: "Modifying files",
        IntentNode.DELETE: "Deleting files",
    }
    
    return descriptions.get(node, node.value.title())


def format_path(path: IntentPath) -> str:
    """Format a path for display.
    
    Args:
        path: The intent path
        
    Returns:
        Formatted string like "Conversation → Act → Write → Modify"
    """
    return " → ".join(node.value.title() for node in path)
