"""Tests for LLM output sanitization (RFC-091).

Validates that control characters are properly removed from LLM outputs
while preserving valid content including Unicode characters.
"""

import json

import pytest

from sunwell.models.core.protocol import _sanitize_dict_values, sanitize_llm_content


class TestSanitizeLlmContent:
    """Unit tests for sanitize_llm_content()."""

    def test_preserves_valid_content(self) -> None:
        """Valid content with newlines and tabs should pass through unchanged."""
        text = "Hello\nWorld\tTab"
        assert sanitize_llm_content(text) == text

    def test_removes_null_character(self) -> None:
        """Null characters (\\x00) should be removed."""
        text = "Hello\x00World"
        assert sanitize_llm_content(text) == "HelloWorld"

    def test_removes_control_chars(self) -> None:
        """Control characters (0x01-0x1F except \\n\\r\\t) should be removed."""
        text = "Hello\x01\x02\x03World"
        assert sanitize_llm_content(text) == "HelloWorld"

    def test_preserves_newline(self) -> None:
        """Newline (\\n) should be preserved."""
        text = "Line1\nLine2"
        assert sanitize_llm_content(text) == text

    def test_preserves_carriage_return(self) -> None:
        """Carriage return (\\r) should be preserved."""
        text = "Line1\r\nLine2"
        assert sanitize_llm_content(text) == text

    def test_preserves_tab(self) -> None:
        """Tab (\\t) should be preserved."""
        text = "Col1\tCol2"
        assert sanitize_llm_content(text) == text

    def test_none_returns_none(self) -> None:
        """None input should return None."""
        assert sanitize_llm_content(None) is None

    def test_empty_string(self) -> None:
        """Empty string should return empty string."""
        assert sanitize_llm_content("") == ""

    def test_preserves_unicode_emoji(self) -> None:
        """Emoji characters should be preserved."""
        text = "Hello 🚀 World 🌍"
        assert sanitize_llm_content(text) == text

    def test_preserves_cjk_characters(self) -> None:
        """CJK (Chinese, Japanese, Korean) characters should be preserved."""
        text = "Hello 世界 こんにちは 안녕하세요"
        assert sanitize_llm_content(text) == text

    def test_preserves_arabic_characters(self) -> None:
        """Arabic characters should be preserved."""
        text = "Hello مرحبا World"
        assert sanitize_llm_content(text) == text

    def test_preserves_extended_ascii(self) -> None:
        """Extended ASCII characters (>= 0x20) should be preserved."""
        text = "Café résumé naïve"
        assert sanitize_llm_content(text) == text

    def test_preserves_code_content(self) -> None:
        """Code with indentation and special characters should be preserved."""
        text = """def hello():
    print("Hello, World!")
    return 42"""
        assert sanitize_llm_content(text) == text

    def test_removes_bell_character(self) -> None:
        """Bell character (\\x07) should be removed."""
        text = "Alert\x07Sound"
        assert sanitize_llm_content(text) == "AlertSound"

    def test_removes_backspace(self) -> None:
        """Backspace character (\\x08) should be removed."""
        text = "Type\x08Delete"
        assert sanitize_llm_content(text) == "TypeDelete"

    def test_removes_form_feed(self) -> None:
        """Form feed character (\\x0C) should be removed."""
        text = "Page1\x0cPage2"
        assert sanitize_llm_content(text) == "Page1Page2"

    def test_all_control_chars_except_whitespace(self) -> None:
        """All control chars 0x00-0x1F except \\t\\n\\r should be removed."""
        # Build string with all control chars
        control_chars = "".join(chr(i) for i in range(32) if chr(i) not in "\t\n\r")
        text = f"A{control_chars}B"
        assert sanitize_llm_content(text) == "AB"


