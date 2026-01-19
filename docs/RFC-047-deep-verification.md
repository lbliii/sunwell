# RFC-047: Deep Verification — Semantic Correctness Beyond Syntax

**Status**: Draft  
**Created**: 2026-01-19  
**Authors**: Sunwell Team  
**Depends on**: RFC-042 (Adaptive Agent, Implemented), RFC-036 (Artifact-First Planning, Implemented)  
**Enhanced by** (optional): RFC-045 (Project Intelligence), RFC-046 (Autonomous Backlog, Implemented)

---

## Summary

Deep Verification ensures generated code is semantically correct, not just syntactically valid. Current validation stops at "does it parse, type-check, and run?" but misses "does it do what it's supposed to do?"

**Core insight**: Syntax validation is necessary but not sufficient. An AI can generate code that passes all linters and type checkers while being completely wrong. Deep Verification adds semantic checks that catch these failures.

**One-liner**: Trust the output — verify code does the right thing, not just that it runs.

---

## Motivation

### The Silent Failure Problem

Current Sunwell validation (RFC-042) catches:

```
✅ Syntax errors (py_compile)
✅ Lint violations (ruff)
✅ Type errors (ty/mypy)
✅ Import failures
✅ Runtime crashes
```

But misses:

```
❌ Wrong algorithm (code runs but produces wrong results)
❌ Missing edge cases (fails on empty input, negative numbers)
❌ Incorrect integration (calls wrong API, misses auth)
❌ Logic errors (off-by-one, wrong comparison)
❌ Contract violations (returns wrong type of result)
❌ Regressions (change breaks existing behavior)
```

### A Real Example

```python
# Goal: "Return users sorted by registration date, newest first"

# Generated code (syntactically perfect, semantically WRONG):
def get_recent_users(db) -> list[User]:
    return db.query(User).order_by(User.created_at).all()  # ASC not DESC!
```

This code:
- ✅ Parses correctly
- ✅ Type checks
- ✅ Imports work
- ✅ Runs without error
- ❌ **Returns users in WRONG order** (oldest first)

Without semantic verification, this bug silently ships.

### Why This Matters

| Without Deep Verification | With Deep Verification |
|---------------------------|------------------------|
| Code passes all gates | Code passes all gates |
| Code ships to user | Semantic check catches logic error |
| Bug discovered in production | Fixed before shipping |
| Trust erodes | Trust builds |

**For autonomous mode (RFC-046) to work, we need trust.** If we can't verify correctness, we can't auto-approve.

---

## Goals and Non-Goals

### Goals

1. **Catch semantic errors** — Detect code that runs but does the wrong thing
2. **Generate behavioral tests** — Auto-create tests that verify expected behavior
3. **Multi-perspective validation** — Multiple viewpoints catch different error classes
4. **Property verification** — Ensure code maintains required invariants
5. **Regression detection** — Catch when changes break existing behavior
6. **Confidence scoring** — Quantify how sure we are the code is correct
7. **Integration with existing gates** — Extend RFC-042 validation cascade

### Non-Goals

1. **Formal verification** — Not attempting mathematical proofs (out of scope)
2. **Full test coverage** — Generate key tests, not exhaustive suites
3. **Security auditing** — Not a replacement for security reviews (future RFC)
4. **Performance testing** — Not validating performance characteristics (future work)
5. **Human replacement** — Augment review, not replace it for complex changes

---

## Design Overview

### The Verification Pyramid

```
                    ┌─────────────────────┐
                    │   SEMANTIC          │  ← RFC-047 (NEW)
                    │   Does it do the    │
                    │   right thing?      │
                    ├─────────────────────┤
                    │   RUNTIME           │  ← RFC-042 (existing)
                    │   Does it run?      │
                    ├─────────────────────┤
                    │   STATIC            │  ← RFC-042 (existing)
                    │   Does it parse?    │
                    └─────────────────────┘
```

Deep Verification adds the semantic layer on top of existing gates.

### Verification Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEEP VERIFICATION FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  INPUT: Generated artifact + contract/spec                        │      │
│  └──────────────────────────────────┬───────────────────────────────┘      │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  1. SPECIFICATION EXTRACTION                                      │      │
│  │     ├─ Parse contract from artifact spec                         │      │
│  │     ├─ Extract implicit specs from docstrings/comments           │      │
│  │     ├─ Mine specs from existing tests (if any)                   │      │
│  │     └─ Infer specs from function signatures                      │      │
│  └──────────────────────────────────┬───────────────────────────────┘      │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  2. TEST GENERATION                                               │      │
│  │     ├─ Happy path tests (normal inputs → expected outputs)       │      │
│  │     ├─ Edge case tests (empty, null, boundary values)            │      │
│  │     ├─ Property tests (invariants that must hold)                │      │
│  │     └─ Integration tests (works with dependencies)               │      │
│  └──────────────────────────────────┬───────────────────────────────┘      │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  3. BEHAVIORAL EXECUTION                                          │      │
│  │     ├─ Run generated tests in isolated environment               │      │
│  │     ├─ Capture actual vs expected outputs                        │      │
│  │     └─ Record execution traces                                   │      │
│  └──────────────────────────────────┬───────────────────────────────┘      │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  4. MULTI-PERSPECTIVE ANALYSIS                                    │      │
│  │     ├─ Correctness Reviewer: "Does output match spec?"           │      │
│  │     ├─ Edge Case Hunter: "What inputs would break this?"         │      │
│  │     ├─ Integration Analyst: "Does it work with dependencies?"    │      │
│  │     └─ Regression Detective: "Did this change break anything?"   │      │
│  └──────────────────────────────────┬───────────────────────────────┘      │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  5. TRIANGULATION & SCORING                                       │      │
│  │     ├─ Cross-check verification signals                          │      │
│  │     ├─ Detect contradictions (high uncertainty)                  │      │
│  │     ├─ Calculate confidence score                                │      │
│  │     └─ Generate verification report                              │      │
│  └──────────────────────────────────┬───────────────────────────────┘      │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  OUTPUT: DeepVerificationResult                                   │      │
│  │    ├─ passed: bool                                               │      │
│  │    ├─ confidence: 0.0-1.0                                        │      │
│  │    ├─ issues: list[SemanticIssue]                                │      │
│  │    ├─ generated_tests: list[GeneratedTest]                       │      │
│  │    └─ recommendations: list[str]                                 │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Relationship to Existing Verification

