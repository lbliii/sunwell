"""Tests for model ID parsing.

Covers Journey H1 (Configure Model) and H12 (Add Custom Model).
"""

import pytest

from sunwell.models.capability.parser import (
    ModelSpec,
    _extract_family,
    _parse_size,
    _parse_version,
    parse_model_id,
)


class TestParseModelId:
    """Test parse_model_id() with various model formats."""

    @pytest.mark.parametrize(
        "model_id,expected_family,expected_version",
        [
            # OpenAI
            ("gpt-4o", "gpt", (4,)),
            ("gpt-4-turbo", "gpt", (4,)),
            ("gpt-3.5-turbo", "gpt", (3, 5)),
            ("gpt-4o-2024-08-06", "gpt", (4,)),
            ("gpt-4o-mini", "gpt", (4,)),
            # OpenAI o-series
            ("o1", "o1", ()),
            ("o1-preview", "o1", ()),
            ("o3-mini", "o3", ()),
            # Anthropic
            ("claude-3.5-sonnet", "claude", (3, 5)),
            ("claude-3-opus", "claude", (3,)),
            ("claude-3-haiku", "claude", (3,)),
            ("claude-sonnet-4-20250514", "claude", (4,)),
            # Llama
            ("llama3.3:70b", "llama", (3, 3)),
            ("llama3.1-8b", "llama", (3, 1)),
            ("llama3", "llama", (3,)),
            ("Llama-3.3-70B-Instruct", "llama", (3, 3)),
            # Qwen
            ("qwen2.5", "qwen", (2, 5)),
            ("qwen3:32b", "qwen", (3,)),
            ("qwen2.5-coder-32b", "qwen", (2, 5)),
            # Mistral
            ("mistral-large", "mistral", ()),
            ("mixtral-8x7b", "mixtral", ()),
            ("mistral-small-latest", "mistral", ()),
            # Gemini
            ("gemini-2.0-flash", "gemini", (2, 0)),
            ("gemini-1.5-pro", "gemini", (1, 5)),
            ("gemini-exp-1206", "gemini", ()),
            # DeepSeek
            ("deepseek-r1", "deepseek", ()),
            ("deepseek-v3", "deepseek", ()),
            ("deepseek-coder", "deepseek", ()),
            # Phi
            ("phi-3", "phi", (3,)),
            ("phi-3.5-mini", "phi", (3, 5)),
            # Gemma
            ("gemma-7b", "gemma", ()),
            ("gemma-2b-it", "gemma", ()),
        ],
    )
    def test_family_and_version(
        self, model_id: str, expected_family: str, expected_version: tuple[int, ...]
    ):
        """Test that family and version are correctly parsed."""
        result = parse_model_id(model_id)
        assert result.family == expected_family
        assert result.version == expected_version

    @pytest.mark.parametrize(
        "model_id,expected_variant",
        [
            ("gpt-4o", "o"),
            ("gpt-4-turbo", "turbo"),
            ("claude-3.5-sonnet", "sonnet"),
            ("claude-3-opus", "opus"),
            ("o1-preview", "preview"),
            ("mistral-large", "large"),
            ("deepseek-r1", "r1"),
            ("deepseek-v3", "v3"),
            ("phi-3.5-mini", "mini"),
        ],
    )
    def test_variant(self, model_id: str, expected_variant: str):
        """Test that variant is correctly extracted."""
        result = parse_model_id(model_id)
        assert result.variant == expected_variant

    @pytest.mark.parametrize(
        "model_id,expected_size",
        [
            ("llama3.3:70b", 70_000_000_000),
            ("llama3.1-8b", 8_000_000_000),
            ("qwen3:32b", 32_000_000_000),
            ("mixtral-8x7b", 56_000_000_000),  # MoE: 8 * 7
            ("gemma-7b", 7_000_000_000),
            ("gemma-2b-it", 2_000_000_000),
        ],
    )
    def test_size(self, model_id: str, expected_size: int):
        """Test that size is correctly parsed."""
        result = parse_model_id(model_id)
        assert result.size == expected_size

    @pytest.mark.parametrize(
        "model_id,expected_provider",
        [
            ("ollama/llama3.3:70b", "ollama"),
            ("together/mistral-large", "together"),
            ("groq/llama3.3:70b", "groq"),
            ("fireworks/qwen2.5", "fireworks"),
            ("gpt-4o", None),  # No provider
        ],
    )
    def test_provider(self, model_id: str, expected_provider: str | None):
        """Test that provider prefix is correctly extracted."""
        result = parse_model_id(model_id)
        assert result.provider == expected_provider

    @pytest.mark.parametrize(
        "model_id,expected_org,expected_custom",
        [
            # First-party orgs are not custom
            ("meta-llama/Llama-3.3-70B-Instruct", "meta-llama", False),
            # Custom fine-tuned models
            ("mycompany/llama3-ft", "mycompany", True),
            ("acme-corp/gpt-4-custom", "acme-corp", True),
            # No org
            ("gpt-4o", None, False),
            # Provider + model (no org)
            ("ollama/llama3.3:70b", None, False),
        ],
    )
    def test_custom_model(
        self, model_id: str, expected_org: str | None, expected_custom: bool
    ):
        """Test custom model detection."""
        result = parse_model_id(model_id)
        assert result.org == expected_org
        assert result.custom == expected_custom

    def test_unknown_model(self):
        """Unknown models are marked as custom with extracted family."""
        result = parse_model_id("totally-unknown-model-v2")
        assert result.family == "totally"
        assert result.custom is True

    def test_version_comparison(self):
        """Version tuples support comparison."""
        spec1 = parse_model_id("claude-3.5-sonnet")
        spec2 = parse_model_id("claude-3-opus")
        assert spec1.version > spec2.version  # (3, 5) > (3,)


class TestParseVersion:
    """Test _parse_version helper."""

    @pytest.mark.parametrize(
        "version_str,expected",
        [
            ("3.5", (3, 5)),
            ("4", (4,)),
            ("3.3.1", (3, 3, 1)),
            ("", ()),
            ("2.0", (2, 0)),
        ],
    )
    def test_parse_version(self, version_str: str, expected: tuple[int, ...]):
        assert _parse_version(version_str) == expected


class TestParseSize:
    """Test _parse_size helper."""

    @pytest.mark.parametrize(
        "size_str,expected",
        [
            ("70", 70_000_000_000),
            ("8", 8_000_000_000),
            ("1.5", 1_500_000_000),
            ("8x7", 56_000_000_000),
            ("", None),
            ("invalid", None),
        ],
    )
    def test_parse_size(self, size_str: str, expected: int | None):
        assert _parse_size(size_str) == expected


class TestExtractFamily:
    """Test _extract_family helper."""

    @pytest.mark.parametrize(
        "model_id,expected",
        [
            ("llama3-instruct", "llama"),
            ("qwen-chat", "qwen"),
            ("model-v2-ft", "model"),
            ("CustomModel-7B", "custommodel"),
            ("123-invalid", "unknown"),
        ],
    )
    def test_extract_family(self, model_id: str, expected: str):
        assert _extract_family(model_id) == expected
