"""Conversational DAG Architecture for Intent Classification.

Models all interactions as a conversation tree where actions are branches,
not separate modes. This replaces the binary chat/task classification with
a more nuanced, permission-aware system.

Core insight: The question isn't "chat or task?" but "how deep into the
action tree should we go?"

Usage:
    from sunwell.agent.intent import (
        IntentNode,
        IntentPath,
        IntentClassification,
        DAGClassifier,
        get_tool_scope,
        requires_approval,
    )
    
    classifier = DAGClassifier(model=model)
    result = await classifier.classify("Add input validation to login")
    # result.path = (CONVERSATION, ACT, WRITE, MODIFY)
    # result.requires_approval = True
"""

from sunwell.agent.intent.classifier import DAGClassifier, classify_intent
from sunwell.agent.intent.dag import (
    INTENT_DAG,
    IntentClassification,
    IntentNode,
    IntentPath,
    build_path_to,
    get_valid_children,
    is_valid_path,
    path_depth,
)
from sunwell.agent.intent.permissions import (
    format_path,
    get_approval_message,
    get_branch_description,
    get_checkpoint_trigger,
    get_tool_scope,
    requires_approval,
    requires_explicit_approval,
)

__all__ = [
    # Types
    "IntentNode",
    "IntentPath",
    "IntentClassification",
    # DAG structure
    "INTENT_DAG",
    "get_valid_children",
    "is_valid_path",
    "path_depth",
    "build_path_to",
    # Classifier
    "DAGClassifier",
    "classify_intent",
    # Permissions
    "get_tool_scope",
    "requires_approval",
    "requires_explicit_approval",
    "get_checkpoint_trigger",
    "get_approval_message",
    "get_branch_description",
    "format_path",
]
