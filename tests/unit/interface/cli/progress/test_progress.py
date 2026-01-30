"""Tests for enhanced progress visualization."""

import pytest
from rich.console import Console

from sunwell.interface.cli.progress.dag_path import (
    DAGPathDisplay,
    NODE_STYLES,
    format_dag_path,
)
from sunwell.interface.cli.progress.status_bar import (
    StatusBar,
    StatusMetrics,
)


class TestDAGPathDisplay:
    """Test DAGPathDisplay class."""
    
    def test_empty_path(self) -> None:
        """Empty path returns no terminal node."""
        display = DAGPathDisplay(console=Console())
        assert display.get_terminal_node() is None
        assert display.get_depth() == 0
    
    def test_update_path(self) -> None:
        """Update path sets current path."""
        display = DAGPathDisplay(console=Console())
        display.update(["conversation", "act", "write"])
        
        assert display.current_path == ["conversation", "act", "write"]
        assert display.get_terminal_node() == "write"
        assert display.get_depth() == 3
    
    def test_render_inline(self) -> None:
        """Inline rendering produces readable string."""
        display = DAGPathDisplay(console=Console())
        display.update(["conversation", "act", "write"])
        
        inline = display.render_inline()
        assert "Conversation" in inline
        assert "Act" in inline
        assert "Write" in inline
        assert " → " in inline


class TestFormatDAGPath:
    """Test format_dag_path function."""
    
    def test_empty_path(self) -> None:
        """Empty path produces empty text."""
        text = format_dag_path([])
        assert text.plain == ""
    
    def test_single_node(self) -> None:
        """Single node path formats correctly."""
        text = format_dag_path(["conversation"])
        assert "Conversation" in text.plain
    
    def test_multi_node_path(self) -> None:
        """Multi-node path includes separators."""
        text = format_dag_path(["conversation", "act", "write"])
        assert " → " in text.plain
        assert "Conversation" in text.plain
        assert "Act" in text.plain
        assert "Write" in text.plain
    
    def test_unknown_node(self) -> None:
        """Unknown nodes use title case."""
        text = format_dag_path(["custom_node"])
        assert "Custom_Node" in text.plain or "Custom_node" in text.plain


class TestNodeStyles:
    """Test NODE_STYLES configuration."""
    
    def test_all_intent_nodes_have_styles(self) -> None:
        """All expected intent nodes have styles defined."""
        expected_nodes = [
            "conversation", "understand", "clarify", "explain",
            "analyze", "review", "audit",
            "plan", "design", "decompose",
            "act", "read", "write", "create", "modify", "delete",
        ]
        for node in expected_nodes:
            assert node in NODE_STYLES, f"Missing style for {node}"
    
    def test_style_format(self) -> None:
        """Each style is (display_name, color) tuple."""
        for node, (name, color) in NODE_STYLES.items():
            assert isinstance(name, str), f"{node} display name should be string"
            assert isinstance(color, str), f"{node} color should be string"
            assert len(name) > 0, f"{node} display name should not be empty"


class TestStatusMetrics:
    """Test StatusMetrics dataclass."""
    
    def test_initial_values(self) -> None:
        """New metrics have zero values."""
        metrics = StatusMetrics()
        assert metrics.tokens_in == 0
        assert metrics.tokens_out == 0
        assert metrics.total_tokens == 0
        assert metrics.cost == 0.0
    
    def test_add_tokens(self) -> None:
        """Adding tokens updates counts."""
        metrics = StatusMetrics()
        metrics.add_tokens(input_tokens=100, output_tokens=50)
        
        assert metrics.tokens_in == 100
        assert metrics.tokens_out == 50
        assert metrics.total_tokens == 150
    
    def test_add_cost(self) -> None:
        """Adding cost accumulates."""
        metrics = StatusMetrics()
        metrics.add_cost(0.01)
        metrics.add_cost(0.02)
        
        assert metrics.cost == pytest.approx(0.03)
    
    def test_elapsed_formatted(self) -> None:
        """Elapsed time formats correctly."""
        import time
        metrics = StatusMetrics(start_time=time.time() - 90)
        
        # Should be "1m 30s" format
        formatted = metrics.elapsed_formatted
        assert "m" in formatted or "s" in formatted
    
    def test_record_calls(self) -> None:
        """Recording calls increments counters."""
        metrics = StatusMetrics()
        metrics.record_llm_call()
        metrics.record_llm_call()
        metrics.record_tool_call()
        
        assert metrics.llm_calls == 2
        assert metrics.tool_calls == 1


class TestStatusBar:
    """Test StatusBar class."""
    
    def test_create_status_bar(self) -> None:
        """StatusBar can be created with default console."""
        bar = StatusBar()
        assert bar.console is not None
        assert bar.metrics is not None
    
    def test_update_path(self) -> None:
        """Updating path stores it."""
        bar = StatusBar()
        bar.update_path(["conversation", "act"])
        
        assert bar.current_path == ["conversation", "act"]
    
    def test_metrics_integration(self) -> None:
        """Status bar metrics can be updated."""
        bar = StatusBar()
        bar.metrics.add_tokens(1000, 500)
        bar.metrics.add_cost(0.05)
        
        assert bar.metrics.total_tokens == 1500
        assert bar.metrics.cost == 0.05
