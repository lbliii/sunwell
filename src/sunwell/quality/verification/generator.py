"""Test Generator for Deep Verification (RFC-047).

Generate behavioral tests from specifications.
"""


import json
import re
import uuid
from typing import TYPE_CHECKING

# Pre-compiled regex for JSON array extraction
_JSON_ARRAY_RE = re.compile(r"\[[\s\S]*\]")

from sunwell.models.protocol import GenerateOptions
from sunwell.quality.verification.types import GeneratedTest, Specification

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.planning.naaru.artifacts import ArtifactSpec


class TestGenerator:
    """Generate behavioral tests from specifications.

    Generates multiple test categories:
    1. Happy path: Normal inputs → expected outputs
    2. Edge cases: Empty, null, boundary, large inputs
    3. Error cases: Invalid inputs → expected errors
    4. Property tests: Invariants that must hold
    """

    def __init__(self, model: ModelProtocol):
        self.model = model

    async def generate(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        max_tests: int = 10,
    ) -> list[GeneratedTest]:
        """Generate tests covering the specification.

        Args:
            artifact: The artifact specification
            content: The generated code to test
            spec: Extracted specification
            max_tests: Maximum number of tests to generate

        Returns:
            List of generated tests, prioritized
        """
        tests: list[GeneratedTest] = []

        # Calculate test budget per category
        budget = self._allocate_budget(spec, max_tests)

        # 1. Happy path tests (always generate)
        if budget["happy_path"] > 0:
            happy_tests = await self._generate_happy_path(
                artifact, content, spec, budget["happy_path"]
            )
            tests.extend(happy_tests)

        # 2. Edge case tests (if spec has edge_cases)
        if spec.edge_cases and budget["edge_case"] > 0:
            edge_tests = await self._generate_edge_cases(
                artifact, content, spec, budget["edge_case"]
            )
            tests.extend(edge_tests)

        # 3. Property tests (if spec has invariants)
        if spec.invariants and budget["property"] > 0:
            prop_tests = await self._generate_property_tests(
                artifact, content, spec, budget["property"]
            )
            tests.extend(prop_tests)

        # 4. Error case tests (if spec has preconditions)
        if spec.preconditions and budget["error_case"] > 0:
            error_tests = await self._generate_error_cases(
                artifact, content, spec, budget["error_case"]
            )
            tests.extend(error_tests)

        # Prioritize and limit
        tests = sorted(tests, key=lambda t: t.priority, reverse=True)
        return tests[:max_tests]

    def _allocate_budget(
        self, spec: Specification, max_tests: int
    ) -> dict[str, int]:
        """Allocate test budget across categories."""
        budget: dict[str, int] = {
            "happy_path": 0,
            "edge_case": 0,
            "property": 0,
            "error_case": 0,
        }

        if max_tests <= 0:
            return budget

        # Always allocate at least 2 for happy path
        budget["happy_path"] = min(2, max_tests)
        remaining = max_tests - budget["happy_path"]

        # Distribute remaining based on spec content
        has_edge_cases = len(spec.edge_cases) > 0
        has_invariants = len(spec.invariants) > 0
        has_preconditions = len(spec.preconditions) > 0

        categories_with_content = sum(
            [has_edge_cases, has_invariants, has_preconditions]
        )

        if categories_with_content > 0 and remaining > 0:
            per_category = remaining // categories_with_content
            extra = remaining % categories_with_content

            if has_edge_cases:
                budget["edge_case"] = per_category + (1 if extra > 0 else 0)
                extra = max(0, extra - 1)
            if has_invariants:
                budget["property"] = per_category + (1 if extra > 0 else 0)
                extra = max(0, extra - 1)
            if has_preconditions:
                budget["error_case"] = per_category + (1 if extra > 0 else 0)

        return budget

    async def _generate_happy_path(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        count: int,
    ) -> list[GeneratedTest]:
        """Generate tests for normal expected usage."""
        prompt = f"""Generate {count} pytest tests for HAPPY PATH scenarios.

ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}

CODE:
```python
{content[:1500]}
```

SPECIFICATION:
- Expected inputs: {self._format_inputs(spec.inputs)}
- Expected outputs: {self._format_outputs(spec.outputs)}
- Postconditions: {spec.postconditions}

Generate tests that verify the code works correctly for typical inputs.
Each test should:
1. Set up realistic input data
2. Call the function/method
3. Assert the output matches expectations

IMPORTANT:
- Use pytest style (def test_xxx)
- Include necessary imports at the top
- Make tests self-contained and runnable
- Use descriptive test names

Output as JSON array:
[
  {{
    "name": "test_description",
    "description": "What this tests",
    "code": "def test_...():\\n    ...",
    "expected_outcome": "pass"
  }}
]"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=2000),
        )

        return self._parse_tests(result.text, category="happy_path", priority=1.0)

    async def _generate_edge_cases(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        count: int,
    ) -> list[GeneratedTest]:
        """Generate tests for edge cases and boundary conditions."""
        edge_case_list = "\n".join(f"- {case}" for case in spec.edge_cases)

        prompt = f"""Generate {count} pytest tests for EDGE CASES.