Sunwell has existing verification infrastructure. This RFC introduces a **new layer** without replacing existing systems:

| Type | Module | Purpose | This RFC |
|------|--------|---------|----------|
| `VerificationResult` | `naaru.artifacts` | Verify artifact satisfies its contract | Complements — spec extraction uses this |
| `VerificationResult` | `routing.tiered_attunement` | Self-verification for routing decisions | Unrelated — different domain |
| `GateResult` | `adaptive.gates` | Validation gate pass/fail | Extends — adds SEMANTIC gate |
| **`DeepVerificationResult`** | **`verification.*` (new)** | **Semantic correctness verification** | **This RFC** |

### Why a New Type?

The existing `artifacts.VerificationResult` checks "does artifact satisfy contract?" (structural).
The new `DeepVerificationResult` checks "does code do the right thing?" (behavioral).

```python
# Existing: Contract verification (RFC-036)
# "Does this function have the right signature?"
artifacts.VerificationResult(passed=True, reason="Has required fields")

# NEW: Semantic verification (RFC-047)  
# "Does this function return correct results?"
DeepVerificationResult(passed=False, issues=[wrong_sort_order])
```

These are complementary: contract verification is fast and happens during planning; 
semantic verification is thorough and happens after generation.

---

## Design Options

### Option A: LLM-Only Verification (Fast, Less Reliable)

Use LLM analysis without executing generated tests.

**Pros**:
- Fast (no test execution overhead)
- Works for all languages
- No sandbox required

**Cons**:
- LLM may hallucinate correctness
- No ground truth from actual execution
- Lower confidence in results

### Option B: Test-First Verification (Slower, More Reliable) ← Recommended

Generate tests, execute them, then analyze results.

**Pros**:
- Ground truth from actual execution
- Catches real bugs, not theoretical ones
- Higher confidence scores

**Cons**:
- Requires execution sandbox
- Test generation adds latency
- More complex infrastructure

### Option C: Hybrid (Best of Both)

LLM analysis first (fast-reject obvious errors), then test execution for survivors.

**Pros**:
- Fast path for obvious failures
- High confidence for passes
- Cost-efficient

**Cons**:
- Most complex implementation
- Two-phase latency

**Decision**: Start with **Option B** (Test-First) for highest reliability. Add **Option C** (Hybrid) fast-path in Phase 3.

---

## Components

### 1. Specification Extractor

Extract what the code *should* do from available sources.

