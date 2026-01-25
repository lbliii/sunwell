"""Tests for response format control."""

import pytest

from sunwell.models.capability.response_format import (
    FormattedResult,
    ResponseFormat,
    format_tool_result,
    get_recommended_format,
)


class TestFormatToolResult:
    """Test tool result formatting."""

    def test_detailed_format(self):
        """Detailed format preserves content."""
        result = format_tool_result("Hello World", ResponseFormat.DETAILED)

        assert result.content == "Hello World"
        assert result.format_used == ResponseFormat.DETAILED

    def test_concise_format(self):
        """Concise format reduces content."""
        long_content = "\n".join([f"Line {i}" for i in range(50)])
        result = format_tool_result(long_content, ResponseFormat.CONCISE)

        assert result.formatted_length < result.original_length
        assert result.format_used == ResponseFormat.CONCISE

    def test_minimal_format(self):
        """Minimal format is very short."""
        long_content = "\n".join([f"Line {i}" for i in range(50)])
        result = format_tool_result(long_content, ResponseFormat.MINIMAL)

        assert result.formatted_length < result.original_length
        assert "more" in result.content

    def test_max_length_truncation(self):
        """Max length should truncate."""
        result = format_tool_result("A" * 1000, ResponseFormat.DETAILED, max_length=100)

        assert len(result.content) == 100
        assert result.content.endswith("...")

    def test_dict_formatting(self):
        """Dict results should be JSON formatted."""
        result = format_tool_result({"key": "value"}, ResponseFormat.DETAILED)

        assert "key" in result.content
        assert "value" in result.content

    def test_compression_ratio(self):
        """Compression ratio should be calculated."""
        result = format_tool_result("Test", ResponseFormat.DETAILED)

        assert result.compression_ratio == 1.0


class TestGetRecommendedFormat:
    """Test format recommendation."""

    def test_unlimited_context_uses_detailed(self):
        """Unlimited context should use detailed."""
        format_level = get_recommended_format(None, 1000)
        assert format_level == ResponseFormat.DETAILED

    def test_small_result_uses_detailed(self):
        """Small results use detailed."""
        format_level = get_recommended_format(10000, 100)
        assert format_level == ResponseFormat.DETAILED

    def test_large_result_uses_concise(self):
        """Large results use concise."""
        # 900 chars = ~225 tokens, 1000 * 0.2 = 200, so 225 > 200 triggers concise
        format_level = get_recommended_format(1000, 900)
        assert format_level == ResponseFormat.CONCISE

    def test_huge_result_uses_minimal(self):
        """Huge results use minimal."""
        # 2100 chars = ~525 tokens, 1000 * 0.5 = 500, so 525 > 500 triggers minimal
        format_level = get_recommended_format(1000, 2100)
        assert format_level == ResponseFormat.MINIMAL


class TestFormattedResult:
    """Test FormattedResult dataclass."""

    def test_immutable(self):
        """FormattedResult should be immutable."""
        result = FormattedResult(
            content="test",
            original_length=4,
            formatted_length=4,
            format_used=ResponseFormat.DETAILED,
        )
        with pytest.raises(AttributeError):
            result.content = "changed"  # type: ignore
