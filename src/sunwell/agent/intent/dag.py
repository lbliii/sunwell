"""Conversational Intent DAG (RFC: Conversational DAG Architecture).

Defines the DAG structure where all interactions are conversational at the root,
with actions as branches. Deeper nodes require more permission.

The DAG:
    Conversation (root)
    ├── Understand (no tools)
    │   ├── Clarify
    │   └── Explain
    ├── Analyze (read-only tools)
    │   ├── Review
    │   └── Audit
    ├── Plan (may lead to action)
    │   ├── Design
    │   └── Decompose
    └── Act (tools required)
        ├── Read
        └── Write
            ├── Create
            ├── Modify
            └── Delete
"""

from dataclasses import dataclass
from enum import Enum


class IntentNode(Enum):
    """Nodes in the conversational intent DAG.
    
    Organized hierarchically:
    - Level 0: CONVERSATION (root)
    - Level 1: UNDERSTAND, ANALYZE, PLAN, ACT
    - Level 2: Leaf nodes for each branch
    - Level 3+: Write operations (CREATE, MODIFY, DELETE)
    """
    
    # Root - all interactions start here
    CONVERSATION = "conversation"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Understanding branch (no tools needed)
    # ═══════════════════════════════════════════════════════════════════════════
    UNDERSTAND = "understand"
    CLARIFY = "clarify"      # Ask for more information from user
    EXPLAIN = "explain"      # Explain a concept, answer a question
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Analysis branch (read-only tools)
    # ═══════════════════════════════════════════════════════════════════════════
    ANALYZE = "analyze"
    REVIEW = "review"        # Code review, provide feedback
    AUDIT = "audit"          # Investigate, debug, trace issues
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Planning branch (may lead to action)
    # ═══════════════════════════════════════════════════════════════════════════
    PLAN = "plan"
    DESIGN = "design"        # Architecture decisions, design choices
    DECOMPOSE = "decompose"  # Break task into subtasks
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Action branch (tools required)
    # ═══════════════════════════════════════════════════════════════════════════
    ACT = "act"
    READ = "read"            # Search, list, grep (read-only tools)
    WRITE = "write"          # File modifications (write tools)
    CREATE = "create"        # Create new files
    MODIFY = "modify"        # Edit existing files
    DELETE = "delete"        # Remove files (most dangerous)


# Type alias for a path through the DAG
IntentPath = tuple[IntentNode, ...]


# ═══════════════════════════════════════════════════════════════════════════════
# DAG Structure - Adjacency List
# ═══════════════════════════════════════════════════════════════════════════════

INTENT_DAG: dict[IntentNode, tuple[IntentNode, ...]] = {
    # Root can go to any top-level branch
    IntentNode.CONVERSATION: (
        IntentNode.UNDERSTAND,
        IntentNode.ANALYZE,
        IntentNode.PLAN,
        IntentNode.ACT,
    ),
    
    # Understanding branch
    IntentNode.UNDERSTAND: (
        IntentNode.CLARIFY,
        IntentNode.EXPLAIN,
    ),
    IntentNode.CLARIFY: (),   # Leaf
    IntentNode.EXPLAIN: (),   # Leaf
    
    # Analysis branch
    IntentNode.ANALYZE: (
        IntentNode.REVIEW,
        IntentNode.AUDIT,
    ),
    IntentNode.REVIEW: (),    # Leaf
    IntentNode.AUDIT: (),     # Leaf
    
    # Planning branch
    IntentNode.PLAN: (
        IntentNode.DESIGN,
        IntentNode.DECOMPOSE,
    ),
    IntentNode.DESIGN: (),    # Leaf
    IntentNode.DECOMPOSE: (), # Leaf
    
    # Action branch
    IntentNode.ACT: (
        IntentNode.READ,
        IntentNode.WRITE,
    ),
    IntentNode.READ: (),      # Leaf (read-only)
    IntentNode.WRITE: (
        IntentNode.CREATE,
        IntentNode.MODIFY,
        IntentNode.DELETE,
    ),
    IntentNode.CREATE: (),    # Leaf
    IntentNode.MODIFY: (),    # Leaf
    IntentNode.DELETE: (),    # Leaf
}


# ═══════════════════════════════════════════════════════════════════════════════
# DAG Navigation
# ═══════════════════════════════════════════════════════════════════════════════

def get_valid_children(node: IntentNode) -> tuple[IntentNode, ...]:
    """Get valid child nodes for a given node.
    
    Args:
        node: The parent node
        
    Returns:
        Tuple of valid child nodes (empty if leaf)
    """
    return INTENT_DAG.get(node, ())


def is_leaf(node: IntentNode) -> bool:
    """Check if a node is a leaf node (no children)."""
    return len(get_valid_children(node)) == 0


def is_valid_path(path: IntentPath) -> bool:
    """Check if a path is valid in the DAG.
    
    A valid path:
    - Starts with CONVERSATION
    - Each node is a valid child of the previous node
    
    Args:
        path: Tuple of IntentNode
        
    Returns:
        True if path is valid
    """
    if not path:
        return False
    
    if path[0] != IntentNode.CONVERSATION:
        return False
    
    for i in range(len(path) - 1):
        parent = path[i]
        child = path[i + 1]
        if child not in get_valid_children(parent):
            return False
    
    return True


