"""Multi-Perspective Analyzer for Deep Verification (RFC-047).

Analyze code correctness from multiple perspectives.
"""


import ast
import asyncio
import json
import re
from typing import TYPE_CHECKING

# Pre-compiled regex for JSON object extraction
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")

from sunwell.models import GenerateOptions
from sunwell.quality.verification.types import (
    BehavioralExecutionResult,
    PerspectiveResult,
    Specification,
)

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.artifacts import ArtifactSpec


class MultiPerspectiveAnalyzer:
    """Analyze code correctness from multiple perspectives.

    Uses different "personas" that focus on different error classes:
    1. Correctness Reviewer: Does output match spec?
    2. Edge Case Hunter: What inputs would break this?
    3. Integration Analyst: Does it work with dependencies?
    4. Regression Detective: Did this change break anything?
    """

    def __init__(self, model: ModelProtocol):
        self.model = model

    async def analyze(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        execution_results: BehavioralExecutionResult | None,
        existing_code: str | None = None,
    ) -> list[PerspectiveResult]:
        """Analyze from all perspectives in parallel.

        Args:
            artifact: The artifact specification
            content: The generated code
            spec: Extracted specification
            execution_results: Results from test execution
            existing_code: Previous version (for regression detection)

        Returns:
            List of results from each perspective
        """
        # Build task list dynamically based on context
        tasks = [
            self._correctness_review(artifact, content, spec, execution_results),
            self._edge_case_hunt(artifact, content, spec, execution_results),
            self._integration_analysis(artifact, content, spec),
        ]

        # Only add regression detection if we have existing code
        if existing_code:
            tasks.append(self._regression_detection(artifact, content, existing_code))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and None results
        valid_results: list[PerspectiveResult] = []
        for r in results:
            if isinstance(r, PerspectiveResult):
                valid_results.append(r)
            elif isinstance(r, Exception):
                # Log but don't fail - other perspectives may succeed
                pass

        return valid_results

    async def _correctness_review(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        execution_results: BehavioralExecutionResult | None,
    ) -> PerspectiveResult:
        """Review whether code correctly implements the spec."""
        test_results_text = self._format_test_results(execution_results)

        prompt = f"""You are a CORRECTNESS REVIEWER. Your job is to verify that code
correctly implements its specification.

ARTIFACT: {artifact.id}
SPECIFICATION:
{spec.description}

Expected outputs: {self._format_outputs(spec.outputs)}
Postconditions: {spec.postconditions}

CODE:
```python
{content[:2000]}
```

TEST RESULTS:
{test_results_text}

---

ANALYZE:
1. Does the code correctly implement the specification?
2. Do the test results confirm correct behavior?
3. Are there any logic errors or incorrect algorithms?

Be strict. If anything is wrong, say so.

Output JSON:
{{
  "verdict": "correct" | "suspicious" | "incorrect",
  "confidence": 0.0-1.0,
  "issues": ["Issue 1", "Issue 2"],
  "recommendations": ["Recommendation 1"]
}}"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=1000),
        )

        return self._parse_perspective_result(result.text, "correctness_reviewer")

    async def _edge_case_hunt(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        execution_results: BehavioralExecutionResult | None,
    ) -> PerspectiveResult:
        """Hunt for unhandled edge cases."""
        test_results_text = self._format_test_results(execution_results)

        prompt = f"""You are an EDGE CASE HUNTER. Your job is to find inputs that
would break this code.

CODE:
```python
{content[:2000]}
```

KNOWN EDGE CASES (already tested):
{spec.edge_cases}

TEST RESULTS:
{test_results_text}

---

HUNT for edge cases that might NOT be handled:
1. Empty/null inputs
2. Boundary values (0, -1, max values)
3. Unicode, special characters
4. Very large inputs
5. Concurrent access
6. Invalid types
7. Resource exhaustion

