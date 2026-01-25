"""Tests for model capability registry.

Covers Journeys A3 (Generate response), H11 (Switch model), H12 (Add custom model),
E4 (Parallel on non-parallel), E5 (Reasoning model constraints).
"""

import pytest

from sunwell.models.capability import ModelCapability, get_capability


class TestOpenAICapabilities:
    """Test OpenAI model capabilities."""

    def test_gpt4o_capabilities(self):
        """GPT-4o should have full capabilities."""
        cap = get_capability("gpt-4o")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.tool_streaming is True
        assert cap.json_mode is True
        assert cap.context_window == 128000

    def test_gpt4o_mini_capabilities(self):
        """GPT-4o-mini should have same capabilities as 4o."""
        cap = get_capability("gpt-4o-mini")
        assert cap.native_tools is True
        assert cap.parallel_tools is True

    def test_gpt4_turbo_capabilities(self):
        """GPT-4-turbo should have native tools but different limits."""
        cap = get_capability("gpt-4-turbo")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.max_output_tokens == 4096

    def test_gpt35_turbo_capabilities(self):
        """GPT-3.5-turbo should have native tools."""
        cap = get_capability("gpt-3.5-turbo")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.json_mode is True


class TestOSeriesCapabilities:
    """Test OpenAI o1/o3 reasoning model capabilities."""

    def test_o1_capabilities(self):
        """o1 should have reasoning flag and restricted tool_choice."""
        cap = get_capability("o1")
        assert cap.native_tools is True
        assert cap.reasoning is True
        assert cap.supports_tool_choice_required is False  # E5

    def test_o1_preview_capabilities(self):
        """o1-preview should inherit o1 capabilities."""
        cap = get_capability("o1-preview")
        assert cap.reasoning is True
        assert cap.supports_tool_choice_required is False

    def test_o3_mini_capabilities(self):
        """o3-mini should have reasoning capabilities."""
        cap = get_capability("o3-mini")
        assert cap.reasoning is True


class TestClaudeCapabilities:
    """Test Anthropic Claude capabilities."""

    def test_claude_35_sonnet_capabilities(self):
        """Claude 3.5 Sonnet should have full capabilities."""
        cap = get_capability("claude-3.5-sonnet")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.tool_streaming is True
        assert cap.needs_tool_schema_strict is True
        assert cap.tool_result_in_user_message is True

    def test_claude_3_opus_capabilities(self):
        """Claude 3 Opus should have basic tool capabilities."""
        cap = get_capability("claude-3-opus")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.needs_tool_schema_strict is True

    def test_claude_4_capabilities(self):
        """Claude 4 should have reasoning capabilities."""
        cap = get_capability("claude-sonnet-4-20250514")
        assert cap.native_tools is True
        assert cap.reasoning is True
        assert cap.max_output_tokens == 64000


class TestLlamaCapabilities:
    """Test Llama family capabilities."""

    def test_llama33_70b_capabilities(self):
        """Llama 3.3 70B should have native tools but no parallel."""
        cap = get_capability("llama3.3:70b")
        assert cap.native_tools is True
        assert cap.parallel_tools is False  # E4: Llama struggles with parallel
        assert cap.json_mode is True

    def test_llama31_capabilities(self):
        """Llama 3.1 should have native tools."""
        cap = get_capability("llama3.1-8b")
        assert cap.native_tools is True
        assert cap.parallel_tools is False

    def test_small_llama3_emulation(self):
        """Small Llama 3 models without size indicator may need emulation."""
        # llama3 without size defaults to smaller model
        cap = get_capability("llama3")
        # Llama 3.0 without size specified - depends on default
        assert cap.json_mode is True

    def test_llama2_emulation(self):
        """Llama 2 should use emulation."""
        cap = get_capability("llama2:7b")
        assert cap.native_tools is False
        assert cap.emulation_style == "json"

    def test_ollama_llama_capabilities(self):
        """Ollama prefix should not affect capabilities."""
        cap = get_capability("ollama/llama3.3:70b")
        assert cap.native_tools is True


