"""Content validation for file isolation.

Defense-in-depth validators that catch common issues with LLM-generated content:
- Tool output contamination (e.g., "✓ Wrote file.py" as file content)
- Error messages written as content
- Traceback contamination

These validators run before files are committed, regardless of isolation strategy.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of content validation.

    Attributes:
        valid: Whether the content passed validation
        message: Description of the issue if invalid
        pattern_matched: The pattern that matched (for debugging)
    """

    valid: bool
    """Whether the content passed validation."""

    message: str | None = None
    """Description of the issue if invalid."""

    pattern_matched: str | None = None
    """The pattern that matched (for debugging)."""

    @classmethod
    def ok(cls) -> "ValidationResult":
        """Create a passing validation result."""
        return cls(valid=True)

    @classmethod
    def fail(cls, message: str, pattern: str | None = None) -> "ValidationResult":
        """Create a failing validation result."""
        return cls(valid=False, message=message, pattern_matched=pattern)


class ContentSanityValidator:
    """Validates file content for common LLM output contamination patterns.

    Detects when tool output, error messages, or other meta-content has been
    accidentally written as file content. This is a common failure mode in
    parallel execution where stdout/stderr can get mixed with content.

    Usage:
        validator = ContentSanityValidator()
        result = validator.validate(content, "src/utils.py")
        if not result.valid:
            logger.error(f"Content validation failed: {result.message}")
    """

    # Patterns that should never appear as file content
    FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
        # Tool success messages
        (r"^✓ Wrote .+ \(\d+.*bytes\)$", "Tool success message"),
        (r"^✓ Edited .+$", "Tool edit message"),
        (r"^✓ Deleted .+$", "Tool delete message"),
        (r"^✓ Copied .+$", "Tool copy message"),
        (r"^✓ Renamed .+$", "Tool rename message"),
        (r"^✓ Patched .+$", "Tool patch message"),
        # Error patterns
        (r"^Error:", "Error message"),
        (r"^ERROR:", "Error message"),
        (r"^Traceback \(most recent call last\):", "Python traceback"),
        (r"^  File \".*\", line \d+", "Python traceback"),
        (r"^Unexpected error:", "Unexpected error message"),
        # Command output patterns
        (r"^Command .+ failed with exit code \d+", "Command failure message"),
        (r"^File not found:", "File not found message"),
        (r"^Permission denied:", "Permission denied message"),
        # LLM meta-content
        (r"^I'll create the file", "LLM meta-response"),
        (r"^Let me (write|create|add)", "LLM meta-response"),
        (r"^Here's the (code|content|file)", "LLM meta-response"),
        (r"^I've (written|created|added)", "LLM meta-response"),
    )

    # Compiled patterns for performance
    _compiled_patterns: list[tuple[re.Pattern, str]] | None = None

    def __init__(self) -> None:
        """Initialize the validator with compiled patterns."""
        if ContentSanityValidator._compiled_patterns is None:
            ContentSanityValidator._compiled_patterns = [
                (re.compile(pattern, re.MULTILINE), desc)
                for pattern, desc in self.FORBIDDEN_PATTERNS
            ]

    def validate(self, content: str, path: str | Path | None = None) -> ValidationResult:
        """Validate file content for contamination patterns.

        Args:
            content: The file content to validate
            path: Optional file path for logging context

        Returns:
            ValidationResult indicating if content is valid
        """
        if not content or not content.strip():
            # Empty content might be intentional
            return ValidationResult.ok()

        # Check each forbidden pattern
        for pattern, description in ContentSanityValidator._compiled_patterns or []:
            if pattern.search(content):
                message = (
                    f"Content appears to be tool output, not file content "
                    f"({description})"
                )
                if path:
                    message = f"{path}: {message}"

                logger.warning(
                    "Content validation failed: %s (pattern: %s)",
                    message,
                    pattern.pattern,
                )

                return ValidationResult.fail(
                    message=message,
                    pattern=pattern.pattern,
                )

        # Check for very short content that's likely a status message
        lines = content.strip().split("\n")
        if len(lines) == 1 and len(content) < 100:
            # Single short line - might be a status message
            if content.startswith(("✓", "✗", "→", "•", "▸")):
                return ValidationResult.fail(
                    message=f"Content appears to be a status indicator: {content[:50]}",
                    pattern="single_line_status",
                )

        return ValidationResult.ok()

    def validate_files(
        self,
        files: dict[str, str],
    ) -> dict[str, ValidationResult]:
        """Validate multiple files at once.

        Args:
            files: Mapping of path -> content

        Returns:
            Mapping of path -> ValidationResult
        """
        return {
            path: self.validate(content, path)
            for path, content in files.items()
        }

    def validate_all_pass(
        self,
        files: dict[str, str],
    ) -> tuple[bool, list[str]]:
        """Check if all files pass validation.

        Args:
            files: Mapping of path -> content

        Returns:
            Tuple of (all_pass, list of failed paths)
        """
        results = self.validate_files(files)
        failed = [path for path, result in results.items() if not result.valid]
        return len(failed) == 0, failed


# Singleton instance for convenience
_default_validator: ContentSanityValidator | None = None


def get_content_validator() -> ContentSanityValidator:
    """Get the default content validator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = ContentSanityValidator()
    return _default_validator


def validate_content(content: str, path: str | None = None) -> ValidationResult:
    """Convenience function to validate content with default validator.

    Args:
        content: The file content to validate
        path: Optional file path for logging context

    Returns:
        ValidationResult indicating if content is valid
    """
    return get_content_validator().validate(content, path)