Output JSON:
{{
  "verdict": "correct" | "suspicious" | "incorrect",
  "confidence": 0.0-1.0,
  "issues": ["Missing handling for X", "Would crash on Y"],
  "recommendations": ["Add check for Z"]
}}"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=1000),
        )

        return self._parse_perspective_result(result.text, "edge_case_hunter")

    async def _integration_analysis(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
    ) -> PerspectiveResult:
        """Analyze integration with dependencies."""
        imports = self._extract_imports(content)

        prompt = f"""You are an INTEGRATION ANALYST. Your job is to verify that
this code will work correctly with its dependencies.

CODE:
```python
{content[:2000]}
```

DEPENDENCIES (imports used):
{imports}

---

ANALYZE:
1. Are dependencies used correctly?
2. Are API calls correct (right method names, parameters)?
3. Are return values handled correctly?
4. Are error cases from dependencies handled?

Output JSON:
{{
  "verdict": "correct" | "suspicious" | "incorrect",
  "confidence": 0.0-1.0,
  "issues": ["Wrong API usage for X", "Missing error handling for Y"],
  "recommendations": ["Check documentation for Z"]
}}"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=1000),
        )

        return self._parse_perspective_result(result.text, "integration_analyst")

    async def _regression_detection(
        self,
        artifact: ArtifactSpec,
        new_content: str,
        existing_content: str,
    ) -> PerspectiveResult:
        """Detect potential regressions from changes."""
        prompt = f"""You are a REGRESSION DETECTIVE. Your job is to verify that
changes don't break existing behavior.

EXISTING CODE:
```python
{existing_content[:1500]}
```

NEW CODE:
```python
{new_content[:1500]}
```

---

DETECT regressions:
1. Did any existing behavior change unintentionally?
2. Are there removed capabilities?
3. Did return types or signatures change?
4. Could existing callers break?

Output JSON:
{{
  "verdict": "correct" | "suspicious" | "incorrect",
  "confidence": 0.0-1.0,
  "issues": ["Removed feature X", "Changed signature of Y"],
  "recommendations": ["Keep backwards compatibility for Z"]
}}"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=1000),
        )

        return self._parse_perspective_result(result.text, "regression_detective")

    def _format_test_results(
        self, execution_results: BehavioralExecutionResult | None
    ) -> str:
        """Format test execution results for prompt."""
        if not execution_results:
            return "No tests were executed."

        parts = [
            f"Total: {execution_results.total_tests}",
            f"Passed: {execution_results.passed}",
            f"Failed: {execution_results.failed}",
            f"Errors: {execution_results.errors}",
            f"Pass rate: {execution_results.pass_rate:.1%}",
        ]

        # Include specific failures
        failures = [
            r for r in execution_results.test_results if not r.passed
        ]
        if failures:
            parts.append("\nFailures:")
            for f in failures[:3]:  # Limit to 3
                parts.append(f"  - {f.test_id}: {f.error_message or 'Failed'}")

        return "\n".join(parts)

    def _format_outputs(self, outputs: tuple) -> str:
        """Format output specs for prompt."""
        if not outputs:
            return "Not specified"
        parts = []
        for out in outputs:
            constraints = ", ".join(out.constraints) if out.constraints else ""
            parts.append(f"{out.type_hint} ({constraints})")
        return "; ".join(parts)

    def _extract_imports(self, content: str) -> str:
        """Extract imports from code."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return "Could not parse imports"

        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        return "\n".join(imports) if imports else "No imports found"

    def _parse_perspective_result(
        self,
        response: str,
        perspective: str,
    ) -> PerspectiveResult:
        """Parse LLM response into PerspectiveResult."""
        # Extract JSON from response
        json_match = _JSON_OBJECT_RE.search(response)

        # Default values if parsing fails
        default = PerspectiveResult(
            perspective=perspective,
            verdict="suspicious",
            confidence=0.5,
            issues=("Could not parse analysis result",),
            recommendations=(),
        )

        if not json_match:
            return default

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return default

        verdict = data.get("verdict", "suspicious")
        if verdict not in ("correct", "suspicious", "incorrect"):
            verdict = "suspicious"

        confidence = data.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        issues = data.get("issues", [])
        if not isinstance(issues, list):
            issues = []
        issues = tuple(str(i) for i in issues)

        recommendations = data.get("recommendations", [])
        if not isinstance(recommendations, list):
            recommendations = []
        recommendations = tuple(str(r) for r in recommendations)

        return PerspectiveResult(
            perspective=perspective,
            verdict=verdict,  # type: ignore
            confidence=confidence,
            issues=issues,
            recommendations=recommendations,
        )
