"""End-to-end journey tests for RFC-136 tool calling.

Tests the complete user and agent journeys through the tool calling system.

Journey Categories:
- Agent Journeys (A1-A11): System components interacting with tools
- Human Journeys (H1-H12): User interactions with the system
- Edge Cases (E1-E8): Unusual but valid scenarios
"""

import pytest

from sunwell.models.capability import (
    ModelCapability,
    ModelSpec,
    NormalizationResult,
    OpenAISchemaAdapter,
    StreamChunk,
    StreamChunkType,
    ToolCallNormalizer,
    ToolQuality,
    ValidationResult,
    audit_tool,
    build_emulation_prompt,
    classify_tool,
    format_tool_result,
    get_capability,
    get_schema_adapter,
    namespace_tools,
    optimize_tool_definitions,
    parse_model_id,
    plan_parallel_execution,
    validate_tool_call,
)
from sunwell.models.capability.parallel import ToolCategory
from sunwell.models.capability.response_format import ResponseFormat
from sunwell.models.capability.streaming import ToolStreamParser
from sunwell.models.core.protocol import Tool, ToolCall
from sunwell.tools.errors import ToolError, ToolErrorCode, get_retry_strategy, should_retry


class TestAgentJourneyA1ReceiveTools:
    """Journey A1: Agent receives tool definitions."""

    def test_tools_formatted_for_openai(self):
        """Tools should be correctly formatted for OpenAI."""
        tools = (
            Tool(name="read_file", description="Read a file", parameters={"type": "object"}),
        )
        adapter = get_schema_adapter("openai")
        formatted = adapter.convert_tools(tools)

        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "read_file"

    def test_tools_formatted_for_anthropic(self):
        """Tools should be correctly formatted for Anthropic."""
        tools = (
            Tool(name="read_file", description="Read a file", parameters={"type": "object"}),
        )
        adapter = get_schema_adapter("anthropic")
        formatted = adapter.convert_tools(tools)

        assert "input_schema" in formatted[0]


class TestAgentJourneyA2FormatSchema:
    """Journey A2: Format tool schema per provider."""

    def test_openai_strict_mode(self):
        """OpenAI should use strict mode by default."""
        tools = (
            Tool(name="test", description="Test", parameters={"type": "object"}),
        )
        adapter = OpenAISchemaAdapter(strict_mode=True)
        formatted = adapter.convert_tools(tools)

        assert formatted[0]["function"]["strict"] is True


class TestAgentJourneyA3GenerateResponse:
    """Journey A3: Generate tool-aware response."""

    def test_capability_aware_routing(self):
        """System should route based on model capabilities."""
        gpt_cap = get_capability("gpt-4o")
        gemma_cap = get_capability("gemma-7b")

        # GPT-4o has native tools
        assert gpt_cap.native_tools is True

        # Gemma needs emulation
        assert gemma_cap.native_tools is False


class TestAgentJourneyA4ParseToolCalls:
    """Journey A4: Parse tool calls from response."""

    def test_parse_json_tool_call(self):
        """Should parse JSON tool calls."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize(
            '```json\n{"tool": "read_file", "arguments": {"path": "test.py"}}\n```'
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"


class TestAgentJourneyA6A7ReceiveHandleResult:
    """Journeys A6-A7: Receive and handle tool result."""

    def test_format_result_for_context(self):
        """Results should be formatted based on context."""
        result = format_tool_result(
            "File contents here...",
            ResponseFormat.CONCISE,
        )
        assert result.format_used == ResponseFormat.CONCISE


class TestAgentJourneyA9RetryEscalate:
    """Journey A9: Retry or escalate on failure."""

    def test_retry_strategy_progression(self):
        """Retry strategy should escalate."""
        error = ToolError(
            code=ToolErrorCode.VALIDATION,
            message="Invalid args",
            recoverable=True,
            retry_strategy="rephrase",
        )

        assert get_retry_strategy(error, attempt=1) == "rephrase"
        assert get_retry_strategy(error, attempt=2) == "interference"
        assert get_retry_strategy(error, attempt=3) == "vortex"


class TestHumanJourneyH1Configure:
    """Journey H1: Configure model for tool calling."""

    def test_parse_various_model_ids(self):
        """Various model ID formats should parse correctly."""
        specs = [
            parse_model_id("gpt-4o"),
            parse_model_id("claude-3.5-sonnet"),
            parse_model_id("ollama/llama3.3:70b"),
        ]

        assert specs[0].family == "gpt"
        assert specs[1].family == "claude"
        assert specs[2].family == "llama"


class TestHumanJourneyH3ObserveProgress:
    """Journey H3: Observe tool calling progress."""

    def test_streaming_provides_progress(self):
        """Streaming should provide real-time progress."""
        parser = ToolStreamParser()
        chunks = parser.feed('{"tool": "read_file", "arguments": {}}')
        chunks += parser.finalize()

        types = [c.type for c in chunks]
        assert StreamChunkType.TOOL_START in types


class TestHumanJourneyH9DebugFailure:
    """Journey H9: Debug a tool failure."""

    def test_errors_have_suggestions(self):
        """Errors should include actionable suggestions."""
        error = ToolError.from_exception(FileNotFoundError("test.py"), "read_file")

        assert error.code == ToolErrorCode.NOT_FOUND
        assert error.suggested_fix is not None
        assert "list_files" in error.suggested_fix


class TestHumanJourneyH11SwitchModel:
    """Journey H11: Switch model mid-session."""

    def test_capabilities_are_independent(self):
        """Each model should have independent capabilities."""
        cap1 = get_capability("gpt-4o")
        cap2 = get_capability("llama3.3:70b")

        assert cap1.parallel_tools != cap2.parallel_tools


class TestHumanJourneyH12AddCustomModel:
    """Journey H12: Add custom/fine-tuned model."""

    def test_custom_model_inherits_capabilities(self):
        """Custom models should inherit base capabilities."""
        cap = get_capability("mycompany/llama3.3-ft-v2")

        # Should inherit Llama 3.3 capabilities
        assert cap.native_tools is True


class TestEdgeCaseE1ModelRefuses:
    """Edge case E1: Model refuses to call tool."""

    def test_no_tool_calls_detected(self):
        """Should handle responses with no tool calls."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize("I don't need to use any tools for this.")

        assert len(result.tool_calls) == 0