CODE:
```python
{content[:1500]}
```

KNOWN EDGE CASES TO TEST:
{edge_case_list}

ADDITIONAL EDGE CASES TO CONSIDER:
- Empty inputs (empty string, empty list, None)
- Boundary values (0, -1, max int, min int)
- Unicode and special characters
- Very large inputs
- Concurrent access (if applicable)

Generate tests that verify edge cases are handled correctly.
Tests should either:
- Pass (if edge case is handled correctly)
- Raise expected exception (if edge case should fail gracefully)

Output as JSON array:
[
  {{
    "name": "test_edge_case_description",
    "description": "What edge case this tests",
    "code": "def test_...():\\n    ...",
    "expected_outcome": "pass"
  }}
]"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.4, max_tokens=2000),
        )

        return self._parse_tests(result.text, category="edge_case", priority=0.9)

    async def _generate_property_tests(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        count: int,
    ) -> list[GeneratedTest]:
        """Generate property-based tests for invariants."""
        invariant_list = "\n".join(f"- {inv}" for inv in spec.invariants)

        prompt = f"""Generate {count} PROPERTY-BASED tests using hypothesis.

CODE:
```python
{content[:1500]}
```

INVARIANTS THAT MUST HOLD:
{invariant_list}

Generate tests that verify these invariants hold for many random inputs.
Use hypothesis @given decorators with appropriate strategies.

IMPORTANT:
- Import hypothesis: from hypothesis import given, strategies as st
- Use appropriate strategies for the input types
- Make assertions that check the invariant

Output as JSON array:
[
  {{
    "name": "test_property_description",
    "description": "What invariant this tests",
    "code": "from hypothesis import given, strategies as st\\n\\n@given(...)\\ndef test_...():\\n    ...",
    "expected_outcome": "pass"
  }}
]"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=2000),
        )

        return self._parse_tests(result.text, category="property", priority=0.8)

    async def _generate_error_cases(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        count: int,
    ) -> list[GeneratedTest]:
        """Generate tests for expected error conditions."""
        precondition_list = "\n".join(f"- {pre}" for pre in spec.preconditions)

        prompt = f"""Generate {count} pytest tests for ERROR CASES.

CODE:
```python
{content[:1500]}
```

PRECONDITIONS (violating these should raise errors):
{precondition_list}

Generate tests that:
1. Violate preconditions intentionally
2. Assert that appropriate exceptions are raised
3. Verify error messages are helpful

Use pytest.raises() for exception testing.

Output as JSON array:
[
  {{
    "name": "test_error_description",
    "description": "What error condition this tests",
    "code": "def test_...():\\n    with pytest.raises(...):\\n        ...",
    "expected_outcome": "error"
  }}
]"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=2000),
        )

        return self._parse_tests(result.text, category="error_case", priority=0.7)

    def _format_inputs(self, inputs: tuple) -> str:
        """Format input specs for prompt."""
        if not inputs:
            return "Not specified"
        parts = []
        for inp in inputs:
            constraints = ", ".join(inp.constraints) if inp.constraints else ""
            parts.append(f"{inp.name}: {inp.type_hint} ({constraints})")
        return "; ".join(parts)

    def _format_outputs(self, outputs: tuple) -> str:
        """Format output specs for prompt."""
        if not outputs:
            return "Not specified"
        parts = []
        for out in outputs:
            constraints = ", ".join(out.constraints) if out.constraints else ""
            parts.append(f"{out.type_hint} ({constraints})")
        return "; ".join(parts)

    def _parse_tests(
        self,
        response: str,
        category: str,
        priority: float,
    ) -> list[GeneratedTest]:
        """Parse LLM response into GeneratedTest objects."""
        tests: list[GeneratedTest] = []

        # Extract JSON array from response
        json_match = _JSON_ARRAY_RE.search(response)
        if not json_match:
            return tests

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return tests

        for item in data:
            if not isinstance(item, dict):
                continue

            name = item.get("name", f"test_{uuid.uuid4().hex[:8]}")
            description = item.get("description", "")
            code = item.get("code", "")
            expected = item.get("expected_outcome", "pass")

            if not code:
                continue

            # Validate code has a test function
            if "def test_" not in code and "@given" not in code:
                continue

            tests.append(
                GeneratedTest(
                    id=f"{category}_{name}",
                    name=name,
                    description=description,
                    category=category,  # type: ignore
                    code=code,
                    expected_outcome=expected if expected in ("pass", "fail", "error") else "pass",  # type: ignore
                    spec_coverage=(),
                    priority=priority,
                )
            )

        return tests
