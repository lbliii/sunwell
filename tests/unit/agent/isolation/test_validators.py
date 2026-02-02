"""Tests for content validation in isolation module."""

import pytest

from sunwell.agent.isolation.validators import (
    ContentSanityValidator,
    ValidationResult,
    get_content_validator,
    validate_content,
)


class TestContentSanityValidator:
    """Tests for ContentSanityValidator."""

    def test_valid_python_code(self) -> None:
        """Normal Python code should pass validation."""
        content = '''
def hello_world():
    """Say hello."""
    print("Hello, world!")


if __name__ == "__main__":
    hello_world()
'''
        validator = ContentSanityValidator()
        result = validator.validate(content, "hello.py")
        assert result.valid
        assert result.message is None

    def test_valid_typescript_code(self) -> None:
        """Normal TypeScript code should pass validation."""
        content = '''
interface TodoItem {
    id: string;
    title: string;
    completed: boolean;
}

export function createTodo(title: string): TodoItem {
    return {
        id: crypto.randomUUID(),
        title,
        completed: false,
    };
}
'''
        validator = ContentSanityValidator()
        result = validator.validate(content, "todo.ts")
        assert result.valid

    def test_detect_tool_success_message(self) -> None:
        """Tool success messages should fail validation."""
        # This is the exact bug from black-box
        content = '✓ Wrote todo.ts (168 bytes)'
        validator = ContentSanityValidator()
        result = validator.validate(content, "src/todo.ts")
        assert not result.valid
        assert "tool output" in result.message.lower()
        assert "Tool success message" in result.message

    def test_detect_edit_message(self) -> None:
        """Tool edit messages should fail validation."""
        content = "✓ Edited src/models/user.py"
        validator = ContentSanityValidator()
        result = validator.validate(content, "user.py")
        assert not result.valid

    def test_detect_error_message(self) -> None:
        """Error messages should fail validation."""
        content = "Error: Unable to parse file"
        validator = ContentSanityValidator()
        result = validator.validate(content)
        assert not result.valid
        assert "Error message" in result.message

    def test_detect_traceback(self) -> None:
        """Python tracebacks should fail validation."""
        content = '''Traceback (most recent call last):
  File "test.py", line 42, in <module>
    raise ValueError("Test error")
ValueError: Test error'''
        validator = ContentSanityValidator()
        result = validator.validate(content)
        assert not result.valid
        assert "traceback" in result.message.lower()

    def test_detect_llm_meta_response(self) -> None:
        """LLM meta-responses should fail validation."""
        meta_responses = [
            "I'll create the file with the following content:",
            "Let me write a function that does X",
            "Here's the code you requested:",
            "I've written the implementation below:",
        ]
        validator = ContentSanityValidator()
        for content in meta_responses:
            result = validator.validate(content)
            assert not result.valid, f"Should detect meta-response: {content}"
            assert "LLM meta-response" in result.message

    def test_empty_content_passes(self) -> None:
        """Empty content should pass (might be intentional)."""
        validator = ContentSanityValidator()
        assert validator.validate("").valid
        assert validator.validate("   ").valid
        assert validator.validate(None).valid is False or validator.validate("").valid

    def test_status_indicator_single_line(self) -> None:
        """Single-line status indicators should fail."""
        indicators = ["✓ Done", "✗ Failed", "→ Processing", "• Item"]
        validator = ContentSanityValidator()
        for content in indicators:
            result = validator.validate(content)
            assert not result.valid, f"Should detect status: {content}"

    def test_validate_files_batch(self) -> None:
        """Batch validation should work correctly."""
        validator = ContentSanityValidator()
        files = {
            "good.py": "print('hello')",
            "bad.py": "✓ Wrote good.py (20 bytes)",
            "also_good.ts": "const x = 1;",
        }
        results = validator.validate_files(files)

        assert results["good.py"].valid
        assert not results["bad.py"].valid
        assert results["also_good.ts"].valid

    def test_validate_all_pass(self) -> None:
        """validate_all_pass should correctly identify failures."""
        validator = ContentSanityValidator()

        # All good
        good_files = {
            "a.py": "x = 1",
            "b.py": "y = 2",
        }
        all_pass, failed = validator.validate_all_pass(good_files)
        assert all_pass
        assert failed == []

        # Some bad
        mixed_files = {
            "good.py": "x = 1",
            "bad.py": "Error: something went wrong",
        }
        all_pass, failed = validator.validate_all_pass(mixed_files)
        assert not all_pass
        assert failed == ["bad.py"]


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_content_validator_singleton(self) -> None:
        """get_content_validator should return singleton."""
        v1 = get_content_validator()
        v2 = get_content_validator()
        assert v1 is v2

    def test_validate_content_function(self) -> None:
        """validate_content convenience function should work."""
        result = validate_content("print('hello')", "test.py")
        assert result.valid

        result = validate_content("✓ Wrote file.py (100 bytes)")
        assert not result.valid


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_ok_factory(self) -> None:
        """ValidationResult.ok() should create passing result."""
        result = ValidationResult.ok()
        assert result.valid
        assert result.message is None
        assert result.pattern_matched is None

    def test_fail_factory(self) -> None:
        """ValidationResult.fail() should create failing result."""
        result = ValidationResult.fail("Test failure", pattern="test_pattern")
        assert not result.valid
        assert result.message == "Test failure"
        assert result.pattern_matched == "test_pattern"
