"""AST-based feature detection for demo scoring (RFC-095).

Deterministic scoring via feature detection. Uses AST parsing where possible
for robustness, with regex fallback for malformed code.
"""

import ast
import re
from dataclasses import dataclass

# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_MARKDOWN_CODE_BLOCK_RE = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)
_TYPE_HINTS_FALLBACK_RE = re.compile(r"(def \w+\([^)]*:\s*\w+|:\s*\w+\s*=)")
_RECURSION_DETECTION_RE = re.compile(r"def (\w+)\(.*\).*\1\(", re.DOTALL)


@dataclass(frozen=True, slots=True)
class DemoScore:
    """Scoring result for demo output.

    Attributes:
        score: Numeric score from 0-10.
        features: Dict mapping feature names to presence (True/False).
        issues: List of missing or problematic features.
        lines: Number of lines in the code.
    """

    score: float
    features: dict[str, bool]
    issues: tuple[str, ...]
    lines: int


class DemoScorer:
    """Scores demo outputs via deterministic feature detection.

    Uses AST parsing for reliable detection, with regex fallback for
    edge cases where AST parsing fails (e.g., incomplete code).

    This is intentionally simpler than benchmark/evaluator.py which uses
    LLM-as-judge. For demo purposes, deterministic scoring is more
    transparent and reproducible.
    """

    def score(self, code: str, expected_features: frozenset[str]) -> DemoScore:
        """Score code against expected features.

        Args:
            code: Python code to score.
            expected_features: Set of feature names expected in good output.

        Returns:
            DemoScore with score, features present, and issues found.
        """
        # Extract code from markdown if present
        code = self._extract_code(code)

        # Detect all features
        feature_detectors: dict[str, callable] = {
            "type_hints": self._has_type_hints,
            "docstring": self._has_docstring,
            "error_handling": self._has_error_handling,
            "zero_division_handling": self._has_zero_check,
            "type_validation": self._has_isinstance_check,
            "empty_list_handling": self._has_empty_check,
            "negative_input_handling": self._has_negative_check,
            "memoization_or_iteration": self._has_optimization,
            "regex_pattern": self._has_regex,
            "edge_case_handling": self._has_edge_case_handling,
        }

        features: dict[str, bool] = {}
        for feature in expected_features:
            detector = feature_detectors.get(feature)
            if detector:
                features[feature] = detector(code)
            else:
                # Unknown feature - check for general pattern
                features[feature] = False

        # Calculate score based on present features
        present_count = sum(1 for f in expected_features if features.get(f, False))
        total_count = len(expected_features)
        score = (present_count / total_count) * 10 if total_count > 0 else 0.0

        # Bonus for having more lines (indicates effort) - cap at +1.5
        lines = len(code.strip().split("\n"))
        if lines > 5:
            score = min(10.0, score + min((lines - 5) * 0.1, 1.5))

        # Collect issues
        issues = tuple(f for f in expected_features if not features.get(f, False))

        return DemoScore(
            score=round(score, 1),
            features=features,
            issues=issues,
            lines=lines,
        )

    def _extract_code(self, text: str) -> str:
        """Extract code from markdown code blocks if present."""
        match = _MARKDOWN_CODE_BLOCK_RE.search(text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _has_type_hints(self, code: str) -> bool:
        """Check for type annotations using AST.

        Detects type hints on:
        - Function parameters and return types (def foo(x: int) -> str)
        - Async function parameters and return types
        - Annotated assignments (x: int = 5)
        - Dataclass fields (@dataclass class Foo: x: int)
        """
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Check sync and async function definitions
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    node.returns or any(arg.annotation for arg in node.args.args)
                ):
                    return True
                # Check annotated assignments (dataclass fields, module-level typed vars)
                if isinstance(node, ast.AnnAssign) and node.annotation:
                    return True
            return False
        except SyntaxError:
            # Fallback to regex for malformed code
            return bool(_TYPE_HINTS_FALLBACK_RE.search(code))

    def _has_docstring(self, code: str) -> bool:
        """Check for docstring using AST.

        Detects docstrings on:
        - Regular functions (def foo)
        - Async functions (async def foo)
        - Classes (class Foo)
        - Module-level docstrings
        """
        try:
            tree = ast.parse(code)
            # Check module-level docstring
            if ast.get_docstring(tree):
                return True
            for node in ast.walk(tree):
                # Check sync functions, async functions, and classes
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if ast.get_docstring(node) is not None:
                        return True
            return False
        except SyntaxError:
            return '"""' in code or "'''" in code

    def _has_error_handling(self, code: str) -> bool:
        """Check for any error handling (try/except or raise)."""
        try:
            tree = ast.parse(code)
            return any(isinstance(node, (ast.Try, ast.Raise)) for node in ast.walk(tree))
        except SyntaxError:
            return "try:" in code or "raise " in code

    def _has_zero_check(self, code: str) -> bool:
        """Check for division by zero handling."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Look for comparisons with 0
                if isinstance(node, ast.Compare):
                    for comparator in node.comparators:
                        if isinstance(comparator, ast.Constant) and comparator.value == 0:
                            return True
                # Also check for ZeroDivisionError
                if (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and isinstance(node.exc.func, ast.Name)
                    and node.exc.func.id == "ZeroDivisionError"
                ):
                    return True
            return False
        except SyntaxError:
            return "== 0" in code or "ZeroDivisionError" in code

    def _has_isinstance_check(self, code: str) -> bool:
        """Check for isinstance() type validation."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "isinstance"
                ):
                    return True
            return False
        except SyntaxError:
            return "isinstance(" in code

    def _has_empty_check(self, code: str) -> bool:
        """Check for empty list/sequence handling."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Check for 'if not x' or 'if len(x) == 0'
                if isinstance(node, ast.If):
                    test = node.test
                    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                        return True
                    if isinstance(test, ast.Compare) and any(
                        isinstance(c, ast.Constant) and c.value == 0
                        for c in test.comparators
                    ):
                        return True
            return False
        except SyntaxError:
            return "if not " in code or "len(" in code

    def _has_negative_check(self, code: str) -> bool:
        """Check for negative input handling."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    # Check for < 0 comparison
                    for i, op in enumerate(node.ops):
                        if (
                            isinstance(op, ast.Lt)
                            and i < len(node.comparators)
                            and isinstance(node.comparators[i], ast.Constant)
                            and node.comparators[i].value == 0
                        ):
                            return True
            return False
        except SyntaxError:
            return "< 0" in code or "<= 0" in code

    def _has_optimization(self, code: str) -> bool:
        """Check for memoization or iterative approach (vs naive recursion)."""
        # Check for cache decorator or iterative loop
        has_cache = "@cache" in code or "@lru_cache" in code or "functools" in code
        has_loop = "for " in code or "while " in code

        # If it has recursion, check if it's also using memoization
        has_recursion = _RECURSION_DETECTION_RE.search(code)

        if has_recursion:
            return has_cache
        return has_loop or has_cache

    def _has_regex(self, code: str) -> bool:
        """Check for regex pattern usage."""
        return "re." in code or "import re" in code or "r'" in code or 'r"' in code

    def _has_edge_case_handling(self, code: str) -> bool:
        """Check for general edge case handling (multiple conditions)."""
        try:
            tree = ast.parse(code)
            if_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.If))
            return if_count >= 2
        except SyntaxError:
            return code.count("if ") >= 2


# Feature name to human-readable display
FEATURE_DISPLAY_NAMES: dict[str, str] = {
    "type_hints": "Type hints",
    "docstring": "Docstring",
    "error_handling": "Error handling",
    "zero_division_handling": "Zero division check",
    "type_validation": "Type validation",
    "empty_list_handling": "Empty list check",
    "negative_input_handling": "Negative input check",
    "memoization_or_iteration": "Optimization",
    "regex_pattern": "Regex pattern",
    "edge_case_handling": "Edge cases",
}