```python
@dataclass(frozen=True, slots=True)
class Specification:
    """Extracted specification for verification."""
    
    description: str
    """Natural language description of expected behavior."""
    
    inputs: tuple[InputSpec, ...]
    """Expected input types and constraints."""
    
    outputs: tuple[OutputSpec, ...]
    """Expected output types and constraints."""
    
    preconditions: tuple[str, ...]
    """Conditions that must be true before execution."""
    
    postconditions: tuple[str, ...]
    """Conditions that must be true after execution."""
    
    invariants: tuple[str, ...]
    """Properties that must always hold."""
    
    edge_cases: tuple[str, ...]
    """Known edge cases to test."""
    
    source: Literal["contract", "docstring", "signature", "existing_tests", "inferred"]
    """Where this spec came from."""
    
    confidence: float
    """0-1, how confident we are in this spec."""


@dataclass(frozen=True, slots=True)
class InputSpec:
    """Specification for an input parameter."""
    
    name: str
    type_hint: str
    constraints: tuple[str, ...]  # "positive", "non-empty", "valid email", etc.
    examples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OutputSpec:
    """Specification for an output value."""
    
    type_hint: str
    constraints: tuple[str, ...]
    examples: tuple[str, ...]


class SpecificationExtractor:
    """Extract specifications from multiple sources.
    
    Sources (in priority order):
    1. Explicit contract from ArtifactSpec (RFC-036)
    2. Docstrings and comments in the code
    3. Type signatures and annotations
    4. Existing tests (if modifying existing code)
    5. LLM inference from function name/context
    """
    
    def __init__(self, model: ModelProtocol):
        self.model = model
    
    async def extract(
        self,
        artifact: ArtifactSpec,
        content: str,
        existing_tests: str | None = None,
    ) -> Specification:
        """Extract specification from all available sources."""
        
        # 1. Start with explicit contract
        contract_spec = self._extract_from_contract(artifact.contract)
        
        # 2. Parse docstrings
        docstring_spec = self._extract_from_docstrings(content)
        
        # 3. Analyze type signatures
        signature_spec = self._extract_from_signatures(content)
        
        # 4. Mine existing tests
        test_spec = None
        if existing_tests:
            test_spec = self._extract_from_tests(existing_tests)
        
        # 5. LLM inference for gaps
        inferred_spec = await self._infer_missing(
            artifact, content, 
            [contract_spec, docstring_spec, signature_spec, test_spec]
        )
        
        # 6. Merge specifications
        return self._merge_specs([
            contract_spec,
            docstring_spec, 
            signature_spec,
            test_spec,
            inferred_spec,
        ])
    
    def _extract_from_contract(self, contract: str) -> Specification | None:
        """Parse explicit contract from artifact spec."""
        # Contract format from RFC-036:
        # "Function that takes X and returns Y, handling Z edge cases"
        ...
    
    def _extract_from_docstrings(self, content: str) -> Specification | None:
        """Parse docstrings for specifications."""
        import ast
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None
        
        specs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                docstring = ast.get_docstring(node)
                if docstring:
                    # Parse Google/NumPy style docstrings
                    specs.append(self._parse_docstring(node.name, docstring))
        
        return self._merge_specs(specs) if specs else None
    
    def _extract_from_signatures(self, content: str) -> Specification | None:
        """Extract specs from type annotations."""
        ...
    
    async def _infer_missing(
        self,
        artifact: ArtifactSpec,
        content: str,
        existing_specs: list[Specification | None],
    ) -> Specification:
        """Use LLM to infer missing specification elements."""
        
        prompt = f"""ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}

CODE:
```python
{content[:2000]}
```

EXISTING SPECIFICATIONS:
{self._format_existing_specs(existing_specs)}

---

Based on the code and context, identify any MISSING specifications:

1. What edge cases should be tested?
2. What invariants should hold?
3. What preconditions are assumed?
4. What postconditions are guaranteed?

Focus on things NOT already covered by existing specs.

Output JSON:
{{
  "edge_cases": ["case 1", "case 2"],
  "invariants": ["invariant 1"],
  "preconditions": ["precondition 1"],
  "postconditions": ["postcondition 1"]
}}"""
        
        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=1000),
        )
        
        return self._parse_inferred_spec(result.content)
```

---

### 2. Test Generator

Generate tests that verify the specification.

```python
@dataclass(frozen=True, slots=True)
class GeneratedTest:
    """A generated test case."""
    
    id: str
    name: str
    description: str
    
    category: Literal[
        "happy_path",      # Normal expected usage
        "edge_case",       # Boundary conditions
        "error_case",      # Expected failures
        "property",        # Invariant checking
        "integration",     # Works with dependencies
        "regression",      # Doesn't break existing behavior
    ]
    
    code: str
    """Executable test code."""
    
    expected_outcome: Literal["pass", "fail", "error"]
    """What should happen when this test runs."""
    
    spec_coverage: tuple[str, ...]
    """Which spec elements this test covers."""
    
    priority: float
    """0-1, higher = more important to run."""


class TestGenerator:
    """Generate behavioral tests from specifications.
    
    Generates multiple test categories:
    1. Happy path: Normal inputs → expected outputs
    2. Edge cases: Empty, null, boundary, large inputs
    3. Error cases: Invalid inputs → expected errors
    4. Property tests: Invariants that must hold
    5. Integration tests: Works with real dependencies
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
        """Generate tests covering the specification."""
        
        tests: list[GeneratedTest] = []
        
        # 1. Happy path tests (always generate)
        tests.extend(await self._generate_happy_path(artifact, content, spec))
        
        # 2. Edge case tests (from spec.edge_cases)
        if spec.edge_cases:
            tests.extend(await self._generate_edge_cases(artifact, content, spec))
        
        # 3. Property tests (from spec.invariants)
        if spec.invariants:
            tests.extend(await self._generate_property_tests(artifact, content, spec))
        
        # 4. Error case tests (from spec.preconditions)
        if spec.preconditions:
            tests.extend(await self._generate_error_cases(artifact, content, spec))
        
        # Prioritize and limit
        tests = sorted(tests, key=lambda t: t.priority, reverse=True)
        return tests[:max_tests]
    
    async def _generate_happy_path(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
    ) -> list[GeneratedTest]:
        """Generate tests for normal expected usage."""
        
        prompt = f"""Generate pytest tests for HAPPY PATH scenarios.

ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}

CODE:
```python
{content[:1500]}
```

SPECIFICATION:
- Expected inputs: {spec.inputs}
- Expected outputs: {spec.outputs}
- Postconditions: {spec.postconditions}

Generate 2-3 tests that verify the code works correctly for typical inputs.
Each test should:
1. Set up realistic input data
2. Call the function/method
3. Assert the output matches expectations

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
        
        return self._parse_tests(result.content, category="happy_path")
    
    async def _generate_edge_cases(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
    ) -> list[GeneratedTest]:
        """Generate tests for edge cases and boundary conditions."""
        
        prompt = f"""Generate pytest tests for EDGE CASES.

CODE:
```python
{content[:1500]}
```

KNOWN EDGE CASES TO TEST:
{chr(10).join(f"- {case}" for case in spec.edge_cases)}

ADDITIONAL EDGE CASES TO CONSIDER:
- Empty inputs (empty string, empty list, None)
- Boundary values (0, -1, max int, min int)
- Unicode and special characters
- Very large inputs
- Concurrent access (if applicable)

Generate 2-4 tests that verify edge cases are handled correctly.
Tests should either:
- Pass (if edge case is handled correctly)
- Raise expected exception (if edge case should fail gracefully)

Output as JSON array:
[
  {{
    "name": "test_edge_case_description",
    "description": "What edge case this tests",
    "code": "def test_...():\\n    ...",
    "expected_outcome": "pass" or "error"
  }}
]"""
        
        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.4, max_tokens=2000),
        )
        
        return self._parse_tests(result.content, category="edge_case")
    
    async def _generate_property_tests(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
    ) -> list[GeneratedTest]:
        """Generate property-based tests for invariants."""
        
        prompt = f"""Generate PROPERTY-BASED tests using hypothesis.

CODE:
```python
{content[:1500]}
```

INVARIANTS THAT MUST HOLD:
{chr(10).join(f"- {inv}" for inv in spec.invariants)}

Generate tests that verify these invariants hold for many random inputs.
Use hypothesis @given decorators with appropriate strategies.

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
        
        return self._parse_tests(result.content, category="property")
```