class TestSanitizeDictValues:
    """Unit tests for _sanitize_dict_values()."""

    def test_sanitizes_string_values(self) -> None:
        """String values in dict should be sanitized."""
        d = {"key": "Hello\x00World"}
        result = _sanitize_dict_values(d)
        assert result["key"] == "HelloWorld"

    def test_sanitizes_nested_dict(self) -> None:
        """Nested dict string values should be sanitized."""
        d = {"outer": {"inner": "Hello\x00World"}}
        result = _sanitize_dict_values(d)
        assert result["outer"]["inner"] == "HelloWorld"

    def test_sanitizes_list_strings(self) -> None:
        """String values in lists should be sanitized."""
        d = {"items": ["Hello\x00", "World\x01"]}
        result = _sanitize_dict_values(d)
        assert result["items"] == ["Hello", "World"]

    def test_preserves_non_string_values(self) -> None:
        """Non-string values (int, float, bool, None) should pass through."""
        d = {"int": 42, "float": 3.14, "bool": True, "none": None}
        result = _sanitize_dict_values(d)
        assert result == d

    def test_complex_nested_structure(self) -> None:
        """Complex nested structures should be fully sanitized."""
        d = {
            "name": "Test\x00",
            "config": {
                "value": "Nested\x01Value",
                "items": [
                    {"text": "Item\x02One"},
                    {"text": "Item\x03Two"},
                ],
            },
            "count": 5,
        }
        result = _sanitize_dict_values(d)
        assert result["name"] == "Test"
        assert result["config"]["value"] == "NestedValue"
        assert result["config"]["items"][0]["text"] == "ItemOne"
        assert result["config"]["items"][1]["text"] == "ItemTwo"
        assert result["count"] == 5


class TestJsonSafety:
    """Property tests ensuring sanitized output is always JSON-safe."""

    def test_sanitized_output_serializes_to_json(self) -> None:
        """Sanitized output should always serialize to valid JSON."""
        # Test with various problematic inputs
        test_cases = [
            "Normal text",
            "With\x00null",
            "With\x01\x02\x03control",
            "Mixed\x00\nValid\tChars",
            "Unicode: 🚀 世界",
            "",
        ]

        for text in test_cases:
            sanitized = sanitize_llm_content(text)
            # This should never raise
            json_str = json.dumps({"content": sanitized})
            # And should parse back
            parsed = json.loads(json_str)
            assert parsed["content"] == sanitized

    def test_sanitized_dict_serializes_to_json(self) -> None:
        """Sanitized dict should always serialize to valid JSON."""
        d = {
            "text": "Hello\x00World",
            "nested": {"value": "Nested\x01Text"},
            "list": ["Item\x02One", "Item\x03Two"],
        }

        sanitized = _sanitize_dict_values(d)
        # This should never raise
        json_str = json.dumps(sanitized)
        # And should parse back
        parsed = json.loads(json_str)
        assert parsed == sanitized


class TestEdgeCases:
    """Edge case tests for sanitization."""

    def test_only_control_chars(self) -> None:
        """String with only control chars should become empty."""
        text = "\x00\x01\x02\x03"
        assert sanitize_llm_content(text) == ""

    def test_very_long_string(self) -> None:
        """Long strings should be handled efficiently."""
        text = "A" * 100000 + "\x00" + "B" * 100000
        result = sanitize_llm_content(text)
        assert len(result) == 200000
        assert "\x00" not in result

    def test_alternating_valid_invalid(self) -> None:
        """Alternating valid and invalid chars should work correctly."""
        text = "A\x00B\x01C\x02D\x03E"
        assert sanitize_llm_content(text) == "ABCDE"

    def test_whitespace_only_preserved(self) -> None:
        """String with only valid whitespace should be preserved."""
        text = "\n\r\t"
        assert sanitize_llm_content(text) == text

    def test_mixed_whitespace_and_control(self) -> None:
        """Valid whitespace mixed with control chars."""
        text = "\n\x00\t\x01\r\x02"
        assert sanitize_llm_content(text) == "\n\t\r"
