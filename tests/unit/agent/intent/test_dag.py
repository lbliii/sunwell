"""Tests for Conversational DAG Architecture.

Verifies the DAG structure, path validation, and classification logic.
"""

import pytest

from sunwell.agent.intent import (
    INTENT_DAG,
    IntentClassification,
    IntentNode,
    build_path_to,
    format_path,
    get_tool_scope,
    get_valid_children,
    is_valid_path,
    path_depth,
    requires_approval,
    requires_explicit_approval,
)
from sunwell.agent.intent.dag import (
    PATH_CREATE,
    PATH_DELETE,
    PATH_EXPLAIN,
    PATH_MODIFY,
    PATH_READ,
    PATH_REVIEW,
)
from sunwell.tools.core.types import ToolTrust


class TestIntentNode:
    """Test IntentNode enum."""
    
    def test_all_nodes_defined(self) -> None:
        """Verify all expected nodes exist."""
        expected = {
            "conversation", "understand", "clarify", "explain",
            "analyze", "review", "audit",
            "plan", "design", "decompose",
            "act", "read", "write", "create", "modify", "delete",
        }
        actual = {node.value for node in IntentNode}
        assert actual == expected
    
    def test_node_values_are_lowercase(self) -> None:
        """Node values should be lowercase strings."""
        for node in IntentNode:
            assert node.value == node.value.lower()


class TestDAGStructure:
    """Test DAG adjacency structure."""
    
    def test_conversation_is_root(self) -> None:
        """CONVERSATION should have all top-level branches."""
        children = get_valid_children(IntentNode.CONVERSATION)
        assert IntentNode.UNDERSTAND in children
        assert IntentNode.ANALYZE in children
        assert IntentNode.PLAN in children
        assert IntentNode.ACT in children
    
    def test_understand_branch(self) -> None:
        """UNDERSTAND branch has CLARIFY and EXPLAIN."""
        children = get_valid_children(IntentNode.UNDERSTAND)
        assert set(children) == {IntentNode.CLARIFY, IntentNode.EXPLAIN}
    
    def test_analyze_branch(self) -> None:
        """ANALYZE branch has REVIEW and AUDIT."""
        children = get_valid_children(IntentNode.ANALYZE)
        assert set(children) == {IntentNode.REVIEW, IntentNode.AUDIT}
    
    def test_plan_branch(self) -> None:
        """PLAN branch has DESIGN and DECOMPOSE."""
        children = get_valid_children(IntentNode.PLAN)
        assert set(children) == {IntentNode.DESIGN, IntentNode.DECOMPOSE}
    
    def test_act_branch(self) -> None:
        """ACT branch has READ and WRITE."""
        children = get_valid_children(IntentNode.ACT)
        assert set(children) == {IntentNode.READ, IntentNode.WRITE}
    
    def test_write_branch(self) -> None:
        """WRITE branch has CREATE, MODIFY, DELETE."""
        children = get_valid_children(IntentNode.WRITE)
        assert set(children) == {IntentNode.CREATE, IntentNode.MODIFY, IntentNode.DELETE}
    
    def test_leaf_nodes_have_no_children(self) -> None:
        """Leaf nodes should have empty children."""
        leaves = [
            IntentNode.CLARIFY, IntentNode.EXPLAIN,
            IntentNode.REVIEW, IntentNode.AUDIT,
            IntentNode.DESIGN, IntentNode.DECOMPOSE,
            IntentNode.READ, IntentNode.CREATE, IntentNode.MODIFY, IntentNode.DELETE,
        ]
        for node in leaves:
            assert get_valid_children(node) == ()


class TestPathValidation:
    """Test path validation functions."""
    
    def test_valid_path_explain(self) -> None:
        """Explain path is valid."""
        assert is_valid_path(PATH_EXPLAIN)
    
    def test_valid_path_modify(self) -> None:
        """Modify path is valid."""
        assert is_valid_path(PATH_MODIFY)
    
    def test_valid_path_delete(self) -> None:
        """Delete path is valid."""
        assert is_valid_path(PATH_DELETE)
    
    def test_invalid_path_missing_root(self) -> None:
        """Path without CONVERSATION root is invalid."""
        invalid = (IntentNode.ACT, IntentNode.WRITE)
        assert not is_valid_path(invalid)
    
    def test_invalid_path_wrong_child(self) -> None:
        """Path with invalid parent-child is invalid."""
        invalid = (IntentNode.CONVERSATION, IntentNode.UNDERSTAND, IntentNode.WRITE)
        assert not is_valid_path(invalid)
    
    def test_empty_path_invalid(self) -> None:
        """Empty path is invalid."""
        assert not is_valid_path(())