---

### 3. Behavioral Executor

Execute generated tests and capture results.

```python
@dataclass(frozen=True, slots=True)
class TestExecutionResult:
    """Result of executing a single test."""
    
    test_id: str
    passed: bool
    
    actual_output: str | None
    expected_output: str | None
    
    error_message: str | None
    error_traceback: str | None
    
    duration_ms: int
    
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class BehavioralExecutionResult:
    """Result of executing all behavioral tests."""
    
    total_tests: int
    passed: int
    failed: int
    errors: int
    
    test_results: tuple[TestExecutionResult, ...]
    
    duration_ms: int
    
    @property
    def pass_rate(self) -> float:
        """Percentage of tests that passed."""
        if self.total_tests == 0:
            return 1.0
        return self.passed / self.total_tests


class BehavioralExecutor:
    """Execute generated tests in isolated environment.
    
    Runs tests in a subprocess sandbox to:
    - Isolate from main process
    - Capture stdout/stderr
    - Enforce timeouts
    - Prevent side effects
    """
    
    def __init__(
        self,
        cwd: Path,
        timeout_per_test: int = 10,
        total_timeout: int = 60,
    ):
        self.cwd = cwd
        self.timeout_per_test = timeout_per_test
        self.total_timeout = total_timeout
    
    async def execute(
        self,
        artifact_content: str,
        tests: list[GeneratedTest],
    ) -> BehavioralExecutionResult:
        """Execute all generated tests.
        
        Args:
            artifact_content: The generated code to test
            tests: Generated tests to run
        
        Returns:
            Execution results for all tests
        """
        import tempfile
        import time
        
        start = time.monotonic()
        results: list[TestExecutionResult] = []
        
        # Create isolated test environment
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Write artifact
            artifact_file = tmp_path / "artifact.py"
            artifact_file.write_text(artifact_content)
            
            # Write test file
            test_code = self._build_test_file(tests)
            test_file = tmp_path / "test_artifact.py"
            test_file.write_text(test_code)
            
            # Run pytest
            for test in tests:
                result = await self._run_single_test(
                    tmp_path, test.name, test.expected_outcome
                )
                results.append(result)
        
        duration = int((time.monotonic() - start) * 1000)
        
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed and not r.error_message)
        errors = sum(1 for r in results if r.error_message)
        
        return BehavioralExecutionResult(
            total_tests=len(results),
            passed=passed,
            failed=failed,
            errors=errors,
            test_results=tuple(results),
            duration_ms=duration,
        )
    
    def _build_test_file(self, tests: list[GeneratedTest]) -> str:
        """Build a single test file from all generated tests."""
        
        imports = """
import pytest
import sys
from pathlib import Path

# Add artifact to path
sys.path.insert(0, str(Path(__file__).parent))

from artifact import *
"""
        
        test_code = imports + "\n\n"
        for test in tests:
            test_code += f"\n\n{test.code}"
        
        return test_code
    
    async def _run_single_test(
        self,
        cwd: Path,
        test_name: str,
        expected_outcome: str,
    ) -> TestExecutionResult:
        """Run a single test and capture result."""
        import asyncio
        import subprocess
        import sys
        import time
        
        start = time.monotonic()
        
        cmd = [
            sys.executable, "-m", "pytest",
            f"test_artifact.py::{test_name}",
            "-v", "--tb=short", "--no-header",
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_per_test,
            )
            
            duration = int((time.monotonic() - start) * 1000)
            
            # Parse result
            passed = proc.returncode == 0
            
            # Adjust for expected_outcome
            if expected_outcome == "error":
                # Test expects an error - pass if we got one
                passed = proc.returncode != 0
            
            return TestExecutionResult(
                test_id=test_name,
                passed=passed,
                actual_output=stdout.decode(),
                expected_output=None,
                error_message=None if passed else "Test failed",
                error_traceback=stderr.decode() if not passed else None,
                duration_ms=duration,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
            )
            
        except asyncio.TimeoutError:
            return TestExecutionResult(
                test_id=test_name,
                passed=False,
                actual_output=None,
                expected_output=None,
                error_message=f"Test timed out after {self.timeout_per_test}s",
                error_traceback=None,
                duration_ms=self.timeout_per_test * 1000,
                stdout="",
                stderr="",
            )
```