class TestQwenCapabilities:
    """Test Qwen family capabilities."""

    def test_qwen3_capabilities(self):
        """Qwen 3 should have full capabilities including reasoning."""
        cap = get_capability("qwen3:32b")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.reasoning is True

    def test_qwen25_capabilities(self):
        """Qwen 2.5 should have native tools but not parallel."""
        cap = get_capability("qwen2.5")
        assert cap.native_tools is True
        assert cap.parallel_tools is False


class TestMistralCapabilities:
    """Test Mistral/Mixtral capabilities."""

    def test_mistral_large_capabilities(self):
        """Mistral Large should have parallel tools."""
        cap = get_capability("mistral-large")
        assert cap.native_tools is True
        assert cap.parallel_tools is True

    def test_mixtral_capabilities(self):
        """Mixtral should have native tools but not parallel."""
        cap = get_capability("mixtral-8x7b")
        assert cap.native_tools is True
        assert cap.parallel_tools is False


class TestGeminiCapabilities:
    """Test Gemini capabilities."""

    def test_gemini_20_capabilities(self):
        """Gemini 2.0 should have full capabilities."""
        cap = get_capability("gemini-2.0-flash")
        assert cap.native_tools is True
        assert cap.parallel_tools is True
        assert cap.reasoning is True
        assert cap.context_window == 1000000

    def test_gemini_15_capabilities(self):
        """Gemini 1.5 should have large context."""
        cap = get_capability("gemini-1.5-pro")
        assert cap.native_tools is True
        assert cap.context_window == 1000000


class TestDeepSeekCapabilities:
    """Test DeepSeek capabilities."""

    def test_deepseek_r1_capabilities(self):
        """DeepSeek R1 should have reasoning flag."""
        cap = get_capability("deepseek-r1")
        assert cap.native_tools is True
        assert cap.reasoning is True
        assert cap.supports_tool_choice_required is False  # E5

    def test_deepseek_v3_capabilities(self):
        """DeepSeek V3 should have basic capabilities."""
        cap = get_capability("deepseek-v3")
        assert cap.native_tools is True
        assert cap.reasoning is False


class TestNoNativeToolsModels:
    """Test models without native tool support."""

    def test_gemma_emulation(self):
        """Gemma should use emulation."""
        cap = get_capability("gemma-7b")
        assert cap.native_tools is False
        assert cap.emulation_style == "json"

    def test_phi_emulation(self):
        """Phi should use emulation."""
        cap = get_capability("phi-3.5-mini")
        assert cap.native_tools is False
        assert cap.emulation_style == "json"


class TestCustomModels:
    """Test custom/fine-tuned model capability inheritance."""

    def test_custom_llama_inherits_capabilities(self):
        """Custom Llama should inherit base capabilities."""
        cap = get_capability("mycompany/llama3.3-code-ft")
        assert cap.native_tools is True  # Inherits from Llama 3.3

    def test_unknown_model_defaults(self):
        """Unknown models should use safe defaults."""
        cap = get_capability("totally-unknown-model")
        assert cap.native_tools is False
        assert cap.emulation_style == "json"


class TestModelSwitching:
    """Test model switching journey (H11)."""

    def test_switch_preserves_independence(self):
        """Switching models should give independent capabilities."""
        cap1 = get_capability("gpt-4o")
        cap2 = get_capability("ollama/llama3:7b")

        # Different models have different capabilities
        assert cap1.native_tools is True
        assert cap1.parallel_tools is True

        # Capabilities are independent
        assert cap1 != cap2


class TestCapabilityDataclass:
    """Test ModelCapability dataclass properties."""

    def test_frozen(self):
        """ModelCapability should be immutable."""
        cap = get_capability("gpt-4o")
        with pytest.raises(AttributeError):
            cap.native_tools = False  # type: ignore

    def test_default_values(self):
        """Default ModelCapability should be conservative."""
        cap = ModelCapability()
        assert cap.native_tools is False
        assert cap.parallel_tools is False
        assert cap.emulation_style == "json"