class TestPathDepth:
    """Test path depth calculation."""
    
    def test_root_depth(self) -> None:
        """Root only has depth 0."""
        assert path_depth((IntentNode.CONVERSATION,)) == 0
    
    def test_branch_depth(self) -> None:
        """First-level branch has depth 1."""
        path = (IntentNode.CONVERSATION, IntentNode.UNDERSTAND)
        assert path_depth(path) == 1
    
    def test_leaf_depth(self) -> None:
        """Leaf nodes have appropriate depth."""
        assert path_depth(PATH_EXPLAIN) == 2
        assert path_depth(PATH_MODIFY) == 3
        assert path_depth(PATH_DELETE) == 3


class TestBuildPath:
    """Test path building."""
    
    def test_build_path_to_explain(self) -> None:
        """Build path to EXPLAIN."""
        path = build_path_to(IntentNode.EXPLAIN)
        assert path == PATH_EXPLAIN
    
    def test_build_path_to_modify(self) -> None:
        """Build path to MODIFY."""
        path = build_path_to(IntentNode.MODIFY)
        assert path == PATH_MODIFY
    
    def test_build_path_to_root(self) -> None:
        """Build path to root."""
        path = build_path_to(IntentNode.CONVERSATION)
        assert path == (IntentNode.CONVERSATION,)


class TestPermissions:
    """Test permission mapping."""
    
    def test_understand_no_tools(self) -> None:
        """UNDERSTAND branch needs no tools."""
        assert get_tool_scope(PATH_EXPLAIN) is None
        assert get_tool_scope(PATH_EXPLAIN) is None
    
    def test_analyze_read_only(self) -> None:
        """ANALYZE branch needs READ_ONLY."""
        assert get_tool_scope(PATH_REVIEW) == ToolTrust.READ_ONLY
    
    def test_read_read_only(self) -> None:
        """READ needs READ_ONLY."""
        assert get_tool_scope(PATH_READ) == ToolTrust.READ_ONLY
    
    def test_write_workspace(self) -> None:
        """WRITE needs WORKSPACE."""
        assert get_tool_scope(PATH_CREATE) == ToolTrust.WORKSPACE
        assert get_tool_scope(PATH_MODIFY) == ToolTrust.WORKSPACE
        assert get_tool_scope(PATH_DELETE) == ToolTrust.WORKSPACE


class TestApprovalRequirements:
    """Test approval requirements."""
    
    def test_understand_no_approval(self) -> None:
        """UNDERSTAND branch doesn't need approval."""
        assert not requires_approval(PATH_EXPLAIN)
    
    def test_analyze_no_approval(self) -> None:
        """ANALYZE branch doesn't need approval."""
        assert not requires_approval(PATH_REVIEW)
    
    def test_read_no_approval(self) -> None:
        """READ doesn't need approval."""
        assert not requires_approval(PATH_READ)
    
    def test_write_needs_approval(self) -> None:
        """WRITE operations need approval."""
        assert requires_approval(PATH_CREATE)
        assert requires_approval(PATH_MODIFY)
        assert requires_approval(PATH_DELETE)
    
    def test_delete_needs_explicit_approval(self) -> None:
        """DELETE needs explicit approval."""
        assert requires_explicit_approval(PATH_DELETE)
        assert not requires_explicit_approval(PATH_MODIFY)
        assert not requires_explicit_approval(PATH_CREATE)


class TestIntentClassification:
    """Test IntentClassification dataclass."""
    
    def test_classification_properties(self) -> None:
        """Test derived properties."""
        result = IntentClassification(
            path=PATH_MODIFY,
            confidence=0.9,
            reasoning="Test",
            task_description="Fix bug",
        )
        
        assert result.depth == 3
        assert result.terminal_node == IntentNode.MODIFY
        assert result.branch == IntentNode.ACT
        assert result.requires_tools
        assert not result.is_read_only
        assert not result.is_destructive
    
    def test_delete_is_destructive(self) -> None:
        """DELETE path is destructive."""
        result = IntentClassification(
            path=PATH_DELETE,
            confidence=0.9,
            reasoning="Test",
        )
        assert result.is_destructive
    
    def test_explain_no_tools(self) -> None:
        """EXPLAIN path doesn't require tools."""
        result = IntentClassification(
            path=PATH_EXPLAIN,
            confidence=0.9,
            reasoning="Test",
        )
        assert not result.requires_tools
        assert result.is_read_only
    
    def test_move_up(self) -> None:
        """move_up() removes terminal node."""
        result = IntentClassification(
            path=PATH_MODIFY,
            confidence=0.9,
            reasoning="Test",
        )
        moved = result.move_up()
        assert moved.terminal_node == IntentNode.WRITE
        assert len(moved.path) == len(result.path) - 1


class TestFormatPath:
    """Test path formatting."""
    
    def test_format_explain_path(self) -> None:
        """Format EXPLAIN path."""
        formatted = format_path(PATH_EXPLAIN)
        assert formatted == "Conversation → Understand → Explain"
    
    def test_format_modify_path(self) -> None:
        """Format MODIFY path."""
        formatted = format_path(PATH_MODIFY)
        assert formatted == "Conversation → Act → Write → Modify"