---

### 4. Multi-Perspective Analyzer

Multiple LLM personas analyze correctness from different angles.

```python
@dataclass(frozen=True, slots=True)
class PerspectiveResult:
    """Result from a single verification perspective."""
    
    perspective: str
    verdict: Literal["correct", "suspicious", "incorrect"]
    confidence: float
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticIssue:
    """A semantic issue found during verification."""
    
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal[
        "wrong_output",        # Produces incorrect results
        "missing_edge_case",   # Doesn't handle edge case
        "logic_error",         # Algorithm bug
        "contract_violation",  # Doesn't satisfy spec
        "integration_issue",   # Doesn't work with dependencies
        "regression",          # Breaks existing behavior
    ]
    description: str
    evidence: str
    """Code snippet or test result showing the issue."""
    
    suggested_fix: str | None


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
        execution_results: BehavioralExecutionResult,
        existing_code: str | None = None,
    ) -> list[PerspectiveResult]:
        """Analyze from all perspectives in parallel."""
        
        # Build task list dynamically based on context
        tasks = [
            self._correctness_review(artifact, content, spec, execution_results),
            self._edge_case_hunt(artifact, content, spec, execution_results),
            self._integration_analysis(artifact, content, spec),
        ]
        
        # Only add regression detection if we have existing code
        if existing_code:
            tasks.append(self._regression_detection(artifact, content, existing_code))
        
        results = await asyncio.gather(*tasks)
        
        # Filter out None results (shouldn't happen, but defensive)
        return [r for r in results if r is not None and isinstance(r, PerspectiveResult)]
    
    async def _correctness_review(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        execution_results: BehavioralExecutionResult,
    ) -> PerspectiveResult:
        """Review whether code correctly implements the spec."""
        
        prompt = f"""You are a CORRECTNESS REVIEWER. Your job is to verify that code
correctly implements its specification.

ARTIFACT: {artifact.id}
SPECIFICATION:
{spec.description}

Expected outputs: {spec.outputs}
Postconditions: {spec.postconditions}

CODE:
```python
{content[:2000]}
```

TEST RESULTS:
{self._format_test_results(execution_results)}

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
        
        return self._parse_perspective_result(result.content, "correctness_reviewer")
    
    async def _edge_case_hunt(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
        execution_results: BehavioralExecutionResult,
    ) -> PerspectiveResult:
        """Hunt for unhandled edge cases."""
        
        prompt = f"""You are an EDGE CASE HUNTER. Your job is to find inputs that
would break this code.

CODE:
```python
{content[:2000]}
```

KNOWN EDGE CASES (already tested):
{spec.edge_cases}

TEST RESULTS:
{self._format_test_results(execution_results)}

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
        
        return self._parse_perspective_result(result.content, "edge_case_hunter")
    
    async def _integration_analysis(
        self,
        artifact: ArtifactSpec,
        content: str,
        spec: Specification,
    ) -> PerspectiveResult:
        """Analyze integration with dependencies."""
        
        prompt = f"""You are an INTEGRATION ANALYST. Your job is to verify that
this code will work correctly with its dependencies.

CODE:
```python
{content[:2000]}
```

DEPENDENCIES (imports used):
{self._extract_imports(content)}

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
        
        return self._parse_perspective_result(result.content, "integration_analyst")
    
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
        
        return self._parse_perspective_result(result.content, "regression_detective")
```

---

### 5. Confidence Triangulator

Cross-check multiple signals to produce final confidence score.

