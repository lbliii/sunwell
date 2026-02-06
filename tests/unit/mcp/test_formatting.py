"""Tests for MCP formatting utilities."""

import json

import pytest

from sunwell.mcp.formatting import (
    DEFAULT_FORMAT,
    FORMAT_COMPACT,
    FORMAT_FULL,
    FORMAT_SUMMARY,
    VALID_FORMATS,
    mcp_json,
    omit_empty,
    resolve_format,
    truncate,
)


class TestMcpJson:
    """Tests for mcp_json serialization."""

    def test_compact_has_no_whitespace(self):
        """Compact format should use minimal separators."""
        data = {"a": 1, "b": "hello"}
        result = mcp_json(data, "compact")
        assert " " not in result
        assert result == '{"a":1,"b":"hello"}'

    def test_summary_has_no_whitespace(self):
        """Summary format should also use minimal separators."""
        data = {"count": 5}
        result = mcp_json(data, "summary")
        assert " " not in result
        assert result == '{"count":5}'

    def test_full_is_pretty_printed(self):
        """Full format should use indent=2."""
        data = {"a": 1}
        result = mcp_json(data, "full")
        parsed = json.loads(result)
        assert parsed == {"a": 1}
        assert "\n" in result
        assert "  " in result

    def test_default_str_handles_non_serializable(self):
        """Non-serializable objects should be converted via str()."""
        from pathlib import Path

        data = {"path": Path("/tmp/foo")}
        result = mcp_json(data, "compact")
        parsed = json.loads(result)
        assert parsed["path"] == "/tmp/foo"

    def test_default_format_is_compact(self):
        """Default format should be compact."""
        data = {"x": 1}
        result = mcp_json(data)
        assert " " not in result

    def test_nested_structures(self):
        """Nested dicts and lists should serialize correctly."""
        data = {"items": [{"id": 1}, {"id": 2}], "meta": {"total": 2}}
        result = mcp_json(data, "compact")
        parsed = json.loads(result)
        assert parsed["items"][0]["id"] == 1
        assert parsed["meta"]["total"] == 2

    def test_empty_data(self):
        """Empty dict should serialize correctly."""
        assert mcp_json({}, "compact") == "{}"
        assert mcp_json([], "compact") == "[]"


class TestTruncate:
    """Tests for truncate helper."""

    def test_short_text_unchanged(self):
        """Short text should be returned as-is."""
        assert truncate("hello", 200) == "hello"

    def test_long_text_truncated(self):
        """Long text should be truncated with ellipsis."""
        text = "a" * 300
        result = truncate(text, 200)
        assert len(result) == 200
        assert result.endswith("...")

    def test_multiline_takes_first_line(self):
        """Multi-line text should use only the first line."""
        text = "first line\nsecond line\nthird line"
        result = truncate(text, 200)
        assert result == "first line"

    def test_none_returns_empty(self):
        """None input should return empty string."""
        assert truncate(None) == ""

    def test_empty_returns_empty(self):
        """Empty string should return empty string."""
        assert truncate("") == ""

    def test_default_max_len_is_200(self):
        """Default max_len should be 200."""
        text = "a" * 250
        result = truncate(text)
        assert len(result) == 200

    def test_exact_boundary(self):
        """Text exactly at max_len should not be truncated."""
        text = "a" * 200
        result = truncate(text, 200)
        assert result == text
        assert "..." not in result

    def test_one_over_boundary(self):
        """Text one char over max_len should be truncated."""
        text = "a" * 201
        result = truncate(text, 200)
        assert len(result) == 200
        assert result.endswith("...")


class TestOmitEmpty:
    """Tests for omit_empty helper."""

    def test_removes_none(self):
        """None values should be removed."""
        assert omit_empty({"a": 1, "b": None}) == {"a": 1}

    def test_removes_empty_list(self):
        """Empty list values should be removed."""
        assert omit_empty({"a": 1, "b": []}) == {"a": 1}

    def test_removes_empty_dict(self):
        """Empty dict values should be removed."""
        assert omit_empty({"a": 1, "b": {}}) == {"a": 1}

    def test_removes_empty_string(self):
        """Empty string values should be removed."""
        assert omit_empty({"a": 1, "b": ""}) == {"a": 1}

    def test_removes_empty_tuple(self):
        """Empty tuple values should be removed."""
        assert omit_empty({"a": 1, "b": ()}) == {"a": 1}

    def test_keeps_non_empty_values(self):
        """Non-empty values should be kept."""
        data = {"a": 1, "b": [1], "c": {"x": 1}, "d": "hi", "e": (1,)}
        assert omit_empty(data) == data

    def test_keeps_zero(self):
        """Zero should NOT be removed (it's a valid value)."""
        assert omit_empty({"a": 0}) == {"a": 0}

    def test_keeps_false(self):
        """False should NOT be removed (it's a valid value)."""
        assert omit_empty({"a": False}) == {"a": False}

    def test_all_empty(self):
        """All-empty dict should return empty dict."""
        assert omit_empty({"a": None, "b": [], "c": {}}) == {}


class TestResolveFormat:
    """Tests for resolve_format helper."""

    def test_valid_formats(self):
        """Valid format strings should be returned as-is (lowered)."""
        assert resolve_format("summary") == "summary"
        assert resolve_format("compact") == "compact"
        assert resolve_format("full") == "full"

    def test_case_insensitive(self):
        """Format strings should be case-insensitive."""
        assert resolve_format("SUMMARY") == "summary"
        assert resolve_format("Compact") == "compact"
        assert resolve_format("FULL") == "full"

    def test_none_returns_default(self):
        """None should return the default format."""
        assert resolve_format(None) == DEFAULT_FORMAT

    def test_empty_string_returns_default(self):
        """Empty string should return the default format."""
        assert resolve_format("") == DEFAULT_FORMAT

    def test_invalid_returns_default(self):
        """Invalid format should return the default format."""
        assert resolve_format("bogus") == DEFAULT_FORMAT
        assert resolve_format("toon") == DEFAULT_FORMAT


class TestConstants:
    """Tests for module constants."""

    def test_default_format_is_compact(self):
        """DEFAULT_FORMAT should be compact."""
        assert DEFAULT_FORMAT == "compact"

    def test_valid_formats_contains_all_tiers(self):
        """VALID_FORMATS should contain all three tiers."""
        assert FORMAT_SUMMARY in VALID_FORMATS
        assert FORMAT_COMPACT in VALID_FORMATS
        assert FORMAT_FULL in VALID_FORMATS
        assert len(VALID_FORMATS) == 3