class TestEdgeCaseE2MalformedJSON:
    """Edge case E2: Malformed JSON tool call."""

    def test_json_repair(self):
        """Should repair common JSON errors."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize("{'tool': 'read_file', 'arguments': {'path': 'test'}}")

        assert len(result.tool_calls) == 1


class TestEdgeCaseE4ParallelOnNonParallel:
    """Edge case E4: Parallel calls on non-parallel model."""

    def test_sequential_for_non_parallel(self):
        """Non-parallel models should get sequential plan."""
        tools = {
            "read_file": Tool(name="read_file", description="Read", parameters={}),
        }
        calls = (
            ToolCall(id="1", name="read_file", arguments={}),
            ToolCall(id="2", name="read_file", arguments={}),
        )
        cap = ModelCapability(parallel_tools=False)

        plan = plan_parallel_execution(calls, tools, cap)

        assert len(plan.sequential_calls) == 2
        assert len(plan.parallel_groups) == 0


class TestEdgeCaseE5ReasoningModelConstraints:
    """Edge case E5: Reasoning model constraints."""

    def test_o1_tool_choice_constraint(self):
        """o1 models should have tool_choice restrictions."""
        cap = get_capability("o1")

        assert cap.reasoning is True
        assert cap.supports_tool_choice_required is False


class TestEdgeCaseE6ContextOverflow:
    """Edge case E6: Context overflow handling."""

    def test_tools_optimized_for_small_context(self):
        """Tools should be optimized for small contexts."""
        tools = tuple(
            Tool(
                name=f"tool_{i}",
                description="A" * 500,
                parameters={"type": "object"},
            )
            for i in range(20)
        )
        cap = ModelCapability(context_window=4096)

        optimized = optimize_tool_definitions(tools, cap)

        assert len(optimized) < len(tools)


class TestEdgeCaseE7RateLimit:
    """Edge case E7: Rate limit handling."""

    def test_rate_limit_error_handling(self):
        """Rate limits should be recoverable."""
        error = ToolError.from_exception(
            Exception("Rate limit exceeded"), "api_call"
        )

        assert error.code == ToolErrorCode.RATE_LIMIT
        assert error.recoverable is True


class TestEdgeCaseE8NetworkFailure:
    """Edge case E8: Network failure handling."""

    def test_network_error_handling(self):
        """Network errors should be recoverable."""
        error = ToolError.from_exception(
            Exception("Connection refused"), "web_fetch"
        )

        assert error.code == ToolErrorCode.NETWORK
        assert error.recoverable is True


class TestToolQualityAudit:
    """Test tool quality auditing for built-in tools."""

    def test_builtin_tool_quality(self):
        """Built-in tools should score >= 0.6."""
        # Simulated built-in tool
        tool = Tool(
            name="read_file",
            description="Read the contents of a file at the specified path and return the text content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative file path to read",
                    }
                },
                "required": ["path"],
            },
        )
        quality = audit_tool(tool)

        assert quality.score >= 0.6


class TestValidationFlow:
    """Test validation-based retry flow."""

    def test_validation_detects_missing_required(self):
        """Validation should catch missing required params."""
        tool = Tool(
            name="test",
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {"required_param": {"type": "string"}},
                "required": ["required_param"],
            },
        )
        call = ToolCall(id="1", name="test", arguments={})

        result = validate_tool_call(call, tool)

        assert result.success is False
        assert len(result.errors) > 0


class TestNamespacingFlow:
    """Test tool namespacing for multi-service."""

    def test_namespace_preserves_functionality(self):
        """Namespacing should preserve tool functionality."""
        tools = (Tool(name="read", description="Read", parameters={}),)

        namespaced = namespace_tools(tools, "files")

        assert namespaced[0].name == "files.read"
        assert "[files]" in namespaced[0].description


class TestParallelExecutionFlow:
    """Test parallel execution planning."""

    def test_read_only_tools_grouped(self):
        """Read-only tools should be grouped for parallel execution."""
        tools = {
            "read_file": Tool(name="read_file", description="Read", parameters={}),
            "list_files": Tool(name="list_files", description="List", parameters={}),
        }
        calls = (
            ToolCall(id="1", name="read_file", arguments={}),
            ToolCall(id="2", name="list_files", arguments={}),
        )
        cap = ModelCapability(parallel_tools=True)

        plan = plan_parallel_execution(calls, tools, cap)

        assert len(plan.parallel_groups) == 1
        assert len(plan.parallel_groups[0]) == 2