```python
@dataclass(frozen=True, slots=True)
class DeepVerificationResult:
    """Final deep verification result with confidence.
    
    Note: Named DeepVerificationResult to distinguish from:
    - sunwell.naaru.artifacts.VerificationResult (artifact contract verification)
    - sunwell.routing.tiered_attunement.VerificationResult (self-verification)
    
    This class focuses on semantic correctness of generated code.
    """
    
    passed: bool
    """Did verification pass overall?"""
    
    confidence: float
    """0-1, how confident we are in correctness."""
    
    issues: tuple[SemanticIssue, ...]
    """Issues found during verification."""
    
    generated_tests: tuple[GeneratedTest, ...]
    """Tests that were generated (can be kept)."""
    
    test_results: BehavioralExecutionResult | None
    """Results from test execution."""
    
    perspective_results: tuple[PerspectiveResult, ...]
    """Results from each verification perspective."""
    
    recommendations: tuple[str, ...]
    """Actionable recommendations."""
    
    duration_ms: int
    """Total verification time."""


class ConfidenceTriangulator:
    """Cross-check verification signals to compute final confidence.
    
    Triangulation strategy:
    1. Test pass rate: Hard evidence from execution
    2. Perspective consensus: Agreement across reviewers
    3. Spec coverage: Did we test what matters?
    4. Signal consistency: Do signals agree or contradict?
    """
    
    def triangulate(
        self,
        spec: Specification,
        execution_results: BehavioralExecutionResult,
        perspective_results: list[PerspectiveResult],
    ) -> DeepVerificationResult:
        """Compute final verification result via triangulation."""
        
        # Signal 1: Test execution (40% weight)
        test_score = execution_results.pass_rate if execution_results else 0.5
        test_weight = 0.4
        
        # Signal 2: Perspective consensus (30% weight)
        verdicts = [p.verdict for p in perspective_results]
        correct_count = sum(1 for v in verdicts if v == "correct")
        perspective_score = correct_count / len(verdicts) if verdicts else 0.5
        perspective_weight = 0.3
        
        # Signal 3: Average perspective confidence (20% weight)
        avg_confidence = sum(p.confidence for p in perspective_results) / len(perspective_results) if perspective_results else 0.5
        confidence_weight = 0.2
        
        # Signal 4: Spec confidence (10% weight)
        spec_score = spec.confidence
        spec_weight = 0.1
        
        # Weighted average
        raw_confidence = (
            test_score * test_weight +
            perspective_score * perspective_weight +
            avg_confidence * confidence_weight +
            spec_score * spec_weight
        )
        
        # Check for contradictions (reduces confidence)
        has_contradiction = self._detect_contradictions(perspective_results, execution_results)
        if has_contradiction:
            raw_confidence *= 0.8  # 20% penalty for contradictions
        
        # Collect all issues
        issues = self._collect_issues(perspective_results, execution_results)
        
        # Determine pass/fail
        passed = (
            raw_confidence >= 0.7 and
            len([i for i in issues if i.severity == "critical"]) == 0 and
            (execution_results is None or execution_results.pass_rate >= 0.8)
        )
        
        # Collect recommendations
        recommendations = self._collect_recommendations(perspective_results, issues)
        
        return DeepVerificationResult(
            passed=passed,
            confidence=raw_confidence,
            issues=tuple(issues),
            generated_tests=tuple(),  # Filled by caller
            test_results=execution_results,
            perspective_results=tuple(perspective_results),
            recommendations=tuple(recommendations),
            duration_ms=0,  # Filled by caller
        )
    
    def _detect_contradictions(
        self,
        perspectives: list[PerspectiveResult],
        execution: BehavioralExecutionResult | None,
    ) -> bool:
        """Detect contradicting signals."""
        
        # Contradiction: Tests pass but reviewers say incorrect
        if execution and execution.pass_rate > 0.9:
            if any(p.verdict == "incorrect" for p in perspectives):
                return True
        
        # Contradiction: Tests fail but reviewers say correct
        if execution and execution.pass_rate < 0.5:
            if all(p.verdict == "correct" for p in perspectives):
                return True
        
        # Contradiction: Reviewers strongly disagree
        verdicts = [p.verdict for p in perspectives]
        if "correct" in verdicts and "incorrect" in verdicts:
            return True
        
        return False
```

---

### 6. Deep Verifier (Orchestrator)

Ties all components together.

```python
class DeepVerifier:
    """Orchestrates deep semantic verification.
    
    Integration with RFC-042 (Adaptive Agent):
    - DeepVerifier runs AFTER syntactic gates pass
    - If DeepVerifier fails, triggers Compound Eye for fix
    - Confidence feeds into technique selection
    
    Integration with RFC-046 (Autonomous Backlog):
    - auto_approvable goals require DeepVerifier pass
    - DeepVerifier confidence determines goal completion
    """
    
    def __init__(
        self,
        model: ModelProtocol,
        cwd: Path,
        config: DeepVerificationConfig | None = None,
    ):
        self.model = model
        self.cwd = cwd
        self.config = config or DeepVerificationConfig()
        
        # Components
        self.spec_extractor = SpecificationExtractor(model)
        self.test_generator = TestGenerator(model)
        self.executor = BehavioralExecutor(cwd)
        self.analyzer = MultiPerspectiveAnalyzer(model)
        self.triangulator = ConfidenceTriangulator()
    
    async def verify(
        self,
        artifact: ArtifactSpec,
        content: str,
        existing_code: str | None = None,
        existing_tests: str | None = None,
    ) -> AsyncIterator[VerificationEvent]:
        """Verify an artifact with streaming events.
        
        Args:
            artifact: The artifact specification
            content: Generated content to verify
            existing_code: Previous version (for regression detection)
            existing_tests: Existing tests (for spec mining)
        
        Yields:
            VerificationEvent for each stage
        """
        import time
        
        start = time.monotonic()
        
        yield VerificationEvent(stage="start", message="Starting deep verification")
        
        # Stage 1: Extract specification
        yield VerificationEvent(stage="spec_extraction", message="Extracting specification")
        spec = await self.spec_extractor.extract(artifact, content, existing_tests)
        yield VerificationEvent(stage="spec_extracted", data={"spec": spec})
        
        # Stage 2: Generate tests
        yield VerificationEvent(stage="test_generation", message="Generating behavioral tests")
        tests = await self.test_generator.generate(
            artifact, content, spec,
            max_tests=self.config.max_tests,
        )
        yield VerificationEvent(stage="tests_generated", data={"count": len(tests)})
        
        # Stage 3: Execute tests
        yield VerificationEvent(stage="test_execution", message="Executing behavioral tests")
        execution_results = await self.executor.execute(content, tests)
        yield VerificationEvent(
            stage="tests_executed",
            data={
                "passed": execution_results.passed,
                "failed": execution_results.failed,
                "errors": execution_results.errors,
            },
        )
        
        # Stage 4: Multi-perspective analysis
        yield VerificationEvent(stage="analysis", message="Running multi-perspective analysis")
        perspectives = await self.analyzer.analyze(
            artifact, content, spec, execution_results, existing_code
        )
        yield VerificationEvent(stage="analyzed", data={"perspectives": len(perspectives)})
        
        # Stage 5: Triangulate
        yield VerificationEvent(stage="triangulation", message="Computing confidence")
        result = self.triangulator.triangulate(spec, execution_results, perspectives)
        
        # Add generated tests and timing
        duration = int((time.monotonic() - start) * 1000)
        result = DeepVerificationResult(
            passed=result.passed,
            confidence=result.confidence,
            issues=result.issues,
            generated_tests=tuple(tests),
            test_results=execution_results,
            perspective_results=result.perspective_results,
            recommendations=result.recommendations,
            duration_ms=duration,
        )
        
        yield VerificationEvent(
            stage="complete",
            message=f"Verification {'PASSED' if result.passed else 'FAILED'}",
            data={"result": result},
        )


@dataclass(frozen=True, slots=True)
class DeepVerificationConfig:
    """Configuration for deep verification."""
    
    max_tests: int = 10
    """Maximum tests to generate."""
    
    test_timeout_s: int = 10
    """Timeout per test in seconds."""
    
    total_timeout_s: int = 120
    """Total verification timeout."""
    
    min_confidence: float = 0.7
    """Minimum confidence to pass."""
    
    require_test_pass: bool = True
    """Require > 80% test pass rate."""
    
    perspectives: tuple[str, ...] = (
        "correctness_reviewer",
        "edge_case_hunter",
        "integration_analyst",
    )
    """Which perspectives to run."""
```

