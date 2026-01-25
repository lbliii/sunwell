"""Tests for RFC-134: Agent Loop Differentiators.

Tests for:
1. Tool call introspection
2. Automatic retry with strategy escalation
3. Tool usage learning
4. Progressive tool enablement
"""

from pathlib import Path

import pytest

from sunwell.agent.validation.introspection import (
    IntrospectionResult,
    introspect_tool_call,
    _sanitize_code_content,
    _normalize_path,
    _validate_required_args,
)
from sunwell.agent.learning import (
    LearningStore,
    ToolPattern,
    classify_task_type,
)
from sunwell.models.core.protocol import ToolCall
from sunwell.tools.progressive import ProgressivePolicy
from sunwell.tools.core.types import ToolTrust


# =============================================================================
# Feature 1: Tool Call Introspection
# =============================================================================


class TestIntrospection:
    """Test suite for tool call introspection (RFC-134)."""

    def test_sanitize_markdown_fences_full(self) -> None:
        """Test stripping full markdown fence wrapper."""
        content = '```python\nprint("hello")\n```'
        sanitized, repairs = _sanitize_code_content(content)
        assert sanitized == 'print("hello")'
        assert len(repairs) == 1
        assert "Stripped markdown code fences" in repairs[0]

    def test_sanitize_markdown_fences_leading_only(self) -> None:
        """Test stripping leading fence only."""
        content = '```python\nprint("hello")'
        sanitized, repairs = _sanitize_code_content(content)
        assert sanitized == 'print("hello")'
        assert len(repairs) == 1

    def test_sanitize_markdown_fences_no_fences(self) -> None:
        """Test content without fences passes through unchanged."""
        content = 'print("hello")'
        sanitized, repairs = _sanitize_code_content(content)
        assert sanitized == content
        assert len(repairs) == 0

    def test_normalize_path_leading_dot_slash(self) -> None:
        """Test normalizing ./path to path."""
        workspace = Path("/project")
        path, repairs = _normalize_path("./src/main.py", workspace)
        assert path == "src/main.py"
        assert len(repairs) == 1

    def test_normalize_path_absolute_within_workspace(self) -> None:
        """Test converting absolute path to relative."""
        workspace = Path("/project")
        path, repairs = _normalize_path("/project/src/main.py", workspace)
        assert path == "src/main.py"
        assert len(repairs) == 1

    def test_normalize_path_already_relative(self) -> None:
        """Test relative path passes through."""
        workspace = Path("/project")
        path, repairs = _normalize_path("src/main.py", workspace)
        assert path == "src/main.py"
        assert len(repairs) == 0

    def test_validate_required_args_missing(self) -> None:
        """Test detection of missing required argument."""
        is_valid, error = _validate_required_args("write_file", {"path": "test.py"})
        assert not is_valid
        assert "content" in error

    def test_validate_required_args_empty_string(self) -> None:
        """Test detection of empty required argument."""
        is_valid, error = _validate_required_args(
            "write_file", {"path": "", "content": "test"}
        )
        assert not is_valid
        assert "path" in error

    def test_validate_required_args_valid(self) -> None:
        """Test valid arguments pass validation."""
        is_valid, error = _validate_required_args(
            "write_file", {"path": "test.py", "content": "test"}
        )
        assert is_valid
        assert error is None

    def test_introspect_blocks_empty_path(self) -> None:
        """Test that empty path blocks tool call."""
        tc = ToolCall(id="1", name="write_file", arguments={"path": "", "content": "x"})
        result = introspect_tool_call(tc, Path("/project"))
        assert result.blocked
        assert "path" in result.block_reason.lower()

    def test_introspect_repairs_markdown_fences(self) -> None:
        """Test introspection repairs markdown fences in content."""
        tc = ToolCall(
            id="1",
            name="write_file",
            arguments={"path": "test.py", "content": '```python\nprint("hi")\n```'},
        )
        result = introspect_tool_call(tc, Path("/project"))
        assert not result.blocked
        assert len(result.repairs) > 0
        assert result.tool_call.arguments["content"] == 'print("hi")'

    def test_introspect_repairs_path(self) -> None:
        """Test introspection repairs path with leading ./."""
        tc = ToolCall(
            id="1",
            name="write_file",
            arguments={"path": "./src/test.py", "content": "test"},
        )
        result = introspect_tool_call(tc, Path("/project"))
        assert not result.blocked
        assert len(result.repairs) > 0
        assert result.tool_call.arguments["path"] == "src/test.py"


