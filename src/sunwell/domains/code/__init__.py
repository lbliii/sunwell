"""Code domain for software development (RFC-DOMAINS).

The code domain handles:
- File operations (read, write, edit)
- Git operations
- Static analysis (lint, type, test)
- Code pattern extraction

This domain uses the existing tools in sunwell.tools.implementations
and provides code-specific validators.
"""

from sunwell.domains.code.validators import (
    LintValidator,
    SyntaxValidator,
    TestValidator,
    TypeValidator,
)
from sunwell.domains.protocol import BaseDomain, DomainType

# Keywords for code domain detection
_CODE_KEYWORDS: frozenset[str] = frozenset({
    # Actions
    "code",
    "implement",
    "build",
    "create",
    "write",
    "fix",
    "debug",
    "refactor",
    "test",
    # Objects
    "function",
    "class",
    "method",
    "api",
    "endpoint",
    "module",
    "package",
    "library",
    # Problems
    "bug",
    "error",
    "exception",
    "crash",
    # Languages
    "python",
    "javascript",
    "typescript",
    "rust",
    "go",
})


class CodeDomain(BaseDomain):
    """Code/software development domain.

    Provides:
    - Tools: File ops, git, run_command (from sunwell.tools.implementations)
    - Validators: Lint, type, test, syntax
    - Patterns: Class definitions, imports, API routes, etc.
    """

    def __init__(self) -> None:
        super().__init__()
        self._domain_type = DomainType.CODE
        self._tools_package = "sunwell.tools.implementations"
        self._validators = [
            SyntaxValidator(),
            LintValidator(),
            TypeValidator(),
            TestValidator(),
        ]
        self._default_validator_names = frozenset({"lint", "type"})
        self._keywords = _CODE_KEYWORDS
        self._high_conf_keywords = frozenset({"implement", "refactor", "debug", "api", "endpoint"})
        self._medium_conf_keywords = frozenset({"code", "function", "class", "test", "bug", "fix"})

    # detect_confidence inherited from BaseDomain with tiered keywords

    def extract_learnings(self, artifact: str, file_path: str | None = None) -> list:
        """Extract code patterns from artifact.

        Delegates to CodePatternExtractor for actual extraction.
        """
        from sunwell.domains.code.patterns import CodePatternExtractor

        extractor = CodePatternExtractor()
        return extractor.extract(artifact, file_path)


__all__ = [
    "CodeDomain",
    "LintValidator",
    "SyntaxValidator",
    "TestValidator",
    "TypeValidator",
]