---

## Integration with Existing Systems

### With RFC-042 (Adaptive Agent)

Deep Verification extends the validation cascade:

```python
# In adaptive agent validation flow:

async def validate_with_deep_verification(
    artifact: Artifact,
    artifact_spec: ArtifactSpec,
) -> ValidationResult:
    """Run full validation including deep verification."""
    
    # Stage 1: Syntactic validation (existing)
    gate_result = await validation_runner.validate_gate(
        ValidationGate(gate_type=GateType.SYNTAX),
        [artifact],
    )
    if not gate_result.passed:
        return gate_result
    
    # Stage 2: Type checking (existing)
    gate_result = await validation_runner.validate_gate(
        ValidationGate(gate_type=GateType.TYPE),
        [artifact],
    )
    if not gate_result.passed:
        return gate_result
    
    # Stage 3: Deep verification (NEW - RFC-047)
    verifier = DeepVerifier(model, cwd)
    async for event in verifier.verify(artifact_spec, artifact.content):
        if event.stage == "complete":
            verification_result = event.data["result"]
            if not verification_result.passed:
                # Trigger Compound Eye for semantic fix
                return ValidationResult(
                    passed=False,
                    errors=[
                        ValidationError(
                            error_type="semantic",
                            message=str(issue),
                        )
                        for issue in verification_result.issues
                    ],
                )
    
    return ValidationResult(passed=True, errors=[])
```

### With RFC-046 (Autonomous Backlog)

Deep Verification determines auto-approval eligibility:

```python
# In autonomous loop goal execution:

async def execute_goal(goal: Goal) -> GoalResult:
    """Execute a goal with deep verification."""
    
    # Execute with adaptive agent
    result = await agent.execute(goal.description)
    
    # Deep verify for auto-approval
    if goal.auto_approvable:
        verifier = DeepVerifier(model, cwd)
        verification = await verifier.verify(...)
        
        if verification.passed and verification.confidence >= 0.85:
            # Auto-approve with high confidence
            return GoalResult(success=True, auto_approved=True)
        else:
            # Require human review
            return GoalResult(
                success=False,
                needs_review=True,
                verification=verification,
            )
    
    return GoalResult(success=True, auto_approved=False)
```

### New Gate Type

Add SEMANTIC gate to validation cascade:

```python
class GateType(Enum):
    # Existing gates...
    SYNTAX = "syntax"
    LINT = "lint"
    TYPE = "type"
    IMPORT = "import"
    
    # NEW: Semantic verification (RFC-047)
    SEMANTIC = "semantic"
    """Deep verification — does it do the right thing?"""
```

---

## Verification Levels

Different levels of verification depth:

```yaml
level_1_quick:  # ~5 seconds
  spec_extraction: contract_only
  test_generation: 0  # No test generation
  execution: false
  perspectives: [correctness_reviewer]
  use_case: "Quick sanity check for trivial changes"

level_2_standard:  # ~30 seconds (DEFAULT)
  spec_extraction: full
  test_generation: 5
  execution: true
  perspectives: [correctness_reviewer, edge_case_hunter]
  use_case: "Normal verification for most changes"

level_3_thorough:  # ~2 minutes
  spec_extraction: full
  test_generation: 10
  execution: true
  perspectives: [all]
  property_tests: true
  use_case: "Critical changes, autonomous mode"
```

---

## CLI Integration

```bash
# Verify a specific file
sunwell verify src/models/user.py
# Output:
# ✅ Deep Verification PASSED
# Confidence: 87%
# Tests: 8/8 passed
# Perspectives: 3/3 correct

# Verify with details
sunwell verify src/models/user.py --verbose
# Shows: generated tests, perspective analysis, issues found

# Quick verification
sunwell verify src/models/user.py --level quick

# Thorough verification
sunwell verify src/models/user.py --level thorough

# Verify and keep generated tests
sunwell verify src/models/user.py --save-tests
# Saves tests to tests/generated/test_user.py
```

---

## Risks and Mitigations

### Risk 1: Test Generation Failures

**Problem**: LLM generates broken/useless tests.