# =============================================================================
# Feature 3: Tool Usage Learning
# =============================================================================


class TestToolPattern:
    """Test suite for tool pattern learning (RFC-134)."""

    def test_tool_pattern_success_rate(self) -> None:
        """Test success rate calculation."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file", "edit_file"),
            success_count=8,
            failure_count=2,
        )
        assert pattern.success_rate == 0.8

    def test_tool_pattern_success_rate_zero(self) -> None:
        """Test success rate with no data."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file",),
        )
        assert pattern.success_rate == 0.5  # Default

    def test_tool_pattern_record(self) -> None:
        """Test recording outcomes."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file",),
        )
        pattern.record(success=True)
        assert pattern.success_count == 1
        pattern.record(success=False)
        assert pattern.failure_count == 1

    def test_tool_pattern_confidence(self) -> None:
        """Test confidence calculation with sample size boost."""
        pattern = ToolPattern(
            task_type="api",
            tool_sequence=("read_file",),
            success_count=10,
            failure_count=0,
        )
        # High success rate + sample size boost
        assert pattern.confidence > 0.7


class TestClassifyTaskType:
    """Test task type classification."""

    def test_classify_test(self) -> None:
        assert classify_task_type("Write unit tests for the API") == "test"

    def test_classify_refactor(self) -> None:
        assert classify_task_type("Refactor the database module") == "refactor"

    def test_classify_fix(self) -> None:
        assert classify_task_type("Fix the bug in login") == "fix"

    def test_classify_api(self) -> None:
        assert classify_task_type("Add a REST API endpoint") == "api"

    def test_classify_new_file(self) -> None:
        assert classify_task_type("Create a new config file") == "new_file"

    def test_classify_general(self) -> None:
        assert classify_task_type("Do something random") == "general"


class TestLearningStoreToolPatterns:
    """Test LearningStore tool pattern tracking (RFC-134)."""

    def test_record_tool_sequence(self) -> None:
        """Test recording a tool sequence."""
        store = LearningStore()
        store.record_tool_sequence(
            task_type="api",
            tools=["read_file", "edit_file"],
            success=True,
        )
        patterns = store.get_tool_patterns(min_samples=1)
        assert len(patterns) == 1
        assert patterns[0].success_count == 1

    def test_record_tool_sequence_updates_existing(self) -> None:
        """Test recording same sequence updates existing pattern."""
        store = LearningStore()
        store.record_tool_sequence("api", ["read_file"], success=True)
        store.record_tool_sequence("api", ["read_file"], success=True)
        store.record_tool_sequence("api", ["read_file"], success=False)

        patterns = store.get_tool_patterns(min_samples=1)
        assert len(patterns) == 1
        assert patterns[0].success_count == 2
        assert patterns[0].failure_count == 1

    def test_suggest_tools_returns_best_pattern(self) -> None:
        """Test suggest_tools returns the best pattern."""
        store = LearningStore()
        # Record a successful pattern
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)
        store.record_tool_sequence("api", ["read_file", "edit_file"], success=True)
        # Record a less successful pattern
        store.record_tool_sequence("api", ["write_file"], success=False)

        suggested = store.suggest_tools("api")
        assert suggested == ["read_file", "edit_file"]

    def test_suggest_tools_empty_for_unknown_type(self) -> None:
        """Test suggest_tools returns empty for unknown task type."""
        store = LearningStore()
        suggested = store.suggest_tools("nonexistent")
        assert suggested == []

    def test_format_tool_suggestions(self) -> None:
        """Test formatting tool suggestions for prompt injection."""
        store = LearningStore()
        store.record_tool_sequence("api", ["read_file"], success=True)

        suggestion = store.format_tool_suggestions("api")
        assert suggestion is not None
        assert "read_file" in suggestion
        assert "api" in suggestion


# =============================================================================
# Feature 4: Progressive Tool Enablement
# =============================================================================


class TestProgressivePolicy:
    """Test suite for progressive tool enablement (RFC-134)."""

    def test_turn_1_read_only(self) -> None:
        """Test turn 1 only has read-only tools."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        tools = policy.get_available_tools()

        assert "read_file" in tools
        assert "list_files" in tools
        assert "search_files" in tools
        assert "edit_file" not in tools
        assert "write_file" not in tools

    def test_turn_2_edit_enabled(self) -> None:
        """Test turn 2+ enables edit_file."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        policy.advance_turn()  # Now turn 2

        tools = policy.get_available_tools()
        assert "edit_file" in tools
        assert "write_file" not in tools

    def test_turn_3_with_validation_write_enabled(self) -> None:
        """Test turn 3+ with validation pass enables write tools."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        policy.advance_turn()  # Turn 2
        policy.advance_turn()  # Turn 3
        policy.record_validation_pass()

        tools = policy.get_available_tools()
        assert "write_file" in tools
        assert "mkdir" in tools

    def test_turn_5_with_2_validations_shell_enabled(self) -> None:
        """Test turn 5+ with 2 validation passes enables shell tools."""
        policy = ProgressivePolicy(base_trust=ToolTrust.SHELL)
        for _ in range(4):  # Advance to turn 5
            policy.advance_turn()
        policy.record_validation_pass()
        policy.record_validation_pass()

        tools = policy.get_available_tools()
        assert "run_command" in tools

    def test_shell_requires_shell_trust(self) -> None:
        """Test shell tools require SHELL trust level."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        for _ in range(4):  # Advance to turn 5
            policy.advance_turn()
        policy.record_validation_pass()
        policy.record_validation_pass()

        tools = policy.get_available_tools()
        assert "run_command" not in tools  # WORKSPACE trust doesn't include shell

    def test_full_trust_bypasses_progressive(self) -> None:
        """Test FULL trust bypasses progressive unlocking."""
        policy = ProgressivePolicy(base_trust=ToolTrust.FULL)
        tools = policy.get_available_tools()

        # All tools available from turn 1
        assert "read_file" in tools
        assert "write_file" in tools
        assert "run_command" in tools
        assert "web_search" in tools

    def test_validation_failures_restrict_tools(self) -> None:
        """Test too many validation failures restricts to read-only."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        policy.advance_turn()
        policy.advance_turn()
        policy.record_validation_pass()
        policy.record_validation_failure()
        policy.record_validation_failure()
        policy.record_validation_failure()

        tools = policy.get_available_tools()
        # Should be restricted to read-only
        assert "read_file" in tools
        assert "edit_file" not in tools
        assert "write_file" not in tools

    def test_is_tool_available(self) -> None:
        """Test is_tool_available method."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        assert policy.is_tool_available("read_file")
        assert not policy.is_tool_available("edit_file")

    def test_unlock_status(self) -> None:
        """Test get_unlock_status method."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        status = policy.get_unlock_status()

        assert status["read_only"] is True
        assert status["edit"] is False
        assert status["write"] is False
        assert status["shell"] is False

    def test_unlock_requirements(self) -> None:
        """Test get_unlock_requirements method."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        requirements = policy.get_unlock_requirements()

        assert "edit" in requirements
        assert "1 more turn" in requirements["edit"]


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for RFC-134 features working together."""

    def test_introspection_repairs_before_pattern_learning(self) -> None:
        """Test that introspection repairs happen before tool pattern recording."""
        tc = ToolCall(
            id="1",
            name="write_file",
            arguments={"path": "./test.py", "content": '```python\ncode\n```'},
        )
        result = introspect_tool_call(tc, Path("/project"))

        # Verify repairs were made
        assert len(result.repairs) >= 2  # Path and content repairs
        assert result.tool_call.arguments["path"] == "test.py"
        assert result.tool_call.arguments["content"] == "code"

    def test_progressive_policy_serialization(self) -> None:
        """Test progressive policy can be serialized to dict."""
        policy = ProgressivePolicy(base_trust=ToolTrust.WORKSPACE)
        policy.advance_turn()
        policy.record_validation_pass()

        data = policy.to_dict()
        assert data["turn"] == 2
        assert data["validation_passes"] == 1
        assert "read_file" in data["available_tools"]