def path_depth(path: IntentPath) -> int:
    """Get the depth of a path (0-indexed from root).
    
    Args:
        path: Tuple of IntentNode
        
    Returns:
        Depth (0 for root only, 1 for first-level, etc.)
    """
    return len(path) - 1 if path else 0


def get_parent(node: IntentNode) -> IntentNode | None:
    """Get the parent node in the DAG.
    
    Args:
        node: The child node
        
    Returns:
        Parent node, or None if root
    """
    if node == IntentNode.CONVERSATION:
        return None
    
    for parent, children in INTENT_DAG.items():
        if node in children:
            return parent
    
    return None


def get_ancestors(node: IntentNode) -> tuple[IntentNode, ...]:
    """Get all ancestors of a node, from root to parent.
    
    Args:
        node: The target node
        
    Returns:
        Tuple of ancestors from root (CONVERSATION) to immediate parent
    """
    ancestors: list[IntentNode] = []
    current = get_parent(node)
    
    while current is not None:
        ancestors.append(current)
        current = get_parent(current)
    
    return tuple(reversed(ancestors))


def build_path_to(node: IntentNode) -> IntentPath:
    """Build the canonical path from root to a given node.
    
    Args:
        node: The target node
        
    Returns:
        Full path from CONVERSATION to node
    """
    ancestors = get_ancestors(node)
    return (*ancestors, node)


# ═══════════════════════════════════════════════════════════════════════════════
# Classification Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class IntentClassification:
    """Result of DAG-based intent classification.
    
    Contains the classified path through the DAG, confidence score,
    and derived properties for routing decisions.
    """
    
    path: IntentPath
    """Path through DAG, e.g., (CONVERSATION, ACT, WRITE, MODIFY)"""
    
    confidence: float
    """Classification confidence (0.0-1.0)"""
    
    reasoning: str
    """Why this path was chosen (for debugging/transparency)"""
    
    task_description: str | None = None
    """Extracted task description if action-oriented"""
    
    @property
    def depth(self) -> int:
        """Depth of classification (0 = root only)."""
        return path_depth(self.path)
    
    @property
    def terminal_node(self) -> IntentNode:
        """The final (deepest) node in the path."""
        return self.path[-1] if self.path else IntentNode.CONVERSATION
    
    @property
    def branch(self) -> IntentNode | None:
        """The first-level branch (UNDERSTAND, ANALYZE, PLAN, ACT)."""
        if len(self.path) > 1:
            return self.path[1]
        return None
    
    @property
    def requires_tools(self) -> bool:
        """Whether this classification requires tool access."""
        # ANALYZE and ACT branches need tools
        return self.branch in (IntentNode.ANALYZE, IntentNode.ACT)
    
    @property
    def is_read_only(self) -> bool:
        """Whether this is a read-only operation (no writes)."""
        # Only WRITE branch is not read-only
        return IntentNode.WRITE not in self.path
    
    @property
    def is_destructive(self) -> bool:
        """Whether this involves destructive operations."""
        return IntentNode.DELETE in self.path
    
    def with_path(self, new_path: IntentPath) -> "IntentClassification":
        """Create a new classification with a different path.
        
        Used when user overrides or moves up the tree.
        """
        return IntentClassification(
            path=new_path,
            confidence=self.confidence,
            reasoning=f"{self.reasoning} (path modified)",
            task_description=self.task_description,
        )
    
    def move_up(self) -> "IntentClassification":
        """Create a new classification one level up in the tree.
        
        Used when user wants to back out of a deeper action.
        """
        if len(self.path) <= 1:
            return self  # Already at root
        
        return self.with_path(self.path[:-1])


# ═══════════════════════════════════════════════════════════════════════════════
# Common Paths (for convenience)
# ═══════════════════════════════════════════════════════════════════════════════

# Conversation-only paths
PATH_EXPLAIN = (IntentNode.CONVERSATION, IntentNode.UNDERSTAND, IntentNode.EXPLAIN)
PATH_CLARIFY = (IntentNode.CONVERSATION, IntentNode.UNDERSTAND, IntentNode.CLARIFY)

# Analysis paths
PATH_REVIEW = (IntentNode.CONVERSATION, IntentNode.ANALYZE, IntentNode.REVIEW)
PATH_AUDIT = (IntentNode.CONVERSATION, IntentNode.ANALYZE, IntentNode.AUDIT)

# Planning paths
PATH_DESIGN = (IntentNode.CONVERSATION, IntentNode.PLAN, IntentNode.DESIGN)
PATH_DECOMPOSE = (IntentNode.CONVERSATION, IntentNode.PLAN, IntentNode.DECOMPOSE)

# Action paths
PATH_READ = (IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.READ)
PATH_CREATE = (IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE, IntentNode.CREATE)
PATH_MODIFY = (IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE, IntentNode.MODIFY)
PATH_DELETE = (IntentNode.CONVERSATION, IntentNode.ACT, IntentNode.WRITE, IntentNode.DELETE)