**Mitigation**:
- Validate generated test syntax before running
- Fallback to LLM-only verification if tests fail to run
- Track test quality metrics over time

### Risk 2: False Positives

**Problem**: Verification rejects correct code.

**Mitigation**:
- Confidence thresholds (don't reject on low-confidence signals)
- Contradiction detection (disagreement = uncertainty, not failure)
- Human override available

### Risk 3: False Negatives

**Problem**: Verification passes incorrect code.

**Mitigation**:
- Multiple perspectives catch different error classes
- Test execution provides ground truth
- Triangulation requires multiple signals to agree

### Risk 4: Performance Overhead

**Problem**: Verification adds significant latency.

**Mitigation**:
- Level 1 (quick) for trivial changes
- Parallel execution of perspectives
- Skip verification for syntax-only gates
- Cache specs for unchanged code

### Risk 5: Spec Extraction Hallucination

**Problem**: LLM hallucinates incorrect specifications.

**Mitigation**:
- Prioritize explicit specs (contract, docstrings) over inferred
- Mark inferred specs with lower confidence
- Cross-check inferred specs against code behavior

---

## Implementation Plan

### Phase 1: Core Components (Week 1-2)

- [ ] Implement `SpecificationExtractor`
  - Contract parsing
  - Docstring extraction
  - Signature analysis
- [ ] Implement `TestGenerator`
  - Happy path tests
  - Edge case tests
- [ ] Implement `BehavioralExecutor`
  - Sandbox execution
  - Result capture
- [ ] CLI: `sunwell verify <file>`

### Phase 2: Multi-Perspective Analysis (Week 3)

- [ ] Implement `MultiPerspectiveAnalyzer`
  - Correctness Reviewer
  - Edge Case Hunter
  - Integration Analyst
- [ ] Implement `ConfidenceTriangulator`
  - Signal weighting
  - Contradiction detection
- [ ] Add `SEMANTIC` gate type

### Phase 3: Integration (Week 4)

- [ ] Integrate with RFC-042 validation cascade
- [ ] Integrate with RFC-046 auto-approval
- [ ] Add property-based testing (hypothesis)
- [ ] Add regression detection perspective

### Phase 4: Polish (Week 5)

- [ ] Verification levels (quick/standard/thorough)
- [ ] Test persistence (`--save-tests`)
- [ ] Performance optimization (parallel perspectives)
- [ ] Documentation

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Semantic bug detection | > 80% | Catch bugs that pass syntax/type |
| False positive rate | < 10% | Don't reject correct code |
| Verification time (L2) | < 30s | Standard verification latency |
| Test pass correlation | > 0.8 | High confidence ↔ tests pass |
| Auto-approval accuracy | > 95% | Auto-approved code is correct |

---

## Future Work

1. **RFC-048: Autonomy Guardrails** — Use verification confidence for autonomy levels
2. **Security Verification** — Specialized perspective for security issues
3. **Performance Verification** — Verify performance characteristics
4. **Multi-language Support** — Extend beyond Python
5. **Verification Learning** — Learn from past verification results

---

## Summary

Deep Verification closes the gap between "code runs" and "code is correct":

| Layer | Question | Existing | RFC-047 |
|-------|----------|----------|---------|
| Syntax | Does it parse? | ✅ py_compile | — |
| Type | Does it type-check? | ✅ ty/mypy | — |
| Runtime | Does it run? | ✅ import/serve | — |
| **Semantic** | **Does it do the right thing?** | ❌ | ✅ |

### Key Components

1. **Specification Extractor** — What should the code do?
2. **Test Generator** — Create tests that verify the spec
3. **Behavioral Executor** — Run tests, get ground truth
4. **Multi-Perspective Analyzer** — Multiple viewpoints on correctness
5. **Confidence Triangulator** — Cross-check signals for final `DeepVerificationResult`

### Integration Points

- **RFC-042**: Adds SEMANTIC gate to validation cascade
- **RFC-046**: Enables confident auto-approval of goals

**The result**: Sunwell can trust its output enough to work autonomously — the foundation for true unsupervised operation.

---

## References

### RFCs

- RFC-036: Artifact-First Planning — **Implemented** (`src/sunwell/naaru/artifacts.py`)
- RFC-042: Adaptive Agent — **Implemented** (`src/sunwell/adaptive/`)
- RFC-046: Autonomous Backlog — **Implemented** (`src/sunwell/backlog/`)

### Implementation Files (to be created)

```
src/sunwell/verification/
├── __init__.py
├── types.py           # DeepVerificationResult, Specification, GeneratedTest, etc.
├── extractor.py       # SpecificationExtractor
├── generator.py       # TestGenerator  
├── executor.py        # BehavioralExecutor
├── analyzer.py        # MultiPerspectiveAnalyzer
├── triangulator.py    # ConfidenceTriangulator
└── verifier.py        # DeepVerifier orchestrator
```

### Related Existing Files

```
src/sunwell/adaptive/
├── gates.py           # GateType enum (add SEMANTIC)
├── validation.py      # ValidationRunner (integrate DeepVerifier)
└── agent.py           # AdaptiveAgent (call after syntactic gates)

src/sunwell/backlog/
├── goals.py           # Goal.auto_approvable (uses verification confidence)
└── loop.py            # AutonomousLoop (verification before auto-approve)

src/sunwell/naaru/
└── artifacts.py       # ArtifactSpec.contract (input for spec extraction)
```

---

*Last updated: 2026-01-19*
