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
    CodeValidator,
    LintValidator,
    SyntaxValidator,
    TestValidator,
    TypeValidator,
)
from sunwell.domains.protocol import BaseDomain, DomainType, DomainValidator

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

    @property
    def domain_type(self) -> DomainType:
        return self._domain_type

    @property
    def tools_package(self) -> str:
        return self._tools_package

    @property
    def validators(self) -> list[DomainValidator]:
        return self._validators

    @property
    def default_validator_names(self) -> frozenset[str]:
        return self._default_validator_names

    def detect_confidence(self, goal: str) -> float:
        """Detect if goal is code-related.

        Uses keyword matching with higher weights for specific terms.
        """
        goal_lower = goal.lower()
        score = 0.0

        # High-confidence indicators (0.4 each)
        high_conf = {"implement", "refactor", "debug", "api", "endpoint"}
        for kw in high_conf:
            if kw in goal_lower:
                score += 0.4

        # Medium-confidence indicators (0.25 each)
        medium_conf = {"code", "function", "class", "test", "bug", "fix"}
        for kw in medium_conf:
            if kw in goal_lower:
                score += 0.25

        # Low-confidence indicators (0.15 each)
        for kw in self._keywords - high_conf - medium_conf:
            if kw in goal_lower:
                score += 0.15

        return min(score, 1.0)

    def extract_learnings(self, artifact: str, file_path: str | None = None) -> list:
        """Extract code patterns from artifact.

        Delegates to CodePatternExtractor for actual extraction.
        """
        from sunwell.domains.code.patterns import CodePatternExtractor

        extractor = CodePatternExtractor()
        return extractor.extract(artifact, file_path)


__all__ = [
    "CodeDomain",
    "CodeValidator",
    "LintValidator",
    "SyntaxValidator",
    "TestValidator",
    "TypeValidator",
]
